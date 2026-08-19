from __future__ import annotations

import json
import os
import tempfile

from dataclasses import (
    asdict,
    dataclass,
)

from pathlib import Path

from app.config import (
    CONFIG_DIR,
)


TOOL_PATHS_FILE = (
    CONFIG_DIR
    / "tool-paths.json"
)

ORFIX_ENVIRONMENT_KEYS = (
    "GMM_ORFIX_PATH",
    "ORFIX_PATH",
)

CONFLICT_HASH_ENVIRONMENT_KEYS = (
    "GMM_CONFLICT_HASH_TOOL_PATH",
    "GMM_SHA256_TOOL_PATH",
)


@dataclass(
    slots=True,
)
class ToolPathsSettings:
    orfix_path: str | None = None

    conflict_hash_tool_path: (
        str
        | None
    ) = None

    def orfix_file(
        self,
    ) -> Path | None:
        return _existing_file(
            self.orfix_path
        )

    def conflict_hash_tool_file(
        self,
    ) -> Path | None:
        return _existing_file(
            self.conflict_hash_tool_path
        )


def _clean_path(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip()

    if not text:
        return None

    path = (
        Path(
            text
        )
        .expanduser()
    )

    try:
        path = path.resolve(
            strict=False
        )

    except OSError:
        path = path.absolute()

    return str(
        path
    )


def _existing_file(
    value: str | None,
) -> Path | None:
    cleaned = _clean_path(
        value
    )

    if cleaned is None:
        return None

    path = Path(
        cleaned
    )

    if not path.is_file():
        return None

    return path


def load_tool_paths_settings(
) -> ToolPathsSettings:
    try:
        raw = json.loads(
            TOOL_PATHS_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
    ):
        settings = ToolPathsSettings()

        apply_tool_paths_to_environment(
            settings
        )

        return settings

    if not isinstance(
        raw,
        dict,
    ):
        settings = ToolPathsSettings()

        apply_tool_paths_to_environment(
            settings
        )

        return settings

    settings = ToolPathsSettings(
        orfix_path=_clean_path(
            raw.get(
                "orfix_path"
            )
        ),
        conflict_hash_tool_path=(
            _clean_path(
                raw.get(
                    "conflict_hash_tool_path"
                )
            )
        ),
    )

    apply_tool_paths_to_environment(
        settings
    )

    return settings


def save_tool_paths_settings(
    settings: ToolPathsSettings,
) -> None:
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    normalized = (
        ToolPathsSettings(
            orfix_path=_clean_path(
                settings.orfix_path
            ),
            conflict_hash_tool_path=(
                _clean_path(
                    settings
                    .conflict_hash_tool_path
                )
            ),
        )
    )

    payload = json.dumps(
        asdict(
            normalized
        ),
        ensure_ascii=False,
        indent=4,
    ) + "\n"

    temporary_handle = None
    temporary_path: Path | None = None

    try:
        temporary_handle = (
            tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="tool-paths-",
                suffix=".tmp",
                dir=CONFIG_DIR,
                delete=False,
            )
        )

        temporary_path = Path(
            temporary_handle.name
        )

        temporary_handle.write(
            payload
        )

        temporary_handle.flush()

        os.fsync(
            temporary_handle.fileno()
        )

        temporary_handle.close()
        temporary_handle = None

        os.replace(
            temporary_path,
            TOOL_PATHS_FILE,
        )

    finally:
        if temporary_handle is not None:
            temporary_handle.close()

        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()
            except OSError:
                pass

    apply_tool_paths_to_environment(
        normalized
    )


def apply_tool_paths_to_environment(
    settings: ToolPathsSettings | None = None,
) -> None:
    if settings is None:
        settings = load_tool_paths_settings()
        return

    configured_files = (
        (
            settings.orfix_file(),
            ORFIX_ENVIRONMENT_KEYS,
        ),
        (
            settings.conflict_hash_tool_file(),
            CONFLICT_HASH_ENVIRONMENT_KEYS,
        ),
    )

    prepend_directories: list[
        str
    ] = []

    for (
        file_path,
        environment_keys,
    ) in configured_files:
        if file_path is None:
            for key in environment_keys:
                os.environ.pop(
                    key,
                    None,
                )

            continue

        file_text = str(
            file_path
        )

        for key in environment_keys:
            os.environ[
                key
            ] = file_text

        directory = str(
            file_path.parent
        )

        if directory not in prepend_directories:
            prepend_directories.append(
                directory
            )

    if not prepend_directories:
        return

    current_path = os.environ.get(
        "PATH",
        "",
    )

    current_parts = [
        item
        for item in current_path.split(
            os.pathsep
        )
        if item
    ]

    normalized_existing = {
        os.path.normcase(
            os.path.abspath(
                item
            )
        )
        for item in current_parts
    }

    additions: list[
        str
    ] = []

    for directory in prepend_directories:
        normalized = os.path.normcase(
            os.path.abspath(
                directory
            )
        )

        if normalized in normalized_existing:
            continue

        normalized_existing.add(
            normalized
        )

        additions.append(
            directory
        )

    if additions:
        os.environ[
            "PATH"
        ] = os.pathsep.join(
            additions
            + current_parts
        )


def configured_orfix_path(
) -> Path | None:
    return (
        load_tool_paths_settings()
        .orfix_file()
    )


def configured_conflict_hash_tool_path(
) -> Path | None:
    return (
        load_tool_paths_settings()
        .conflict_hash_tool_file()
    )


__all__ = [
    "CONFLICT_HASH_ENVIRONMENT_KEYS",
    "ORFIX_ENVIRONMENT_KEYS",
    "TOOL_PATHS_FILE",
    "ToolPathsSettings",
    "apply_tool_paths_to_environment",
    "configured_conflict_hash_tool_path",
    "configured_orfix_path",
    "load_tool_paths_settings",
    "save_tool_paths_settings",
]
