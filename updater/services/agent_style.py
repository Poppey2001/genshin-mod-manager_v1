from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        return Path(str(frozen_root))
    return Path(__file__).resolve().parents[2]


def bundled_stylesheet_path() -> Path:
    return _resource_root() / "updater" / "styles" / "update_agent.qss"


def component_stylesheet_path(component_root: Path | None) -> Path | None:
    if component_root is None:
        return None
    return Path(component_root).expanduser() / "styles" / "update_agent.qss"


def _valid_qss(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(text.strip()) and text.count("{") == text.count("}")


def load_agent_stylesheet(component_root: Path | None = None) -> str:
    candidates = (
        component_stylesheet_path(component_root),
        bundled_stylesheet_path(),
    )

    for candidate in candidates:
        if candidate is None or not candidate.is_file() or not _valid_qss(candidate):
            continue
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            continue

    return ""


def apply_agent_style(
    application: QApplication,
    *,
    component_root: Path | None = None,
) -> None:
    stylesheet = load_agent_stylesheet(component_root)
    if stylesheet:
        application.setStyleSheet(stylesheet)


__all__ = [
    "apply_agent_style",
    "bundled_stylesheet_path",
    "component_stylesheet_path",
    "load_agent_stylesheet",
]
