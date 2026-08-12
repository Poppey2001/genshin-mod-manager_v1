from __future__ import annotations

import threading

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.gamebanana.client import (
    GameBananaClient,
)

from app.gamebanana.downloader import (
    GameBananaDownloadCancelled,
    GameBananaDownloader,
)

from app.gamebanana.models import (
    GameBananaFile,
)

from app.games import (
    GameDefinition,
)


# ============================================================
# Einzelne Mod laden
# ============================================================

class GameBananaFetchSignals(
    QObject
):
    finished = Signal(
        object
    )

    failed = Signal(
        str
    )


class GameBananaFetchWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        reference: str | int,
        expected_game: (
            GameDefinition
            | None
        ),
    ) -> None:
        super().__init__()

        self.reference = reference

        self.expected_game = (
            expected_game
        )

        self.signals = (
            GameBananaFetchSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            client = (
                GameBananaClient()
            )

            mod = client.fetch_mod(
                self.reference,
                expected_game=(
                    self.expected_game
                ),
            )

        except Exception as error:
            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        self.signals.finished.emit(
            mod
        )


# ============================================================
# Browser / Suche
# ============================================================

class GameBananaBrowseSignals(
    QObject
):
    finished = Signal(
        object
    )

    failed = Signal(
        str
    )


class GameBananaBrowseWorker(
    QRunnable
):
    MODE_LATEST = "latest"

    MODE_SEARCH = "search"

    def __init__(
        self,
        *,
        game: GameDefinition,
        mode: str,
        page: int = 1,
        query: str = "",
    ) -> None:
        super().__init__()

        if mode not in {
            self.MODE_LATEST,
            self.MODE_SEARCH,
        }:
            raise ValueError(
                (
                    "Unbekannter Browse-Modus: "
                    f"{mode}"
                )
            )

        self.game = game

        self.mode = mode

        self.page = max(
            1,
            int(
                page
            ),
        )

        self.query = (
            query.strip()
        )

        self.signals = (
            GameBananaBrowseSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        client = (
            GameBananaClient()
        )

        try:
            if (
                self.mode
                == self.MODE_SEARCH
            ):
                result = (
                    client.search_recent_mods(
                        game=self.game,
                        query=self.query,
                    )
                )

            else:
                result = (
                    client.browse_latest(
                        game=self.game,
                        page=self.page,
                    )
                )

        except Exception as error:
            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        self.signals.finished.emit(
            result
        )


# ============================================================
# Download
# ============================================================

class GameBananaDownloadSignals(
    QObject
):
    # object statt int, damit große
    # Byte-Werte sicher durch Qt gehen.
    progress = Signal(
        object,
        object,
    )

    finished = Signal(
        object
    )

    failed = Signal(
        str
    )

    cancelled = Signal()


class GameBananaDownloadWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        file: GameBananaFile,
        destination_directory: Path,
    ) -> None:
        super().__init__()

        self.file = file

        self.destination_directory = (
            Path(
                destination_directory
            )
        )

        self.signals = (
            GameBananaDownloadSignals()
        )

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
            self._cancel_event
            .is_set()
        )

    @Slot()
    def run(
        self,
    ) -> None:
        downloader = (
            GameBananaDownloader()
        )

        try:
            result = (
                downloader.download(
                    file=self.file,
                    destination_directory=(
                        self.destination_directory
                    ),
                    progress_callback=(
                        self.signals
                        .progress
                        .emit
                    ),
                    cancel_callback=(
                        self.is_cancelled
                    ),
                )
            )

        except GameBananaDownloadCancelled:
            self.signals.cancelled.emit()

            return

        except Exception as error:
            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        self.signals.finished.emit(
            result
        )


__all__ = [
    "GameBananaFetchWorker",
    "GameBananaBrowseWorker",
    "GameBananaDownloadWorker",
]