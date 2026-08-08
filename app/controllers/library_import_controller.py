from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)

from app.workers.import_worker import (
    ImportWorker,
)


class LibraryImportController(QObject):
    """
    Verwaltet den asynchronen Mod-Import.

    Der Controller kennt keine konkreten
    UI-Widgets oder Dialoge.
    """

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

        self._task: ImportWorker | None = None

    @property
    def is_running(
        self,
    ) -> bool:
        return self._task is not None

    def start(
        self,
        *,
        sources: list[Path],
        library_root: Path,
        options: Any,
    ) -> bool:
        """
        Startet einen Import.

        False bedeutet, dass bereits ein
        Import läuft.
        """
        if self._task is not None:
            return False

        worker = ImportWorker(
            sources=sources,
            library_root=library_root,
            options=options,
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

        worker.signals.cancelled.connect(
            self._on_cancelled
        )

        self._task = worker

        self._thread_pool.start(
            worker
        )

        return True

    def cancel(
        self,
    ) -> bool:
        """
        Fordert den Abbruch des laufenden
        Imports an.
        """
        if self._task is None:
            return False

        self._task.cancel()

        return True

    def _on_progress(
        self,
        current: int,
        total: int,
        source_name: str,
    ) -> None:
        self.progress.emit(
            current,
            total,
            source_name,
        )

    def _on_finished(
        self,
        result: object,
    ) -> None:
        # Wichtig:
        # Zustand zuerst freigeben und danach
        # das Ereignis an die UI weitergeben.
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