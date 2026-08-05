from __future__ import annotations

import threading

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.services.mod_importer import (
    ImportCancelledError,
    ImportOptions,
    ModImporter,
)


class ImportWorkerSignals(QObject):
    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class ImportWorker(QRunnable):
    """Führt den Import außerhalb des UI-Threads aus."""

    def __init__(
        self,
        sources: list[Path],
        library_root: Path,
        options: ImportOptions,
    ) -> None:
        super().__init__()

        self.sources = sources
        self.library_root = library_root
        self.options = options

        self.signals = ImportWorkerSignals()

        self._cancel_event = threading.Event()

        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        importer = ModImporter()

        try:
            result = importer.import_sources(
                sources=self.sources,
                library_root=self.library_root,
                options=self.options,
                progress_callback=(
                    self.signals.progress.emit
                ),
                cancel_callback=(
                    self.is_cancelled
                ),
            )

        except ImportCancelledError:
            self.signals.cancelled.emit()
            return

        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: {error}"
            )
            return

        self.signals.finished.emit(
            result
        )