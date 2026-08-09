from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from app.controllers.library_mod_action_controller import (
    LibraryModActionController,
)

from app.i18n import tr

from app.models.mod import ModInfo

from app.services.mod_manager import (
    ModState,
)

from app.widgets.library.library_mod_list import (
    LibraryModListWidget,
)

from app.widgets.library.mod_details_panel import (
    ModDetailsPanel,
)


OperationRunningProvider = Callable[
    [],
    bool,
]

RefreshStatsCallback = Callable[
    [],
    None,
]


class LibrarySelectionController(QObject):
    """
    Synchronisiert Mod-Auswahl, Detailpanel,
    Einzelaktionen und Bulk-Buttons.

    LibraryPage muss dadurch die Auswahl-
    und State-Synchronisation nicht mehr
    selbst verwalten.
    """

    def __init__(
        self,
        *,
        mod_list_widget: LibraryModListWidget,
        details_panel: ModDetailsPanel,
        mod_action_controller: (
            LibraryModActionController
        ),
        operation_running_provider: (
            OperationRunningProvider
        ),
        refresh_stats_callback: (
            RefreshStatsCallback
        ),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._mod_list_widget = (
            mod_list_widget
        )

        self._details_panel = (
            details_panel
        )

        self._mod_action_controller = (
            mod_action_controller
        )

        self._operation_running_provider = (
            operation_running_provider
        )

        self._refresh_stats_callback = (
            refresh_stats_callback
        )

    # ==================================================
    # Auswahl
    # ==================================================

    def selected_mod(
        self,
    ) -> ModInfo | None:
        return (
            self._mod_list_widget.selected_mod()
        )

    def selected_mods(
        self,
    ) -> list[ModInfo]:
        return (
            self._mod_list_widget.selected_mods()
        )

    # ==================================================
    # Komplette Aktualisierung
    # ==================================================

    def refresh(
        self,
    ) -> None:
        """
        Synchronisiert die komplette
        Auswahl-abhängige Oberfläche.
        """

        self._update_details()
        self.update_bulk_buttons()

    # ==================================================
    # Einzelnen Mod aktualisieren
    # ==================================================

    def refresh_mod_state(
        self,
        mod: ModInfo,
    ) -> None:
        """
        Aktualisiert den Zustand eines Mods
        in der Liste und synchronisiert danach
        die restliche Oberfläche.
        """

        state = (
            self._mod_action_controller.get_state(
                mod
            )
        )

        self._mod_list_widget.update_mod_state(
            mod=mod,
            state=state,
        )

        self._refresh_stats_callback()

        self.refresh()

    # ==================================================
    # Bulk-Buttons
    # ==================================================

    def update_bulk_buttons(
        self,
    ) -> None:
        selected_mods = (
            self.selected_mods()
        )

        operation_running = (
            self._operation_running_provider()
        )

        enabled = (
            bool(selected_mods)
            and not operation_running
        )

        self._mod_list_widget.bulk_enable_button.setEnabled(
            enabled
        )

        self._mod_list_widget.bulk_disable_button.setEnabled(
            enabled
        )

        self._mod_list_widget.bulk_adopt_button.setEnabled(
            enabled
        )

    # ==================================================
    # Detailpanel
    # ==================================================

    def _update_details(
        self,
    ) -> None:
        selected_mods = (
            self.selected_mods()
        )

        # --------------------------------------------------
        # Mehrfachauswahl
        # --------------------------------------------------

        if len(selected_mods) > 1:
            count = len(
                selected_mods
            )

            self._details_panel.show_multiple(
                count
            )

            self._details_panel.toggle_button.setText(
                tr(
                    "library.details.multiple_title",
                    count=count,
                )
            )

            self._details_panel.toggle_button.setEnabled(
                False
            )

            self._details_panel.adopt_button.setEnabled(
                False
            )

            return

        # --------------------------------------------------
        # Keine Auswahl
        # --------------------------------------------------

        mod = self.selected_mod()

        if mod is None:
            self._details_panel.show_empty()

            self._details_panel.toggle_button.setText(
                tr(
                    "library.details.action.enable"
                )
            )

            self._details_panel.toggle_button.setEnabled(
                False
            )

            self._details_panel.adopt_button.setEnabled(
                False
            )

            return

        # --------------------------------------------------
        # Einzelner Mod
        # --------------------------------------------------

        state = (
            self._mod_action_controller.get_state(
                mod
            )
        )

        self._details_panel.show_mod(
            mod=mod,
            state=state,
        )

        self._update_action_buttons(
            state
        )

    # ==================================================
    # Action-Buttons
    # ==================================================

    def _update_action_buttons(
        self,
        state: ModState,
    ) -> None:
        toggle_button = (
            self._details_panel.toggle_button
        )

        adopt_button = (
            self._details_panel.adopt_button
        )

        operation_running = (
            self._operation_running_provider()
        )

        # --------------------------------------------------
        # Standardzustand
        # --------------------------------------------------

        toggle_button.setEnabled(
            False
        )

        adopt_button.setEnabled(
            False
        )

        # --------------------------------------------------
        # Deaktivierter Mod
        # --------------------------------------------------

        if state == ModState.DISABLED:
            toggle_button.setText(
                tr(
                    "library.details.action.enable"
                )
            )

            toggle_button.setEnabled(
                not operation_running
            )

            return

        # --------------------------------------------------
        # Aktivierter Mod
        # --------------------------------------------------

        if state == ModState.ENABLED:
            toggle_button.setText(
                tr(
                    "library.details.action.disable"
                )
            )

            toggle_button.setEnabled(
                not operation_running
            )

            return

        # --------------------------------------------------
        # Defekter Link
        # --------------------------------------------------

        if state == ModState.BROKEN:
            toggle_button.setText(
                tr(
                    "library.details.action.remove_broken"
                )
            )

            toggle_button.setEnabled(
                not operation_running
            )

            return

        # --------------------------------------------------
        # Mods-Ordner nicht konfiguriert
        # --------------------------------------------------

        if state == ModState.NOT_CONFIGURED:
            toggle_button.setText(
                tr(
                    "library.details.action.not_configured"
                )
            )

            return

        # --------------------------------------------------
        # Konflikt
        # --------------------------------------------------

        if state == ModState.CONFLICT:
            toggle_button.setText(
                tr(
                    "library.details.action.conflict"
                )
            )

            adopt_button.setEnabled(
                not operation_running
            )

            return

        # --------------------------------------------------
        # Fallback
        # --------------------------------------------------

        toggle_button.setText(
            tr(
                "library.details.action.unavailable"
            )
        )