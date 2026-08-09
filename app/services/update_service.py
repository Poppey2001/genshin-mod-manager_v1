from __future__ import annotations

import json
import logging
import platform

from dataclasses import dataclass

from enum import Enum

from typing import Any

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import urlencode

from urllib.request import (
    Request,
    urlopen,
)

from packaging.version import (
    InvalidVersion,
    Version,
)

from app.update_config import (
    APPIMAGE_ARCHITECTURE,
    APPIMAGE_SUFFIX,
    GITHUB_API_VERSION,
    UPDATE_CHECK_TIMEOUT,
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


class UpdateService:
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
                "GitHub owner fehlt."
            )

        if not self.repository:
            raise ValueError(
                "GitHub repository fehlt."
            )

        try:
            self.current_version = Version(
                current_version
            )

        except InvalidVersion as error:
            raise ValueError(
                (
                    "Ungültige aktuelle "
                    f"Version: {current_version}"
                )
            ) from error

        self.channel = channel

        self.timeout = max(
            float(timeout),
            1.0,
        )

    def check_for_update(
        self,
    ) -> UpdateInfo | None:
        releases = (
            self._fetch_releases()
        )

        candidates: list[
            UpdateInfo
        ] = []

        for release in releases:
            update = (
                self._parse_release(
                    release
                )
            )

            if update is None:
                continue

            if (
                update.version
                <= self.current_version
            ):
                continue

            if not self._channel_allows(
                update
            ):
                continue

            candidates.append(
                update
            )

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda update: (
                update.version
            ),
        )

    def _channel_allows(
        self,
        update: UpdateInfo,
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
            return (
                not update.prerelease
                and not (
                    update.version
                    .is_prerelease
                )
            )

        return False

    def _parse_release(
        self,
        release: dict[
            str,
            Any,
        ],
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

        version_text = (
            self._version_from_tag(
                tag_name
            )
        )

        try:
            version = Version(
                version_text
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
            prerelease=bool(
                release.get(
                    "prerelease",
                    False,
                )
            ),
            assets=assets,
        )

    @staticmethod
    def _version_from_tag(
        tag_name: str,
    ) -> str:
        tag_name = (
            tag_name.strip()
        )

        if (
            len(tag_name) > 1
            and tag_name[0]
            in {"v", "V"}
        ):
            return tag_name[1:]

        return tag_name

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
                (
                    "GitHub API HTTP "
                    f"{error.code}"
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                (
                    "GitHub konnte nicht "
                    f"erreicht werden: {reason}"
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                (
                    "Zeitüberschreitung bei "
                    "der Update-Prüfung."
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
                (
                    "Ungültige Antwort "
                    "von GitHub."
                )
            ) from error

        if not isinstance(
            data,
            list,
        ):
            raise UpdateServiceError(
                (
                    "Unerwartetes GitHub-"
                    "Antwortformat."
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