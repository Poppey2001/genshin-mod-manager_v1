from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class IniAssignment:
    """Eine von einer Taste veränderte INI-Einstellung."""

    name: str
    raw_value: str
    values: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class IniStateLabel:
    """Optionale Beschreibung eines Zustands aus Kommentaren."""

    index: int
    label: str


@dataclass(slots=True, frozen=True)
class IniKeyBinding:
    """Eine erkannte [Key...]-Sektion."""

    section_name: str

    keys: tuple[str, ...]
    back_keys: tuple[str, ...]

    key_type: str
    condition: str | None

    assignments: tuple[IniAssignment, ...]
    run_commands: tuple[str, ...]

    comments: tuple[str, ...]
    state_labels: tuple[IniStateLabel, ...]

    smart: str | None = None
    wrap: str | None = None


@dataclass(slots=True, frozen=True)
class IniFileAnalysis:
    """Analyse einer Merge- oder Master-INI."""

    path: Path
    namespace: str | None

    merged_sources: tuple[str, ...]
    key_bindings: tuple[IniKeyBinding, ...]

    warnings: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ModIniAnalysis:
    """Gesamtergebnis für einen Mod."""

    root_path: Path
    files: tuple[IniFileAnalysis, ...]
    warnings: tuple[str, ...] = ()

    @property
    def has_controls(self) -> bool:
        return any(
            file.key_bindings
            for file in self.files
        )