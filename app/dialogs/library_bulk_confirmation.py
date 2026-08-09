from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from app.workers.bulk_mod_worker import (
    BulkAction,
)

from app.i18n import tr

@dataclass(
    frozen=True,
    slots=True,
)
class BulkConfirmation:
    title: str


def confirm_bulk_action(
    *,
    action: BulkAction,
    selected_count: int,
    parent: QWidget | None = None,
) -> BulkConfirmation | None:
    """
    Zeigt den Bestätigungsdialog für
    eine Sammelaktion.

    None bedeutet:
    Benutzer hat abgebrochen.
    """

    title = _action_title(
        action
    )

    description = _action_description(
        action
    )

    answer = QMessageBox.question(
        parent,
        title,
        tr(
            "library.bulk.confirmation",
            count=selected_count,
            description=description,
        ),
        (
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        ),
        QMessageBox.StandardButton.No,
    )

    if (
        answer
        != QMessageBox.StandardButton.Yes
    ):
        return None

    return BulkConfirmation(
        title=title
    )


def _action_title(
    action: BulkAction,
) -> str:
    key = {
        BulkAction.ENABLE:
            "library.bulk.action.enable_title",

        BulkAction.DISABLE:
            "library.bulk.action.disable_title",

        BulkAction.ADOPT:
            "library.bulk.action.adopt_title",
    }[action]

    return tr(key)


def _action_description(
    action: BulkAction,
) -> str:
    key = {
        BulkAction.ENABLE:
            (
                "library.bulk.action."
                "enable_description"
            ),

        BulkAction.DISABLE:
            (
                "library.bulk.action."
                "disable_description"
            ),

        BulkAction.ADOPT:
            (
                "library.bulk.action."
                "adopt_description"
            ),
    }[action]

    return tr(key)