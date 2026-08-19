from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    Qt,
)

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)

from app.dialogs.mod_info_dialog import (
    ModInfoDialog,
)

from app.i18n import (
    tr,
)

from app.models.mod import (
    ModInfo,
)

from app.services.mod_info_service import (
    ModInfoService,
)

from app.services.mod_manager import (
    ModManager,
)


SelectedModProvider = Callable[
    [],
    ModInfo | None,
]


class LibraryModInfoController(QObject):
    """
    Steuert die Anzeige und Analyse
    der INI-Informationen eines Mods.
    """

    def __init__(
        self,
        *,
        mod_manager: ModManager,
        selected_mod_provider: SelectedModProvider,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._dialog_parent = parent

        self._selected_mod_provider = (
            selected_mod_provider
        )

        self._service = ModInfoService(
            mod_manager=mod_manager
        )

    def show_selected_mod(
        self,
    ) -> None:
        mod = (
            self._selected_mod_provider()
        )

        if mod is None:
            return

        self.show_mod(
            mod
        )

    def show_mod(
        self,
        mod: object,
    ) -> None:
        if not isinstance(
            mod,
            ModInfo,
        ):
            return

        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )

        try:
            analysis = (
                self._service.analyze(
                    mod
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self._dialog_parent,
                tr(
                    "mod_info.analysis_failed.title"
                ),
                tr(
                    "mod_info.analysis_failed.message",
                    error_type=type(error).__name__,
                    error=error,
                ),
            )

            return

        finally:
            QApplication.restoreOverrideCursor()

        dialog = ModInfoDialog(
            mod_name=mod.name,
            analysis=analysis,
            parent=self._dialog_parent,
        )

        dialog.exec()