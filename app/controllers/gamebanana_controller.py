from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)

from app.config import (
    AppConfig,
    CACHE_DIR,
)

from app.gamebanana.models import (
    GameBananaBrowseResult,
    GameBananaFile,
    GameBananaMod,
)

from app.games import (
    get_game,
)

from app.workers.gamebanana_worker import (
    GameBananaBrowseWorker,
    GameBananaDownloadWorker,
    GameBananaFetchWorker,
)


class GameBananaController(
    QObject
):
    """
    Koordiniert Browser, Mod-Details
    und Downloads.

    Jede Operation bleibt an das Spiel
    gebunden, mit dem sie gestartet wurde.
    """

    # ========================================================
    # Browse
    # ========================================================

    browse_started = Signal(
        str
    )

    browse_loaded = Signal(
        object,
        str,
    )

    browse_failed = Signal(
        str
    )

    # ========================================================
    # Mod-Details
    # ========================================================

    lookup_started = Signal()

    mod_loaded = Signal(
        object,
        str,
    )

    lookup_failed = Signal(
        str
    )

    # ========================================================
    # Download
    # ========================================================

    download_started = Signal(
        object
    )

    download_progress = Signal(
        object,
        object,
    )

    download_finished = Signal(
        object,
        str,
    )

    download_failed = Signal(
        str
    )

    download_cancelled = Signal()

    # ========================================================
    # Global
    # ========================================================

    busy_changed = Signal(
        bool
    )

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self._browse_worker: (
            GameBananaBrowseWorker
            | None
        ) = None

        self._fetch_worker: (
            GameBananaFetchWorker
            | None
        ) = None

        self._download_worker: (
            GameBananaDownloadWorker
            | None
        ) = None

        self._current_browse: (
            GameBananaBrowseResult
            | None
        ) = None

        self._current_mod: (
            GameBananaMod
            | None
        ) = None

        self._current_mod_game_id: (
            str
            | None
        ) = None

        self._busy = False

    # ========================================================
    # Zustand
    # ========================================================

    @property
    def is_busy(
        self,
    ) -> bool:
        return self._busy

    @property
    def current_browse(
        self,
    ) -> (
        GameBananaBrowseResult
        | None
    ):
        return (
            self._current_browse
        )

    @property
    def current_mod(
        self,
    ) -> (
        GameBananaMod
        | None
    ):
        return (
            self._current_mod
        )

    @property
    def current_mod_game_id(
        self,
    ) -> str | None:
        return (
            self._current_mod_game_id
        )

    def _set_busy(
        self,
        value: bool,
    ) -> None:
        value = bool(
            value
        )

        if (
            self._busy
            == value
        ):
            return

        self._busy = value

        self.busy_changed.emit(
            value
        )

    # ========================================================
    # Neueste Mods
    # ========================================================

    def browse_latest(
        self,
        *,
        page: int = 1,
    ) -> bool:
        return (
            self._start_browse(
                mode=(
                    GameBananaBrowseWorker
                    .MODE_LATEST
                ),
                page=max(
                    1,
                    int(
                        page
                    ),
                ),
                query="",
            )
        )

    # ========================================================
    # Suche
    # ========================================================

    def search(
        self,
        query: str,
    ) -> bool:
        query = (
            query.strip()
        )

        if len(
            query
        ) < 2:
            return False

        return (
            self._start_browse(
                mode=(
                    GameBananaBrowseWorker
                    .MODE_SEARCH
                ),
                page=1,
                query=query,
            )
        )

    def _start_browse(
        self,
        *,
        mode: str,
        page: int,
        query: str,
    ) -> bool:
        if self.is_busy:
            return False

        game = get_game(
            self.config.selected_game
        )

        game_id = (
            self._stable_game_id(
                game
            )
        )

        worker = (
            GameBananaBrowseWorker(
                game=game,
                mode=mode,
                page=page,
                query=query,
            )
        )

        worker.signals.finished.connect(
            lambda result: (
                self._on_browse_finished(
                    result,
                    game_id,
                )
            )
        )

        worker.signals.failed.connect(
            self._on_browse_failed
        )

        self._browse_worker = (
            worker
        )

        self._set_busy(
            True
        )

        self.browse_started.emit(
            mode
        )

        self.thread_pool.start(
            worker
        )

        return True

    def _on_browse_finished(
        self,
        result: GameBananaBrowseResult,
        game_id: str,
    ) -> None:
        self._browse_worker = None

        self._current_browse = (
            result
        )

        self._set_busy(
            False
        )

        self.browse_loaded.emit(
            result,
            game_id,
        )

    def _on_browse_failed(
        self,
        message: str,
    ) -> None:
        self._browse_worker = None

        self._set_busy(
            False
        )

        self.browse_failed.emit(
            message
        )

    # ========================================================
    # Mod laden
    # ========================================================

    def lookup(
        self,
        reference: str | int,
    ) -> bool:
        if self.is_busy:
            return False

        game = get_game(
            self.config.selected_game
        )

        game_id = (
            self._stable_game_id(
                game
            )
        )

        worker = (
            GameBananaFetchWorker(
                reference=reference,
                expected_game=game,
            )
        )

        worker.signals.finished.connect(
            lambda mod: (
                self._on_lookup_finished(
                    mod,
                    game_id,
                )
            )
        )

        worker.signals.failed.connect(
            self._on_lookup_failed
        )

        self._fetch_worker = (
            worker
        )

        self._set_busy(
            True
        )

        self.lookup_started.emit()

        self.thread_pool.start(
            worker
        )

        return True

    def _on_lookup_finished(
        self,
        mod: GameBananaMod,
        game_id: str,
    ) -> None:
        self._fetch_worker = None

        self._current_mod = (
            mod
        )

        self._current_mod_game_id = (
            game_id
        )

        self._set_busy(
            False
        )

        self.mod_loaded.emit(
            mod,
            game_id,
        )

    def _on_lookup_failed(
        self,
        message: str,
    ) -> None:
        self._fetch_worker = None

        self._set_busy(
            False
        )

        self.lookup_failed.emit(
            message
        )

    # ========================================================
    # Download
    # ========================================================

    def download(
        self,
        file: GameBananaFile,
    ) -> bool:
        if self.is_busy:
            return False

        mod = (
            self._current_mod
        )

        game_id = (
            self._current_mod_game_id
        )

        if (
            mod is None
            or game_id is None
        ):
            return False

        if (
            game_id
            != self.config.selected_game
        ):
            return False

        if (
            file
            not in mod.files
        ):
            return False

        destination_directory = (
            CACHE_DIR
            / "gamebanana"
            / game_id
            / str(
                mod.id
            )
        )

        worker = (
            GameBananaDownloadWorker(
                file=file,
                destination_directory=(
                    destination_directory
                ),
            )
        )

        worker.signals.progress.connect(
            self.download_progress
        )

        worker.signals.finished.connect(
            lambda result: (
                self._on_download_finished(
                    result,
                    game_id,
                )
            )
        )

        worker.signals.failed.connect(
            self._on_download_failed
        )

        worker.signals.cancelled.connect(
            self._on_download_cancelled
        )

        self._download_worker = (
            worker
        )

        self._set_busy(
            True
        )

        self.download_started.emit(
            file
        )

        self.thread_pool.start(
            worker
        )

        return True

    def cancel_download(
        self,
    ) -> bool:
        worker = (
            self._download_worker
        )

        if worker is None:
            return False

        worker.cancel()

        return True

    def _on_download_finished(
        self,
        result,
        game_id: str,
    ) -> None:
        self._download_worker = None

        self._set_busy(
            False
        )

        self.download_finished.emit(
            result,
            game_id,
        )

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self._download_worker = None

        self._set_busy(
            False
        )

        self.download_failed.emit(
            message
        )

    def _on_download_cancelled(
        self,
    ) -> None:
        self._download_worker = None

        self._set_busy(
            False
        )

        self.download_cancelled.emit()

    # ========================================================
    # Reset
    # ========================================================

    def clear(
        self,
    ) -> None:
        if self.is_busy:
            return

        self._current_browse = None

        self._current_mod = None

        self._current_mod_game_id = None

    def shutdown(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            self._download_worker.cancel()

    # ========================================================
    # Game ID
    # ========================================================

    @staticmethod
    def _stable_game_id(
        game,
    ) -> str:
        value = getattr(
            game,
            "game_id",
            None,
        )

        if value:
            return str(
                value
            )

        raw_id = getattr(
            game,
            "id",
            None,
        )

        if hasattr(
            raw_id,
            "value",
        ):
            return str(
                raw_id.value
            )

        return str(
            raw_id
        )


__all__ = [
    "GameBananaController",
]