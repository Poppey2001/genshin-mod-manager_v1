from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QWidget,
)

from app.dialogs.import_options_dialog import (
    ImportOptionsDialog,
)

from app.services.mod_importer import (
    is_supported_import_source,
)
from app.i18n import tr

@dataclass(
    frozen=True,
    slots=True,
)
class PreparedImport:
    """
    Vollständig vorbereiteter Importauftrag.
    """

    sources: list[Path]
    options: Any


def prepare_import_request(
    *,
    paths: list[Path],
    parent: QWidget | None = None,
) -> PreparedImport | None:
    """
    Prüft die Importquellen und öffnet
    anschließend den ImportOptionsDialog.

    None bedeutet:
    - keine gültigen Quellen
    - oder Benutzer hat abgebrochen
    """

    supported_paths = [
        path
        for path in paths
        if is_supported_import_source(
            path
        )
    ]

    if not supported_paths:
        QMessageBox.warning(
            parent,
            tr(
                "library.import."
                "unsupported_title"
            ),
            tr(
                "library.import."
                "unsupported_message"
            ),
        )
                

        return None

    dialog = ImportOptionsDialog(
        sources=supported_paths,
        parent=parent,
    )

    if (
        dialog.exec()
        != QDialog.DialogCode.Accepted
    ):
        return None

    options = (
        dialog.selected_options()
    )

    return PreparedImport(
        sources=supported_paths,
        options=options,
    )