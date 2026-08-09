from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from app.controllers.library_operation_state import (
    LibraryOperation,
    LibraryOperationState,
)
from app.widgets.library.library_header import (
    LibraryHeader,
)


ActionCallback = Callable[[], None]


class LibraryHeaderController(QObject):
    """
    Verbindet die Header-Aktionen und hält
    den Header-Zustand synchron mit den
    laufenden Bibliotheks-Operationen.
    """

    def __init__(
        self,
        *,
        header: LibraryHeader,
        operation_state: LibraryOperationState,
        import_archives_callback: ActionCallback,
        import_directory_callback: ActionCallback,
        scan_callback: ActionCallback,
        cancel_import_callback: ActionCallback,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._header = header
        self._operation_state = operation_state

        self._header.import_archives_requested.connect(
            import_archives_callback
        )

        self._header.import_directory_requested.connect(
            import_directory_callback
        )

        self._header.scan_requested.connect(
            scan_callback
        )

        self._header.cancel_import_requested.connect(
            cancel_import_callback
        )

        self.refresh()

    def refresh(
        self,
    ) -> None:
        operation_running = (
            self._operation_state.is_running()
        )

        import_running = (
            self._operation_state.is_operation_running(
                LibraryOperation.IMPORT
            )
        )

        self._header.import_button.setEnabled(
            not operation_running
        )

        self._header.refresh_button.setEnabled(
            not operation_running
        )

        self._header.cancel_import_button.setVisible(
            import_running
        )

        self._header.cancel_import_button.setEnabled(
            import_running
        )

    def mark_import_cancel_requested(
        self,
    ) -> None:
        self._header.cancel_import_button.setVisible(
            True
        )

        self._header.cancel_import_button.setEnabled(
            False
        )