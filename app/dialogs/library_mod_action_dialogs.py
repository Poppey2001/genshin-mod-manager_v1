from __future__ import annotations

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from app.controllers.library_mod_action_controller import (
    ModActionResult,
    ModActionStatus,
)
from app.i18n import tr

def show_mod_action_problem(
    *,
    result: ModActionResult,
    parent: QWidget | None = None,
) -> bool:
    """
    Zeigt einen Dialog für nicht ausführbare
    Einzel-Mod-Aktionen.

    Rückgabe:
        True  -> Ergebnis wurde behandelt
        False -> Aktion war erfolgreich
    """

    if (
        result.status
        == ModActionStatus.NOT_CONFIGURED
    ):
        QMessageBox.warning(
            parent,
            tr(
                "library.mod_action.dialog."
                "missing_folder_title"
            ),
            result.message,
        )
        return True

    if (
        result.status
        == ModActionStatus.CONFLICT
    ):
        QMessageBox.warning(
            parent,
            tr(
                "library.mod_action.dialog."
                "conflict_title"
            ),
            result.message,
        )
        return True

    if (
        result.status
        == ModActionStatus.NOT_CONFLICT
    ):
        QMessageBox.information(
            parent,
            tr(
                "library.mod_action.dialog."
                "no_conflict_title"
            ),
            result.message,
        )
        return True

    return False


def confirm_adopt_existing(
    *,
    mod_name: str,
    parent: QWidget | None = None,
) -> bool:
    answer = QMessageBox.question(
        parent,
        tr(
            "library.mod_action.dialog."
            "adopt_title"
        ),
        tr(
            "library.mod_action.dialog."
            "adopt_message",
            mod_name=mod_name,
        ),
        (
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        ),
        QMessageBox.StandardButton.No,
    )

    return (
        answer
        == QMessageBox.StandardButton.Yes
    )