from __future__ import annotations

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from app.controllers.library_operation_state import (
    LibraryOperation,
)
from app.i18n import tr

def operation_title(
    operation: LibraryOperation,
) -> str:
    key = {
        LibraryOperation.SCAN:
            "library.operation.scan_running",

        LibraryOperation.IMPORT:
            "library.operation.import_running",

        LibraryOperation.BULK:
            "library.operation.bulk_running",
    }.get(
        operation,
        "library.operation.action_running",
    )

    return tr(key)


def operation_block_message(
    *,
    requested: LibraryOperation,
    blocking: LibraryOperation,
) -> str:
    key = {
        (
            LibraryOperation.IMPORT,
            LibraryOperation.BULK,
        ): (
            "library.operation.block."
            "import_by_bulk"
        ),

        (
            LibraryOperation.IMPORT,
            LibraryOperation.IMPORT,
        ): (
            "library.operation.block."
            "import_by_import"
        ),

        (
            LibraryOperation.IMPORT,
            LibraryOperation.SCAN,
        ): (
            "library.operation.block."
            "import_by_scan"
        ),

        (
            LibraryOperation.BULK,
            LibraryOperation.BULK,
        ): (
            "library.operation.block."
            "bulk_by_bulk"
        ),

        (
            LibraryOperation.BULK,
            LibraryOperation.SCAN,
        ): (
            "library.operation.block."
            "bulk_by_scan"
        ),

        (
            LibraryOperation.BULK,
            LibraryOperation.IMPORT,
        ): (
            "library.operation.block."
            "bulk_by_import"
        ),

        (
            LibraryOperation.SCAN,
            LibraryOperation.BULK,
        ): (
            "library.operation.block."
            "scan_by_bulk"
        ),

        (
            LibraryOperation.SCAN,
            LibraryOperation.IMPORT,
        ): (
            "library.operation.block."
            "scan_by_import"
        ),
    }.get(
        (
            requested,
            blocking,
        ),
        "library.operation.block.default",
    )

    return tr(key)

def show_operation_blocked(
    *,
    requested: LibraryOperation,
    blocking: LibraryOperation,
    parent: QWidget | None = None,
) -> None:
    QMessageBox.information(
        parent,
        operation_title(
            blocking
        ),
        operation_block_message(
            requested=requested,
            blocking=blocking,
        ),
    )