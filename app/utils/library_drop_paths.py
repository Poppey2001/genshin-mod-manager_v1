from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData

from app.services.mod_importer import (
    is_supported_import_source,
)


def extract_import_paths(
    mime_data: QMimeData,
) -> list[Path]:
    """
    Extrahiert unterstützte lokale Importpfade
    aus Drag-&-Drop-Mime-Daten.

    - ignoriert nicht-lokale URLs
    - ignoriert nicht unterstützte Dateien
    - entfernt doppelte Pfade
    - erhält die ursprüngliche Reihenfolge
    """

    if not mime_data.hasUrls():
        return []

    paths: list[Path] = []
    seen_paths: set[Path] = set()

    for url in mime_data.urls():
        if not url.isLocalFile():
            continue

        local_file = url.toLocalFile()

        if not local_file:
            continue

        path = Path(
            local_file
        ).expanduser()

        if not path.exists():
            continue

        if not is_supported_import_source(
            path
        ):
            continue

        try:
            normalized_path = path.resolve()
        except OSError:
            normalized_path = path.absolute()

        if normalized_path in seen_paths:
            continue

        seen_paths.add(
            normalized_path
        )

        paths.append(
            path
        )

    return paths