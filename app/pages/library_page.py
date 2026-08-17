from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.games import (
    GameScope,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.models.mod import (
    ModInfo,
)

from app.controllers.library_bulk_controller import (
    LibraryBulkController,
)

from app.controllers.library_drop_handler import (
    LibraryDropHandler,
)

from app.controllers.library_header_controller import (
    LibraryHeaderController,
)

from app.controllers.library_import_controller import (
    LibraryImportController,
)

from app.controllers.library_mod_action_controller import (
    LibraryModActionController,
)

from app.controllers.library_mod_info_controller import (
    LibraryModInfoController,
)

from app.controllers.library_operation_state import (
    LibraryOperation,
    LibraryOperationState,
)

from app.controllers.library_scan_controller import (
    LibraryScanController,
    ScanRequestStatus,
)

from app.controllers.library_selection_controller import (
    LibrarySelectionController,
)

from app.dialogs.library_bulk_confirmation import (
    confirm_bulk_action,
)

from app.dialogs.library_import_picker import (
    choose_import_archives,
    choose_import_directory,
)

from app.dialogs.library_import_request import (
    prepare_import_request,
)

from app.dialogs.library_mod_action_dialogs import (
    confirm_adopt_existing,
    show_mod_action_problem,
)

from app.dialogs.library_operation_dialogs import (
    operation_block_message,
    show_operation_blocked,
)

from app.services.conflict_scanner import (
    ConflictItem,
    ConflictReport,
    ConflictScanner,
)

from app.services.mod_importer import (
    ImportBatchResult,
    ImportStatus,
)

from app.services.mod_manager import (
    ModManager,
    ModManagerError,
    ModState,
)

from app.services.mod_metadata import (
    load_mod_metadata,
    set_gamebanana_mod_id,
)

from app.services.mod_scanner import (
    ScanResult,
)

from app.utils.bulk_result_formatter import (
    bulk_result_requires_warning,
    format_bulk_result,
    format_bulk_status,
)

from app.utils.import_result_formatter import (
    format_import_result,
    format_import_status,
)

from app.widgets.library.library_filter_bar import (
    LibraryFilterBar,
)

from app.widgets.library.library_empty_state import (
    LibraryEmptyState,
    LibraryFilterEmptyState,
)

from app.widgets.library.library_gallery import (
    LibraryGalleryWidget,
)

from app.widgets.library.library_header import (
    LibraryHeader,
)

from app.widgets.library.library_mod_list import (
    LibraryModListWidget,
)

from app.widgets.library.library_operation_status import (
    LibraryOperationStatusWidget,
)

from app.widgets.library.library_stats import (
    LibraryStatsWidget,
)

from app.widgets.library.mod_details_panel import (
    ModDetailsPanel,
)

from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
)


