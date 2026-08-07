from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.services.mod_scanner import (
    ModScanner,
    ScanCancelledError,
)


class ScanSignals(QObject):
    """
    Signale des asynchronen Bibliotheks-Scans.
    """

    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    progress = Signal(
        int,
        int,
        str,
    )


class ScanTask(QRunnable):
    """
    Führt den Mod-Bibliotheks-Scan außerhalb
    des UI-Threads aus.
    """

    def __init__(
        self,
        root_path: Path,
    ) -> None:
        super().__init__()

        self.root_path = root_path

        self.signals = ScanSignals()

        self._cancel_event = (
            threading.Event()
        )

        self.setAutoDelete(
            True
        )

    def cancel(
        self,
    ) -> None:
        self._cancel_event.set()

    def is_cancelled(
        self,
    ) -> bool:
        return (
            self._cancel_event.is_set()
        )

    @Slot()
    def run(
        self,
    ) -> None:
        scanner = ModScanner(
            calculate_network_sizes=False
        )

        try:
            result = scanner.scan(
                root_path=self.root_path,
                progress_callback=(
                    self.signals.progress.emit
                ),
                cancel_callback=(
                    self.is_cancelled
                ),
            )

        except ScanCancelledError:
            self.signals.cancelled.emit()
            return

        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: "
                f"{error}"
            )
            return

        self.signals.finished.emit(
            result
        )