from __future__ import annotations

import os
import sys
from pathlib import Path


APP_FOLDER_WINDOWS = "Genshin Mod Manager"
APP_FOLDER_LINUX = "genshin-mod-manager"


def component_root() -> Path:
    """Directory used by the Update Agent for hot-updateable resources."""
    if sys.platform.casefold().startswith("win"):
        local_appdata = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        ).expanduser()
        return local_appdata / APP_FOLDER_WINDOWS / "Components"

    xdg_data = os.environ.get("XDG_DATA_HOME", "").strip()
    data_home = Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share"
    return data_home / APP_FOLDER_LINUX / "components"


def resolve_component_path(relative_path: str, bundled_path: Path) -> Path:
    """Prefer an externally updated component and fall back to the bundled file."""
    relative = Path(relative_path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        return bundled_path

    root = component_root().resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return bundled_path

    return candidate if candidate.is_file() else bundled_path


def read_component_text(relative_path: str, bundled_path: Path) -> tuple[str, Path]:
    source = resolve_component_path(relative_path, bundled_path)
    return source.read_text(encoding="utf-8"), source


__all__ = [
    "component_root",
    "read_component_text",
    "resolve_component_path",
]
