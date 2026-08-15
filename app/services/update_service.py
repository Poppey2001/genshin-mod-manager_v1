from __future__ import annotations

import json
import logging
import platform

from dataclasses import (
    dataclass,
)

from enum import (
    Enum,
)

from typing import (
    Any,
)

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
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

from app.update_config import (
    APPIMAGE_ARCHITECTURE_ALIASES,
    APPIMAGE_SUFFIX,
    GITHUB_API_VERSION,
    UPDATE_CHECK_TIMEOUT,
    WINDOWS_UPDATE_KEYWORDS,
    WINDOWS_UPDATE_SUFFIX,
)


logger = logging.getLogger(
    __name__
)


GITHUB_API_BASE_URL = (
    "https://api.github.com"
)


# ============================================================
# Exceptions
# ============================================================

class UpdateServiceError(
    RuntimeError
):
    pass


# ============================================================
# Channel
# ============================================================

class UpdateChannel(
    str,
    Enum,
):
    STABLE = "stable"
    PRERELEASE = "prerelease"


# ============================================================
# Release Asset
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class ReleaseAsset:
    name: str

    download_url: str

    size: int

    content_type: (
        str
        | None
    ) = None

    digest: (
        str
        | None
    ) = None

    @property
    def sha256(
        self,
    ) -> str | None:
        digest = (
            self.digest
            or ""
        ).strip()

        algorithm, separator, value = (
            digest.partition(
                ":"
            )
        )

        if (
            separator != ":"
            or algorithm.casefold()
            != "sha256"
            or not value
        ):
            return None

        return (
            value.strip()
            .casefold()
        )

    @property
    def sha256(
        self,
    ) -> str | None:
        digest = (
            self.digest
            or ""
        ).strip()

        algorithm, separator, value = (
            digest.partition(
                ":"
            )
        )

        if (
            separator != ":"
            or algorithm.casefold()
            != "sha256"
            or not value
        ):
            return None

        return (
            value
            .strip()
            .casefold()
        )

