from __future__ import annotations

import json
import logging

from dataclasses import (
    dataclass,
)

from pathlib import Path

from typing import Any


logger = logging.getLogger(
    __name__
)


MOD_METADATA_FILENAME = (
    ".xxmimm-mod.json"
)

DOWNLOAD_METADATA_SUFFIX = (
    ".xxmimm-source.json"
)

SCHEMA_VERSION = 1


@dataclass(
    frozen=True,
    slots=True,
)
class ModMetadata:
    schema_version: int = (
        SCHEMA_VERSION
    )

    game_id: str | None = None

    gamebanana_mod_id: int | None = None

    preview_file: str | None = None


# ============================================================
# Library metadata
# ============================================================

def metadata_path_for_mod(
    mod_directory: Path | str,
) -> Path:
    return (
        Path(
            mod_directory
        )
        / MOD_METADATA_FILENAME
    )


def load_mod_metadata(
    mod_directory: Path | str,
) -> ModMetadata:
    path = metadata_path_for_mod(
        mod_directory
    )

    if not path.is_file():
        return ModMetadata()

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        logger.exception(
            "Mod-Metadaten konnten nicht "
            "gelesen werden: %s",
            path,
        )

        return ModMetadata()

    if not isinstance(
        data,
        dict,
    ):
        return ModMetadata()

    game_id = data.get(
        "game_id"
    )

    if not isinstance(
        game_id,
        str,
    ):
        game_id = None

    preview_file = data.get(
        "preview_file"
    )

    if not isinstance(
        preview_file,
        str,
    ):
        preview_file = None

    gamebanana_id = None

    gamebanana = data.get(
        "gamebanana"
    )

    if isinstance(
        gamebanana,
        dict,
    ):
        candidate = (
            gamebanana.get(
                "mod_id"
            )
        )

        if (
            isinstance(
                candidate,
                int,
            )
            and not isinstance(
                candidate,
                bool,
            )
            and candidate > 0
        ):
            gamebanana_id = (
                candidate
            )

    return ModMetadata(
        schema_version=(
            SCHEMA_VERSION
        ),
        game_id=game_id,
        gamebanana_mod_id=(
            gamebanana_id
        ),
        preview_file=(
            preview_file
        ),
    )


def save_mod_metadata(
    mod_directory: Path | str,
    metadata: ModMetadata,
) -> Path:
    directory = (
        Path(
            mod_directory
        )
        .expanduser()
        .absolute()
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = metadata_path_for_mod(
        directory
    )

    data: dict[
        str,
        Any,
    ] = {
        "schema_version": (
            SCHEMA_VERSION
        ),
        "game_id": (
            metadata.game_id
        ),
    }

    if (
        metadata.gamebanana_mod_id
        is not None
    ):
        data["gamebanana"] = {
            "mod_id": (
                metadata
                .gamebanana_mod_id
            ),
        }

    if metadata.preview_file:
        data["preview_file"] = (
            metadata.preview_file
        )

    temporary = (
        path.with_suffix(
            ".tmp"
        )
    )

    temporary.write_text(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(
        path
    )

    return path


def set_gamebanana_mod_id(
    mod_directory: Path | str,
    *,
    game_id: str,
    mod_id: int,
) -> Path:
    if mod_id <= 0:
        raise ValueError(
            "Die GameBanana-ID muss "
            "größer als 0 sein."
        )

    current = load_mod_metadata(
        mod_directory
    )

    return save_mod_metadata(
        mod_directory,
        ModMetadata(
            game_id=game_id,
            gamebanana_mod_id=(
                mod_id
            ),
            preview_file=(
                current.preview_file
            ),
        ),
    )


# ============================================================
# Download sidecar
# ============================================================

def download_metadata_path(
    archive_path: Path | str,
) -> Path:
    archive = Path(
        archive_path
    )

    return archive.with_name(
        archive.name
        + DOWNLOAD_METADATA_SUFFIX
    )


def write_gamebanana_download_metadata(
    archive_path: Path | str,
    *,
    game_id: str,
    mod_id: int,
) -> Path:
    path = download_metadata_path(
        archive_path
    )

    data = {
        "schema_version": (
            SCHEMA_VERSION
        ),
        "game_id": game_id,
        "gamebanana": {
            "mod_id": mod_id,
        },
    }

    path.write_text(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def transfer_download_metadata(
    source_archive: Path | str,
    destination_mod: Path | str,
) -> bool:
    sidecar = download_metadata_path(
        source_archive
    )

    if not sidecar.is_file():
        return False

    try:
        data = json.loads(
            sidecar.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return False

    if not isinstance(
        data,
        dict,
    ):
        return False

    game_id = data.get(
        "game_id"
    )

    gamebanana = data.get(
        "gamebanana"
    )

    if not isinstance(
        game_id,
        str,
    ):
        return False

    if not isinstance(
        gamebanana,
        dict,
    ):
        return False

    mod_id = gamebanana.get(
        "mod_id"
    )

    if (
        not isinstance(
            mod_id,
            int,
        )
        or isinstance(
            mod_id,
            bool,
        )
        or mod_id <= 0
    ):
        return False

    save_mod_metadata(
        destination_mod,
        ModMetadata(
            game_id=game_id,
            gamebanana_mod_id=(
                mod_id
            ),
        ),
    )

    return True


__all__ = [
    "MOD_METADATA_FILENAME",
    "ModMetadata",
    "load_mod_metadata",
    "save_mod_metadata",
    "set_gamebanana_mod_id",
    "write_gamebanana_download_metadata",
    "transfer_download_metadata",
]