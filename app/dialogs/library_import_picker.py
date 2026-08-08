from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QWidget,
)


ARCHIVE_FILE_FILTER = (
    "Unterstützte Archive "
    "(*.zip *.7z *.rar "
    "*.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tbz2 "
    "*.tar.xz *.txz);;"
    "ZIP-Archive (*.zip);;"
    "7-Zip-Archive (*.7z);;"
    "RAR-Archive (*.rar);;"
    "TAR-Archive "
    "(*.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tbz2 "
    "*.tar.xz *.txz);;"
    "Alle Dateien (*)"
)


def choose_import_archives(
    parent: QWidget | None = None,
) -> list[Path]:
    """
    Öffnet den Dateidialog für unterstützte
    Mod-Archive.
    """
    selected_files, _selected_filter = (
        QFileDialog.getOpenFileNames(
            parent,
            "Mod-Archive auswählen",
            str(Path.home()),
            ARCHIVE_FILE_FILTER,
        )
    )

    return [
        Path(file_path)
        for file_path in selected_files
    ]


def choose_import_directory(
    parent: QWidget | None = None,
) -> list[Path]:
    """
    Öffnet den Dialog zur Auswahl eines
    einzelnen Mod-Ordners.
    """
    selected_directory = (
        QFileDialog.getExistingDirectory(
            parent,
            "Mod-Ordner auswählen",
            str(Path.home()),
        )
    )

    if not selected_directory:
        return []

    return [
        Path(selected_directory)
    ]