# ============================================================
# Update Info
# ============================================================

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

    published_at: (
        str
        | None
    )

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
            for asset
            in self.assets
            if (
                asset.name
                .casefold()
                .endswith(
                    APPIMAGE_SUFFIX
                    .casefold()
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

        aliases = {
            value.casefold()
            for value
            in APPIMAGE_ARCHITECTURE_ALIASES
        }

        # ----------------------------------------------------
        # Systemarchitektur zusätzlich berücksichtigen
        # ----------------------------------------------------

        if machine in {
            "x86_64",
            "amd64",
        }:
            aliases.update(
                {
                    "x86_64",
                    "amd64",
                }
            )

        for asset in candidates:
            name = (
                asset.name
                .casefold()
            )

            if any(
                alias
                in name
                for alias
                in aliases
            ):
                return asset

        # ----------------------------------------------------
        # Nur ein AppImage vorhanden:
        # dann dieses verwenden.
        # ----------------------------------------------------

        if len(
            candidates
        ) == 1:
            return candidates[
                0
            ]

        return None

    def find_windows_asset(
        self,
    ) -> ReleaseAsset | None:
        candidates = [
            asset
            for asset
            in self.assets
            if (
                asset.name
                .casefold()
                .endswith(
                    WINDOWS_UPDATE_SUFFIX
                    .casefold()
                )
            )
        ]

        if not candidates:
            return None

        # ----------------------------------------------------
        # Bevorzugt eindeutig benanntes Windows-Paket.
        # ----------------------------------------------------

        for asset in candidates:
            name = (
                asset.name
                .casefold()
            )

            if (
                any(
                    keyword
                    in name
                    for keyword
                    in WINDOWS_UPDATE_KEYWORDS
                )
                and (
                    "windows"
                    in name
                    or "win64"
                    in name
                )
            ):
                return asset

        # ----------------------------------------------------
        # Nur ein ZIP vorhanden.
        # ----------------------------------------------------

        if len(
            candidates
        ) == 1:
            return candidates[
                0
            ]

        return None
# ============================================================
# Service
# ============================================================

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
        self.owner = (
            owner.strip()
        )

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
            self.current_version = (
                Version(
                    current_version
                )
            )

        except InvalidVersion as error:
            raise ValueError(
                (
                    "Ungültige lokale "
                    f"Version: {current_version}"
                )
            ) from error

        self.channel = channel

        self.timeout = max(
            1.0,
            float(
                timeout
            ),
        )

    # ========================================================
    # Public
    # ========================================================

    def check_for_update(
        self,
    ) -> UpdateInfo | None:
        releases = (
            self._fetch_releases()
        )

        available: list[
            UpdateInfo
        ] = []

        for raw_release in releases:
            update = (
                self._parse_release(
                    raw_release
                )
            )

            if update is None:
                continue

            # ------------------------------------------------
            # Nicht neuer
            # ------------------------------------------------

            if (
                update.version
                <= self.current_version
            ):
                continue

            # ------------------------------------------------
            # Kanal
            # ------------------------------------------------

            if not (
                self._channel_allows(
                    update
                )
            ):
                continue

            available.append(
                update
            )

        if not available:
            return None

        return max(
            available,
            key=lambda item: (
                item.version
            ),
        )

    # ========================================================
    # Channel
    # ========================================================

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

    # ========================================================
    # GitHub
    # ========================================================

    def _fetch_releases(
        self,
    ) -> list[
        dict[
            str,
            Any,
        ]
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
            headers=(
                self._github_headers()
            ),
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=(
                    self.timeout
                ),
            ) as response:
                raw = response.read()

        except HTTPError as error:
            if error.code == 404:
                raise UpdateServiceError(
                    (
                        "GitHub Repository wurde "
                        "nicht gefunden. Prüfe "
                        "GITHUB_OWNER und "
                        "GITHUB_REPOSITORY."
                    )
                ) from error

            if error.code == 403:
                raise UpdateServiceError(
                    (
                        "GitHub hat die Anfrage "
                        "abgelehnt oder das "
                        "API-Limit wurde erreicht."
                    )
                ) from error

            raise UpdateServiceError(
                (
                    "GitHub API HTTP "
                    f"{error.code}."
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
                    "erreicht werden: "
                    f"{reason}"
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
                raw.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateServiceError(
                (
                    "GitHub hat keine gültige "
                    "JSON-Antwort geliefert."
                )
            ) from error

        if not isinstance(
            data,
            list,
        ):
            raise UpdateServiceError(
                (
                    "Unerwartetes "
                    "GitHub-Antwortformat."
                )
            )

        return [
            item
            for item
            in data
            if isinstance(
                item,
                dict,
            )
        ]

    # ========================================================
    # Header
    # ========================================================

    @staticmethod
    def _github_headers(
    ) -> dict[
        str,
        str,
    ]:
        headers = {
            "Accept": (
                "application/vnd.github+json"
            ),
            "X-GitHub-Api-Version": (
                GITHUB_API_VERSION
            ),
            "User-Agent": (
                "XXMI-Mod-Manager-Updater"
            ),
        }

        return headers

    # ========================================================
    # Release Parsing
    # ========================================================

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

        tag = release.get(
            "tag_name"
        )

        if not isinstance(
            tag,
            str,
        ):
            return None

        tag = tag.strip()

        if not tag:
            return None

        version_text = (
            self._version_from_tag(
                tag
            )
        )

        try:
            version = (
                Version(
                    version_text
                )
            )

        except InvalidVersion:
            logger.warning(
                (
                    "Ungültiger Release-Tag "
                    "ignoriert: %s"
                ),
                tag,
            )

            return None

        release_name = release.get(
            "name"
        )

        if not isinstance(
            release_name,
            str,
        ):
            release_name = ""

        release_name = (
            release_name.strip()
            or tag
        )

        notes = release.get(
            "body"
        )

        if not isinstance(
            notes,
            str,
        ):
            notes = ""

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

        return UpdateInfo(
            current_version=(
                self.current_version
            ),
            version=version,
            tag_name=tag,
            release_name=(
                release_name
            ),
            release_notes=notes,
            release_url=(
                release_url
            ),
            published_at=(
                published_at
            ),
            prerelease=bool(
                release.get(
                    "prerelease",
                    False,
                )
            ),
            assets=(
                self._parse_assets(
                    release.get(
                        "assets"
                    )
                )
            ),
        )

    @staticmethod
    def _version_from_tag(
        tag: str,
    ) -> str:
        tag = tag.strip()

        if (
            len(
                tag
            ) > 1
            and tag[
                0
            ] in {
                "v",
                "V",
            }
        ):
            return tag[
                1:
            ]

        return tag

    # ========================================================
    # Assets
    # ========================================================

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

        for item in raw_assets:
            if not isinstance(
                item,
                dict,
            ):
                continue

            name = item.get(
                "name"
            )

            download_url = item.get(
                "browser_download_url"
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

            size = item.get(
                "size",
                0,
            )

            if not isinstance(
                size,
                int,
            ):
                size = 0

            content_type = item.get(
                "content_type"
            )

            if not isinstance(
                content_type,
                str,
            ):
                content_type = None

            digest = item.get(
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


__all__ = [
    "ReleaseAsset",
    "UpdateChannel",
    "UpdateInfo",
    "UpdateService",
    "UpdateServiceError",
]