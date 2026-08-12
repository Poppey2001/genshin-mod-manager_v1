from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QWidget,
)
from app.dialogs.archive_security_dialog import (
    review_archive_security,
)

from app.services.archive_security import (
    ArchiveSecurityError,
    inspect_archive,
    is_supported_archive,
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
    # ========================================================
    # Archiv-Sicherheitsprüfung
    # ========================================================

    security_reports = []

    for path in supported_paths:
        if not path.is_file():
            continue

        if not is_supported_archive(
            path
        ):
            continue

        try:
            report = inspect_archive(
                path
            )

        except ArchiveSecurityError as error:
            QMessageBox.critical(
                parent,
                tr(
                    "archive.security.scan_failed.title"
                ),
                (
                    tr(
                        "archive.security.scan_failed.message",
                        archive=path.name,
                    )
                    + "\n\n"
                    + str(error)
                ),
            )

            return None

        security_reports.append(
            report
        )

    if security_reports:
        allowed = review_archive_security(
            reports=security_reports,
            parent=parent,
        )

        if not allowed:
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