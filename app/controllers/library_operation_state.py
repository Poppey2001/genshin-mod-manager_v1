from __future__ import annotations

from enum import Enum, auto

from app.controllers.library_bulk_controller import (
    LibraryBulkController,
)
from app.controllers.library_import_controller import (
    LibraryImportController,
)
from app.controllers.library_scan_controller import (
    LibraryScanController,
)


class LibraryOperation(Enum):
    SCAN = auto()
    IMPORT = auto()
    BULK = auto()


class LibraryOperationState:
    """
    Zentrale Sicht auf alle laufenden
    Bibliotheks-Operationen.

    Die Klasse enthält keine UI-Logik.
    """

    def __init__(
        self,
        *,
        scan_controller: LibraryScanController,
        import_controller: LibraryImportController,
        bulk_controller: LibraryBulkController,
    ) -> None:
        self._scan_controller = (
            scan_controller
        )

        self._import_controller = (
            import_controller
        )

        self._bulk_controller = (
            bulk_controller
        )

    def is_running(
        self,
    ) -> bool:
        return any(
            (
                self._scan_controller.is_running,
                self._import_controller.is_running,
                self._bulk_controller.is_running,
            )
        )

    def is_operation_running(
        self,
        operation: LibraryOperation,
    ) -> bool:
        if operation is LibraryOperation.SCAN:
            return (
                self._scan_controller.is_running
            )

        if operation is LibraryOperation.IMPORT:
            return (
                self._import_controller.is_running
            )

        if operation is LibraryOperation.BULK:
            return (
                self._bulk_controller.is_running
            )

        return False

    def blocking_operation(
        self,
        requested: LibraryOperation,
    ) -> LibraryOperation | None:
        """
        Liefert die Operation, die eine neue
        Aktion aktuell blockiert.

        Besonderheit:
        Ein laufender Scan blockiert keinen
        neuen Scan-Request. Der ScanController
        kümmert sich selbst um den
        RESTART_QUEUED-Fall.
        """

        if requested is LibraryOperation.SCAN:
            if self._bulk_controller.is_running:
                return LibraryOperation.BULK

            if self._import_controller.is_running:
                return LibraryOperation.IMPORT

            return None

        if requested is LibraryOperation.IMPORT:
            if self._bulk_controller.is_running:
                return LibraryOperation.BULK

            if self._import_controller.is_running:
                return LibraryOperation.IMPORT

            if self._scan_controller.is_running:
                return LibraryOperation.SCAN

            return None

        if requested is LibraryOperation.BULK:
            if self._bulk_controller.is_running:
                return LibraryOperation.BULK

            if self._scan_controller.is_running:
                return LibraryOperation.SCAN

            if self._import_controller.is_running:
                return LibraryOperation.IMPORT

            return None

        return None

    def can_start(
        self,
        requested: LibraryOperation,
    ) -> bool:
        return (
            self.blocking_operation(
                requested
            )
            is None
        )