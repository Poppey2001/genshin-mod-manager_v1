from __future__ import annotations

import hashlib
import json
import logging

from dataclasses import (
    asdict,
    dataclass,
)

from pathlib import Path
from typing import Any

from app.config import (
    CACHE_DIR,
    CONFIG_DIR,
)


logger = logging.getLogger(
    __name__
)


CACHE_SETTINGS_FILE = (
    CONFIG_DIR
    / "gamebanana-image-cache.json"
)

DEFAULT_CACHE_DIRECTORY = (
    CACHE_DIR
    / "gamebanana"
    / "images"
)

MIN_CACHE_SIZE_MB = 64
MAX_CACHE_SIZE_MB = 32768
DEFAULT_CACHE_SIZE_MB = 512


@dataclass(
    slots=True,
)
class GameBananaImageCacheSettings:
    enabled: bool = True

    directory: str | None = None

    max_size_mb: int = (
        DEFAULT_CACHE_SIZE_MB
    )

    @property
    def resolved_directory(
        self,
    ) -> Path:
        if not self.directory:
            return (
                DEFAULT_CACHE_DIRECTORY
            )

        return (
            Path(
                self.directory
            )
            .expanduser()
            .absolute()
        )

    def validate(
        self,
    ) -> None:
        self.max_size_mb = max(
            MIN_CACHE_SIZE_MB,
            min(
                int(
                    self.max_size_mb
                ),
                MAX_CACHE_SIZE_MB,
            ),
        )

        if self.directory:
            self.directory = str(
                Path(
                    self.directory
                )
                .expanduser()
                .absolute()
            )

    def to_dict(
        self,
    ) -> dict[
        str,
        Any,
    ]:
        return asdict(
            self
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[
            str,
            Any,
        ],
    ) -> (
        GameBananaImageCacheSettings
    ):
        settings = cls()

        enabled = data.get(
            "enabled"
        )

        if isinstance(
            enabled,
            bool,
        ):
            settings.enabled = (
                enabled
            )

        directory = data.get(
            "directory"
        )

        if (
            directory is None
            or isinstance(
                directory,
                str,
            )
        ):
            settings.directory = (
                directory
            )

        max_size_mb = data.get(
            "max_size_mb"
        )

        if (
            isinstance(
                max_size_mb,
                int,
            )
            and not isinstance(
                max_size_mb,
                bool,
            )
        ):
            settings.max_size_mb = (
                max_size_mb
            )

        settings.validate()

        return settings


def load_gamebanana_image_cache_settings(
) -> GameBananaImageCacheSettings:
    if not CACHE_SETTINGS_FILE.is_file():
        return (
            GameBananaImageCacheSettings()
        )

    try:
        data = json.loads(
            CACHE_SETTINGS_FILE
            .read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Ungültige Cache-Konfiguration."
            )

        return (
            GameBananaImageCacheSettings
            .from_dict(
                data
            )
        )

    except (
        OSError,
        TypeError,
        json.JSONDecodeError,
    ):
        logger.exception(
            (
                "GameBanana-Cache-"
                "Konfiguration konnte "
                "nicht geladen werden."
            )
        )

        return (
            GameBananaImageCacheSettings()
        )


