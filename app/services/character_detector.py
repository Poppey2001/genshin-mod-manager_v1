from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


METADATA_FILES = (
    "mod.json",
    "metadata.json",
    "info.json",
)

CHARACTER_TEXT_FILES = (
    "character.txt",
    "characters.txt",
)

CHARACTER_METADATA_KEYS = (
    "character",
    "characters",
    "target_character",
    "target_characters",
    "targetCharacter",
    "targetCharacters",
)

GENERIC_NAMES = {
    "mod",
    "mods",
    "character",
    "characters",
    "default",
    "unknown",
    "genshin",
    "skin",
    "outfit",
}

INI_CHARACTER_PATTERN = re.compile(
    r"^[;#]\s*"
    r"(?:character|characters|char|target|target_character)"
    r"\s*[:=]\s*(.+?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

BRACKET_FOLDER_PATTERN = re.compile(
    r"^\[(?P<character>[^\]]{2,60})\]"
)

DOUBLE_SEPARATOR_PATTERN = re.compile(
    r"^(?P<character>.{2,60}?)(?:__| -- )"
)


def detect_characters(
    mod_directory: Path,
) -> tuple[str, ...]:
    """
    Erkennt die Charaktere eines Mod-Ordners.

    Reihenfolge:
    1. character.txt / characters.txt
    2. JSON-Metadaten
    3. Kommentare in INI-Dateien
    4. Mod-Ordnername
    """
    characters: list[str] = []

    characters.extend(
        _detect_from_text_files(
            mod_directory
        )
    )

    characters.extend(
        _detect_from_metadata_files(
            mod_directory
        )
    )

    characters.extend(
        _detect_from_ini_files(
            mod_directory
        )
    )

    if not characters:
        characters.extend(
            _detect_from_directory_name(
                mod_directory.name
            )
        )

    return _remove_duplicates(
        characters
    )


def _detect_from_text_files(
    mod_directory: Path,
) -> list[str]:
    characters: list[str] = []

    for filename in CHARACTER_TEXT_FILES:
        file_path = mod_directory / filename

        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )[:4096]
        except OSError:
            continue

        characters.extend(
            _split_character_names(content)
        )

    return characters


def _detect_from_metadata_files(
    mod_directory: Path,
) -> list[str]:
    characters: list[str] = []

    for filename in METADATA_FILES:
        file_path = mod_directory / filename

        if not file_path.is_file():
            continue

        try:
            if file_path.stat().st_size > 256_000:
                continue

            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            data = json.loads(content)

        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        characters.extend(
            _extract_characters_from_json(data)
        )

    return characters


def _extract_characters_from_json(
    data: Any,
) -> list[str]:
    if not isinstance(data, dict):
        return []

    characters: list[str] = []

    for key in CHARACTER_METADATA_KEYS:
        if key not in data:
            continue

        value = data[key]

        if isinstance(value, str):
            characters.extend(
                _split_character_names(value)
            )

        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    characters.extend(
                        _split_character_names(entry)
                    )

    return characters


def _detect_from_ini_files(
    mod_directory: Path,
) -> list[str]:
    """
    Durchsucht höchstens zehn INI-Dateien.

    Dadurch bleibt der Scan auch auf Netzlaufwerken
    einigermaßen schnell.
    """
    characters: list[str] = []
    checked_files = 0

    try:
        ini_files = mod_directory.rglob("*.ini")

        for ini_file in ini_files:
            if checked_files >= 10:
                break

            checked_files += 1

            try:
                with ini_file.open(
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as file:
                    content = file.read(128_000)

            except OSError:
                continue

            for match in INI_CHARACTER_PATTERN.finditer(
                content
            ):
                characters.extend(
                    _split_character_names(
                        match.group(1)
                    )
                )

    except OSError:
        return characters

    return characters


def _detect_from_directory_name(
    directory_name: str,
) -> list[str]:
    bracket_match = (
        BRACKET_FOLDER_PATTERN.match(
            directory_name
        )
    )

    if bracket_match:
        return _split_character_names(
            bracket_match.group("character")
        )

    separator_match = (
        DOUBLE_SEPARATOR_PATTERN.match(
            directory_name
        )
    )

    if separator_match:
        return _split_character_names(
            separator_match.group("character")
        )

    return []


def _split_character_names(
    value: str,
) -> list[str]:
    parts = re.split(
        r"[,;\n|]+",
        value,
    )

    characters: list[str] = []

    for part in parts:
        normalized = _normalize_character_name(
            part
        )

        if normalized is not None:
            characters.append(normalized)

    return characters


def _normalize_character_name(
    value: str,
) -> str | None:
    name = value.strip()

    name = name.strip(
        "[](){}"
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    )

    if not name:
        return None

    if len(name) < 2 or len(name) > 60:
        return None

    if name.casefold() in GENERIC_NAMES:
        return None

    return name


def _remove_duplicates(
    characters: list[str],
) -> tuple[str, ...]:
    result: list[str] = []
    known_names: set[str] = set()

    for character in characters:
        normalized_key = character.casefold()

        if normalized_key in known_names:
            continue

        known_names.add(normalized_key)
        result.append(character)

    result.sort(
        key=str.casefold
    )

    return tuple(result)