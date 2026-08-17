from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLocale, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QTextDocumentFragment
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.controllers.gamebanana_controller import GameBananaController
from app.gamebanana import GameBananaFile, GameBananaMod
from app.gamebanana.browser import GAMEBANANA_GAME_IDS, GameBananaBrowseResult
from app.i18n import tr, translation_manager
from app.widgets.gamebanana import (
    GameBananaPreviewGallery,
    GameBananaResultCard,
)

from app.widgets.common.state_panel import (
    StatePanel,
)
from app.workers.gamebanana_browse_worker import GameBananaBrowseWorker


class GameBananaPage(QWidget):
    """
    Moderne GameBanana-Seite mit Browser, Suchleiste,
    Direkt-Lookup, Detailansicht und Download/Import.
    """

    # MainWindow unterstützt die neue Signatur:
    # path, game_id, mod_id
    install_requested = Signal(object, str, int)

    # Unterhalb dieses Wertes werden Browser und Details
    # vertikal angeordnet. So funktionieren auch längere
    # Übersetzungen auf kleineren Fenstern sauber.
    RESPONSIVE_BREAKPOINT = 1180

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("gameBananaPage")

        self.config = config
        self.controller = GameBananaController(config=self.config, parent=self)

        self._current_mod: GameBananaMod | None = None
        self._current_game_id: str | None = None
        self._browse_worker: GameBananaBrowseWorker | None = None
        self._browse_page = 1
        self._browse_query = ""
        self._browse_loaded_once = False
        self._result_cards: list[GameBananaResultCard] = []
        self._last_browse_has_next = False

        # Dynamische Statusmeldungen werden als Translation-Key
        # gespeichert, damit ein Sprachwechsel auch bereits
        # sichtbare Zustände aktualisieren kann.
        self._status_key: str | None = None
        self._status_params: dict[str, object] = {}

        # Header
        self.title_label = QLabel(self)
        self.subtitle_label = QLabel(self)
        self.game_badge = QLabel(self)

        # Browser
        self.browse_title_label = QLabel(self)
        self.search_input = QLineEdit(self)
        self.search_button = QPushButton(self)
        self.latest_button = QPushButton(self)
        self.search_hint_label = QLabel(self)
        self.browse_status_label = QLabel(self)
        self.previous_button = QPushButton(self)
        self.next_button = QPushButton(self)
        self.results_scroll = QScrollArea(self)
        self.results_content = QWidget()
        self.results_layout = QVBoxLayout(self.results_content)

        # Gemeinsamer Browser-State:
        # Loading / Empty / Error
        self.browse_state_panel = StatePanel(self)

        self._browse_state_mode = "idle"
        self._browse_state_message = ""

        # Direct lookup
        self.direct_title_label = QLabel(self)
        self.reference_input = QLineEdit(self)
        self.lookup_button = QPushButton(self)

        # Details
        self.details_title_label = QLabel(self)

        # Gemeinsamer Details-State:
        # Empty / Loading / Error
        self.details_state_panel = StatePanel(self)

        self._details_state_mode = "empty"
        self._details_state_message = ""
        self._last_lookup_reference = None

        self.mod_frame = QFrame(self)
        self.mod_name_label = QLabel(self.mod_frame)
        self.mod_id_label = QLabel(self.mod_frame)
        self.author_label = QLabel(self.mod_frame)
        self.source_game_label = QLabel(self.mod_frame)
        self.preview_gallery = GameBananaPreviewGallery(
            parent=self.mod_frame
        )
        self.description_view = QTextBrowser(self.mod_frame)
        self.file_label = QLabel(self.mod_frame)
        self.file_combobox = QComboBox(self.mod_frame)
        self.profile_button = QPushButton(self.mod_frame)
        self.install_button = QPushButton(self.mod_frame)

        # Operation status
        self.operation_frame = QFrame(self)
        self.progress_bar = QProgressBar(self.operation_frame)
        self.status_label = QLabel(self.operation_frame)
        self.cancel_button = QPushButton(self.operation_frame)

        self._build_ui()
        self._connect_signals()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()
        self._sync_busy_state()
        self._update_responsive_layout()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 16)
        main_layout.setSpacing(14)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(16)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)

        self.title_label.setObjectName("pageTitle")
        self.subtitle_label.setObjectName("pageDescription")
        self.subtitle_label.setWordWrap(True)

        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header.addLayout(header_text, stretch=1)

        self.game_badge.setObjectName("gameBananaGameBadge")
        self.game_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_badge.setMinimumHeight(38)
        self.game_badge.setWordWrap(True)
        self.game_badge.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Preferred,
        )
        header.addWidget(self.game_badge, alignment=Qt.AlignmentFlag.AlignTop)
        main_layout.addLayout(header)

        # ----------------------------------------------------
        # Search / Browse card
        # ----------------------------------------------------
        browse_card = QFrame(self)
        browse_card.setObjectName("gameBananaBrowseCard")
        browse_layout = QVBoxLayout(browse_card)
        browse_layout.setContentsMargins(14, 12, 14, 12)
        browse_layout.setSpacing(8)

        self.browse_title_label.setObjectName("gameBananaSectionTitle")
        browse_layout.addWidget(self.browse_title_label)

        self.browse_status_label.setObjectName("gameBananaBrowseStatus")
        self.browse_status_label.setWordWrap(True)
        browse_layout.addWidget(self.browse_status_label)

        # Das Eingabefeld bekommt immer die komplette Breite.
        # Dadurch können Button-Texte in längeren Sprachen das
        # Suchfeld nicht zusammendrücken.
        self.search_input.setObjectName("gameBananaSearchInput")
        self.search_input.setMinimumHeight(40)
        self.search_input.setClearButtonEnabled(True)
        browse_layout.addWidget(self.search_input)

        search_actions = QHBoxLayout()
        search_actions.setSpacing(8)

        self.search_button.setObjectName("gameBananaPrimaryButton")
        self.search_button.setMinimumHeight(40)
        self.search_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        search_actions.addWidget(self.search_button, stretch=1)

        self.latest_button.setObjectName("gameBananaSecondaryButton")
        self.latest_button.setMinimumHeight(40)
        self.latest_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        search_actions.addWidget(self.latest_button, stretch=1)

        browse_layout.addLayout(search_actions)

        self.search_hint_label.setObjectName("gameBananaHint")
        self.search_hint_label.setWordWrap(True)
        browse_layout.addWidget(self.search_hint_label)
        main_layout.addWidget(browse_card)

        # ----------------------------------------------------
        # Workspace splitter
        # ----------------------------------------------------
        self.workspace_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )
        self.workspace_splitter.setObjectName("gameBananaSplitter")
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(8)

        browser_panel = self._create_browser_panel(self.workspace_splitter)
        details_panel = self._create_details_panel(self.workspace_splitter)
        self.workspace_splitter.addWidget(browser_panel)
        self.workspace_splitter.addWidget(details_panel)
        self.workspace_splitter.setStretchFactor(0, 5)
        self.workspace_splitter.setStretchFactor(1, 4)
        self.workspace_splitter.setSizes([760, 580])
        main_layout.addWidget(self.workspace_splitter, stretch=1)

    def _create_browser_panel(self, parent: QWidget) -> QWidget:
        panel = QFrame(parent)
        panel.setObjectName("gameBananaBrowserPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.results_scroll.setObjectName("gameBananaResultsScroll")
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.results_content.setObjectName("gameBananaResultsContent")
        self.results_layout.setContentsMargins(12, 12, 12, 12)
        self.results_layout.setSpacing(9)
        self.results_layout.addStretch(1)
        self.results_scroll.setWidget(self.results_content)
        layout.addWidget(self.results_scroll, stretch=1)

        self.browse_state_panel.setObjectName(
            "gameBananaBrowseStatePanel"
        )
        self.browse_state_panel.hide()
        layout.addWidget(
            self.browse_state_panel,
            stretch=1,
        )

        self.pagination_frame = QFrame(panel)
        self.pagination_frame.setObjectName(
            "gameBananaPagination"
        )
        pagination_layout = QHBoxLayout(
            self.pagination_frame
        )
        pagination_layout.setContentsMargins(10, 8, 10, 8)
        pagination_layout.setSpacing(8)

        self.previous_button.setObjectName("gameBananaSecondaryButton")
        self.next_button.setObjectName("gameBananaSecondaryButton")
        self.previous_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.next_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        pagination_layout.addWidget(self.previous_button, stretch=1)
        pagination_layout.addWidget(self.next_button, stretch=1)
        layout.addWidget(
            self.pagination_frame
        )
        return panel

    def _create_details_panel(self, parent: QWidget) -> QWidget:
        details_scroll = QScrollArea(parent)
        details_scroll.setObjectName("gameBananaDetailsScroll")
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("gameBananaDetailsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Direct lookup card
        direct_card = QFrame(content)
        direct_card.setObjectName("gameBananaDirectCard")
        direct_layout = QVBoxLayout(direct_card)
        direct_layout.setContentsMargins(13, 12, 13, 12)
        direct_layout.setSpacing(8)

        self.direct_title_label.setObjectName("gameBananaSectionTitle")
        direct_layout.addWidget(self.direct_title_label)

        self.reference_input.setObjectName("gameBananaReferenceInput")
        self.reference_input.setClearButtonEnabled(True)
        self.reference_input.setMinimumHeight(38)
        direct_layout.addWidget(self.reference_input)

        self.lookup_button.setObjectName("gameBananaSecondaryButton")
        self.lookup_button.setMinimumHeight(38)
        self.lookup_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        direct_layout.addWidget(self.lookup_button)
        layout.addWidget(direct_card)

        # Details title + empty state
        self.details_title_label.setObjectName("gameBananaSectionTitle")
        layout.addWidget(self.details_title_label)

        self.details_state_panel.setObjectName(
            "gameBananaDetailsStatePanel"
        )
        self.details_state_panel.setMinimumHeight(
            220
        )
        layout.addWidget(
            self.details_state_panel
        )

        # Mod card
        self.mod_frame.setObjectName("gameBananaModCard")
        mod_layout = QVBoxLayout(self.mod_frame)
        mod_layout.setContentsMargins(15, 14, 15, 14)
        mod_layout.setSpacing(8)

        self.mod_name_label.setObjectName("gameBananaModTitle")
        self.mod_name_label.setWordWrap(True)
        mod_layout.addWidget(self.mod_name_label)

        self.mod_id_label.setObjectName("gameBananaModId")
        self.mod_id_label.setWordWrap(True)
        mod_layout.addWidget(self.mod_id_label)

        self.author_label.setObjectName("gameBananaModMeta")
        self.source_game_label.setObjectName("gameBananaModMeta")
        self.author_label.setWordWrap(True)
        self.source_game_label.setWordWrap(True)
        mod_layout.addWidget(self.author_label)
        mod_layout.addWidget(self.source_game_label)

        # Alle Preview-/Screenshot-Bilder werden vor der
        # Beschreibung und vor dem Download angezeigt.
        mod_layout.addWidget(self.preview_gallery)

        self.description_view.setObjectName("gameBananaDescription")
        self.description_view.setOpenExternalLinks(False)
        self.description_view.setReadOnly(True)
        self.description_view.setMinimumHeight(150)
        self.description_view.setMaximumHeight(280)
        mod_layout.addWidget(self.description_view)

        self.file_label.setObjectName("gameBananaFieldLabel")
        mod_layout.addWidget(self.file_label)
        self.file_combobox.setObjectName("gameBananaFileCombo")
        self.file_combobox.setMinimumHeight(38)
        mod_layout.addWidget(self.file_combobox)

        self.profile_button.setObjectName("gameBananaSecondaryButton")
        self.profile_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        mod_layout.addWidget(self.profile_button)

        self.install_button.setObjectName("gameBananaPrimaryButton")
        self.install_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        mod_layout.addWidget(self.install_button)
        self.mod_frame.hide()
        layout.addWidget(self.mod_frame)

        # Operation card
        self.operation_frame.setObjectName("gameBananaOperationCard")
        operation_layout = QVBoxLayout(self.operation_frame)
        operation_layout.setContentsMargins(13, 11, 13, 11)
        operation_layout.setSpacing(7)

        self.status_label.setObjectName("gameBananaStatus")
        self.status_label.setWordWrap(True)
        operation_layout.addWidget(self.status_label)

        self.progress_bar.setObjectName("gameBananaProgress")
        self.progress_bar.setTextVisible(True)
        operation_layout.addWidget(self.progress_bar)

        self.cancel_button.setObjectName("gameBananaDangerButton")
        self.cancel_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        operation_layout.addWidget(self.cancel_button)
        self.operation_frame.hide()
        layout.addWidget(self.operation_frame)
        layout.addStretch(1)

        details_scroll.setWidget(content)
        return details_scroll

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self._search)
        self.search_input.returnPressed.connect(self._search)
        self.latest_button.clicked.connect(self._load_latest)
        self.previous_button.clicked.connect(self._load_previous_page)
        self.next_button.clicked.connect(self._load_next_page)

        self.lookup_button.clicked.connect(self._lookup)
        self.reference_input.returnPressed.connect(self._lookup)
        self.profile_button.clicked.connect(self._open_profile)
        self.install_button.clicked.connect(self._download_and_install)
        self.cancel_button.clicked.connect(self._cancel_download)
        self.file_combobox.currentIndexChanged.connect(self._sync_busy_state)

        self.controller.lookup_started.connect(self._on_lookup_started)
        self.controller.mod_loaded.connect(self._on_mod_loaded)
        self.controller.lookup_failed.connect(self._on_lookup_failed)
        self.controller.download_started.connect(self._on_download_started)
        self.controller.download_progress.connect(self._on_download_progress)
        self.controller.download_finished.connect(self._on_download_finished)
        self.controller.download_failed.connect(self._on_download_failed)
        self.controller.download_cancelled.connect(self._on_download_cancelled)
        self.controller.busy_changed.connect(self._on_busy_changed)

        self.browse_state_panel.primary_requested.connect(
            self._on_browse_state_primary
        )

        self.details_state_panel.primary_requested.connect(
            self._retry_last_lookup
        )

        # Initiale Zustände.
        self._show_details_empty_state()

    # ========================================================
    # Lazy first load
    # ========================================================

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._browse_loaded_once:
            return
        self._browse_loaded_once = True
        QTimer.singleShot(0, self._load_latest)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        splitter = getattr(self, "workspace_splitter", None)
        if splitter is None:
            return

        if self.width() < self.RESPONSIVE_BREAKPOINT:
            orientation = Qt.Orientation.Vertical
            sizes = [430, 520]
        else:
            orientation = Qt.Orientation.Horizontal
            sizes = [760, 580]

        if splitter.orientation() != orientation:
            splitter.setOrientation(orientation)
            splitter.setSizes(sizes)

    # ========================================================
    # Game
    # ========================================================

    def can_change_game(self) -> bool:
        return not (self.controller.is_busy or self._browse_worker is not None)

    def on_game_changed(self, _game_id: str) -> None:
        if not self.can_change_game():
            return

        self.controller.clear()
        self._current_mod = None
        self._current_game_id = None
        self.file_combobox.clear()
        self.preview_gallery.clear()
        self.mod_frame.hide()
        self._last_lookup_reference = None
        self._show_details_empty_state()
        self.reference_input.clear()
        self.search_input.clear()
        self.operation_frame.hide()
        self.progress_bar.setValue(0)
        self._set_status(None)

        self._browse_page = 1
        self._browse_query = ""
        self._last_browse_has_next = False
        self._clear_results()
        self._browse_state_mode = "idle"
        self._browse_state_message = ""
        self._update_game_label()
        self._sync_busy_state()
        QTimer.singleShot(0, self._load_latest)

    # ========================================================
    # Browser / Search
    # ========================================================

    def _search(self) -> None:
        query = self.search_input.text().strip()
        if len(query) < 2:
            QMessageBox.information(
                self,
                tr("gamebanana.search.short.title"),
                tr("gamebanana.search.short.message"),
            )
            return
        self._start_browse(page=1, query=query)

    def _load_latest(self, _checked: bool = False, *, page: int = 1) -> None:
        self.search_input.clear()
        self._start_browse(page=max(1, int(page)), query="")

    def _load_previous_page(self, _checked: bool = False) -> None:
        if self._browse_query:
            return
        self._load_latest(page=max(1, self._browse_page - 1))

    def _load_next_page(self, _checked: bool = False) -> None:
        if self._browse_query:
            return
        self._load_latest(page=self._browse_page + 1)

    def _start_browse(self, *, page: int, query: str) -> None:
        if self.controller.is_busy or self._browse_worker is not None:
            QMessageBox.information(
                self,
                tr("gamebanana.busy.title"),
                tr("gamebanana.busy.message"),
            )
            return

        game_id = str(self.config.selected_game)
        if game_id not in GAMEBANANA_GAME_IDS:
            self._clear_results()

            self._browse_page = max(
                1,
                int(page),
            )
            self._browse_query = query.strip()
            self._last_browse_has_next = False

            self._show_browse_error_state(
                tr(
                    "gamebanana.error.browse.unsupported_game",
                    game=game_id,
                ),
                retry_available=False,
            )

            self.browse_status_label.setText(
                tr(
                    "gamebanana.status.browse_failed"
                )
            )

            self._sync_busy_state()
            return

        worker = GameBananaBrowseWorker(game_id=game_id, page=page, query=query)
        worker.signals.finished.connect(self._on_browse_finished)
        worker.signals.failed.connect(self._on_browse_failed)
        worker.signals.cancelled.connect(self._on_browse_cancelled)
        self._browse_worker = worker
        self._browse_page = max(1, int(page))
        self._browse_query = query.strip()
        self._last_browse_has_next = False

        self._clear_results()

        self._show_browse_loading_state()

        self.browse_status_label.setText(
            tr("gamebanana.browse.search_mode")
            if self._browse_query
            else tr("gamebanana.browse.page", page=self._browse_page)
        )
        self._sync_busy_state()
        self.controller.thread_pool.start(worker)

    def _on_browse_finished(self, result: GameBananaBrowseResult) -> None:
        self._browse_worker = None
        if result.game_id != self.config.selected_game:
            self._sync_busy_state()
            return

        self._browse_page = result.page
        self._browse_query = result.query
        self._last_browse_has_next = result.has_next
        self._set_results(result.mods)
        count = len(result.mods)

        if result.query:
            self.browse_status_label.setText(tr("gamebanana.browse.search_mode"))
            empty_key = "gamebanana.status.search_empty"
        else:
            self.browse_status_label.setText(
                tr("gamebanana.browse.page", page=result.page)
            )
            empty_key = "gamebanana.status.latest_empty"

        if count:
            self._show_browse_content()
        else:
            self._show_browse_empty_state(
                empty_key
            )

        self.previous_button.setEnabled(
            not result.query and result.has_previous
        )
        self.next_button.setEnabled(
            not result.query and result.has_next and count > 0
        )
        self._sync_busy_state()

    def _on_browse_failed(self, message: str) -> None:
        self._browse_worker = None

        self._show_browse_error_state(
            message
            or tr(
                "gamebanana.status.browse_failed"
            )
        )

        self.browse_status_label.setText(
            tr(
                "gamebanana.status.browse_failed"
            )
        )

        self._sync_busy_state()

    def _on_browse_cancelled(self) -> None:
        self._browse_worker = None
        self._sync_busy_state()

    def _clear_results(self) -> None:
        cards = tuple(self._result_cards)
        self._result_cards.clear()
        for card in cards:
            self.results_layout.removeWidget(card)
            card.deleteLater()

    def _set_results(self, mods: tuple[GameBananaMod, ...]) -> None:
        self._clear_results()
        for mod in mods:
            card = GameBananaResultCard(mod=mod, parent=self.results_content)
            card.open_requested.connect(self._open_browse_mod)
            self._result_cards.append(card)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    def _open_browse_mod(self, mod_id: int) -> None:
        self.reference_input.setText(str(mod_id))
        self._lookup_reference(mod_id)

    # ========================================================
    # Direct lookup + details
    # ========================================================

    def _lookup(self) -> None:
        reference = self.reference_input.text().strip()
        if reference:
            self._lookup_reference(reference)

    def _lookup_reference(self, reference) -> None:
        if self._browse_worker is not None:
            QMessageBox.information(
                self,
                tr("gamebanana.busy.title"),
                tr("gamebanana.busy.message"),
            )
            return

        self._current_mod = None
        self._current_game_id = None
        self._last_lookup_reference = reference
        self.file_combobox.clear()
        self.preview_gallery.clear()
        self.mod_frame.hide()

        self._show_details_loading_state()

        if not self.controller.lookup(reference):
            QMessageBox.information(
                self,
                tr("gamebanana.busy.title"),
                tr("gamebanana.busy.message"),
            )

    def _on_lookup_started(self) -> None:
        self._show_details_loading_state()

        self._show_operation_status(True)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self._set_status(
            "gamebanana.status.loading"
        )

    def _on_mod_loaded(self, mod: GameBananaMod, game_id: str) -> None:
        self._current_mod = mod
        self._current_game_id = game_id
        self.reference_input.setText(str(mod.id))
        self.mod_name_label.setText(mod.name)
        self.mod_id_label.setText(tr("gamebanana.mod.id", id=mod.id))

        unknown = tr("gamebanana.value.unknown")
        self.author_label.setText(
            tr("gamebanana.mod.author", author=mod.author or unknown)
        )
        self.source_game_label.setText(
            tr("gamebanana.mod.game", game=mod.game_name or unknown)
        )

        self.preview_gallery.set_preview_urls(
            mod.all_preview_urls
        )

        description = mod.description or tr("gamebanana.mod.no_description")
        plain_description = QTextDocumentFragment.fromHtml(description).toPlainText()
        self.description_view.setPlainText(plain_description)

        self.file_combobox.clear()
        for file in mod.files:
            self.file_combobox.addItem(self._file_display_name(file), userData=file)

        default_file = mod.default_file()
        if default_file is not None:
            for index in range(self.file_combobox.count()):
                if self.file_combobox.itemData(index) == default_file:
                    self.file_combobox.setCurrentIndex(index)
                    break

        self._show_details_content()

        self._set_status(
            "gamebanana.status.loaded",
            count=len(mod.files),
        )
        self._show_operation_status(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._sync_busy_state()

    def _on_lookup_failed(self, message: str) -> None:
        self._show_details_error_state(
            message
            or tr(
                "gamebanana.status.lookup_failed"
            )
        )

        self._set_status(
            "gamebanana.status.lookup_failed"
        )

        self._show_operation_status(True)
        self.progress_bar.hide()
        self.cancel_button.hide()

    # ========================================================
    # Unified Browser States
    # ========================================================

    def _show_browse_content(
        self,
    ) -> None:
        self._browse_state_mode = "content"
        self._browse_state_message = ""

        self.browse_state_panel.hide()
        self.results_scroll.show()
        self.pagination_frame.show()

    def _show_browse_loading_state(
        self,
    ) -> None:
        self._browse_state_mode = "loading"
        self._browse_state_message = ""

        self.results_scroll.hide()
        self.pagination_frame.hide()

        title_key = (
            "gamebanana.status.searching"
            if self._browse_query
            else "gamebanana.status.loading_latest"
        )

        self.browse_state_panel.show_loading(
            title=tr(
                title_key
            ),
            description=tr(
                "gamebanana.search.hint"
            ),
        )

        self.browse_state_panel.show()

    def _show_browse_empty_state(
        self,
        empty_key: str,
    ) -> None:
        self._browse_state_mode = (
            "empty_search"
            if self._browse_query
            else "empty_latest"
        )

        self._browse_state_message = ""

        self.results_scroll.hide()
        self.pagination_frame.hide()

        if self._browse_query:
            description = (
                self._browse_query
            )

            primary_text = tr(
                "gamebanana.latest"
            )
        else:
            description = tr(
                "gamebanana.browse.page",
                page=self._browse_page,
            )

            primary_text = (
                tr(
                    "gamebanana.previous"
                )
                if self._browse_page > 1
                else tr(
                    "gamebanana.latest"
                )
            )

        self.browse_state_panel.show_empty(
            title=tr(
                empty_key
            ),
            description=description,
            primary_text=primary_text,
        )

        self.browse_state_panel.show()

    def _show_browse_error_state(
        self,
        message: str,
        *,
        retry_available: bool = True,
    ) -> None:
        self._browse_state_mode = (
            "error"
            if retry_available
            else "unsupported"
        )

        self._browse_state_message = str(
            message
        ).strip()

        self.results_scroll.hide()
        self.pagination_frame.hide()

        primary_text = ""

        if retry_available:
            primary_text = (
                tr(
                    "gamebanana.search.button"
                )
                if self._browse_query
                else tr(
                    "gamebanana.latest"
                )
            )

        self.browse_state_panel.show_error(
            title=tr(
                "gamebanana.error.browse.title"
            ),
            description=(
                self._browse_state_message
                or tr(
                    "gamebanana.status.browse_failed"
                )
            ),
            primary_text=primary_text,
        )

        self.browse_state_panel.show()

    def _on_browse_state_primary(
        self,
    ) -> None:
        mode = self._browse_state_mode

        if mode == "empty_search":
            self._load_latest()
            return

        if mode == "empty_latest":
            if self._browse_page > 1:
                self._load_previous_page()
            else:
                self._load_latest()
            return

        if mode == "error":
            self._start_browse(
                page=max(
                    1,
                    self._browse_page,
                ),
                query=self._browse_query,
            )

    # ========================================================
    # Unified Details States
    # ========================================================

    def _show_details_content(
        self,
    ) -> None:
        self._details_state_mode = "content"
        self._details_state_message = ""

        self.details_state_panel.hide()
        self.mod_frame.show()

    def _show_details_empty_state(
        self,
    ) -> None:
        self._details_state_mode = "empty"
        self._details_state_message = ""

        self.mod_frame.hide()

        self.details_state_panel.show_empty(
            title=tr(
                "gamebanana.details.empty"
            ),
            description=tr(
                "gamebanana.reference.placeholder"
            ),
        )

        self.details_state_panel.show()

    def _show_details_loading_state(
        self,
    ) -> None:
        self._details_state_mode = "loading"
        self._details_state_message = ""

        self.mod_frame.hide()

        self.details_state_panel.show_loading(
            title=tr(
                "gamebanana.status.loading"
            ),
            description=tr(
                "gamebanana.details.title"
            ),
        )

        self.details_state_panel.show()

    def _show_details_error_state(
        self,
        message: str,
    ) -> None:
        self._details_state_mode = "error"
        self._details_state_message = str(
            message
        ).strip()

        self.mod_frame.hide()

        self.details_state_panel.show_error(
            title=tr(
                "gamebanana.error.lookup.title"
            ),
            description=(
                self._details_state_message
                or tr(
                    "gamebanana.status.lookup_failed"
                )
            ),
            primary_text=tr(
                "gamebanana.lookup"
            ),
        )

        self.details_state_panel.show()

    def _retry_last_lookup(
        self,
    ) -> None:
        if self._details_state_mode != "error":
            return

        reference = (
            self._last_lookup_reference
        )

        if reference is None:
            return

        self._lookup_reference(
            reference
        )

    def _refresh_unified_state_texts(
        self,
    ) -> None:
        """
        Aktualisiert sichtbare States beim Sprachwechsel.
        """

        browse_mode = self._browse_state_mode

        if browse_mode == "loading":
            self._show_browse_loading_state()

        elif browse_mode == "empty_search":
            self._show_browse_empty_state(
                "gamebanana.status.search_empty"
            )

        elif browse_mode == "empty_latest":
            self._show_browse_empty_state(
                "gamebanana.status.latest_empty"
            )

        elif browse_mode in (
            "error",
            "unsupported",
        ):
            self._show_browse_error_state(
                self._browse_state_message,
                retry_available=(
                    browse_mode
                    == "error"
                ),
            )

        details_mode = (
            self._details_state_mode
        )

        if details_mode == "empty":
            self._show_details_empty_state()

        elif details_mode == "loading":
            self._show_details_loading_state()

        elif details_mode == "error":
            self._show_details_error_state(
                self._details_state_message
            )

    # ========================================================
    # File + download
    # ========================================================

    def _file_display_name(self, file: GameBananaFile) -> str:
        if file.size is None:
            return file.name

        locale = QLocale(self.config.language)
        size_mb = file.size / 1024 / 1024
        size_text = locale.toString(size_mb, "f", 1)

        return tr(
            "gamebanana.file.display",
            name=file.name,
            size=size_text,
        )

    def _selected_file(self) -> GameBananaFile | None:
        value = self.file_combobox.currentData()
        return value if isinstance(value, GameBananaFile) else None

    def _download_and_install(self) -> None:
        file = self._selected_file()
        if file is None:
            return
        if not self.controller.download(file):
            QMessageBox.warning(
                self,
                tr("gamebanana.error.download.title"),
                tr("gamebanana.error.download.start"),
            )

    def _on_download_started(self, file: GameBananaFile) -> None:
        self._show_operation_status(True)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self._set_status("gamebanana.status.downloading", file=file.name)

    def _on_download_progress(self, current, total) -> None:
        current_bytes = int(current)
        total_bytes = int(total)
        if total_bytes <= 0:
            self.progress_bar.setRange(0, 0)
            self._set_status(
                "gamebanana.status.download_bytes",
                current=self._format_bytes(current_bytes),
            )
            return

        self.progress_bar.setRange(0, 100)
        percentage = int(min(100, current_bytes * 100 / total_bytes))
        self.progress_bar.setValue(percentage)
        self._set_status(
            "gamebanana.status.download_progress",
            current=self._format_bytes(current_bytes),
            total=self._format_bytes(total_bytes),
        )

    def _on_download_finished(self, result, game_id: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.cancel_button.hide()
        self._set_status("gamebanana.status.download_finished")

        mod_id = int(self._current_mod.id) if self._current_mod is not None else 0
        self.install_requested.emit(result.path, game_id, mod_id)

    def _on_download_failed(self, message: str) -> None:
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._set_status("gamebanana.status.download_failed")
        QMessageBox.critical(
            self,
            tr("gamebanana.error.download.title"),
            tr("gamebanana.error.download.message"),
        )

    def _on_download_cancelled(self) -> None:
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._set_status("gamebanana.status.cancelled")

    def _cancel_download(self) -> None:
        if self.controller.cancel_download():
            self.cancel_button.setEnabled(False)
            self._set_status("gamebanana.status.cancelling")

    # ========================================================
    # External browser
    # ========================================================

    def _open_profile(self) -> None:
        mod = self._current_mod
        if mod is None or not mod.profile_url:
            return
        QDesktopServices.openUrl(QUrl(mod.profile_url))

    # ========================================================
    # Busy state
    # ========================================================

    def _on_busy_changed(self, _busy: bool) -> None:
        self._sync_busy_state()

    def _sync_busy_state(self, *_args) -> None:
        busy = self.controller.is_busy or self._browse_worker is not None
        for widget in (
            self.search_input,
            self.search_button,
            self.latest_button,
            self.reference_input,
            self.lookup_button,
            self.file_combobox,
        ):
            widget.setEnabled(not busy)

        self.install_button.setEnabled(
            not busy and self._selected_file() is not None
        )
        self.profile_button.setEnabled(
            not busy
            and self._current_mod is not None
            and bool(self._current_mod.profile_url)
        )

        if busy or self._browse_query:
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
        else:
            self.previous_button.setEnabled(self._browse_page > 1)
            self.next_button.setEnabled(
                self._last_browse_has_next and bool(self._result_cards)
            )

    def _show_operation_status(self, visible: bool) -> None:
        self.operation_frame.setVisible(bool(visible))

    def _set_status(self, key: str | None, **params) -> None:
        self._status_key = key
        self._status_params = dict(params)

        if key is None:
            self.status_label.clear()
            return

        self.status_label.setText(
            tr(key, **params)
        )

    # ========================================================
    # Translation
    # ========================================================

    def _update_game_label(self) -> None:
        game = self.config.current_game
        self.game_badge.setText(
            tr("gamebanana.current_game", game=game.name, importer=game.importer)
        )

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.title_label.setText(tr("gamebanana.title"))
        self.subtitle_label.setText(tr("gamebanana.search.hint"))
        self.browse_title_label.setText(tr("gamebanana.browse.title"))
        self.search_input.setPlaceholderText(tr("gamebanana.search.placeholder"))
        self.search_button.setText(tr("gamebanana.search.button"))
        self.latest_button.setText(tr("gamebanana.latest"))
        self.search_hint_label.setText(tr("gamebanana.search.hint"))
        self.previous_button.setText(tr("gamebanana.previous"))
        self.next_button.setText(tr("gamebanana.next"))
        self.direct_title_label.setText(tr("gamebanana.direct.title"))
        self.reference_input.setPlaceholderText(tr("gamebanana.reference.placeholder"))
        self.lookup_button.setText(tr("gamebanana.lookup"))
        self.details_title_label.setText(tr("gamebanana.details.title"))
        self.file_label.setText(tr("gamebanana.files"))
        self.profile_button.setText(tr("gamebanana.open_page"))
        self.install_button.setText(tr("gamebanana.download_install"))
        self.cancel_button.setText(tr("common.cancel"))

        self.browse_status_label.setText(
            tr("gamebanana.browse.search_mode")
            if self._browse_query
            else tr("gamebanana.browse.page", page=self._browse_page)
        )
        self._update_game_label()

        if self._status_key is not None:
            self.status_label.setText(
                tr(self._status_key, **self._status_params)
            )

        mod = self._current_mod
        if mod is not None:
            unknown = tr("gamebanana.value.unknown")
            self.mod_id_label.setText(tr("gamebanana.mod.id", id=mod.id))
            self.author_label.setText(
                tr("gamebanana.mod.author", author=mod.author or unknown)
            )
            self.source_game_label.setText(
                tr("gamebanana.mod.game", game=mod.game_name or unknown)
            )

            selected_file = self._selected_file()
            self.file_combobox.blockSignals(True)
            self.file_combobox.clear()

            for file in mod.files:
                self.file_combobox.addItem(
                    self._file_display_name(file),
                    userData=file,
                )

            if selected_file is not None:
                for index in range(self.file_combobox.count()):
                    if self.file_combobox.itemData(index) == selected_file:
                        self.file_combobox.setCurrentIndex(index)
                        break

            self.file_combobox.blockSignals(False)

        self._refresh_unified_state_texts()
        self._sync_busy_state()

    def shutdown(self) -> None:
        if self._browse_worker is not None:
            self._browse_worker.cancel()

        self.preview_gallery.shutdown()
        self.controller.shutdown()

    # ========================================================
    # Style + utilities
    # ========================================================

    def _apply_stylesheet(self) -> None:
        style_path = (
            Path(__file__).resolve().parents[1] / "styles" / "gamebanana.qss"
        )
        try:
            stylesheet = style_path.read_text(encoding="utf-8")
        except OSError:
            return
        self.setStyleSheet(stylesheet)

    def _format_bytes(self, value: int) -> str:
        size = float(max(0, value))
        locale = QLocale(self.config.language)

        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024.0 or unit == "GB":
                if unit == "B":
                    number = locale.toString(int(size))
                else:
                    number = locale.toString(size, "f", 1)
                return f"{number} {unit}"

            size /= 1024.0

        return f"{size:.1f} GB"


__all__ = ["GameBananaPage"]