def save_gamebanana_image_cache_settings(
    settings: (
        GameBananaImageCacheSettings
    ),
) -> None:
    settings.validate()

    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = (
        CACHE_SETTINGS_FILE
        .with_suffix(
            ".tmp"
        )
    )

    temporary_file.write_text(
        json.dumps(
            settings.to_dict(),
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        CACHE_SETTINGS_FILE
    )


class GameBananaImageCache:
    """
    Verwaltet ausschließlich vom
    GameBanana-Bildcache erzeugte Dateien.

    Beim Leeren werden bewusst nur
    *.img und *.part gelöscht.
    """

    def __init__(
        self,
        *,
        settings: (
            GameBananaImageCacheSettings
            | None
        ) = None,
    ) -> None:
        self.settings = (
            settings
            or load_gamebanana_image_cache_settings()
        )

        self.settings.validate()

    @property
    def directory(
        self,
    ) -> Path:
        return (
            self.settings
            .resolved_directory
        )

    @property
    def maximum_bytes(
        self,
    ) -> int:
        return (
            self.settings.max_size_mb
            * 1024
            * 1024
        )

    def cache_path_for(
        self,
        url: str,
    ) -> Path:
        digest = hashlib.sha256(
            url.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            self.directory
            / f"{digest}.img"
        )

    def read(
        self,
        url: str,
    ) -> bytes | None:
        if not self.settings.enabled:
            return None

        path = (
            self.cache_path_for(
                url
            )
        )

        if not path.is_file():
            return None

        try:
            data = path.read_bytes()

            if not data:
                path.unlink(
                    missing_ok=True
                )

                return None

            # Als zuletzt benutzt markieren.
            path.touch()

            return data

        except OSError:
            logger.exception(
                (
                    "Cache-Bild konnte "
                    "nicht gelesen werden: %s"
                ),
                path,
            )

            return None

    def write(
        self,
        url: str,
        data: bytes,
    ) -> Path | None:
        if not self.settings.enabled:
            return None

        if not data:
            return None

        directory = (
            self.directory
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            self.cache_path_for(
                url
            )
        )

        temporary = (
            destination
            .with_suffix(
                ".part"
            )
        )

        try:
            temporary.write_bytes(
                data
            )

            temporary.replace(
                destination
            )

        except OSError:
            temporary.unlink(
                missing_ok=True
            )

            logger.exception(
                (
                    "GameBanana-Bild konnte "
                    "nicht gecacht werden."
                )
            )

            return None

        self.enforce_limit()

        return destination

    def size_bytes(
        self,
    ) -> int:
        directory = (
            self.directory
        )

        if not directory.is_dir():
            return 0

        total = 0

        try:
            for path in directory.glob(
                "*.img"
            ):
                try:
                    total += (
                        path.stat()
                        .st_size
                    )

                except OSError:
                    continue

        except OSError:
            return total

        return total

    def clear(
        self,
    ) -> int:
        """
        Löscht nur Dateien unseres
        Bild-Caches.

        Rückgabe:
            Anzahl gelöschter Dateien.
        """

        directory = (
            self.directory
        )

        if not directory.is_dir():
            return 0

        deleted = 0

        for pattern in (
            "*.img",
            "*.part",
        ):
            for path in directory.glob(
                pattern
            ):
                try:
                    path.unlink(
                        missing_ok=True
                    )

                    deleted += 1

                except OSError:
                    logger.exception(
                        (
                            "Cache-Datei konnte "
                            "nicht gelöscht werden: %s"
                        ),
                        path,
                    )

        return deleted

    def enforce_limit(
        self,
    ) -> None:
        directory = (
            self.directory
        )

        if not directory.is_dir():
            return

        files: list[
            tuple[
                float,
                int,
                Path,
            ]
        ] = []

        total_size = 0

        for path in directory.glob(
            "*.img"
        ):
            try:
                stat = path.stat()

            except OSError:
                continue

            size = stat.st_size

            total_size += size

            files.append(
                (
                    stat.st_mtime,
                    size,
                    path,
                )
            )

        maximum = (
            self.maximum_bytes
        )

        if total_size <= maximum:
            return

        # Älteste Dateien zuerst.
        files.sort(
            key=lambda value: value[0]
        )

        for (
            _modified,
            size,
            path,
        ) in files:
            if total_size <= maximum:
                break

            try:
                path.unlink(
                    missing_ok=True
                )

            except OSError:
                continue

            total_size -= size


__all__ = [
    "GameBananaImageCache",
    "GameBananaImageCacheSettings",
    "DEFAULT_CACHE_DIRECTORY",
    "DEFAULT_CACHE_SIZE_MB",
    "load_gamebanana_image_cache_settings",
    "save_gamebanana_image_cache_settings",
]