class LibraryPage(
    QWidget
):
    RESPONSIVE_BREAKPOINT = 1080
    TIGHT_BREAKPOINT = 760

    """
    Library des aktuell ausgewählten XXMI-Spiels.

    Enthält:
    - Tabellenansicht
    - Galerieansicht
    - Preview-Fallback
    - Mod-Aktivierung
    - Import
    - Bulk-Aktionen
    - GameBanana-Metadaten
    - Konflikterkennung
    """

    conflict_count_changed = Signal(
        int
    )

    conflict_report_changed = Signal(
        object
    )

    def __init__(
        self,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config

        self._responsive_mode = ""
        self._root_layout: QVBoxLayout | None = None
        self.list_splitter: QSplitter | None = None
        self.gallery_splitter: QSplitter | None = None

        # ====================================================
        # Game Scope
        # ====================================================

        self.game_scope = (
            GameScope(
                config=self.config,
                game_id=(
                    self.config
                    .selected_game
                ),
            )
        )

        # ====================================================
        # Gemeinsamer ModManager
        # ====================================================

        self.mod_manager = (
            ModManager(
                config=(
                    self.game_scope
                )
            )
        )

        # ====================================================
        # Konflikte
        # ====================================================

        self.conflict_scanner = (
            ConflictScanner(
                game_scope=(
                    self.game_scope
                ),
                mod_manager=(
                    self.mod_manager
                ),
            )
        )

        self._conflict_report = (
            ConflictReport()
        )

        self._last_scanned_mods: tuple[
            ModInfo,
            ...,
        ] = ()

        # ====================================================
        # GameBanana Import-Metadaten
        #
        # key:
        #   absoluter Downloadpfad
        #
        # value:
        #   (game_id, mod_id)
        # ====================================================

        self._pending_gamebanana_imports: dict[
            str,
            tuple[
                str,
                int,
            ],
        ] = {}

        # ====================================================
        # Controller
        # ====================================================

        self.mod_action_controller = (
            LibraryModActionController(
                mod_manager=(
                    self.mod_manager
                )
            )
        )

        self.scan_controller = (
            LibraryScanController(
                parent=self
            )
        )

        self.bulk_controller = (
            LibraryBulkController(
                mod_manager=(
                    self.mod_manager
                ),
                parent=self,
            )
        )

        self.import_controller = (
            LibraryImportController(
                parent=self
            )
        )

        self.operation_state = (
            LibraryOperationState(
                scan_controller=(
                    self.scan_controller
                ),
                import_controller=(
                    self.import_controller
                ),
                bulk_controller=(
                    self.bulk_controller
                ),
            )
        )

        # ====================================================
        # Hauptwidgets
        # ====================================================

        self.header_widget = (
            LibraryHeader(
                parent=self
            )
        )

        self.stats_widget = (
            LibraryStatsWidget(
                parent=self
            )
        )

        self.filter_bar = (
            LibraryFilterBar(
                parent=self
            )
        )

        self.operation_status = (
            LibraryOperationStatusWidget(
                parent=self
            )
        )

        # ====================================================
        # Empty Library
        # ====================================================

        self.empty_state = LibraryEmptyState(
            parent=self
        )

        self.filter_empty_state = LibraryFilterEmptyState(
            parent=self
        )

        self.workspace_state_stack = QStackedWidget(
            self
        )

        self._library_scan_completed = False

        # ====================================================
        # Liste
        # ====================================================

        self.mod_list_widget = (
            LibraryModListWidget(
                parent=self
            )
        )

        # ====================================================
        # Details
        # ====================================================

        self.details_panel = (
            ModDetailsPanel(
                parent=self
            )
        )

        # ====================================================
        # Galerie
        # ====================================================

        self.gallery_widget = (
            LibraryGalleryWidget(
                parent=self
            )
        )

        # ====================================================
        # Gallery Details
        # ====================================================

        self.gallery_details_panel = (
            ModDetailsPanel(
                parent=self
            )
        )

        self.gallery_details_panel.show_empty()

        # Die Gallery ist für einzelne Mod-Aktionen gedacht.
        # Conflict-Adoption und direkte Metadatenbearbeitung
        # bleiben in der Listenansicht.
        if hasattr(
            self.gallery_details_panel,
            "adopt_button",
        ):
            self.gallery_details_panel.adopt_button.hide()

        if hasattr(
            self.gallery_details_panel,
            "gamebanana_id_button",
        ):
            self.gallery_details_panel.gamebanana_id_button.hide()

        if hasattr(
            self.gallery_details_panel,
            "set_metadata_edit_enabled",
        ):
            self.gallery_details_panel.set_metadata_edit_enabled(
                False
            )

        self._gallery_selected_mod: (
            ModInfo
            | None
        ) = None

        # ====================================================
        # View Switcher
        # ====================================================

        self.view_title_label = QLabel()

        self.view_title_label.setObjectName(
            "libraryViewTitle"
        )

        self.view_count_label = QLabel()

        self.view_count_label.setObjectName(
            "libraryViewCount"
        )

        self.list_view_button = (
            QPushButton()
        )

        self.gallery_view_button = (
            QPushButton()
        )

        self.list_view_button.setObjectName(
            "libraryViewButton"
        )

        self.gallery_view_button.setObjectName(
            "libraryViewButton"
        )

        self.list_view_button.setCheckable(
            True
        )

        self.gallery_view_button.setCheckable(
            True
        )

        self.view_button_group = (
            QButtonGroup(
                self
            )
        )

        self.view_button_group.setExclusive(
            True
        )

        self.view_button_group.addButton(
            self.list_view_button,
            0,
        )

        self.view_button_group.addButton(
            self.gallery_view_button,
            1,
        )

        self.list_view_button.setChecked(
            True
        )

        self.content_stack = (
            QStackedWidget(
                self
            )
        )

        # ====================================================
        # Selection Controller
        #
        # WICHTIG:
        # is_running bleibt Callable.
        # ====================================================

        self.selection_controller = (
            LibrarySelectionController(
                mod_list_widget=(
                    self.mod_list_widget
                ),
                details_panel=(
                    self.details_panel
                ),
                mod_action_controller=(
                    self.mod_action_controller
                ),
                operation_running_provider=(
                    self.operation_state
                    .is_running
                ),
                refresh_stats_callback=(
                    self._update_stats
                ),
                parent=self,
            )
        )

        # ====================================================
        # Mod Info
        # ====================================================

        self.mod_info_controller = (
            LibraryModInfoController(
                mod_manager=(
                    self.mod_manager
                ),
                selected_mod_provider=(
                    self.mod_list_widget
                    .selected_mod
                ),
                parent=self,
            )
        )

        # ====================================================
        # Header Controller
        # ====================================================

        self.header_controller = (
            LibraryHeaderController(
                header=(
                    self.header_widget
                ),
                operation_state=(
                    self.operation_state
                ),
                import_archives_callback=(
                    self._choose_import_archives
                ),
                import_directory_callback=(
                    self._choose_import_directory
                ),
                scan_callback=(
                    self.scan_mods
                ),
                cancel_import_callback=(
                    self.cancel_import
                ),
                parent=self,
            )
        )

        # ====================================================
        # Drag & Drop
        # ====================================================

        self.drop_handler = (
            LibraryDropHandler(
                import_callback=(
                    self._request_import
                ),
                parent=self,
            )
        )

        self.drop_handler.install_on(
            self
        )

        self.drop_handler.install_on(
            self.mod_list_widget
            .drop_target()
        )

        # ====================================================
        # UI
        # ====================================================

        self._build_ui()

        self._connect_signals()

        translation_manager.language_changed.connect(
            self._on_language_changed
        )

        self._retranslate_view_buttons()

        initial_view_index = (
            1
            if (
                getattr(
                    self.config,
                    "library_view_mode",
                    "list",
                )
                == "gallery"
            )
            else 0
        )

        self._set_library_view(
            initial_view_index,
            reapply_filters=False,
        )

        self._update_responsive_layout(
            force=True
        )

        # ====================================================
        # Initialer Scan
        # ====================================================

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        self.setObjectName(
            "libraryPage"
        )

        layout = QVBoxLayout(
            self
        )

        self._root_layout = layout

        layout.setContentsMargins(
            22,
            20,
            22,
            16,
        )

        layout.setSpacing(
            14
        )

        layout.addWidget(
            self.header_widget
        )

        layout.addWidget(
            self.stats_widget
        )

        layout.addWidget(
            self.filter_bar
        )

        # ====================================================
        # Workspace
        # ====================================================

        workspace = QFrame(
            self
        )

        workspace.setObjectName(
            "libraryWorkspace"
        )

        workspace_layout = QVBoxLayout(
            workspace
        )

        workspace_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        workspace_layout.setSpacing(
            0
        )

        workspace_layout.addWidget(
            self._create_view_toolbar()
        )

        # Index 0 = List + Details
        self.content_stack.addWidget(
            self._create_content_splitter()
        )

        # Index 1 = Gallery + Details
        self.content_stack.addWidget(
            self._create_gallery_splitter()
        )

        workspace_layout.addWidget(
            self.content_stack,
            stretch=1,
        )

        self.workspace_state_stack.addWidget(
            workspace
        )

        self.workspace_state_stack.addWidget(
            self.empty_state
        )

        self.workspace_state_stack.addWidget(
            self.filter_empty_state
        )

        self.workspace_state_stack.setCurrentWidget(
            workspace
        )

        layout.addWidget(
            self.workspace_state_stack,
            stretch=1,
        )

        layout.addWidget(
            self.operation_status
        )

        self._apply_stylesheet()

    def _create_view_toolbar(
        self,
    ) -> QWidget:
        frame = QFrame(
            self
        )

        frame.setObjectName(
            "libraryViewToolbar"
        )

        layout = QHBoxLayout(
            frame
        )

        layout.setContentsMargins(
            14,
            8,
            14,
            8,
        )

        layout.setSpacing(
            10
        )

        self.view_title_label.setObjectName(
            "libraryViewTitle"
        )

        layout.addWidget(
            self.view_title_label
        )

        layout.addWidget(
            self.view_count_label
        )

        layout.addStretch(
            1
        )

        mode_frame = QFrame(
            frame
        )

        mode_frame.setObjectName(
            "libraryViewModeFrame"
        )

        mode_layout = QHBoxLayout(
            mode_frame
        )

        mode_layout.setContentsMargins(
            3,
            3,
            3,
            3,
        )

        mode_layout.setSpacing(
            2
        )

        self.list_view_button.setMinimumWidth(
            104
        )

        self.gallery_view_button.setMinimumWidth(
            104
        )

        mode_layout.addWidget(
            self.list_view_button
        )

        mode_layout.addWidget(
            self.gallery_view_button
        )

        layout.addWidget(
            mode_frame
        )

        return frame

    def _create_content_splitter(
        self,
    ) -> QSplitter:
        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.setObjectName(
            "librarySplitter"
        )

        splitter.setChildrenCollapsible(
            False
        )

        splitter.setHandleWidth(
            8
        )

        splitter.addWidget(
            self.mod_list_widget
        )

        splitter.addWidget(
            self.details_panel
        )

        splitter.setStretchFactor(
            0,
            5,
        )

        splitter.setStretchFactor(
            1,
            2,
        )

        splitter.setSizes(
            [
                1080,
                420,
            ]
        )

        self.list_splitter = splitter

        return splitter

    def _create_gallery_splitter(
        self,
    ) -> QSplitter:
        """Gallery links und Mod-Details rechts."""

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.setObjectName(
            "librarySplitter"
        )

        splitter.setChildrenCollapsible(
            False
        )

        splitter.setHandleWidth(
            8
        )

        splitter.addWidget(
            self.gallery_widget
        )

        splitter.addWidget(
            self.gallery_details_panel
        )

        splitter.setStretchFactor(
            0,
            5,
        )

        splitter.setStretchFactor(
            1,
            2,
        )

        splitter.setSizes(
            [
                1050,
                400,
            ]
        )

        self.gallery_splitter = splitter

        return splitter

    # ========================================================
    # Responsive Layout
    # ========================================================

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._update_responsive_layout()

    def _update_responsive_layout(
        self,
        *,
        force: bool = False,
    ) -> None:
        width = self.width()

        if width < self.TIGHT_BREAKPOINT:
            mode = "tight"
        elif width < self.RESPONSIVE_BREAKPOINT:
            mode = "stacked"
        else:
            mode = "wide"

        if (
            not force
            and mode == self._responsive_mode
        ):
            return

        self._responsive_mode = mode
        self.setProperty(
            "responsiveMode",
            mode,
        )

        root_layout = self._root_layout

        if root_layout is not None:
            if mode == "wide":
                root_layout.setContentsMargins(
                    22, 20, 22, 16
                )
                root_layout.setSpacing(14)
            elif mode == "stacked":
                root_layout.setContentsMargins(
                    16, 16, 16, 14
                )
                root_layout.setSpacing(12)
            else:
                root_layout.setContentsMargins(
                    10, 12, 10, 10
                )
                root_layout.setSpacing(10)

        stacked = mode != "wide"

        orientation = (
            Qt.Orientation.Vertical
            if stacked
            else Qt.Orientation.Horizontal
        )

        splitter_configs = (
            (
                self.list_splitter,
                self.details_panel,
                [620, 360]
                if stacked
                else [1080, 420],
            ),
            (
                self.gallery_splitter,
                self.gallery_details_panel,
                [620, 360]
                if stacked
                else [1050, 400],
            ),
        )

        for splitter, detail_panel, sizes in splitter_configs:
            if splitter is None:
                continue

            detail_panel.set_stacked_mode(
                stacked
            )

            changed = (
                splitter.orientation()
                != orientation
            )

            if changed:
                splitter.setOrientation(
                    orientation
                )

            if changed or force:
                splitter.setSizes(
                    sizes
                )

        if mode == "tight":
            self.view_title_label.hide()
            self.list_view_button.setMinimumWidth(86)
            self.gallery_view_button.setMinimumWidth(86)
        else:
            self.view_title_label.show()
            self.list_view_button.setMinimumWidth(104)
            self.gallery_view_button.setMinimumWidth(104)

        style = self.style()
        style.unpolish(self)
        style.polish(self)

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        # Scan
        self.scan_controller.progress.connect(
            self._on_scan_progress
        )
        self.scan_controller.finished.connect(
            self._on_scan_finished
        )
        self.scan_controller.failed.connect(
            self._on_scan_failed
        )
        self.scan_controller.cancelled.connect(
            self._on_scan_cancelled
        )

        # Import
        self.import_controller.progress.connect(
            self._on_import_progress
        )
        self.import_controller.finished.connect(
            self._on_import_finished
        )
        self.import_controller.failed.connect(
            self._on_import_failed
        )
        self.import_controller.cancelled.connect(
            self._on_import_cancelled
        )

        # Bulk
        self.bulk_controller.progress.connect(
            self._on_bulk_progress
        )
        self.bulk_controller.finished.connect(
            self._on_bulk_finished
        )
        self.bulk_controller.failed.connect(
            self._on_bulk_failed
        )

        # List
        self.mod_list_widget.info_requested.connect(
            self.mod_info_controller.show_mod
        )
        self.mod_list_widget.enable_requested.connect(
            partial(
                self._start_bulk_action,
                BulkAction.ENABLE,
            )
        )
        self.mod_list_widget.disable_requested.connect(
            partial(
                self._start_bulk_action,
                BulkAction.DISABLE,
            )
        )
        self.mod_list_widget.adopt_requested.connect(
            partial(
                self._start_bulk_action,
                BulkAction.ADOPT,
            )
        )
        self.mod_list_widget.cancel_requested.connect(
            self.cancel_bulk_action
        )
        self.mod_list_widget.selection_changed.connect(
            self._refresh_selection_ui
        )

        # List detail panel
        self.details_panel.toggle_requested.connect(
            self._toggle_selected_mod
        )
        self.details_panel.adopt_requested.connect(
            self._ignore_selected_conflict
        )
        self.details_panel.info_requested.connect(
            self.mod_info_controller.show_selected_mod
        )

        if hasattr(
            self.details_panel,
            "gamebanana_id_requested",
        ):
            self.details_panel.gamebanana_id_requested.connect(
                self._edit_selected_gamebanana_id
            )

        # Gallery cards
        self.gallery_widget.toggle_requested.connect(
            self._toggle_gallery_mod
        )

        if hasattr(
            self.gallery_widget,
            "info_requested",
        ):
            self.gallery_widget.info_requested.connect(
                self.mod_info_controller.show_mod
            )

        # Gallery detail panel
        self.gallery_details_panel.toggle_requested.connect(
            self._toggle_gallery_selected_mod
        )
        self.gallery_details_panel.info_requested.connect(
            self._show_gallery_selected_mod_info
        )

        # View switch
        self.list_view_button.clicked.connect(
            lambda _checked=False:
            self._set_library_view(
                0
            )
        )
        self.gallery_view_button.clicked.connect(
            lambda _checked=False:
            self._set_library_view(
                1
            )
        )

        # Empty Library -> Import
        self.empty_state.import_archives_requested.connect(
            self._choose_import_archives
        )

        self.empty_state.import_directory_requested.connect(
            self._choose_import_directory
        )

        self.filter_empty_state.reset_requested.connect(
            self.filter_bar.reset_filters
        )

        # Filters
        self.filter_bar.filters_changed.connect(
            self._apply_mod_filters
        )

    # ========================================================
    # View
    # ========================================================

    def _set_library_view(
        self,
        index: int,
        *,
        reapply_filters: bool = True,
    ) -> None:
        index = (
            1
            if index == 1
            else 0
        )

        self.content_stack.setCurrentIndex(
            index
        )

        self.list_view_button.setChecked(
            index == 0
        )

        self.gallery_view_button.setChecked(
            index == 1
        )

        if hasattr(
            self.config,
            "library_view_mode",
        ):
            self.config.library_view_mode = (
                "gallery"
                if index == 1
                else "list"
            )

        self._retranslate_view_buttons()

        if reapply_filters:
            self._apply_mod_filters()

    def _retranslate_view_buttons(
        self,
    ) -> None:
        self.view_title_label.setText(
            tr(
                "library.view.title"
            )
        )

        self.list_view_button.setText(
            "☷  "
            + tr(
                "library.view.list"
            )
        )

        self.gallery_view_button.setText(
            "▦  "
            + tr(
                "library.view.gallery"
            )
        )

    def _on_language_changed(
        self,
        _language: str | None = None,
    ) -> None:
        self._retranslate_view_buttons()
        self.empty_state.retranslate_ui()
        self.filter_empty_state.retranslate_ui()
        self._apply_mod_filters()
        self._refresh_selection_ui()

        retranslate = getattr(
            self.gallery_details_panel,
            "retranslate_ui",
            None,
        )

        if callable(
            retranslate
        ):
            retranslate()

    # ========================================================
    # Selection
    # ========================================================

    def _refresh_selection_ui(
        self,
        *_args,
    ) -> None:
        self.selection_controller.refresh()

        self._sync_gallery_operation_state()

        selected_mods = (
            self.selection_controller
            .selected_mods()
        )

        self.details_panel.set_metadata_edit_enabled(
            (
                len(
                    selected_mods
                )
                == 1
            )
            and not (
                self.operation_state
                .is_running()
            )
        )

        self.details_panel.retranslate_ui()

    # ========================================================
    # Gallery Operation State
    # ========================================================

    def _sync_gallery_operation_state(
        self,
    ) -> None:
        running = (
            self.operation_state
            .is_running()
        )

        self.gallery_widget.set_operation_running(
            running
        )

        mod = self._selected_gallery_mod()

        if mod is None:
            self.gallery_details_panel.toggle_button.setEnabled(
                False
            )
            return

        state = (
            self.mod_action_controller
            .get_state_for_path(
                mod.path
            )
        )

        can_toggle = state in {
            ModState.ENABLED,
            ModState.DISABLED,
            ModState.BROKEN,
        }

        self.gallery_details_panel.toggle_button.setEnabled(
            can_toggle
            and not running
        )

    def _connect_gallery_card_selection_signals(
        self,
    ) -> None:
        """
        Verbindet die Card-Auswahl mit dem Gallery-Detailpanel.

        Die aktuelle Gallery besitzt selected_requested bereits auf
        LibraryModCard. Dadurch bleibt dieses Rework kompatibel, ohne
        eine zweite Ersatzdatei für library_gallery.py zu verlangen.
        """

        cards = getattr(
            self.gallery_widget,
            "_cards",
            (),
        )

        for card in cards:
            signal = getattr(
                card,
                "selected_requested",
                None,
            )

            if signal is None:
                continue

            try:
                signal.disconnect(
                    self._on_gallery_selection_changed
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            signal.connect(
                self._on_gallery_selection_changed
            )

    def _selected_gallery_mod(
        self,
    ) -> ModInfo | None:
        if self._gallery_selected_mod is not None:
            return self._gallery_selected_mod

        selected_card = getattr(
            self.gallery_widget,
            "_selected_card",
            None,
        )

        if selected_card is None:
            return None

        mod = getattr(
            selected_card,
            "mod",
            None,
        )

        if isinstance(
            mod,
            ModInfo,
        ):
            return mod

        return None

    def _on_gallery_selection_changed(
        self,
        mod: object,
    ) -> None:
        if not isinstance(
            mod,
            ModInfo,
        ):
            self._gallery_selected_mod = None
            self.gallery_details_panel.show_empty()
            return

        self._gallery_selected_mod = mod

        state = (
            self.mod_action_controller
            .get_state_for_path(
                mod.path
            )
        )

        self.gallery_details_panel.show_mod(
            mod=mod,
            state=state,
        )

        if hasattr(
            self.gallery_details_panel,
            "set_metadata_edit_enabled",
        ):
            self.gallery_details_panel.set_metadata_edit_enabled(
                False
            )

        can_toggle = state in {
            ModState.ENABLED,
            ModState.DISABLED,
            ModState.BROKEN,
        }

        self.gallery_details_panel.toggle_button.setEnabled(
            can_toggle
            and not (
                self.operation_state
                .is_running()
            )
        )

    def _toggle_gallery_selected_mod(
        self,
    ) -> None:
        mod = self._selected_gallery_mod()

        if mod is None:
            return

        self._toggle_gallery_mod(
            mod
        )

    def _show_gallery_selected_mod_info(
        self,
    ) -> None:
        mod = self._selected_gallery_mod()

        if mod is None:
            return

        self.mod_info_controller.show_mod(
            mod
        )

    # ========================================================
    # Statistics
    # ========================================================

    def _update_stats(
        self,
    ) -> None:
        stats = (
            self.mod_list_widget
            .statistics()
        )

        # ----------------------------------------------------
        # Konfliktzahl kommt NICHT mehr nur aus der Tabelle.
        #
        # Dadurch zählen auch manuell in XXMI abgelegte Mods.
        # ----------------------------------------------------

        conflict_count = (
            self._conflict_report
            .count
        )

        self.stats_widget.set_values(
            total=stats.total,
            active=stats.active,
            conflicts=conflict_count,
            characters=stats.characters,
        )

        self.conflict_count_changed.emit(
            conflict_count
        )

    # ========================================================
    # Conflict Scanner
    # ========================================================

    def refresh_conflicts(
        self,
    ) -> None:
        report = (
            self.conflict_scanner
            .scan(
                self._last_scanned_mods
            )
        )

        self._conflict_report = report

        self.conflict_count_changed.emit(
            report.count
        )

        self.conflict_report_changed.emit(
            report
        )

        self._update_stats()

    def conflict_report(
        self,
    ) -> ConflictReport:
        return (
            self._conflict_report
        )

    # ========================================================
    # Conflict Page: Adopt
    # ========================================================

    def adopt_conflict(
        self,
        conflict: ConflictItem,
    ) -> None:
        """
        Nur echte Library-Konflikte dürfen automatisch
        übernommen werden.

        Unmanaged Active Mods bleiben unangetastet.
        """

        if (
            not conflict.can_adopt
            or conflict.library_mod_path
            is None
        ):
            QMessageBox.information(
                self,
                tr(
                    "conflicts.manual.title"
                ),
                tr(
                    "conflicts.manual.message"
                ),
            )

            return

        target_path = (
            Path(
                conflict
                .library_mod_path
            )
            .expanduser()
            .absolute()
        )

        mod = next(
            (
                candidate
                for candidate
                in self._last_scanned_mods
                if (
                    Path(
                        candidate.path
                    )
                    .expanduser()
                    .absolute()
                    == target_path
                )
            ),
            None,
        )

        if mod is None:
            return

        problem = (
            self.mod_action_controller
            .validate_adopt(
                mod
            )
        )

        if problem is not None:
            show_mod_action_problem(
                result=problem,
                parent=self,
            )

            return

        if not confirm_adopt_existing(
            mod_name=(
                mod.name
            ),
            parent=self,
        ):
            return

        try:
            result = (
                self.mod_action_controller
                .adopt(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog.adopt_failed"
                ),
                str(
                    error
                ),
            )

            return

        if show_mod_action_problem(
            result=result,
            parent=self,
        ):
            return

        self._sync_mod_state(
            mod=mod,
            state=result.state,
        )

        self.operation_status.set_status(
            result.message
        )

    # ========================================================
    # Import UI
    # ========================================================

    def _set_import_ui_running(
        self,
        running: bool,
        source_count: int = 0,
    ) -> None:
        self.header_controller.refresh()

        if running:
            self.operation_status.start_import(
                source_count
            )

        else:
            self.operation_status.finish_operation()

        self._refresh_selection_ui()

        self._sync_gallery_operation_state()

        self.empty_state.set_actions_enabled(
            not running
        )

    # ========================================================
    # Import Picker
    # ========================================================

    def _choose_import_archives(
        self,
    ) -> None:
        paths = choose_import_archives(
            parent=self
        )

        if not paths:
            return

        self._request_import(
            paths
        )

    def _choose_import_directory(
        self,
    ) -> None:
        paths = choose_import_directory(
            parent=self
        )

        if not paths:
            return

        self._request_import(
            paths
        )

    # ========================================================
    # Import
    # ========================================================

    def _request_import(
        self,
        paths: list[
            Path
        ],
    ) -> bool:
        blocking_operation = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.IMPORT
            )
        )

        if blocking_operation is not None:
            show_operation_blocked(
                requested=(
                    LibraryOperation.IMPORT
                ),
                blocking=(
                    blocking_operation
                ),
                parent=self,
            )

            return False

        prepared_import = (
            prepare_import_request(
                paths=paths,
                parent=self,
            )
        )

        if prepared_import is None:
            return False

        # ====================================================
        # WICHTIG:
        # Controller ZUERST starten.
        # UI ERST DANACH auf running setzen.
        # ====================================================

        started = (
            self.import_controller
            .start(
                sources=(
                    prepared_import
                    .sources
                ),
                library_root=(
                    self.game_scope
                    .mod_library_directory
                ),
                options=(
                    prepared_import
                    .options
                ),
            )
        )

        if not started:
            QMessageBox.warning(
                self,
                tr(
                    "library.dialog.import.title"
                ),
                tr(
                    "library.status.import_start_failed"
                ),
            )

            return False

        self._set_import_ui_running(
            True,
            source_count=len(
                prepared_import.sources
            ),
        )

        self.operation_status.set_status(
            tr(
                "library.status.import_started"
            )
        )

        return True

    def _on_import_progress(
        self,
        current: int,
        total: int,
        source_name: str,
    ) -> None:
        self.operation_status.update_import_progress(
            current=current,
            total=total,
            source_name=source_name,
        )

    def _on_import_finished(
        self,
        result: ImportBatchResult,
    ) -> None:
        metadata_errors = (
            self._apply_pending_gamebanana_metadata(
                result
            )
        )

        self._set_import_ui_running(
            False
        )

        message = (
            format_import_result(
                result
            )
        )

        title = tr(
            "library.dialog.import.completed"
        )

        dialog = (
            QMessageBox.warning
            if result.failed_count
            else QMessageBox.information
        )

        dialog(
            self,
            title,
            message,
        )

        if metadata_errors:
            QMessageBox.warning(
                self,
                tr(
                    "library.gamebanana_metadata.error.title"
                ),
                tr(
                    "library.gamebanana_metadata.error.message",
                    errors=(
                        "\n".join(
                            metadata_errors
                        )
                    ),
                ),
            )

        self.operation_status.set_status(
            format_import_status(
                result
            )
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    def _on_import_failed(
        self,
        message: str,
    ) -> None:
        self._pending_gamebanana_imports.clear()

        self._set_import_ui_running(
            False
        )

        QMessageBox.critical(
            self,
            tr(
                "library.dialog.import.failed"
            ),
            message,
        )

        self.operation_status.set_status(
            tr(
                "library.status.import_failed"
            )
        )

    def _on_import_cancelled(
        self,
    ) -> None:
        self._pending_gamebanana_imports.clear()

        self._set_import_ui_running(
            False
        )

        self.operation_status.set_status(
            tr(
                "library.status.import_cancelled"
            )
        )

    # ========================================================
    # External Import
    # ========================================================

    def request_external_import(
        self,
        paths: list[
            Path
        ],
    ) -> bool:
        normalized_paths = [
            Path(
                path
            )
            .expanduser()
            .absolute()
            for path
            in paths
        ]

        return self._request_import(
            normalized_paths
        )

    # ========================================================
    # GameBanana Import
    # ========================================================

    def request_gamebanana_import(
        self,
        *,
        path: Path,
        game_id: str,
        mod_id: int,
    ) -> bool:
        source = (
            Path(
                path
            )
            .expanduser()
            .absolute()
        )

        if not source.is_file():
            return False

        if (
            game_id
            != self.game_scope.game_id
        ):
            return False

        if mod_id <= 0:
            return False

        key = (
            self._import_source_key(
                source
            )
        )

        self._pending_gamebanana_imports[
            key
        ] = (
            game_id,
            int(
                mod_id
            ),
        )

        started = (
            self._request_import(
                [
                    source
                ]
            )
        )

        if not started:
            self._pending_gamebanana_imports.pop(
                key,
                None,
            )

        return started

    def _apply_pending_gamebanana_metadata(
        self,
        result: ImportBatchResult,
    ) -> list[
        str
    ]:
        errors: list[
            str
        ] = []

        for item in result.items:
            key = (
                self._import_source_key(
                    item.source
                )
            )

            pending = (
                self._pending_gamebanana_imports
                .pop(
                    key,
                    None,
                )
            )

            if pending is None:
                continue

            (
                game_id,
                mod_id,
            ) = pending

            if (
                item.status
                != ImportStatus.IMPORTED
                or item.destination
                is None
            ):
                continue

            try:
                set_gamebanana_mod_id(
                    item.destination,
                    game_id=(
                        game_id
                    ),
                    mod_id=(
                        mod_id
                    ),
                )

            except (
                OSError,
                ValueError,
            ) as error:
                errors.append(
                    (
                        f"{item.destination.name}: "
                        f"{error}"
                    )
                )

        return errors

    @staticmethod
    def _import_source_key(
        path: Path,
    ) -> str:
        return str(
            Path(
                path
            )
            .expanduser()
            .absolute()
        )

    # ========================================================
    # Cancel Import
    # ========================================================

    def cancel_import(
        self,
    ) -> None:
        if not (
            self.import_controller
            .cancel()
        ):
            return

        self.header_controller.mark_import_cancel_requested()

        self.operation_status.set_status(
            tr(
                "library.status.import_cancelling"
            )
        )

    # ========================================================
    # Scan
    # ========================================================

    def scan_mods(
        self,
    ) -> None:
        if not (
            self._prepare_scan_start()
        ):
            return

        mods_directory = (
            self.game_scope
            .mod_library_directory
        )

        try:
            mods_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as error:
            self.operation_status.set_status(
                tr(
                    "library.status.directory_failed"
                )
            )

            QMessageBox.critical(
                self,
                tr(
                    "library.error.directory.title"
                ),
                str(
                    error
                ),
            )

            return

        request_status = (
            self.scan_controller
            .request_scan(
                root_path=(
                    mods_directory
                )
            )
        )

        if (
            request_status
            == ScanRequestStatus.FAILED
        ):
            self.operation_status.set_status(
                tr(
                    "library.status.scan_start_failed"
                )
            )

            return

        if (
            request_status
            == ScanRequestStatus.RESTART_QUEUED
        ):
            self.operation_status.set_status(
                tr(
                    "library.status.scan_restart"
                )
            )

            return

        # ====================================================
        # request_scan() ist jetzt erfolgreich.
        # Erst jetzt UI sperren.
        # ====================================================

        self._set_scan_ui_running(
            True
        )

        self.filter_bar.set_path_text(
            str(
                mods_directory
            )
        )

        self.filter_bar.set_location_text(
            tr(
                "library.location.checking"
            )
        )

        self.operation_status.set_status(
            tr(
                "library.status.scan_started"
            )
        )

    def _prepare_scan_start(
        self,
    ) -> bool:
        blocking_operation = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.SCAN
            )
        )

        if blocking_operation is None:
            return True

        self.operation_status.set_status(
            operation_block_message(
                requested=(
                    LibraryOperation.SCAN
                ),
                blocking=(
                    blocking_operation
                ),
            )
        )

        return False

    def _set_scan_ui_running(
        self,
        running: bool,
    ) -> None:
        self.header_controller.refresh()

        if running:
            self.operation_status.start_scan()

        else:
            self.operation_status.finish_operation()

        self._refresh_selection_ui()

        self._sync_gallery_operation_state()

        self.empty_state.set_actions_enabled(
            not running
        )

    def cancel_scan(
        self,
    ) -> None:
        self.scan_controller.cancel()

    # ========================================================
    # Scan Callbacks
    # ========================================================

    def _on_scan_progress(
        self,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.operation_status.update_scan_progress(
            current=current,
            total=total,
            mod_name=mod_name,
        )

    def _on_scan_finished(
        self,
        result: ScanResult,
    ) -> None:
        self._display_result(
            result
        )

        location = (
            tr(
                "library.location.network"
            )
            if result.is_network
            else tr(
                "library.location.local"
            )
        )

        self.filter_bar.set_location_text(
            location
        )

        self.operation_status.set_status(
            tr(
                "library.status.scan_result",
                count=len(
                    result.mods
                ),
                seconds=(
                    result.duration_seconds
                ),
            )
        )

        self._set_scan_ui_running(
            False
        )

    def _on_scan_failed(
        self,
        message: str,
    ) -> None:
        self._set_scan_ui_running(
            False
        )

        self.operation_status.set_status(
            tr(
                "library.status.scan_failed"
            )
        )

        QMessageBox.critical(
            self,
            tr(
                "library.dialog.scan.failed"
            ),
            message,
        )

    def _on_scan_cancelled(
        self,
    ) -> None:
        self._set_scan_ui_running(
            False
        )

        self.operation_status.set_status(
            tr(
                "library.status.scan_cancelled"
            )
        )

    # ========================================================
    # Scan Result
    # ========================================================

    def _display_result(
        self,
        result: ScanResult,
    ) -> None:
        self._last_scanned_mods = (
            tuple(
                result.mods
            )
        )

        state_provider = (
            self.mod_action_controller
            .get_state_for_path
        )

        self.mod_list_widget.set_mods(
            mods=result.mods,
            state_provider=state_provider,
        )

        # Neue Gallery-Card-Liste bedeutet auch eine neue Auswahl.
        self._gallery_selected_mod = None
        self.gallery_details_panel.show_empty()

        self.gallery_widget.set_mods(
            mods=result.mods,
            state_provider=state_provider,
        )

        self._connect_gallery_card_selection_signals()

        self.filter_bar.set_mods(
            result.mods
        )

        self._library_scan_completed = True

        self._apply_mod_filters()
        self.refresh_conflicts()

    # ========================================================
    # Filter
    # ========================================================

    def _apply_mod_filters(
        self,
        _value: object | None = None,
    ) -> None:
        search_term = (
            self.filter_bar
            .search_term()
        )

        character = (
            self.filter_bar
            .selected_character()
        )

        mod_type = (
            self.filter_bar
            .selected_mod_type()
        )

        status = (
            self.filter_bar
            .selected_status()
        )

        list_visible = (
            self.mod_list_widget
            .apply_filters(
                search_term=search_term,
                character=character,
                mod_type=mod_type,
                status=status,
            )
        )

        gallery_visible = (
            self.gallery_widget
            .apply_filters(
                search_term=search_term,
                character=character,
                mod_type=mod_type,
                status=status,
            )
        )

        total_mods = (
            self.mod_list_widget
            .row_count()
        )

        visible_mods = (
            gallery_visible
            if (
                self.content_stack.currentIndex()
                == 1
            )
            else list_visible
        )

        filter_text = tr(
            "library.status.filter_result",
            visible=visible_mods,
            total=total_mods,
        )

        self.view_count_label.setText(
            filter_text
        )

        self.operation_status.set_status(
            filter_text
        )

        self._refresh_selection_ui()

        self._sync_library_empty_state(
            total_mods=total_mods,
            visible_mods=visible_mods,
        )

    # ========================================================
    # Empty Library / Empty Filter Result
    # ========================================================

    def _sync_library_empty_state(
        self,
        *,
        total_mods: int | None = None,
        visible_mods: int | None = None,
    ) -> None:
        """
        Drei klar getrennte Zustände:

        1. total == 0
           -> echte leere Library
           -> Import / Mod-Ordner

        2. total > 0 und visible == 0
           -> Filter liefern keine Treffer
           -> Filter zurücksetzen

        3. visible > 0
           -> normale List-/Gallery-Ansicht
        """

        if not self._library_scan_completed:
            self.workspace_state_stack.setCurrentIndex(
                0
            )
            return

        if total_mods is None:
            total_mods = len(
                self._last_scanned_mods
            )

        total_mods = max(
            0,
            int(total_mods),
        )

        # Wirklich leere Bibliothek.
        if total_mods == 0:
            self.empty_state.set_actions_enabled(
                not self.operation_state.is_running()
            )

            self.workspace_state_stack.setCurrentWidget(
                self.empty_state
            )
            return

        # Wenn die Methode ohne sichtbare Anzahl aufgerufen wird,
        # bleibt bei vorhandenen Mods zunächst die normale Ansicht.
        if visible_mods is None:
            self.workspace_state_stack.setCurrentIndex(
                0
            )
            return

        visible_mods = max(
            0,
            int(visible_mods),
        )

        # Mods existieren, aber Filter treffen nichts.
        if visible_mods == 0:
            self.filter_empty_state.set_total_mods(
                total_mods
            )

            self.workspace_state_stack.setCurrentWidget(
                self.filter_empty_state
            )
            return

        # Normalfall.
        self.workspace_state_stack.setCurrentIndex(
            0
        )

    # ========================================================
    # State Sync
    # ========================================================

    def _sync_mod_state(
        self,
        *,
        mod: ModInfo,
        state: (
            ModState
            | None
        ) = None,
        reapply_filters: bool = True,
    ) -> ModState:
        if state is None:
            state = (
                self.mod_action_controller
                .get_state_for_path(
                    mod.path
                )
            )

        self.mod_list_widget.update_mod_state(
            mod=mod,
            state=state,
        )

        self.gallery_widget.update_mod_state(
            mod=mod,
            state=state,
        )

        gallery_mod = self._selected_gallery_mod()

        if (
            gallery_mod is not None
            and gallery_mod.path == mod.path
        ):
            self._gallery_selected_mod = mod

            self.gallery_details_panel.show_mod(
                mod=mod,
                state=state,
            )

            if hasattr(
                self.gallery_details_panel,
                "set_metadata_edit_enabled",
            ):
                self.gallery_details_panel.set_metadata_edit_enabled(
                    False
                )

            can_toggle = state in {
                ModState.ENABLED,
                ModState.DISABLED,
                ModState.BROKEN,
            }

            self.gallery_details_panel.toggle_button.setEnabled(
                can_toggle
                and not (
                    self.operation_state
                    .is_running()
                )
            )

        if reapply_filters:
            self._apply_mod_filters()
        else:
            self._refresh_selection_ui()

        self.refresh_conflicts()

        return state

    # ========================================================
    # Detailpanel Toggle
    # ========================================================

    def _toggle_selected_mod(
        self,
    ) -> None:
        mod = (
            self.selection_controller
            .selected_mod()
        )

        if mod is None:
            return

        if (
            self.operation_state
            .is_running()
        ):
            return

        try:
            result = (
                self.mod_action_controller
                .toggle(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog.mod_management_failed"
                ),
                str(
                    error
                ),
            )

            return

        if show_mod_action_problem(
            result=result,
            parent=self,
        ):
            self._sync_mod_state(
                mod=mod,
                state=result.state,
            )

            return

        self._sync_mod_state(
            mod=mod,
            state=result.state,
        )

        self.operation_status.set_status(
            result.message
        )

    # ========================================================
    # Galerie Toggle
    # ========================================================

    def _toggle_gallery_mod(
        self,
        mod: ModInfo,
    ) -> None:
        if (
            self.operation_state
            .is_running()
        ):
            return

        try:
            result = (
                self.mod_action_controller
                .toggle(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog.mod_management_failed"
                ),
                str(
                    error
                ),
            )

            return

        if show_mod_action_problem(
            result=result,
            parent=self,
        ):
            self._sync_mod_state(
                mod=mod,
                state=result.state,
            )

            return

        self._sync_mod_state(
            mod=mod,
            state=result.state,
        )

        self.operation_status.set_status(
            result.message
        )

    # ========================================================
    # Selected Conflict Adopt
    # ========================================================

    def _ignore_selected_conflict(
        self,
    ) -> None:
        mod = (
            self.selection_controller
            .selected_mod()
        )

        if mod is None:
            return

        problem = (
            self.mod_action_controller
            .validate_adopt(
                mod
            )
        )

        if problem is not None:
            show_mod_action_problem(
                result=problem,
                parent=self,
            )

            return

        if not confirm_adopt_existing(
            mod_name=(
                mod.name
            ),
            parent=self,
        ):
            return

        try:
            result = (
                self.mod_action_controller
                .adopt(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog.adopt_failed"
                ),
                str(
                    error
                ),
            )

            return

        if show_mod_action_problem(
            result=result,
            parent=self,
        ):
            return

        self._sync_mod_state(
            mod=mod,
            state=result.state,
        )

        self.operation_status.set_status(
            result.message
        )

    # ========================================================
    # GameBanana-ID bearbeiten
    # ========================================================

    def _edit_selected_gamebanana_id(
        self,
    ) -> None:
        if (
            self.operation_state
            .is_running()
        ):
            return

        selected = (
            self.selection_controller
            .selected_mods()
        )

        if len(
            selected
        ) != 1:
            return

        mod = selected[
            0
        ]

        metadata = (
            load_mod_metadata(
                mod.path
            )
        )

        current_value = (
            metadata
            .gamebanana_mod_id
            or 1
        )

        (
            mod_id,
            accepted,
        ) = QInputDialog.getInt(
            self,
            tr(
                "library.gamebanana_id.dialog.title"
            ),
            tr(
                "library.gamebanana_id.dialog.message",
                mod_name=(
                    mod.name
                ),
            ),
            current_value,
            1,
            2_147_483_647,
            1,
        )

        if not accepted:
            return

        try:
            set_gamebanana_mod_id(
                mod.path,
                game_id=(
                    self.game_scope
                    .game_id
                ),
                mod_id=(
                    mod_id
                ),
            )

        except (
            OSError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.gamebanana_id.error.title"
                ),
                tr(
                    "library.gamebanana_id.error.message",
                    error=(
                        error
                    ),
                ),
            )

            return

        state = (
            self.mod_action_controller
            .get_state_for_path(
                mod.path
            )
        )

        self.details_panel.show_mod(
            mod=mod,
            state=state,
        )

        self._refresh_selection_ui()

        self.operation_status.set_status(
            tr(
                "library.gamebanana_id.status.saved",
                mod_name=(
                    mod.name
                ),
                mod_id=(
                    mod_id
                ),
            )
        )

    # ========================================================
    # Bulk
    # ========================================================

    def _can_start_bulk_action(
        self,
        selected_mods: list[
            ModInfo
        ],
    ) -> bool:
        blocking_operation = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.BULK
            )
        )

        if blocking_operation is not None:
            show_operation_blocked(
                requested=(
                    LibraryOperation.BULK
                ),
                blocking=(
                    blocking_operation
                ),
                parent=self,
            )

            return False

        if not selected_mods:
            QMessageBox.information(
                self,
                tr(
                    "library.dialog.no_selection.title"
                ),
                tr(
                    "library.dialog.no_selection.message"
                ),
            )

            return False

        return True

    def _start_bulk_action(
        self,
        action: BulkAction,
        _checked: bool = False,
    ) -> None:
        selected_mods = (
            self.selection_controller
            .selected_mods()
        )

        if not (
            self._can_start_bulk_action(
                selected_mods
            )
        ):
            return

        confirmation = (
            confirm_bulk_action(
                action=action,
                selected_count=len(
                    selected_mods
                ),
                parent=self,
            )
        )

        if confirmation is None:
            return

        # ====================================================
        # WICHTIG:
        # Controller zuerst.
        # UI danach.
        # ====================================================

        started = (
            self.bulk_controller
            .start(
                mods=(
                    selected_mods
                ),
                action=(
                    action
                ),
            )
        )

        if not started:
            QMessageBox.warning(
                self,
                tr(
                    "library.dialog.bulk.title"
                ),
                tr(
                    "library.status.bulk_start_failed"
                ),
            )

            return

        self._set_bulk_ui_running(
            running=True,
            item_count=len(
                selected_mods
            ),
        )

        started_key = {
            BulkAction.ENABLE: (
                "library.status."
                "bulk_enable_started"
            ),
            BulkAction.DISABLE: (
                "library.status."
                "bulk_disable_started"
            ),
            BulkAction.ADOPT: (
                "library.status."
                "bulk_adopt_started"
            ),
        }[
            action
        ]

        self.operation_status.set_status(
            tr(
                started_key
            )
        )

    def _set_bulk_ui_running(
        self,
        running: bool,
        item_count: int = 0,
    ) -> None:
        self.mod_list_widget.set_bulk_operation_running(
            running
        )

        self.header_controller.refresh()

        if running:
            self.operation_status.start_bulk(
                item_count
            )

        else:
            self.operation_status.finish_operation()

        self._refresh_selection_ui()

        self._sync_gallery_operation_state()

    def _on_bulk_progress(
        self,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.operation_status.update_bulk_progress(
            current=current,
            total=total,
            mod_name=mod_name,
        )

    def _on_bulk_finished(
        self,
        result: BulkBatchResult,
    ) -> None:
        self._set_bulk_ui_running(
            running=False
        )

        message = (
            format_bulk_result(
                result
            )
        )

        title = tr(
            "library.dialog.bulk.completed"
        )

        dialog = (
            QMessageBox.warning
            if bulk_result_requires_warning(
                result
            )
            else QMessageBox.information
        )

        dialog(
            self,
            title,
            message,
        )

        self.operation_status.set_status(
            format_bulk_status(
                result
            )
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    def _on_bulk_failed(
        self,
        message: str,
    ) -> None:
        self._set_bulk_ui_running(
            running=False
        )

        QMessageBox.critical(
            self,
            tr(
                "library.dialog.bulk.failed"
            ),
            message,
        )

        self.operation_status.set_status(
            tr(
                "library.status.bulk_failed"
            )
        )

    def cancel_bulk_action(
        self,
    ) -> None:
        if not (
            self.bulk_controller
            .cancel()
        ):
            return

        self.mod_list_widget.mark_bulk_cancel_requested()

        self.operation_status.set_status(
            tr(
                "library.status.bulk_cancelling"
            )
        )

    # ========================================================
    # Game Switch
    # ========================================================

    def can_change_game(
        self,
    ) -> bool:
        return not (
            self.operation_state
            .is_running()
        )

    def on_game_changed(
        self,
        game_id: str,
    ) -> None:
        if (
            self.operation_state
            .is_running()
        ):
            return

        # ----------------------------------------------------
        # Doppelten Startup-Scan vermeiden.
        # ----------------------------------------------------

        if (
            game_id
            == self.game_scope.game_id
        ):
            return

        self.game_scope.set_game(
            game_id
        )

        self._pending_gamebanana_imports.clear()

        self._library_scan_completed = False

        self.workspace_state_stack.setCurrentIndex(
            0
        )

        self._last_scanned_mods = ()

        self._conflict_report = (
            ConflictReport()
        )

        # ----------------------------------------------------
        # Alte UI-Daten sofort entfernen.
        # ----------------------------------------------------

        self.mod_list_widget.set_mods(
            mods=[],
            state_provider=(
                self.mod_action_controller
                .get_state_for_path
            ),
        )

        self.gallery_widget.clear()

        self.filter_bar.set_mods(
            []
        )

        mods_directory = (
            self.game_scope
            .mod_library_directory
        )

        self.filter_bar.set_path_text(
            str(
                mods_directory
            )
        )

        self.filter_bar.set_location_text(
            tr(
                "library.location.checking"
            )
        )

        self.stats_widget.set_values(
            total=0,
            active=0,
            conflicts=0,
            characters=0,
        )

        self.conflict_count_changed.emit(
            0
        )

        self.conflict_report_changed.emit(
            self._conflict_report
        )

        self._refresh_selection_ui()

        self.operation_status.set_status(
            tr(
                "library.status.game_changed",
                game=(
                    self.game_scope
                    .game
                    .name
                ),
            )
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    # ========================================================
    # Stylesheet
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        style_path = (
            Path(
                __file__
            )
            .resolve()
            .parents[
                1
            ]
            / "styles"
            / "library.qss"
        )

        try:
            stylesheet = (
                style_path.read_text(
                    encoding="utf-8"
                )
            )

        except OSError as error:
            raise RuntimeError(
                tr(
                    "library.error.stylesheet_load",
                    path=(
                        style_path
                    ),
                )
            ) from error

        self.setStyleSheet(
            stylesheet
        )

    # ========================================================
    # Public Conflict / Duplicate API
    # ========================================================

    def library_mod_paths(
        self,
    ) -> tuple[
        Path,
        ...,
    ]:
        return tuple(
            Path(
                mod.path
            )
            for mod
            in self._last_scanned_mods
        )

    def current_game_id(
        self,
    ) -> str:
        return (
            self.game_scope
            .game_id
        )

    def active_mods_root(
        self,
    ) -> Path:
        return (
            self.game_scope
            .active_mods_directory
        )

    # ========================================================
    # Profiles API
    # ========================================================

    def profile_mods(
        self,
    ) -> tuple[
        ModInfo,
        ...,
    ]:
        return tuple(
            self._last_scanned_mods
        )

    def profile_mod_state(
        self,
        path: Path,
    ) -> ModState:
        return self.mod_manager.get_state(
            path
        )

    def profile_mod_manager(
        self,
    ) -> ModManager:
        return self.mod_manager

    def profile_operations_running(
        self,
    ) -> bool:
        return self.operation_state.is_running()

__all__ = [
    "LibraryPage",
]