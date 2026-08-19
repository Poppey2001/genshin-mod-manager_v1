from __future__ import annotations

import ast
import json
import logging
import platform
import re

from dataclasses import dataclass

from enum import Enum

from typing import Any

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    quote,
    urlencode,
)

from urllib.request import (
    Request,
    urlopen,
)

from packaging.version import (
    InvalidVersion,
    Version,
)

from app.i18n import tr

from app.update_config import (
    APPIMAGE_ARCHITECTURE,
    APPIMAGE_SUFFIX,
    GITHUB_API_VERSION,
    GITHUB_VERSION_FILE,
    GITHUB_VERSION_REF,
    UPDATE_CHECK_TIMEOUT,
    WINDOWS_INSTALLER_ARCHITECTURE,
    WINDOWS_INSTALLER_NAME_TOKENS,
    WINDOWS_INSTALLER_SUFFIX,
)


logger = logging.getLogger(
    __name__
)


GITHUB_API_BASE_URL = (
    "https://api.github.com"
)


class UpdateServiceError(
    RuntimeError
):
    pass


class UpdateChannel(
    str,
    Enum,
):
    STABLE = "stable"
    PRERELEASE = "prerelease"


@dataclass(
    frozen=True,
    slots=True,
)
class ReleaseAsset:
    name: str
    download_url: str
    size: int

    content_type: str | None = None
    digest: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class UpdateInfo:
    current_version: Version
    version: Version

    tag_name: str
    release_name: str
    release_notes: str
    release_url: str

    published_at: str | None

    prerelease: bool

    assets: tuple[
        ReleaseAsset,
        ...,
    ]

    # Exact Git commit used for the remote app/version.py check.
    # Windows source-build updates use this same commit so version
    # detection and downloaded source can never race each other.
    source_commit: str

    # False means:
    # app/version.py already contains a newer version,
    # but a matching GitHub Release has not been published yet.
    release_ready: bool = True

    def find_appimage_asset(
        self,
    ) -> ReleaseAsset | None:
        candidates = [
            asset
            for asset in self.assets
            if asset.name.casefold().endswith(
                APPIMAGE_SUFFIX.casefold()
            )
        ]

        if not candidates:
            return None

        machine = (
            platform.machine()
            .strip()
            .casefold()
        )

        architecture_names = {
            "x86_64": {
                "x86_64",
                "amd64",
            },
            "amd64": {
                "x86_64",
                "amd64",
            },
            "aarch64": {
                "aarch64",
                "arm64",
            },
            "arm64": {
                "aarch64",
                "arm64",
            },
        }

        expected_names = (
            architecture_names.get(
                machine,
                {
                    APPIMAGE_ARCHITECTURE
                    .casefold()
                },
            )
        )

        for asset in candidates:
            name = (
                asset.name.casefold()
            )

            if any(
                architecture
                in name
                for architecture
                in expected_names
            ):
                return asset

        if len(candidates) == 1:
            return candidates[0]

        return None

    def find_windows_installer_asset(
        self,
    ) -> ReleaseAsset | None:
        candidates = [
            asset
            for asset in self.assets
            if (
                asset.name.casefold().endswith(
                    WINDOWS_INSTALLER_SUFFIX.casefold()
                )
                and any(
                    token.casefold()
                    in asset.name.casefold()
                    for token
                    in WINDOWS_INSTALLER_NAME_TOKENS
                )
            )
        ]

        if not candidates:
            return None

        machine = (
            platform.machine()
            .strip()
            .casefold()
        )

        architecture_names = {
            "x86_64": {
                "x86_64",
                "amd64",
                "x64",
            },
            "amd64": {
                "x86_64",
                "amd64",
                "x64",
            },
            "x64": {
                "x86_64",
                "amd64",
                "x64",
            },
            "aarch64": {
                "aarch64",
                "arm64",
            },
            "arm64": {
                "aarch64",
                "arm64",
            },
        }

        expected_names = (
            architecture_names.get(
                machine,
                {
                    WINDOWS_INSTALLER_ARCHITECTURE
                    .casefold()
                },
            )
        )

        for asset in candidates:
            name = (
                asset.name.casefold()
            )

            if any(
                architecture
                in name
                for architecture
                in expected_names
            ):
                return asset

        if len(candidates) == 1:
            return candidates[0]

        return None


