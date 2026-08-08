from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)

from app.services.mod_scanner import (
    ScanResult,
)

from app.workers.library_scan_worker import (
    ScanTask,
)


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

    @property
    def is_running(
        self,
    ) -> bool:
        return self._task is not None

    def start(
        self,
        *,
        root_path: Path,
    ) -> bool:
        if self._task is not None:
            return False

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

        return True

    def cancel(
        self,
    ) -> bool:
        if self._task is None:
            return False

        self._task.cancel()

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

        self.finished.emit(
            result
        )

    def _on_failed(
        self,
        message: str,
    ) -> None:
        self._task = None

        self.failed.emit(
            message
        )

    def _on_cancelled(
        self,
    ) -> None:
        self._task = None

        self.cancelled.emit()