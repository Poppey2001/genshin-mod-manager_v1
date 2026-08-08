from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)

from app.models.mod import ModInfo
from app.services.mod_manager import ModManager

from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
    BulkModWorker,
)


class LibraryBulkController(QObject):
    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        mod_manager: ModManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._mod_manager = mod_manager

        self._thread_pool = (
            QThreadPool.globalInstance()
        )

        self._task: BulkModWorker | None = None

    @property
    def is_running(
        self,
    ) -> bool:
        return self._task is not None

    def start(
        self,
        *,
        mods: list[ModInfo],
        action: BulkAction,
    ) -> bool:
        if self._task is not None:
            return False

        if not mods:
            return False

        worker = BulkModWorker(
            mods=mods,
            action=action,
            mod_manager=self._mod_manager,
        )

        worker.signals.progress.connect(
            self._on_progress
        )

        worker.signals.finished.connect(
            self._on_finished
        )

        worker.signals.failed.connect(
            self._on_failed
        )

        self._task = worker

        # WICHTIG:
        # Worker niemals mit worker.run() direkt starten.
        self._thread_pool.start(
            worker
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
        result: BulkBatchResult,
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