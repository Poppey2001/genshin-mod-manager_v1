from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.services.mod_duplicate_service import (
    DuplicateCheckCancelled,
    ModDuplicateService,
)


class ModDuplicateSignals(QObject):
    # source_key, current, total, filename
    progress = Signal(str, int, int, str)
    # worker, result
    finished = Signal(object, object)
    # worker, source_key, technical message
    failed = Signal(object, str, str)


class ModDuplicateWorker(QRunnable):
    """Runs GMM's built-in duplicate hash check outside the UI thread."""

    def __init__(
        self,
        *,
        source: Path | str,
        library_paths: tuple[Path, ...] | list[Path] | tuple[str, ...],
        game_id: str,
        service: ModDuplicateService | None = None,
    ) -> None:
        super().__init__()
        self.source = Path(source).expanduser().absolute()
        self.library_paths = tuple(Path(path) for path in library_paths)
        self.game_id = str(game_id)
        self.service = service or ModDuplicateService()
        self.signals = ModDuplicateSignals()
        self._cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _emit_progress(
        self,
        current: int,
        total: int,
        name: str,
    ) -> None:
        self.signals.progress.emit(
            str(self.source),
            int(current),
            int(total),
            str(name),
        )

    @Slot()
    def run(self) -> None:
        source_key = str(self.source)

        try:
            result = self.service.check_for_duplicate(
                source=self.source,
                library_paths=self.library_paths,
                game_id=self.game_id,
                progress_callback=self._emit_progress,
                cancel_callback=self.is_cancelled,
            )
        except DuplicateCheckCancelled:
            # The page has no separate cancelled state for one card. Treat a
            # cancellation as a normal technical failure message only when the
            # worker was explicitly cancelled.
            self.signals.failed.emit(
                self,
                source_key,
                "Duplicate check cancelled.",
            )
            return
        except Exception as error:
            self.signals.failed.emit(
                self,
                source_key,
                f"{type(error).__name__}: {error}",
            )
            return

        if self.is_cancelled():
            self.signals.failed.emit(
                self,
                source_key,
                "Duplicate check cancelled.",
            )
            return

        self.signals.finished.emit(self, result)


__all__ = [
    "ModDuplicateSignals",
    "ModDuplicateWorker",
]
