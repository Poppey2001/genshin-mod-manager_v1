from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ModStructure:
    """Aus einer Ordnerstruktur erkannte Mod-Informationen."""

    character: str | None
    mod_type: str
    mod_name: str
    relative_path: str


MOD_TYPE_ALIASES = {
    "character skin": "Character Skin",
    "character skins": "Character Skin",
    "characterskin": "Character Skin",
    "skin": "Character Skin",
    "skins": "Character Skin",

    "weapon skin": "Weapon Skin",
    "weapon skins": "Weapon Skin",
    "weapons": "Weapon Skin",

    "effects": "Effects",
    "effect": "Effects",
    "visual effects": "Effects",
    "vfx": "Effects",

    "ui": "UI",
    "interface": "UI",

    "shader": "Shader",
    "shaders": "Shader",

    "other": "Sonstiges",
    "misc": "Sonstiges",
    "sonstiges": "Sonstiges",
}


def detect_mod_structure(
    library_root: Path,
    mod_directory: Path,
) -> ModStructure:
    """
    Erkennt eine Struktur wie:

    Bibliothek / Charakter / Mod-Typ / Mod
    """

    try:
        relative_path = mod_directory.relative_to(
            library_root
        )
    except ValueError:
        relative_path = Path(mod_directory.name)

    parts = relative_path.parts

    character: str | None = None
    mod_type = "Unbekannt"
    mod_name = mod_directory.name

    if len(parts) >= 3:
        character = normalize_folder_name(
            parts[0]
        )

        mod_type = normalize_mod_type(
            parts[1]
        )

        mod_name = normalize_folder_name(
            parts[-1]
        )

    elif len(parts) == 2:
        first_part = normalize_folder_name(
            parts[0]
        )

        normalized_type = normalize_mod_type(
            parts[0]
        )

        if normalized_type != "Unbekannt":
            mod_type = normalized_type
        else:
            character = first_part

        mod_name = normalize_folder_name(
            parts[-1]
        )

    elif len(parts) == 1:
        mod_name = normalize_folder_name(
            parts[0]
        )

    return ModStructure(
        character=character,
        mod_type=mod_type,
        mod_name=mod_name,
        relative_path=str(relative_path),
    )


def normalize_mod_type(
    folder_name: str,
) -> str:
    """Normalisiert verschiedene Namen eines Mod-Typs."""
    normalized = normalize_key(
        folder_name
    )

    return MOD_TYPE_ALIASES.get(
        normalized,
        normalize_folder_name(folder_name),
    )


def normalize_key(
    value: str,
) -> str:
    value = value.replace(
        "_",
        " ",
    )

    value = value.replace(
        "-",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip().casefold()


def normalize_folder_name(
    value: str,
) -> str:
    value = value.replace(
        "_",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()