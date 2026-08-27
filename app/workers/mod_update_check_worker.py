from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.gamebanana.client import GameBananaClient
from app.models.mod import ModInfo
from app.services.library_mod_update_service import (
    LibraryModUpdateService,
    ModUpdateResult,
)


class ModUpdateCheckSignals(QObject):
    progress = Signal(int, int, str)
    result = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class ModUpdateCheckWorker(QRunnable):
    """Checks GameBanana revisions outside the Qt UI thread."""

    def __init__(
        self,
        *,
        service: LibraryModUpdateService,
        game_id: str,
        mods: tuple[ModInfo, ...],
    ) -> None:
        super().__init__()
        self.service = service
        self.game_id = str(game_id)
        self.mods = tuple(mods)
        self.signals = ModUpdateCheckSignals()
        self._cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        results: list[ModUpdateResult] = []
        client = GameBananaClient(timeout=20.0)
        total = len(self.mods)

        try:
            for index, mod in enumerate(self.mods, start=1):
                if self.is_cancelled():
                    self.signals.cancelled.emit()
                    return

                self.signals.progress.emit(
                    index - 1,
                    total,
                    mod.name,
                )

                result = self.service.check_mod(
                    game_id=self.game_id,
                    mod=mod,
                    client=client,
                )
                results.append(result)
                self.signals.result.emit(result)

                self.signals.progress.emit(
                    index,
                    total,
                    mod.name,
                )

        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: {error}"
            )
            return

        if self.is_cancelled():
            self.signals.cancelled.emit()
            return

        self.signals.finished.emit(tuple(results))


__all__ = ["ModUpdateCheckWorker", "ModUpdateCheckSignals"]
