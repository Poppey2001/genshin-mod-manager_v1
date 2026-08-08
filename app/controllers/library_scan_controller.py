from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)

from app.services.mod_scanner import ScanResult
from app.workers.library_scan_worker import ScanTask


class ScanRequestStatus(Enum):
    STARTED = auto()
    RESTART_QUEUED = auto()
    FAILED = auto()


class LibraryScanController(QObject):
    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._thread_pool = (
            QThreadPool.globalInstance()
        )

        self._task: ScanTask | None = None

        # Falls während eines laufenden Scans
        # ein neuer Scan angefordert wird.
        self._pending_root_path: Path | None = None

    @property
    def is_running(
        self,
    ) -> bool:
        return self._task is not None

    @property
    def has_pending_restart(
        self,
    ) -> bool:
        return self._pending_root_path is not None

    def request_scan(
        self,
        *,
        root_path: Path,
    ) -> ScanRequestStatus:
        """
        Startet einen Scan.

        Falls bereits ein Scan läuft, wird
        dieser abgebrochen und anschließend
        automatisch mit root_path neu gestartet.
        """

        if self._task is not None:
            self._pending_root_path = root_path

            self._task.cancel()

            return (
                ScanRequestStatus.RESTART_QUEUED
            )

        started = self._start_task(
            root_path=root_path
        )

        if not started:
            return ScanRequestStatus.FAILED

        return ScanRequestStatus.STARTED

    def cancel(
        self,
    ) -> bool:
        """
        Bricht den aktuellen Scan vollständig ab.

        Ein vorgemerkter automatischer Neustart
        wird dabei verworfen.
        """

        self._pending_root_path = None

        if self._task is None:
            return False

        self._task.cancel()

        return True

    def _start_task(
        self,
        *,
        root_path: Path,
    ) -> bool:
        if self._task is not None:
            return False

        try:
            task = ScanTask(
                root_path=root_path
            )

            task.signals.progress.connect(
                self._on_progress
            )

            task.signals.finished.connect(
                self._on_finished
            )

            task.signals.failed.connect(
                self._on_failed
            )

            task.signals.cancelled.connect(
                self._on_cancelled
            )

            self._task = task

            self._thread_pool.start(
                task
            )

        except Exception:
            self._task = None
            return False

        return True

    def _on_progress(
        self,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.progress.emit(
            current,
            total,
            mod_name,
        )

    def _on_finished(
        self,
        result: ScanResult,
    ) -> None:
        self._task = None

        if self._start_pending_scan():
            return

        self.finished.emit(
            result
        )

    def _on_failed(
        self,
        message: str,
    ) -> None:
        self._task = None

        if self._start_pending_scan():
            return

        self.failed.emit(
            message
        )

    def _on_cancelled(
        self,
    ) -> None:
        self._task = None

        if self._start_pending_scan():
            return

        self.cancelled.emit()

    def _start_pending_scan(
        self,
    ) -> bool:
        root_path = self._pending_root_path

        if root_path is None:
            return False

        # Wichtig:
        # Vor dem Start zurücksetzen.
        self._pending_root_path = None

        started = self._start_task(
            root_path=root_path
        )

        if not started:
            self.failed.emit(
                (
                    "Der vorgemerkte "
                    "Bibliotheks-Scan konnte "
                    "nicht gestartet werden."
                )
            )

        return True