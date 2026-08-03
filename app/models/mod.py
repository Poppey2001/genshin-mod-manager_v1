from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ModInfo:
    """Informationen über einen gefundenen Mod-Ordner."""

    name: str
    path: Path

    is_symlink: bool
    is_network: bool

    file_count: int
    ini_file_count: int

    total_size: int | None
    modified_at: float | None

    preview_path: Path | None = None
    error: str | None = None
    
    characters: tuple[str, ...] =()
    
    mod_type: str = "Unbekannt"
    relative_path: str = ""    