from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QWidget,
)
from app.i18n import tr

def _archive_file_filter(
) -> str:
    return ";;".join(
        (
            tr(
                "library.import_picker."
                "supported_archives"
            ),
            tr(
                "library.import_picker."
                "zip_archives"
            ),
            tr(
                "library.import_picker."
                "seven_zip_archives"
            ),
            tr(
                "library.import_picker."
                "rar_archives"
            ),
            tr(
                "library.import_picker."
                "tar_archives"
            ),
            tr(
                "library.import_picker."
                "all_files"
            ),
        )
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
            tr(
                "library.import_picker."
                "archive_title"
            ),
            str(Path.home()),
            _archive_file_filter(),
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
            tr(
                "library.import_picker."
                "directory_title"
            ),
            str(Path.home()),
        )
    )

    if not selected_directory:
        return []

    return [
        Path(selected_directory)
    ]