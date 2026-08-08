from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from app.workers.bulk_mod_worker import (
    BulkAction,
)


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
        (
            f"Ausgewählte Mods: "
            f"{selected_count}\n\n"
            f"{description}\n\n"
            "Möchtest du fortfahren?"
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
    return {
        BulkAction.ENABLE: (
            "Mods aktivieren"
        ),
        BulkAction.DISABLE: (
            "Mods deaktivieren"
        ),
        BulkAction.ADOPT: (
            "Konflikte übernehmen"
        ),
    }[action]


def _action_description(
    action: BulkAction,
) -> str:
    return {
        BulkAction.ENABLE: (
            "Die ausgewählten deaktivierten "
            "Mods werden aktiviert. Bereits "
            "aktive Mods werden übersprungen."
        ),
        BulkAction.DISABLE: (
            "Die ausgewählten aktiven Mods "
            "werden deaktiviert. Bereits "
            "deaktivierte Mods werden "
            "übersprungen."
        ),
        BulkAction.ADOPT: (
            "Vorhandene Konflikt-Ordner "
            "werden in die Verwaltung "
            "aufgenommen. Mod-Dateien werden "
            "nicht überschrieben."
        ),
    }[action]