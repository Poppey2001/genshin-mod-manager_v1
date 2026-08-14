from __future__ import annotations

from PySide6.QtCore import (
    QUrl,
    Signal,
)

from PySide6.QtGui import (
    QDesktopServices,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.controllers.gamebanana_controller import (
    GameBananaController,
)

from app.gamebanana.models import (
    GameBananaBrowseResult,
    GameBananaFile,
    GameBananaMod,
    GameBananaModSummary,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.widgets.gamebanana.mod_details import (
    GameBananaModDetails,
)

from app.widgets.gamebanana.mod_grid import (
    GameBananaModGrid,
)


class GameBananaPage(
    QWidget
):
    install_requested = Signal(
        object,
        str,
        int,
    )

    VIEW_BROWSER = 0
    VIEW_DETAILS = 1

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config

        self.controller = (
            GameBananaController(
                config=self.config,
                parent=self,
            )
        )

        self._current_browse: (
            GameBananaBrowseResult
            | None
        ) = None

        self._current_mod: (
            GameBananaMod
            | None
        ) = None

        self._current_game_id: (
            str
            | None
        ) = None

        self._loaded_game_id: (
            str
            | None
        ) = None

        # ----------------------------------------------------
        # Root
        # ----------------------------------------------------

        self.title_label = QLabel()

        self.subtitle_label = QLabel()

        self.view_stack = (
            QStackedWidget()
        )

        # ----------------------------------------------------
        # Browser
        # ----------------------------------------------------

        self.search_input = (
            QLineEdit()
        )

        self.search_button = (
            QPushButton()
        )

        self.latest_button = (
            QPushButton()
        )

        self.mod_grid = (
            GameBananaModGrid()
        )

        self.previous_button = (
            QPushButton()
        )

        self.page_label = QLabel()

        self.next_button = (
            QPushButton()
        )

        self.reference_input = (
            QLineEdit()
        )

        self.lookup_button = (
            QPushButton()
        )

        self.status_label = QLabel()

        # ----------------------------------------------------
        # Details
        # ----------------------------------------------------

        self.details = (
            GameBananaModDetails()
        )

        self._build_ui()

        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self._refresh_controls()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            28,
            22,
            28,
            22,
        )

        root.setSpacing(
            12
        )

        self.title_label.setObjectName(
            "pageTitle"
        )

        self.subtitle_label.setObjectName(
            "pageDescription"
        )

        root.addWidget(
            self.title_label
        )

        root.addWidget(
            self.subtitle_label
        )

        self.view_stack.addWidget(
            self._create_browser_view()
        )

        self.view_stack.addWidget(
            self.details
        )

        root.addWidget(
            self.view_stack,
            stretch=1,
        )

        self.setStyleSheet(
            """
            QLabel#pageTitle {
                color: #ffffff;
                font-size: 27px;
                font-weight: 800;
            }

            QLabel#pageDescription {
                color: #89919f;
                font-size: 13px;
            }

            QLineEdit {
                min-height: 40px;
                background: #181d25;
                border: 1px solid #303744;
                border-radius: 8px;
                color: #ffffff;
                padding: 0 12px;
            }

            QLineEdit:focus {
                border-color: #7665e8;
            }

            QPushButton {
                min-height: 38px;
                background: #222833;
                border: 1px solid #343b48;
                border-radius: 8px;
                color: #dce0e7;
                padding: 0 14px;
            }

            QPushButton:hover {
                background: #2b323e;
            }

            QPushButton:disabled {
                color: #626b79;
                background: #181c23;
            }
            """
        )

    def _create_browser_view(
        self,
    ) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            0,
            4,
            0,
            0,
        )

        layout.setSpacing(
            12
        )

        # ----------------------------------------------------
        # Search
        # ----------------------------------------------------

        search_row = (
            QHBoxLayout()
        )

        search_row.addWidget(
            self.search_input,
            stretch=1,
        )

        search_row.addWidget(
            self.search_button
        )

        search_row.addWidget(
            self.latest_button
        )

        layout.addLayout(
            search_row
        )

        # ----------------------------------------------------
        # Grid
        # ----------------------------------------------------

        layout.addWidget(
            self.mod_grid,
            stretch=1,
        )

        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        pagination_row = (
            QHBoxLayout()
        )

        pagination_row.addWidget(
            self.previous_button
        )

        pagination_row.addStretch(
            1
        )

        pagination_row.addWidget(
            self.page_label
        )

        pagination_row.addStretch(
            1
        )

        pagination_row.addWidget(
            self.next_button
        )

        layout.addLayout(
            pagination_row
        )

        # ----------------------------------------------------
        # Direct Lookup
        # ----------------------------------------------------

        direct_frame = QFrame()

        direct_frame.setObjectName(
            "gameBananaDirectLookup"
        )

        direct_layout = QHBoxLayout(
            direct_frame
        )

        direct_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        direct_layout.addWidget(
            self.reference_input,
            stretch=1,
        )

        direct_layout.addWidget(
            self.lookup_button
        )

        layout.addWidget(
            direct_frame
        )

        layout.addWidget(
            self.status_label
        )

        return page

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        self.search_button.clicked.connect(
            self._search
        )

        self.search_input.returnPressed.connect(
            self._search
        )

        self.latest_button.clicked.connect(
            self._show_latest
        )

        self.previous_button.clicked.connect(
            self._previous_page
        )

        self.next_button.clicked.connect(
            self._next_page
        )

        self.lookup_button.clicked.connect(
            self._lookup_reference
        )

        self.reference_input.returnPressed.connect(
            self._lookup_reference
        )

        self.mod_grid.mod_clicked.connect(
            self._open_mod_summary
        )

        # ----------------------------------------------------
        # Details
        # ----------------------------------------------------

        self.details.back_requested.connect(
            self._show_browser
        )

        self.details.open_requested.connect(
            self._open_profile
        )

        self.details.install_requested.connect(
            self._download_file
        )

        self.details.cancel_requested.connect(
            self._cancel_download
        )

        # ----------------------------------------------------
        # Browse Controller
        # ----------------------------------------------------

        self.controller.browse_started.connect(
            self._on_browse_started
        )

        self.controller.browse_loaded.connect(
            self._on_browse_loaded
        )

        self.controller.browse_failed.connect(
            self._on_browse_failed
        )

        # ----------------------------------------------------
        # Lookup Controller
        # ----------------------------------------------------

        self.controller.lookup_started.connect(
            self._on_lookup_started
        )

        self.controller.mod_loaded.connect(
            self._on_mod_loaded
        )

        self.controller.lookup_failed.connect(
            self._on_lookup_failed
        )

        # ----------------------------------------------------
        # Download Controller
        # ----------------------------------------------------

        self.controller.download_started.connect(
            self._on_download_started
        )

        self.controller.download_progress.connect(
            self._on_download_progress
        )

        self.controller.download_finished.connect(
            self._on_download_finished
        )

        self.controller.download_failed.connect(
            self._on_download_failed
        )

        self.controller.download_cancelled.connect(
            self._on_download_cancelled
        )

        self.controller.busy_changed.connect(
            self._on_busy_changed
        )

    # ========================================================
    # Show
    # ========================================================

    def showEvent(
        self,
        event,
    ) -> None:
        super().showEvent(
            event
        )

        if self.controller.is_busy:
            return

        if (
            self._loaded_game_id
            != self.config.selected_game
        ):
            self._load_latest(
                page=1
            )

    # ========================================================
    # Game
    # ========================================================

    def can_change_game(
        self,
    ) -> bool:
        return not (
            self.controller.is_busy
        )

    def on_game_changed(
        self,
        _game_id: str,
    ) -> None:
        if self.controller.is_busy:
            return

        self.controller.clear()

        self._current_browse = None

        self._current_mod = None

        self._current_game_id = None

        self._loaded_game_id = None

        self.mod_grid.clear()

        self.details.clear_mod()

        self.search_input.clear()

        self.reference_input.clear()

        self.status_label.clear()

        self._show_browser()

        self._update_game_subtitle()

        self._refresh_controls()

        if self.isVisible():
            self._load_latest(
                page=1
            )

    # ========================================================
    # Latest
    # ========================================================

    def _show_latest(
        self,
    ) -> None:
        self.search_input.clear()

        self._load_latest(
            page=1
        )

    def _load_latest(
        self,
        *,
        page: int,
    ) -> None:
        started = (
            self.controller
            .browse_latest(
                page=page
            )
        )

        if not started:
            self._show_busy_message()

    # ========================================================
    # Search
    # ========================================================

    def _search(
        self,
    ) -> None:
        query = (
            self.search_input
            .text()
            .strip()
        )

        if len(
            query
        ) < 2:
            QMessageBox.information(
                self,
                "GameBanana",
                (
                    "Gib mindestens zwei "
                    "Zeichen für die Suche ein."
                ),
            )

            return

        if not self.controller.search(
            query
        ):
            self._show_busy_message()

    # ========================================================
    # Pagination
    # ========================================================

    def _previous_page(
        self,
    ) -> None:
        result = (
            self._current_browse
        )

        if (
            result is None
            or result.is_search
            or not result.has_previous
        ):
            return

        self._load_latest(
            page=max(
                1,
                result.page - 1,
            )
        )

    def _next_page(
        self,
    ) -> None:
        result = (
            self._current_browse
        )

        if (
            result is None
            or result.is_search
            or not result.has_next
        ):
            return

        self._load_latest(
            page=result.page + 1
        )

    # ========================================================
    # Browse
    # ========================================================

    def _on_browse_started(
        self,
        mode: str,
    ) -> None:
        if mode == "search":
            self.status_label.setText(
                "GameBanana wird durchsucht …"
            )
        else:
            self.status_label.setText(
                "Neueste Mods werden geladen …"
            )

    def _on_browse_loaded(
        self,
        result: GameBananaBrowseResult,
        game_id: str,
    ) -> None:
        self._current_browse = (
            result
        )

        self._loaded_game_id = (
            game_id
        )

        self.mod_grid.set_mods(
            result.items
        )

        if result.is_search:
            self.status_label.setText(
                (
                    f"{len(result.items)} "
                    "passende Mods gefunden."
                )
            )
        else:
            self.status_label.setText(
                (
                    f"{len(result.items)} "
                    "Mods geladen."
                )
            )

        self._refresh_controls()

    def _on_browse_failed(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            (
                "Die GameBanana-Liste "
                "konnte nicht geladen werden."
            )
        )

        QMessageBox.warning(
            self,
            "GameBanana",
            message,
        )

    # ========================================================
    # Card
    # ========================================================

    def _open_mod_summary(
        self,
        summary: GameBananaModSummary,
    ) -> None:
        if not self.controller.lookup(
            summary.id
        ):
            self._show_busy_message()

    # ========================================================
    # Direct Lookup
    # ========================================================

    def _lookup_reference(
        self,
    ) -> None:
        reference = (
            self.reference_input
            .text()
            .strip()
        )

        if not reference:
            return

        if not self.controller.lookup(
            reference
        ):
            self._show_busy_message()

    # ========================================================
    # Details
    # ========================================================

    def _on_lookup_started(
        self,
    ) -> None:
        self.status_label.setText(
            "Mod-Details werden geladen …"
        )

    def _on_mod_loaded(
        self,
        mod: GameBananaMod,
        game_id: str,
    ) -> None:
        self._current_mod = mod

        self._current_game_id = (
            game_id
        )

        self.details.set_mod(
            mod
        )

        self.view_stack.setCurrentIndex(
            self.VIEW_DETAILS
        )

    def _on_lookup_failed(
        self,
        message: str,
    ) -> None:
        QMessageBox.warning(
            self,
            "GameBanana",
            message,
        )

    def _show_browser(
        self,
    ) -> None:
        if self.controller.is_busy:
            return

        self.view_stack.setCurrentIndex(
            self.VIEW_BROWSER
        )

    # ========================================================
    # Open GameBanana
    # ========================================================

    def _open_profile(
        self,
    ) -> None:
        mod = (
            self._current_mod
        )

        if (
            mod is None
            or not mod.profile_url
        ):
            return

        QDesktopServices.openUrl(
            QUrl(
                mod.profile_url
            )
        )

    # ========================================================
    # Download
    # ========================================================

    def _download_file(
        self,
        file: GameBananaFile,
    ) -> None:
        """
        Startet den Download einer Datei aus
        der aktuell geöffneten GameBanana-Mod.
        """

        started = (
            self.controller.download(
                file
            )
        )

        if started:
            return

        QMessageBox.warning(
            self,
            tr(
                "gamebanana.error.download.title"
            ),
            tr(
                "gamebanana.error.download.start"
            ),
        )

    def _on_download_started(
        self,
        file: GameBananaFile,
    ) -> None:
        """
        Der Fortschritt gehört im neuen UI
        zur Detailansicht und nicht mehr
        direkt zur GameBananaPage.
        """

        self.details.start_download(
            file
        )

    def _on_download_progress(
        self,
        current,
        total,
    ) -> None:
        self.details.update_download(
            int(
                current
            ),
            int(
                total
            ),
        )

    def _on_download_finished(
        self,
        result,
        game_id: str,
        mod_id: int,
    ) -> None:
        """
        Download abgeschlossen.

        Wichtig:
        mod_id wird jetzt explizit bis zum
        Library-Import weitergereicht.
        """

        self.details.finish_download()

        self.install_requested.emit(
            result.path,
            game_id,
            mod_id,
        )

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self.details.fail_download(
            message
        )

        QMessageBox.critical(
            self,
            tr(
                "gamebanana.error.download.title"
            ),
            message,
        )

    def _on_download_cancelled(
        self,
    ) -> None:
        self.details.fail_download(
            tr(
                "gamebanana.status.cancelled"
            )
        )

    def _cancel_download(
        self,
    ) -> None:
        if not (
            self.controller
            .cancel_download()
        ):
            return

        self.details.fail_download(
            tr(
                "gamebanana.status.cancelling"
            )
        )

    # ========================================================
    # Busy
    # ========================================================

    def _on_busy_changed(
        self,
        busy: bool,
    ) -> None:
        self.search_input.setEnabled(
            not busy
        )

        self.search_button.setEnabled(
            not busy
        )

        self.latest_button.setEnabled(
            not busy
        )

        self.reference_input.setEnabled(
            not busy
        )

        self.lookup_button.setEnabled(
            not busy
        )

        self.mod_grid.setEnabled(
            not busy
        )

        self.details.set_busy(
            busy
        )

        self._refresh_controls()

    def _refresh_controls(
        self,
    ) -> None:
        busy = (
            self.controller.is_busy
        )

        result = (
            self._current_browse
        )

        self.previous_button.setEnabled(
            (
                not busy
                and result is not None
                and not result.is_search
                and result.has_previous
            )
        )

        self.next_button.setEnabled(
            (
                not busy
                and result is not None
                and not result.is_search
                and result.has_next
            )
        )

        if (
            result is not None
            and result.is_search
        ):
            self.page_label.setText(
                "Suchergebnis"
            )

        else:
            page = (
                result.page
                if result is not None
                else 1
            )

            self.page_label.setText(
                f"Seite {page}"
            )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "gamebanana.title"
            )
        )

        self.search_input.setPlaceholderText(
            tr(
                "gamebanana.search.placeholder"
            )
        )

        self.search_button.setText(
            tr(
                "gamebanana.search.button"
            )
        )

        self.latest_button.setText(
            tr(
                "gamebanana.latest"
            )
        )

        self.previous_button.setText(
            tr(
                "gamebanana.previous"
            )
        )

        self.next_button.setText(
            tr(
                "gamebanana.next"
            )
        )

        self.reference_input.setPlaceholderText(
            tr(
                "gamebanana.reference.placeholder"
            )
        )

        self.lookup_button.setText(
            tr(
                "gamebanana.lookup"
            )
        )

        self._update_game_subtitle()

    def _update_game_subtitle(
        self,
    ) -> None:
        game = (
            self.config.current_game
        )

        self.subtitle_label.setText(
            (
                f"{game.name} • "
                f"{game.importer}"
            )
        )

    # ========================================================
    # Busy message
    # ========================================================

    def _show_busy_message(
        self,
    ) -> None:
        QMessageBox.information(
            self,
            tr(
                "gamebanana.busy.title"
            ),
            tr(
                "gamebanana.busy.message"
            ),
        )

    # ========================================================
    # Shutdown
    # ========================================================

    def shutdown(
        self,
    ) -> None:
        self.controller.shutdown()