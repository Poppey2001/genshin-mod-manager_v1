from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QUrl,
    Signal,
)

from PySide6.QtGui import (
    QDesktopServices,
    QTextDocumentFragment,
)

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
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


SUMMARY_ROLE = (
    int(
        Qt.ItemDataRole.UserRole
    )
    + 40
)


class GameBananaPage(
    QWidget
):
    """
    Browser, Detailansicht und Download
    für GameBanana.

    Nach dem Download wird die Datei weiterhin
    über install_requested an den bestehenden
    Library-Import übergeben.
    """

    install_requested = Signal(
        object,
        str,
    )

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

        self._create_widgets()

        self._build_ui()

        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self._clear_details()

        self._refresh_controls()

    # ========================================================
    # Widgets
    # ========================================================

    def _create_widgets(
        self,
    ) -> None:
        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self.title_label = QLabel()

        self.game_label = QLabel()

        # --------------------------------------------------
        # Browser
        # --------------------------------------------------

        self.browse_title_label = QLabel()

        self.search_input = (
            QLineEdit()
        )

        self.search_button = (
            QPushButton()
        )

        self.latest_button = (
            QPushButton()
        )

        self.search_hint_label = QLabel()

        self.results_list = (
            QListWidget()
        )

        self.previous_button = (
            QPushButton()
        )

        self.page_label = QLabel()

        self.next_button = (
            QPushButton()
        )

        # --------------------------------------------------
        # Direkte Mod-ID / URL
        # --------------------------------------------------

        self.direct_title_label = QLabel()

        self.reference_input = (
            QLineEdit()
        )

        self.lookup_button = (
            QPushButton()
        )

        # --------------------------------------------------
        # Detailansicht
        # --------------------------------------------------

        self.details_frame = QFrame()

        self.details_title_label = QLabel()

        self.mod_name_label = QLabel()

        self.mod_id_label = QLabel()

        self.author_label = QLabel()

        self.source_game_label = QLabel()

        self.category_label = QLabel()

        self.stats_label = QLabel()

        self.description_view = (
            QTextBrowser()
        )

        self.description_view.setOpenExternalLinks(
            False
        )

        # --------------------------------------------------
        # Dateien
        # --------------------------------------------------

        self.file_label = QLabel()

        self.file_combobox = (
            QComboBox()
        )

        # --------------------------------------------------
        # Aktionen
        # --------------------------------------------------

        self.profile_button = (
            QPushButton()
        )

        self.install_button = (
            QPushButton()
        )

        self.cancel_button = (
            QPushButton()
        )

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        self.progress_bar = (
            QProgressBar()
        )

        self.status_label = QLabel()

        self.progress_bar.setVisible(
            False
        )

        self.cancel_button.setVisible(
            False
        )

    # ========================================================
    # Hauptlayout
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        main_layout = (
            QVBoxLayout(
                self
            )
        )

        main_layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        main_layout.setSpacing(
            14
        )

        self.title_label.setObjectName(
            "pageTitle"
        )

        self.game_label.setObjectName(
            "pageSubtitle"
        )

        main_layout.addWidget(
            self.title_label
        )

        main_layout.addWidget(
            self.game_label
        )

        # --------------------------------------------------
        # Split View
        # --------------------------------------------------

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.setChildrenCollapsible(
            False
        )

        splitter.addWidget(
            self._build_browser_panel()
        )

        splitter.addWidget(
            self._build_details_panel()
        )

        splitter.setStretchFactor(
            0,
            2,
        )

        splitter.setStretchFactor(
            1,
            3,
        )

        splitter.setSizes(
            [
                480,
                760,
            ]
        )

        main_layout.addWidget(
            splitter,
            stretch=1,
        )

        main_layout.addWidget(
            self.progress_bar
        )

        main_layout.addWidget(
            self.status_label
        )

    # ========================================================
    # Linkes Browser-Panel
    # ========================================================

    def _build_browser_panel(
        self,
    ) -> QWidget:
        panel = QFrame()

        panel.setObjectName(
            "gameBananaBrowserPanel"
        )

        layout = QVBoxLayout(
            panel
        )

        layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        layout.setSpacing(
            10
        )

        self.browse_title_label.setObjectName(
            "gameBananaSectionTitle"
        )

        layout.addWidget(
            self.browse_title_label
        )

        # --------------------------------------------------
        # Suche
        # --------------------------------------------------

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

        self.search_hint_label.setWordWrap(
            True
        )

        self.search_hint_label.setObjectName(
            "pageSubtitle"
        )

        layout.addWidget(
            self.search_hint_label
        )

        # --------------------------------------------------
        # Ergebnisliste
        # --------------------------------------------------

        layout.addWidget(
            self.results_list,
            stretch=1,
        )

        # --------------------------------------------------
        # Pagination
        # --------------------------------------------------

        paging_row = (
            QHBoxLayout()
        )

        paging_row.addWidget(
            self.previous_button
        )

        paging_row.addStretch(
            1
        )

        paging_row.addWidget(
            self.page_label
        )

        paging_row.addStretch(
            1
        )

        paging_row.addWidget(
            self.next_button
        )

        layout.addLayout(
            paging_row
        )

        # --------------------------------------------------
        # Direkter Lookup
        # --------------------------------------------------

        self.direct_title_label.setObjectName(
            "gameBananaSectionTitle"
        )

        layout.addWidget(
            self.direct_title_label
        )

        direct_row = (
            QHBoxLayout()
        )

        direct_row.addWidget(
            self.reference_input,
            stretch=1,
        )

        direct_row.addWidget(
            self.lookup_button
        )

        layout.addLayout(
            direct_row
        )

        return panel

    # ========================================================
    # Rechtes Detail-Panel
    # ========================================================

    def _build_details_panel(
        self,
    ) -> QWidget:
        panel = QFrame()

        panel.setObjectName(
            "gameBananaDetailsPanel"
        )

        outer_layout = (
            QVBoxLayout(
                panel
            )
        )

        outer_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.details_frame.setObjectName(
            "gameBananaModCard"
        )

        layout = QVBoxLayout(
            self.details_frame
        )

        layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        layout.setSpacing(
            8
        )

        self.details_title_label.setObjectName(
            "gameBananaSectionTitle"
        )

        self.mod_name_label.setObjectName(
            "gameBananaModTitle"
        )

        for label in (
            self.mod_name_label,
            self.mod_id_label,
            self.author_label,
            self.source_game_label,
            self.category_label,
            self.stats_label,
        ):
            label.setWordWrap(
                True
            )

        layout.addWidget(
            self.details_title_label
        )

        layout.addWidget(
            self.mod_name_label
        )

        layout.addWidget(
            self.mod_id_label
        )

        layout.addWidget(
            self.author_label
        )

        layout.addWidget(
            self.source_game_label
        )

        layout.addWidget(
            self.category_label
        )

        layout.addWidget(
            self.stats_label
        )

        self.description_view.setMinimumHeight(
            180
        )

        layout.addWidget(
            self.description_view,
            stretch=1,
        )

        layout.addWidget(
            self.file_label
        )

        layout.addWidget(
            self.file_combobox
        )

        action_row = (
            QHBoxLayout()
        )

        action_row.addWidget(
            self.profile_button
        )

        action_row.addStretch(
            1
        )

        action_row.addWidget(
            self.install_button
        )

        action_row.addWidget(
            self.cancel_button
        )

        layout.addLayout(
            action_row
        )

        outer_layout.addWidget(
            self.details_frame,
            stretch=1,
        )

        return panel

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        # Browser
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

        self.results_list.itemClicked.connect(
            self._on_result_clicked
        )

        # Direkter Lookup
        self.lookup_button.clicked.connect(
            self._lookup_reference
        )

        self.reference_input.returnPressed.connect(
            self._lookup_reference
        )

        # Details
        self.profile_button.clicked.connect(
            self._open_profile
        )

        self.install_button.clicked.connect(
            self._download_and_install
        )

        self.cancel_button.clicked.connect(
            self._cancel_download
        )

        self.file_combobox.currentIndexChanged.connect(
            self._refresh_controls
        )

        # Controller: Browse
        self.controller.browse_started.connect(
            self._on_browse_started
        )

        self.controller.browse_loaded.connect(
            self._on_browse_loaded
        )

        self.controller.browse_failed.connect(
            self._on_browse_failed
        )

        # Controller: Detail
        self.controller.lookup_started.connect(
            self._on_lookup_started
        )

        self.controller.mod_loaded.connect(
            self._on_mod_loaded
        )

        self.controller.lookup_failed.connect(
            self._on_lookup_failed
        )

        # Controller: Download
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
    # Seite sichtbar
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

        # Nur automatisch laden, wenn für das
        # aktive Spiel noch keine Liste vorhanden ist.
        if (
            self._loaded_game_id
            != self.config.selected_game
        ):
            self._load_latest(
                page=1
            )

    # ========================================================
    # Spielwechsel
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

        self.results_list.clear()

        self.search_input.clear()

        self.reference_input.clear()

        self._clear_details()

        self.progress_bar.setVisible(
            False
        )

        self.status_label.clear()

        self._update_game_label()

        self._refresh_controls()

        if self.isVisible():
            self._load_latest(
                page=1
            )

    # ========================================================
    # Latest
    # ========================================================

    def _load_latest(
        self,
        *,
        page: int,
    ) -> None:
        started = (
            self.controller.browse_latest(
                page=page
            )
        )

        if not started:
            self._show_busy_message()

    def _show_latest(
        self,
    ) -> None:
        self.search_input.clear()

        self._load_latest(
            page=1
        )

    # ========================================================
    # Suche
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
                tr(
                    "gamebanana.search.short.title"
                ),
                tr(
                    "gamebanana.search.short.message"
                ),
            )

            return

        started = (
            self.controller.search(
                query
            )
        )

        if not started:
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
    # Browse Events
    # ========================================================

    def _on_browse_started(
        self,
        mode: str,
    ) -> None:
        if (
            mode
            == "search"
        ):
            self.status_label.setText(
                tr(
                    "gamebanana.status.searching"
                )
            )

        else:
            self.status_label.setText(
                tr(
                    "gamebanana.status.loading_latest"
                )
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

        self.results_list.clear()

        for summary in result.items:
            item = QListWidgetItem(
                self._summary_display_text(
                    summary
                )
            )

            item.setData(
                SUMMARY_ROLE,
                summary,
            )

            if summary.profile_url:
                item.setToolTip(
                    summary.profile_url
                )

            self.results_list.addItem(
                item
            )

        if result.is_search:
            if result.items:
                self.status_label.setText(
                    tr(
                        "gamebanana.status.search_results",
                        count=len(
                            result.items
                        ),
                    )
                )

            else:
                self.status_label.setText(
                    tr(
                        "gamebanana.status.search_empty"
                    )
                )

        else:
            if result.items:
                self.status_label.setText(
                    tr(
                        "gamebanana.status.latest_results",
                        count=len(
                            result.items
                        ),
                    )
                )

            else:
                self.status_label.setText(
                    tr(
                        "gamebanana.status.latest_empty"
                    )
                )

        self._refresh_controls()

    def _on_browse_failed(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            tr(
                "gamebanana.status.browse_failed"
            )
        )

        QMessageBox.warning(
            self,
            tr(
                "gamebanana.error.browse.title"
            ),
            message,
        )

        self._refresh_controls()

    # ========================================================
    # Ergebnis anklicken
    # ========================================================

    def _on_result_clicked(
        self,
        item: QListWidgetItem,
    ) -> None:
        summary = (
            item.data(
                SUMMARY_ROLE
            )
        )

        if not isinstance(
            summary,
            GameBananaModSummary,
        ):
            return

        self._begin_lookup(
            summary.id
        )

    # ========================================================
    # Direkter Lookup
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

        self._begin_lookup(
            reference
        )

    def _begin_lookup(
        self,
        reference: str | int,
    ) -> None:
        started = (
            self.controller.lookup(
                reference
            )
        )

        if not started:
            self._show_busy_message()

    def _on_lookup_started(
        self,
    ) -> None:
        self.status_label.setText(
            tr(
                "gamebanana.status.loading"
            )
        )

    # ========================================================
    # Mod geladen
    # ========================================================

    def _on_mod_loaded(
        self,
        mod: GameBananaMod,
        game_id: str,
    ) -> None:
        self._current_mod = (
            mod
        )

        self._current_game_id = (
            game_id
        )

        self._loaded_game_id = (
            game_id
        )

        unknown = tr(
            "gamebanana.value.unknown"
        )

        self.mod_name_label.setText(
            mod.name
        )

        self.mod_id_label.setText(
            tr(
                "gamebanana.mod.id",
                id=mod.id,
            )
        )

        self.author_label.setText(
            tr(
                "gamebanana.mod.author",
                author=(
                    mod.author
                    or unknown
                ),
            )
        )

        self.source_game_label.setText(
            tr(
                "gamebanana.mod.game",
                game=(
                    mod.game_name
                    or unknown
                ),
            )
        )

        self.category_label.setText(
            tr(
                "gamebanana.mod.category",
                category=(
                    mod.category
                    or unknown
                ),
            )
        )

        self.stats_label.setText(
            tr(
                "gamebanana.mod.stats",
                downloads=(
                    self._format_count(
                        mod.downloads
                    )
                ),
                likes=(
                    self._format_count(
                        mod.likes
                    )
                ),
                views=(
                    self._format_count(
                        mod.views
                    )
                ),
            )
        )

        description = (
            mod.description
            or tr(
                "gamebanana.mod.no_description"
            )
        )

        plain_description = (
            QTextDocumentFragment
            .fromHtml(
                description
            )
            .toPlainText()
        )

        self.description_view.setPlainText(
            plain_description
        )

        # --------------------------------------------------
        # Dateien
        # --------------------------------------------------

        self.file_combobox.clear()

        for file in mod.files:
            self.file_combobox.addItem(
                self._file_display_name(
                    file
                ),
                userData=file,
            )

        default_file = (
            mod.default_file()
        )

        if default_file is not None:
            for index in range(
                self.file_combobox.count()
            ):
                if (
                    self.file_combobox.itemData(
                        index
                    )
                    == default_file
                ):
                    self.file_combobox.setCurrentIndex(
                        index
                    )

                    break

        self.details_frame.setVisible(
            True
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.loaded",
                count=len(
                    mod.files
                ),
            )
        )

        self._refresh_controls()

    def _on_lookup_failed(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            tr(
                "gamebanana.status.lookup_failed"
            )
        )

        QMessageBox.warning(
            self,
            tr(
                "gamebanana.error.lookup.title"
            ),
            message,
        )

        self._refresh_controls()

    def _clear_details(
        self,
    ) -> None:
        self._current_mod = None

        self._current_game_id = None

        self.mod_name_label.clear()

        self.mod_id_label.clear()

        self.author_label.clear()

        self.source_game_label.clear()

        self.category_label.clear()

        self.stats_label.clear()

        self.description_view.clear()

        self.file_combobox.clear()

        self.details_frame.setVisible(
            False
        )

    # ========================================================
    # Datei
    # ========================================================

    def _selected_file(
        self,
    ) -> GameBananaFile | None:
        value = (
            self.file_combobox
            .currentData()
        )

        if isinstance(
            value,
            GameBananaFile,
        ):
            return value

        return None

    # ========================================================
    # Download
    # ========================================================

    def _download_and_install(
        self,
    ) -> None:
        file = (
            self._selected_file()
        )

        if file is None:
            return

        started = (
            self.controller.download(
                file
            )
        )

        if not started:
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
        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(
            0
        )

        self.cancel_button.setVisible(
            True
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.downloading",
                file=file.name,
            )
        )

    def _on_download_progress(
        self,
        current,
        total,
    ) -> None:
        current_bytes = int(
            current
        )

        total_bytes = int(
            total
        )

        if total_bytes <= 0:
            self.progress_bar.setRange(
                0,
                0,
            )

            self.status_label.setText(
                tr(
                    "gamebanana.status.download_bytes",
                    current=(
                        self._format_bytes(
                            current_bytes
                        )
                    ),
                )
            )

            return

        self.progress_bar.setRange(
            0,
            100,
        )

        percentage = int(
            min(
                100,
                (
                    current_bytes
                    * 100
                    / total_bytes
                ),
            )
        )

        self.progress_bar.setValue(
            percentage
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.download_progress",
                current=(
                    self._format_bytes(
                        current_bytes
                    )
                ),
                total=(
                    self._format_bytes(
                        total_bytes
                    )
                ),
            )
        )

    def _on_download_finished(
        self,
        result,
        game_id: str,
    ) -> None:
        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(
            100
        )

        self.cancel_button.setVisible(
            False
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.download_finished"
            )
        )

        # Wichtig:
        # MainWindow reicht diesen Pfad an
        # LibraryPage weiter.
        self.install_requested.emit(
            result.path,
            game_id,
        )

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self.progress_bar.setVisible(
            False
        )

        self.cancel_button.setVisible(
            False
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.download_failed"
            )
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
        self.progress_bar.setVisible(
            False
        )

        self.cancel_button.setVisible(
            False
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.cancelled"
            )
        )

    def _cancel_download(
        self,
    ) -> None:
        if (
            self.controller
            .cancel_download()
        ):
            self.status_label.setText(
                tr(
                    "gamebanana.status.cancelling"
                )
            )

    # ========================================================
    # GameBanana-Seite öffnen
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
    # UI State
    # ========================================================

    def _on_busy_changed(
        self,
        _busy: bool,
    ) -> None:
        self._refresh_controls()

    def _refresh_controls(
        self,
        *_args,
    ) -> None:
        busy = (
            self.controller.is_busy
        )

        for widget in (
            self.search_input,
            self.search_button,
            self.latest_button,
            self.results_list,
            self.reference_input,
            self.lookup_button,
            self.file_combobox,
        ):
            widget.setEnabled(
                not busy
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

        self.install_button.setEnabled(
            (
                not busy
                and self._current_mod
                is not None
                and self._selected_file()
                is not None
            )
        )

        self.profile_button.setEnabled(
            (
                not busy
                and self._current_mod
                is not None
                and bool(
                    self._current_mod
                    .profile_url
                )
            )
        )

        self._update_page_label()

    # ========================================================
    # Pagination Label
    # ========================================================

    def _update_page_label(
        self,
    ) -> None:
        result = (
            self._current_browse
        )

        if (
            result is not None
            and result.is_search
        ):
            self.page_label.setText(
                tr(
                    "gamebanana.browse.search_mode"
                )
            )

            return

        page = (
            result.page
            if result is not None
            else 1
        )

        self.page_label.setText(
            tr(
                "gamebanana.browse.page",
                page=page,
            )
        )

    # ========================================================
    # Aktuelles Spiel
    # ========================================================

    def _update_game_label(
        self,
    ) -> None:
        game = (
            self.config.current_game
        )

        self.game_label.setText(
            tr(
                "gamebanana.current_game",
                game=game.name,
                importer=game.importer,
            )
        )

    # ========================================================
    # Übersetzung
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

        self.browse_title_label.setText(
            tr(
                "gamebanana.browse.title"
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

        self.search_hint_label.setText(
            tr(
                "gamebanana.search.hint"
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

        self.direct_title_label.setText(
            tr(
                "gamebanana.direct.title"
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

        self.details_title_label.setText(
            tr(
                "gamebanana.details.title"
            )
        )

        self.file_label.setText(
            tr(
                "gamebanana.files"
            )
        )

        self.profile_button.setText(
            tr(
                "gamebanana.open_page"
            )
        )

        self.install_button.setText(
            tr(
                "gamebanana.download_install"
            )
        )

        self.cancel_button.setText(
            tr(
                "common.cancel"
            )
        )

        self._update_game_label()

        self._update_page_label()

        self._refresh_detail_translation()

    def _refresh_detail_translation(
        self,
    ) -> None:
        mod = (
            self._current_mod
        )

        if mod is None:
            return

        unknown = tr(
            "gamebanana.value.unknown"
        )

        self.mod_id_label.setText(
            tr(
                "gamebanana.mod.id",
                id=mod.id,
            )
        )

        self.author_label.setText(
            tr(
                "gamebanana.mod.author",
                author=(
                    mod.author
                    or unknown
                ),
            )
        )

        self.source_game_label.setText(
            tr(
                "gamebanana.mod.game",
                game=(
                    mod.game_name
                    or unknown
                ),
            )
        )

        self.category_label.setText(
            tr(
                "gamebanana.mod.category",
                category=(
                    mod.category
                    or unknown
                ),
            )
        )

        self.stats_label.setText(
            tr(
                "gamebanana.mod.stats",
                downloads=(
                    self._format_count(
                        mod.downloads
                    )
                ),
                likes=(
                    self._format_count(
                        mod.likes
                    )
                ),
                views=(
                    self._format_count(
                        mod.views
                    )
                ),
            )
        )

    # ========================================================
    # Busy Dialog
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
    # Result Display
    # ========================================================

    def _summary_display_text(
        self,
        summary: GameBananaModSummary,
    ) -> str:
        secondary: list[str] = []

        if summary.author:
            secondary.append(
                summary.author
            )

        if summary.category:
            secondary.append(
                summary.category
            )

        secondary.append(
            f"#{summary.id}"
        )

        return (
            f"{summary.name}\n"
            + " · ".join(
                secondary
            )
        )

    # ========================================================
    # File Display
    # ========================================================

    @staticmethod
    def _file_display_name(
        file: GameBananaFile,
    ) -> str:
        if file.size is None:
            return file.name

        megabytes = (
            file.size
            / 1024
            / 1024
        )

        return (
            f"{file.name} "
            f"({megabytes:.1f} MB)"
        )

    # ========================================================
    # Count Format
    # ========================================================

    @staticmethod
    def _format_count(
        value: int | None,
    ) -> str:
        if value is None:
            return "-"

        return (
            f"{value:,}"
            .replace(
                ",",
                ".",
            )
        )

    # ========================================================
    # Byte Format
    # ========================================================

    @staticmethod
    def _format_bytes(
        value: int,
    ) -> str:
        value = max(
            0,
            value,
        )

        if value < 1024:
            return f"{value} B"

        if (
            value
            < 1024
            * 1024
        ):
            return (
                f"{value / 1024:.1f} KB"
            )

        if (
            value
            < 1024
            * 1024
            * 1024
        ):
            return (
                f"{value / 1024 / 1024:.1f} MB"
            )

        return (
            f"{value / 1024 / 1024 / 1024:.2f} GB"
        )

    # ========================================================
    # Shutdown
    # ========================================================

    def shutdown(
        self,
    ) -> None:
        self.controller.shutdown()