class UpdateService:
    """
    Shared update backend for Linux and Windows.

    Version source:
        GitHub main/app/version.py -> APP_VERSION

    Release source:
        GitHub Releases

    This separation is intentional:
    app/version.py decides WHETHER an update exists.
    The release only provides downloadable platform assets.
    """

    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        current_version: str,
        channel: UpdateChannel,
        timeout: float = (
            UPDATE_CHECK_TIMEOUT
        ),
    ) -> None:
        self.owner = owner.strip()

        self.repository = (
            repository.strip()
        )

        if not self.owner:
            raise ValueError(
                tr(
                    "updates.error.service.owner_missing"
                )
            )

        if not self.repository:
            raise ValueError(
                tr(
                    "updates.error.service.repository_missing"
                )
            )

        try:
            self.current_version = (
                self._normalize_version(
                    current_version
                )
            )

        except InvalidVersion as error:
            raise ValueError(
                tr(
                    "updates.error.service.invalid_current_version",
                    version=current_version,
                )
            ) from error

        self.channel = channel

        self.timeout = max(
            float(timeout),
            1.0,
        )

    # ========================================================
    # Public update check
    # ========================================================

    def check_for_update(
        self,
    ) -> UpdateInfo | None:
        # IMPORTANT:
        # Never derive "latest version" from a release tag.
        # The remote app/version.py is always authoritative.
        remote_commit = (
            self._fetch_remote_commit()
        )

        remote_version = (
            self._fetch_remote_version(
                remote_commit
            )
        )

        logger.info(
            (
                "Update-Version geprüft: "
                "lokal=%s, GitHub-%s/%s=%s, commit=%s"
            ),
            self.current_version,
            GITHUB_VERSION_REF,
            GITHUB_VERSION_FILE,
            remote_version,
            remote_commit,
        )

        if (
            remote_version
            <= self.current_version
        ):
            return None

        if not (
            self._version_channel_allows(
                remote_version
            )
        ):
            logger.info(
                (
                    "Remote-Version %s ist neuer, "
                    "wird aber vom Update-Kanal %s "
                    "nicht erlaubt."
                ),
                remote_version,
                self.channel.value,
            )

            return None

        # A newer version definitely exists at this point.
        # Releases are now used ONLY to locate binaries for exactly
        # this version.
        releases = (
            self._fetch_releases()
        )

        matching_release = (
            self._find_release_for_version(
                releases,
                remote_version,
            )
        )

        if matching_release is not None:
            update = (
                self._parse_release(
                    matching_release,
                    source_commit=remote_commit,
                )
            )

            if update is not None:
                logger.info(
                    (
                        "Passendes GitHub Release "
                        "für %s gefunden: %s"
                    ),
                    remote_version,
                    update.tag_name,
                )

                return update

        # GitHub source is ahead of the published binaries.
        # Do not incorrectly say "up to date".
        logger.warning(
            (
                "app/version.py meldet Version %s, "
                "aber es existiert noch kein "
                "passendes veröffentlichtes Release."
            ),
            remote_version,
        )

        return self._version_only_update(
            remote_version,
            source_commit=remote_commit,
        )

    # ========================================================
    # Version backend
    # ========================================================

    def _fetch_remote_commit(
        self,
    ) -> str:
        ref = quote(
            GITHUB_VERSION_REF,
            safe="",
        )

        url = (
            f"{GITHUB_API_BASE_URL}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/commits/{ref}"
        )

        request = Request(
            url,
            headers={
                "Accept": (
                    "application/vnd.github+json"
                ),
                "X-GitHub-Api-Version": (
                    GITHUB_API_VERSION
                ),
                "User-Agent": (
                    "Genshin-Mod-Manager-Updater"
                ),
                "Cache-Control": (
                    "no-cache"
                ),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_data = response.read()

        except HTTPError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_http",
                    code=error.code,
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_unreachable",
                    reason=reason,
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_timeout"
                )
            ) from error

        try:
            data = json.loads(
                raw_data.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_invalid_response"
                )
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_unexpected_response"
                )
            )

        commit = data.get(
            "sha"
        )

        if not isinstance(
            commit,
            str,
        ):
            raise UpdateServiceError(
                tr(
                    "updates.error.source.commit_missing"
                )
            )

        commit = commit.strip()

        if not re.fullmatch(
            r"[0-9a-fA-F]{40}",
            commit,
        ):
            raise UpdateServiceError(
                tr(
                    "updates.error.source.commit_invalid"
                )
            )

        return commit.casefold()

    def _fetch_remote_version(
        self,
        ref: str,
    ) -> Version:
        path = quote(
            GITHUB_VERSION_FILE.strip(
                "/"
            ),
            safe="/",
        )

        query = urlencode(
            {
                "ref": ref,
            }
        )

        url = (
            f"{GITHUB_API_BASE_URL}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/contents/{path}"
            f"?{query}"
        )

        request = Request(
            url,
            headers={
                # GitHub's raw media type returns the file
                # contents directly instead of Base64 JSON.
                "Accept": (
                    "application/vnd.github.raw+json"
                ),
                "X-GitHub-Api-Version": (
                    GITHUB_API_VERSION
                ),
                "User-Agent": (
                    "Genshin-Mod-Manager-Updater"
                ),
                # We want current version.py, not a stale local/proxy
                # cache answer.
                "Cache-Control": (
                    "no-cache"
                ),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_data = (
                    response.read()
                )

        except HTTPError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.http",
                    code=error.code,
                    path=GITHUB_VERSION_FILE,
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.unreachable",
                    reason=reason,
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.timeout"
                )
            ) from error

        try:
            source = raw_data.decode(
                "utf-8"
            )

        except UnicodeDecodeError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.encoding"
                )
            ) from error

        version_text = (
            self._extract_app_version(
                source
            )
        )

        if version_text is None:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.missing",
                    path=GITHUB_VERSION_FILE,
                )
            )

        try:
            return self._normalize_version(
                version_text
            )

        except InvalidVersion as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.invalid",
                    version=version_text,
                )
            ) from error

    @staticmethod
    def _extract_app_version(
        source: str,
    ) -> str | None:
        """
        Parse remote version.py without executing remote Python code.

        Supported:
            APP_VERSION = "0.5.8b1"
            APP_VERSION: str = "0.5.8b1"
        """

        try:
            tree = ast.parse(
                source,
                filename=GITHUB_VERSION_FILE,
            )

        except SyntaxError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.version_file.syntax"
                )
            ) from error

        for node in tree.body:
            value_node: ast.AST | None = None

            if isinstance(
                node,
                ast.Assign,
            ):
                if any(
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and target.id
                    == "APP_VERSION"
                    for target
                    in node.targets
                ):
                    value_node = (
                        node.value
                    )

            elif isinstance(
                node,
                ast.AnnAssign,
            ):
                if (
                    isinstance(
                        node.target,
                        ast.Name,
                    )
                    and node.target.id
                    == "APP_VERSION"
                ):
                    value_node = (
                        node.value
                    )

            if value_node is None:
                continue

            if (
                isinstance(
                    value_node,
                    ast.Constant,
                )
                and isinstance(
                    value_node.value,
                    str,
                )
            ):
                value = (
                    value_node.value
                    .strip()
                )

                if value:
                    return value

        return None

    @staticmethod
    def _normalize_version(
        value: str,
    ) -> Version:
        text = (
            str(
                value
            )
            .strip()
        )

        if (
            len(text) > 1
            and text[0]
            in {
                "v",
                "V",
            }
        ):
            text = (
                text[1:]
            )

        return Version(
            text
        )

    def _version_channel_allows(
        self,
        version: Version,
    ) -> bool:
        if (
            self.channel
            == UpdateChannel.PRERELEASE
        ):
            return True

        if (
            self.channel
            == UpdateChannel.STABLE
        ):
            return not (
                version.is_prerelease
            )

        return False

    # ========================================================
    # Matching release
    # ========================================================

    def _find_release_for_version(
        self,
        releases: list[
            dict[str, Any]
        ],
        version: Version,
    ) -> dict[
        str,
        Any,
    ] | None:
        for release in releases:
            if bool(
                release.get(
                    "draft",
                    False,
                )
            ):
                continue

            release_version = (
                self._release_version(
                    release
                )
            )

            if (
                release_version
                == version
            ):
                return release

        return None

    def _release_version(
        self,
        release: dict[
            str,
            Any,
        ],
    ) -> Version | None:
        tag_name = (
            release.get(
                "tag_name"
            )
        )

        if not isinstance(
            tag_name,
            str,
        ):
            return None

        tag_name = (
            tag_name.strip()
        )

        if not tag_name:
            return None

        try:
            return self._normalize_version(
                tag_name
            )

        except InvalidVersion:
            logger.warning(
                (
                    "Release mit ungültiger "
                    "Version ignoriert: %s"
                ),
                tag_name,
            )

            return None

    def _version_only_update(
        self,
        version: Version,
        *,
        source_commit: str,
    ) -> UpdateInfo:
        tag_name = (
            f"v{version}"
        )

        return UpdateInfo(
            current_version=(
                self.current_version
            ),
            version=version,
            tag_name=tag_name,
            release_name=tag_name,
            release_notes="",
            release_url=(
                f"https://github.com/"
                f"{self.owner}/"
                f"{self.repository}/"
                f"releases"
            ),
            published_at=None,
            prerelease=(
                version.is_prerelease
            ),
            assets=(),
            source_commit=source_commit,
            release_ready=False,
        )

    # ========================================================
    # Release parsing
    # ========================================================

    def _parse_release(
        self,
        release: dict[
            str,
            Any,
        ],
        *,
        source_commit: str,
    ) -> UpdateInfo | None:
        if bool(
            release.get(
                "draft",
                False,
            )
        ):
            return None

        tag_name = release.get(
            "tag_name"
        )

        if not isinstance(
            tag_name,
            str,
        ):
            return None

        tag_name = (
            tag_name.strip()
        )

        if not tag_name:
            return None

        version = (
            self._release_version(
                release
            )
        )

        if version is None:
            return None

        release_name = (
            release.get(
                "name"
            )
        )

        if not isinstance(
            release_name,
            str,
        ):
            release_name = ""

        release_name = (
            release_name.strip()
        )

        if not release_name:
            release_name = tag_name

        release_notes = (
            release.get(
                "body"
            )
        )

        if not isinstance(
            release_notes,
            str,
        ):
            release_notes = ""

        release_url = (
            release.get(
                "html_url"
            )
        )

        if not isinstance(
            release_url,
            str,
        ):
            release_url = ""

        published_at = (
            release.get(
                "published_at"
            )
        )

        if not isinstance(
            published_at,
            str,
        ):
            published_at = None

        assets = (
            self._parse_assets(
                release.get(
                    "assets"
                )
            )
        )

        return UpdateInfo(
            current_version=(
                self.current_version
            ),
            version=version,
            tag_name=tag_name,
            release_name=release_name,
            release_notes=release_notes,
            release_url=release_url,
            published_at=published_at,
            prerelease=(
                bool(
                    release.get(
                        "prerelease",
                        False,
                    )
                )
                or version.is_prerelease
            ),
            assets=assets,
            source_commit=source_commit,
            release_ready=True,
        )

    @staticmethod
    def _parse_assets(
        raw_assets: Any,
    ) -> tuple[
        ReleaseAsset,
        ...,
    ]:
        if not isinstance(
            raw_assets,
            list,
        ):
            return ()

        assets: list[
            ReleaseAsset
        ] = []

        for raw_asset in raw_assets:
            if not isinstance(
                raw_asset,
                dict,
            ):
                continue

            name = raw_asset.get(
                "name"
            )

            download_url = (
                raw_asset.get(
                    "browser_download_url"
                )
            )

            if not isinstance(
                name,
                str,
            ):
                continue

            if not isinstance(
                download_url,
                str,
            ):
                continue

            size = raw_asset.get(
                "size",
                0,
            )

            if not isinstance(
                size,
                int,
            ):
                size = 0

            content_type = (
                raw_asset.get(
                    "content_type"
                )
            )

            if not isinstance(
                content_type,
                str,
            ):
                content_type = None

            digest = raw_asset.get(
                "digest"
            )

            if not isinstance(
                digest,
                str,
            ):
                digest = None

            assets.append(
                ReleaseAsset(
                    name=name,
                    download_url=(
                        download_url
                    ),
                    size=size,
                    content_type=(
                        content_type
                    ),
                    digest=digest,
                )
            )

        return tuple(
            assets
        )

    # ========================================================
    # GitHub releases
    # ========================================================

    def _fetch_releases(
        self,
    ) -> list[
        dict[str, Any]
    ]:
        query = urlencode(
            {
                "per_page": 100,
                "page": 1,
            }
        )

        url = (
            f"{GITHUB_API_BASE_URL}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/releases"
            f"?{query}"
        )

        request = Request(
            url,
            headers={
                "Accept": (
                    "application/vnd.github+json"
                ),
                "X-GitHub-Api-Version": (
                    GITHUB_API_VERSION
                ),
                "User-Agent": (
                    "Genshin-Mod-Manager-Updater"
                ),
                "Cache-Control": (
                    "no-cache"
                ),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_data = (
                    response.read()
                )

        except HTTPError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_http",
                    code=error.code,
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_unreachable",
                    reason=reason,
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_timeout"
                )
            ) from error

        try:
            data = json.loads(
                raw_data.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_invalid_response"
                )
            ) from error

        if not isinstance(
            data,
            list,
        ):
            raise UpdateServiceError(
                tr(
                    "updates.error.service.github_unexpected_response"
                )
            )

        return [
            item
            for item in data
            if isinstance(
                item,
                dict,
            )
        ]


__all__ = [
    "ReleaseAsset",
    "UpdateChannel",
    "UpdateInfo",
    "UpdateService",
    "UpdateServiceError",
]
