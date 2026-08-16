from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.gamebanana.browser import GameBananaBrowserService


class GameBananaBrowseSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class GameBananaBrowseWorker(QRunnable):
    """Lädt GameBanana-Browse-Ergebnisse außerhalb des UI-Threads."""

    def __init__(
        self,
        *,
        game_id: str,
        page: int = 1,
        query: str = "",
    ) -> None:
        super().__init__()
        self.game_id = str(game_id)
        self.page = max(1, int(page))
        self.query = str(query)
        self.signals = GameBananaBrowseSignals()
        self._cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        if self.is_cancelled():
            self.signals.cancelled.emit()
            return

        service = GameBananaBrowserService()
        try:
            result = service.browse(
                game_id=self.game_id,
                page=self.page,
                query=self.query,
                cancel_callback=self.is_cancelled,
            )
        except Exception as error:
            if self.is_cancelled():
                self.signals.cancelled.emit()
                return
            self.signals.failed.emit(f"{type(error).__name__}: {error}")
            return

        if self.is_cancelled():
            self.signals.cancelled.emit()
            return

        self.signals.finished.emit(result)


__all__ = ["GameBananaBrowseWorker"]
