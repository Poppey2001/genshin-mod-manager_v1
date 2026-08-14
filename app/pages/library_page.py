from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
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
from app.widgets.library.library_gallery import (
    LibraryGalleryWidget,
)

from app.config import AppConfig

from app.games import (
    GameScope,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.models.mod import ModInfo

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

from app.services.mod_importer import (
    ImportBatchResult,
    ImportStatus
)

from app.services.mod_manager import (
    ModManager,
    ModManagerError,
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
    """
    Mod-Bibliothek des aktuell
    ausgewählten XXMI-Spiels.
    """

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config

        # ====================================================
        # Game Scope / gemeinsamer ModManager
        # ====================================================

        self.game_scope = GameScope(
            config=self.config,
            game_id=(
                self.config.selected_game
            ),
        )

        self.mod_manager = ModManager(
            config=self.game_scope
        )

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
        # Widgets
        # ====================================================

        self.operation_status = (
            LibraryOperationStatusWidget(
                parent=self
            )
        )

        self.mod_list_widget = (
            LibraryModListWidget(
                parent=self
            )
        )

        self.filter_bar = (
            LibraryFilterBar(
                parent=self
            )
        )

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

        self.details_panel = (
            ModDetailsPanel(
                parent=self
            )
        )
        self._pending_gamebanana_imports: dict[
            str,
            tuple[
                str,
                int,
            ],
        ] = {}
        
        # ====================================================
        # Zweite Library-Ansicht
        # ====================================================

        self.gallery_widget = (
            LibraryGalleryWidget(
                parent=self
            )
        )

        self.content_stack = (
            QStackedWidget(
                self
            )
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

        # ====================================================
        # Selection Controller
        #
        # WICHTIG:
        # operation_running_provider bleibt Callable.
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
                    self.operation_state.is_running
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
        # Header
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

        self._connect_signals()

        self._build_ui()

        translation_manager.language_changed.connect(
            self._on_language_changed
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )
        
        self._retranslate_view_buttons()

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        # ----------------------------------------------------
        # Scan
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Import
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Bulk
        # ----------------------------------------------------

        self.bulk_controller.progress.connect(
            self._on_bulk_progress
        )

        self.bulk_controller.finished.connect(
            self._on_bulk_finished
        )

        self.bulk_controller.failed.connect(
            self._on_bulk_failed
        )

        # ----------------------------------------------------
        # Mod List
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Details
        # ----------------------------------------------------

        self.details_panel.toggle_requested.connect(
            self._toggle_selected_mod
        )

        self.details_panel.adopt_requested.connect(
            self._ignore_selected_conflict
        )

        self.details_panel.info_requested.connect(
            self.mod_info_controller
            .show_selected_mod
        )

        self.details_panel.gamebanana_id_requested.connect(
            self._edit_selected_gamebanana_id
        )

        # ----------------------------------------------------
        # Filter
        # ----------------------------------------------------

        self.filter_bar.filters_changed.connect(
            self._apply_mod_filters
        )
        
        self.gallery_widget.toggle_requested.connect(
            self._toggle_gallery_mod
        )

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

    # ========================================================
    # Selection / Translation
    # ========================================================

    def _refresh_selection_ui(
        self,
        *_args,
    ) -> None:
        self.selection_controller.refresh()
        self.gallery_widget.set_operation_running(
            self.operation_state
            .is_running()
        )

        self._sync_details_ui()

    def _sync_details_ui(
        self,
    ) -> None:
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

        # SelectionController setzt momentan
        # noch einige zustandsabhängige Texte.
        # Danach übersetzt das Panel diese
        # anhand seines gespeicherten States.
        self.details_panel.retranslate_ui()

    def _on_language_changed(
        self,
        _language: str | None = None,
    ) -> None:
        self._retranslate_view_buttons()
        
        self._refresh_selection_ui()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        layout.setSpacing(
            16
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

        layout.addWidget(
            self._create_view_toolbar()
        )

        self.content_stack.addWidget(
            self._create_content_splitter()
        )

        self.content_stack.addWidget(
            self.gallery_widget
        )

        layout.addWidget(
            self.content_stack,
            stretch=1,
        )

        self._set_library_view(
            0
        )

        layout.addWidget(
            self.operation_status
        )

        self._apply_stylesheet()

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

        splitter.addWidget(
            self.mod_list_widget
        )

        splitter.addWidget(
            self.details_panel
        )

        splitter.setStretchFactor(
            0,
            4,
        )

        splitter.setStretchFactor(
            1,
            1,
        )

        splitter.setSizes(
            [
                980,
                420,
            ]
        )

        return splitter

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

        self.stats_widget.set_values(
            total=stats.total,
            active=stats.active,
            conflicts=stats.conflicts,
            characters=stats.characters,
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

    # ========================================================
    # Import Auswahl
    # ========================================================

    def _choose_import_archives(
        self,
    ) -> None:
        paths = choose_import_archives(
            parent=self
        )

        if paths:
            self._request_import(
                paths
            )

    def _choose_import_directory(
        self,
    ) -> None:
        paths = choose_import_directory(
            parent=self
        )

        if paths:
            self._request_import(
                paths
            )

    # ========================================================
    # Import
    # ========================================================

    def _request_import(
        self,
        paths: list[Path],
    ) -> bool:
        blocking = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.IMPORT
            )
        )

        if blocking is not None:
            show_operation_blocked(
                requested=(
                    LibraryOperation.IMPORT
                ),
                blocking=blocking,
                parent=self,
            )

            return False

        prepared = prepare_import_request(
            paths=paths,
            parent=self,
        )

        if prepared is None:
            return False

        # ====================================================
        # WICHTIG:
        # Controller zuerst starten.
        # Erst danach UI = running.
        # ====================================================

        started = (
            self.import_controller.start(
                sources=(
                    prepared.sources
                ),
                library_root=(
                    self.game_scope
                    .mod_library_directory
                ),
                options=(
                    prepared.options
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
                    (
                        "library.status."
                        "import_start_failed"
                    )
                ),
            )

            return False

        self._set_import_ui_running(
            True,
            source_count=len(
                prepared.sources
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
        
        if metadata_errors:
            QMessageBox.warning(
                self,
                tr(
                    (
                        "library.gamebanana_metadata."
                        "error.title"
                    )
                ),
                tr(
                    (
                        "library.gamebanana_metadata."
                        "error.message"
                    ),
                    errors=(
                        "\n".join(
                            metadata_errors
                        )
                    ),
                ),
            )

        message = format_import_result(
            result
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

    def request_external_import(
        self,
        paths: list[Path],
    ) -> None:
        """
        Öffentlicher Einstieg z. B.
        für GameBanana-Downloads.
        """

        self._request_import(
            [
                Path(
                    path
                )
                .expanduser()
                for path
                in paths
            ]
        )

    def cancel_import(
        self,
    ) -> None:
        if not (
            self.import_controller.cancel()
        ):
            return

        self.header_controller.mark_import_cancel_requested()

        self.operation_status.set_status(
            tr(
                (
                    "library.status."
                    "import_cancelling"
                )
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
                    (
                        "library.status."
                        "directory_failed"
                    )
                )
            )

            QMessageBox.critical(
                self,
                tr(
                    (
                        "library.error."
                        "directory.title"
                    )
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
                    (
                        "library.status."
                        "scan_start_failed"
                    )
                )
            )

            return

        if (
            request_status
            == (
                ScanRequestStatus
                .RESTART_QUEUED
            )
        ):
            self.operation_status.set_status(
                tr(
                    (
                        "library.status."
                        "scan_restart"
                    )
                )
            )

            return

        # ====================================================
        # WICHTIG:
        # request_scan muss erfolgreich sein,
        # bevor running=True.
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

    def cancel_scan(
        self,
    ) -> None:
        self.scan_controller.cancel()

    def _prepare_scan_start(
        self,
    ) -> bool:
        blocking = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.SCAN
            )
        )

        if blocking is None:
            return True

        self.operation_status.set_status(
            operation_block_message(
                requested=(
                    LibraryOperation.SCAN
                ),
                blocking=blocking,
            )
        )

        return False

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
                (
                    "library.status."
                    "scan_cancelled"
                )
            )
        )

    # ========================================================
    # Scan-Ergebnis anzeigen
    # ========================================================

    def _display_result(
        self,
        result: ScanResult,
    ) -> None:
        """
        Übernimmt das Ergebnis des Library-Scans
        und synchronisiert alle Library-Ansichten.

        Sowohl Tabellenansicht als auch Galerie
        verwenden denselben State-Provider.
        """

        # ----------------------------------------------------
        # Ein gemeinsamer State-Provider für beide Ansichten.
        #
        # Dadurch zeigen Liste und Galerie immer denselben
        # Aktivierungs-/Konfliktstatus an.
        # ----------------------------------------------------

        state_provider = (
            self.mod_action_controller
            .get_state_for_path
        )

        # ----------------------------------------------------
        # Listenansicht
        # ----------------------------------------------------

        self.mod_list_widget.set_mods(
            mods=result.mods,
            state_provider=(
                state_provider
            ),
        )

        # ----------------------------------------------------
        # Galerieansicht
        #
        # Die Gallery Cards laden ihre Preview anschließend
        # selbst asynchron.
        # ----------------------------------------------------

        self.gallery_widget.set_mods(
            mods=result.mods,
            state_provider=(
                state_provider
            ),
        )

        # ----------------------------------------------------
        # Filterdaten aktualisieren
        #
        # Erst nachdem beide Ansichten ihre Mods besitzen,
        # damit anschließend derselbe Filter auf beide
        # Views angewendet werden kann.
        # ----------------------------------------------------

        self.filter_bar.set_mods(
            result.mods
        )

        # ----------------------------------------------------
        # Aktuelle Filter anwenden
        # ----------------------------------------------------

        self._apply_mod_filters()

        # ----------------------------------------------------
        # Statistik aktualisieren
        # ----------------------------------------------------

        self._update_stats()

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

        if not (
            confirm_adopt_existing(
                mod_name=(
                    mod.name
                ),
                parent=self,
            )
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
                    (
                        "library.dialog."
                        "adopt_failed"
                    )
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

        self.operation_status.set_status(
            result.message
        )

        self.selection_controller.refresh_mod_state(
            mod
        )

        self._sync_details_ui()

    def _toggle_selected_mod(
        self,
    ) -> None:
        mod = (
            self.selection_controller
            .selected_mod()
        )

        if mod is None:
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
                    (
                        "library.dialog."
                        "mod_management_failed"
                    )
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

        self.operation_status.set_status(
            result.message
        )

        self.selection_controller.refresh_mod_state(
            mod
        )

        self._sync_details_ui()

    # ========================================================
    # GameBanana ID / Metadaten
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
            metadata.gamebanana_mod_id
            or 1
        )

        (
            mod_id,
            accepted,
        ) = QInputDialog.getInt(
            self,
            tr(
                (
                    "library.gamebanana_id."
                    "dialog.title"
                )
            ),
            tr(
                (
                    "library.gamebanana_id."
                    "dialog.message"
                ),
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
                    (
                        "library.gamebanana_id."
                        "error.title"
                    )
                ),
                tr(
                    (
                        "library.gamebanana_id."
                        "error.message"
                    ),
                    error=error,
                ),
            )

            return

        state = (
            self.mod_action_controller
            .get_state_for_path(
                mod.path
            )
        )

        # show_mod lädt nach dem Speichern
        # automatisch Preview / GB-Fallback neu.
        self.details_panel.show_mod(
            mod=mod,
            state=state,
        )

        self._sync_details_ui()

        self.operation_status.set_status(
            tr(
                (
                    "library.gamebanana_id."
                    "status.saved"
                ),
                mod_name=(
                    mod.name
                ),
                mod_id=(
                    mod_id
                ),
            )
        )

    # ========================================================
    # Filter
    # ========================================================

    def _apply_mod_filters(
        self,
        _value: object | None = None,
    ) -> None:
        visible = (
            self.mod_list_widget
            .apply_filters(

                search_term=(
                    self.filter_bar
                    .search_term()
                ),
                character=(
                    self.filter_bar
                    .selected_character()
                ),
                mod_type=(
                    self.filter_bar
                    .selected_mod_type()
                ),
                status=(
                    self.filter_bar
                    .selected_status()
                ),
            )
        )


        total = (
            self.mod_list_widget
            .row_count()
        )

        self.operation_status.set_status(
            tr(
                (
                    "library.status."
                    "filter_result"
                ),
                visible=visible,
                total=total,
            )
        )

        self._refresh_selection_ui()

    # ========================================================
    # Bulk
    # ========================================================

    def _can_start_bulk_action(
        self,
        selected_mods: list[
            ModInfo
        ],
    ) -> bool:
        blocking = (
            self.operation_state
            .blocking_operation(
                LibraryOperation.BULK
            )
        )

        if blocking is not None:
            show_operation_blocked(
                requested=(
                    LibraryOperation.BULK
                ),
                blocking=blocking,
                parent=self,
            )

            return False

        if not selected_mods:
            QMessageBox.information(
                self,
                tr(
                    (
                        "library.dialog."
                        "no_selection.title"
                    )
                ),
                tr(
                    (
                        "library.dialog."
                        "no_selection.message"
                    )
                ),
            )

            return False

        return True

    def _start_bulk_action(
        self,
        action: BulkAction,
        _checked: bool = False,
    ) -> None:
        selected = (
            self.selection_controller
            .selected_mods()
        )

        if not (
            self._can_start_bulk_action(
                selected
            )
        ):
            return

        confirmation = (
            confirm_bulk_action(
                action=action,
                selected_count=len(
                    selected
                ),
                parent=self,
            )
        )

        if confirmation is None:
            return

        # ====================================================
        # WICHTIG:
        # Controller zuerst starten.
        # Erst danach running=True.
        # ====================================================

        started = (
            self.bulk_controller.start(
                mods=selected,
                action=action,
            )
        )

        if not started:
            QMessageBox.warning(
                self,
                tr(
                    "library.dialog.bulk.title"
                ),
                tr(
                    (
                        "library.status."
                        "bulk_start_failed"
                    )
                ),
            )

            return

        self._set_bulk_ui_running(
            running=True,
            item_count=len(
                selected
            ),
        )

        key = {
            BulkAction.ENABLE: (
                (
                    "library.status."
                    "bulk_enable_started"
                )
            ),
            BulkAction.DISABLE: (
                (
                    "library.status."
                    "bulk_disable_started"
                )
            ),
            BulkAction.ADOPT: (
                (
                    "library.status."
                    "bulk_adopt_started"
                )
            ),
        }[
            action
        ]

        self.operation_status.set_status(
            tr(
                key
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
            False
        )

        message = format_bulk_result(
            result
        )

        title = tr(
            "library.dialog.bulk.completed"
        )

        dialog = (
            QMessageBox.warning
            if (
                bulk_result_requires_warning(
                    result
                )
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
            False
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
            self.bulk_controller.cancel()
        ):
            return

        self.mod_list_widget.mark_bulk_cancel_requested()

        self.operation_status.set_status(
            tr(
                (
                    "library.status."
                    "bulk_cancelling"
                )
            )
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
                    (
                        "library.error."
                        "stylesheet_load"
                    ),
                    path=(
                        style_path
                    ),
                )
            ) from error

        self.setStyleSheet(
            stylesheet
        )

    # ========================================================
    # Game Change
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

        self.game_scope.set_game(
            game_id
        )

        mods_directory = (
            self.game_scope
            .mod_library_directory
        )

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

        self._refresh_selection_ui()

        self.operation_status.set_status(
            tr(
                (
                    "library.status."
                    "game_changed"
                ),
                game=(
                    self.game_scope
                    .game.name
                ),
            )
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )
    
    def _create_view_toolbar(
        self,
    ) -> QWidget:
        frame = QFrame()

        frame.setObjectName(
            "libraryViewToolbar"
        )

        layout = QHBoxLayout(
            frame
        )

        layout.setContentsMargins(
            10,
            6,
            10,
            6,
        )

        layout.setSpacing(
            6
        )

        label = QLabel(
            tr(
                "library.view.title"
            )
        )

        label.setObjectName(
            "sectionLabel"
        )

        layout.addWidget(
            label
        )

        layout.addStretch(
            1
        )

        layout.addWidget(
            self.list_view_button
        )

        layout.addWidget(
            self.gallery_view_button
        )

        return frame

    def _set_library_view(
        self,
        index: int,
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

        self._retranslate_view_buttons()

    def _retranslate_view_buttons(
        self,
    ) -> None:
        self.list_view_button.setText(
            tr(
                "library.view.list"
            )
        )

        self.gallery_view_button.setText(
            tr(
                "library.view.gallery"
            )
        )
        
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
                    (
                        "library.dialog."
                        "mod_management_failed"
                    )
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

        new_state = (
            self.mod_action_controller
            .get_state_for_path(
                mod.path
            )
        )

        # Liste aktualisieren
        self.mod_list_widget.update_mod_state(
            mod=mod,
            state=new_state,
        )

        # Galerie aktualisieren
        self.gallery_widget.update_mod_state(
            mod=mod,
            state=new_state,
        )

        self._update_stats()

        self.operation_status.set_status(
            result.message
        )

        self._refresh_selection_ui()

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
    ) -> list[str]:
        errors: list[str] = []

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
                    game_id=game_id,
                    mod_id=mod_id,
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

__all__ = [
    "LibraryPage",
]