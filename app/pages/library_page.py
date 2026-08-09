from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
)

from PySide6.QtWidgets import (
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import tr
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
)

from app.services.mod_manager import (
    ModManager,
    ModManagerError,
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


class LibraryPage(QWidget):
    """Zeigt die erkannten Mod-Ordner an."""

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config

        # --------------------------------------------------
        # Mod Manager
        # --------------------------------------------------

        mod_manager = ModManager(
            config=self.config
        )

        # --------------------------------------------------
        # Mod Actions
        # --------------------------------------------------

        self.mod_action_controller = (
            LibraryModActionController(
                mod_manager=mod_manager
            )
        )

        # --------------------------------------------------
        # Scan Controller
        # --------------------------------------------------

        self.scan_controller = (
            LibraryScanController(
                parent=self
            )
        )

        # --------------------------------------------------
        # Bulk Controller
        # --------------------------------------------------

        self.bulk_controller = (
            LibraryBulkController(
                mod_manager=mod_manager,
                parent=self,
            )
        )

        # --------------------------------------------------
        # Import Controller
        # --------------------------------------------------

        self.import_controller = (
            LibraryImportController(
                parent=self
            )
        )

        # --------------------------------------------------
        # Zentraler Operationszustand
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Status / Progress
        # --------------------------------------------------

        self.operation_status = (
            LibraryOperationStatusWidget(
                parent=self
            )
        )

        # --------------------------------------------------
        # Mod Liste
        # --------------------------------------------------

        self.mod_list_widget = (
            LibraryModListWidget(
                parent=self
            )
        )

        # --------------------------------------------------
        # Filter
        # --------------------------------------------------

        self.filter_bar = (
            LibraryFilterBar(
                parent=self
            )
        )

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self.header_widget = (
            LibraryHeader(
                parent=self
            )
        )

        # --------------------------------------------------
        # Statistik
        # --------------------------------------------------

        self.stats_widget = (
            LibraryStatsWidget(
                parent=self
            )
        )

        # --------------------------------------------------
        # Detailpanel
        # --------------------------------------------------

        self.details_panel = (
            ModDetailsPanel(
                parent=self
            )
        )

        # --------------------------------------------------
        # Selection Controller
        #
        # WICHTIG:
        # operation_running_provider bleibt eine Callable.
        # Keine Klammern hinter is_running.
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Mod Info Controller
        # --------------------------------------------------

        self.mod_info_controller = (
            LibraryModInfoController(
                mod_manager=mod_manager,
                selected_mod_provider=(
                    self.mod_list_widget.selected_mod
                ),
                parent=self,
            )
        )

        # --------------------------------------------------
        # Header Controller
        # --------------------------------------------------

        self.header_controller = (
            LibraryHeaderController(
                header=self.header_widget,
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

        # --------------------------------------------------
        # Drag & Drop
        # --------------------------------------------------

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
            self.mod_list_widget.drop_target()
        )

        # --------------------------------------------------
        # UI / Signale
        # --------------------------------------------------

        self._connect_signals()
        self._build_ui()

        # --------------------------------------------------
        # Initialer Scan
        # --------------------------------------------------

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    # ==================================================
    # Signale
    # ==================================================

    def _connect_signals(
        self,
    ) -> None:
        # --------------------------------------------------
        # Scan
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Import
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Bulk
        # --------------------------------------------------

        self.bulk_controller.progress.connect(
            self._on_bulk_progress
        )

        self.bulk_controller.finished.connect(
            self._on_bulk_finished
        )

        self.bulk_controller.failed.connect(
            self._on_bulk_failed
        )

        # --------------------------------------------------
        # Mod Liste
        # --------------------------------------------------

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
            self.selection_controller.refresh
        )

        # --------------------------------------------------
        # Detailpanel
        # --------------------------------------------------

        self.details_panel.toggle_requested.connect(
            self._toggle_selected_mod
        )

        self.details_panel.adopt_requested.connect(
            self._ignore_selected_conflict
        )

        self.details_panel.info_requested.connect(
            self.mod_info_controller.show_selected_mod
        )

        # --------------------------------------------------
        # Filter
        # --------------------------------------------------

        self.filter_bar.filters_changed.connect(
            self._apply_mod_filters
        )

    # ==================================================
    # UI
    # ==================================================

    def _build_ui(
        self,
    ) -> None:
        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        main_layout.setSpacing(
            16
        )

        main_layout.addWidget(
            self.header_widget
        )

        main_layout.addWidget(
            self.stats_widget
        )

        main_layout.addWidget(
            self.filter_bar
        )

        main_layout.addWidget(
            self._create_content_splitter(),
            stretch=1,
        )

        main_layout.addWidget(
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
                1050,
                330,
            ]
        )

        return splitter

    # ==================================================
    # Statistik
    # ==================================================

    def _update_stats(
        self,
    ) -> None:
        stats = (
            self.mod_list_widget.statistics()
        )

        self.stats_widget.set_values(
            total=stats.total,
            active=stats.active,
            conflicts=stats.conflicts,
            characters=stats.characters,
        )

    # ==================================================
    # Import UI
    # ==================================================

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

        self.selection_controller.refresh()

    # ==================================================
    # Import Auswahl
    # ==================================================

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

    # ==================================================
    # Import starten
    # ==================================================

    def _request_import(
        self,
        paths: list[Path],
    ) -> None:
        blocking_operation = (
            self.operation_state.blocking_operation(
                LibraryOperation.IMPORT
            )
        )

        if blocking_operation is not None:
            show_operation_blocked(
                requested=LibraryOperation.IMPORT,
                blocking=blocking_operation,
                parent=self,
            )

            return

        prepared_import = (
            prepare_import_request(
                paths=paths,
                parent=self,
            )
        )

        if prepared_import is None:
            return

        # WICHTIG:
        # Controller zuerst starten.
        # Erst danach UI auf "running" setzen.

        started = self.import_controller.start(
            sources=prepared_import.sources,
            library_root=(
                self.config.mod_library_directory
            ),
            options=prepared_import.options,
        )

        if not started:
            QMessageBox.warning(
                self,
                tr(
                    "library.dialog."
                    "import.title"
                ),
                tr(
                    "library.status."
                    "import_start_failed"
                ),
            )

            return

        self._set_import_ui_running(
            True,
            source_count=len(
                prepared_import.sources
            ),
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "import_started"
            )
        )

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
        self._set_import_ui_running(
            False
        )

        message = format_import_result(
            result
        )

        title = tr(
            "library.dialog."
            "import.completed"
        )

        if result.failed_count:
            QMessageBox.warning(
                self,
                title,
                message,
            )

        else:
            QMessageBox.information(
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
        self._set_import_ui_running(
            False
        )

        QMessageBox.critical(
            self,
            tr(
                "library.dialog."
                "import.failed"
            ),
            message,
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "import_failed"
            )
        )

    def _on_import_cancelled(
        self,
    ) -> None:
        self._set_import_ui_running(
            False
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "import_cancelled"
            )
        )

    def cancel_import(
        self,
    ) -> None:
        if not self.import_controller.cancel():
            return

        self.header_controller.mark_import_cancel_requested()

        self.operation_status.set_status(
            tr(
                "library.status."
                "import_cancelling"
            )
        )

    # ==================================================
    # Scan
    # ==================================================

    def scan_mods(
        self,
    ) -> None:
        if not self._prepare_scan_start():
            return

        mods_directory = (
            self.config.mod_library_directory
        )

        if not mods_directory.exists():
            self.filter_bar.set_path_text(
                str(mods_directory)
            )

            self.operation_status.set_status(
                tr(
                    "library.status."
                    "library_missing"
                )
            )

            return

        request_status = (
            self.scan_controller.request_scan(
                root_path=mods_directory
            )
        )

        if (
            request_status
            == ScanRequestStatus.FAILED
        ):
            self.operation_status.set_status(
                tr(
                    "library.status."
                    "scan_start_failed"
                )
            )

            return

        if (
            request_status
            == ScanRequestStatus.RESTART_QUEUED
        ):
            self.operation_status.set_status(
                tr(
                    "library.status."
                    "scan_restart"
                )
            )

            return

        # request_scan() muss erfolgreich sein,
        # bevor die UI auf running gesetzt wird.

        self._set_scan_ui_running(
            True
        )

        self.filter_bar.set_path_text(
            str(mods_directory)
        )

        self.filter_bar.set_location_text(
            tr(
                "library.location."
                "checking"
            )
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "scan_started"
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

        self.selection_controller.refresh()

    def cancel_scan(
        self,
    ) -> None:
        self.scan_controller.cancel()

    def _prepare_scan_start(
        self,
    ) -> bool:
        blocking_operation = (
            self.operation_state.blocking_operation(
                LibraryOperation.SCAN
            )
        )

        if blocking_operation is None:
            return True

        self.operation_status.set_status(
            operation_block_message(
                requested=LibraryOperation.SCAN,
                blocking=blocking_operation,
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
                "library.location."
                "network"
            )
            if result.is_network
            else tr(
                "library.location."
                "local"
            )
        )

        self.filter_bar.set_location_text(
            location
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "scan_result",
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
                "library.status."
                "scan_failed"
            )
        )

        QMessageBox.critical(
            self,
            tr(
                "library.dialog."
                "scan.failed"
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
                "library.status."
                "scan_cancelled"
            )
        )

    # ==================================================
    # Scan Ergebnis
    # ==================================================

    def _display_result(
        self,
        result: ScanResult,
    ) -> None:
        self.mod_list_widget.set_mods(
            mods=result.mods,
            state_provider=(
                self.mod_action_controller.
                get_state_for_path
            ),
        )

        self.filter_bar.set_mods(
            result.mods
        )

        self._apply_mod_filters()
        self._update_stats()

    # ==================================================
    # Einzelnen Konflikt übernehmen
    # ==================================================

    def _ignore_selected_conflict(
        self,
    ) -> None:
        mod = (
            self.selection_controller.selected_mod()
        )

        if mod is None:
            return

        problem = (
            self.mod_action_controller.validate_adopt(
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
            mod_name=mod.name,
            parent=self,
        ):
            return

        try:
            result = (
                self.mod_action_controller.adopt(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog."
                    "adopt_failed"
                ),
                str(error),
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

    # ==================================================
    # Filter
    # ==================================================

    def _apply_mod_filters(
        self,
        _value: object | None = None,
    ) -> None:
        visible_mods = (
            self.mod_list_widget.apply_filters(
                search_term=(
                    self.filter_bar.search_term()
                ),
                character=(
                    self.filter_bar.selected_character()
                ),
                mod_type=(
                    self.filter_bar.selected_mod_type()
                ),
                status=(
                    self.filter_bar.selected_status()
                ),
            )
        )

        total_mods = (
            self.mod_list_widget.row_count()
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "filter_result",
                visible=visible_mods,
                total=total_mods,
            )
        )

        self.selection_controller.refresh()

    # ==================================================
    # Bulk
    # ==================================================

    def _can_start_bulk_action(
        self,
        selected_mods: list[ModInfo],
    ) -> bool:
        blocking_operation = (
            self.operation_state.blocking_operation(
                LibraryOperation.BULK
            )
        )

        if blocking_operation is not None:
            show_operation_blocked(
                requested=LibraryOperation.BULK,
                blocking=blocking_operation,
                parent=self,
            )

            return False

        if not selected_mods:
            QMessageBox.information(
                self,
                tr(
                    "library.dialog."
                    "no_selection.title"
                ),
                tr(
                    "library.dialog."
                    "no_selection.message"
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
            self.selection_controller.selected_mods()
        )

        if not self._can_start_bulk_action(
            selected_mods
        ):
            return

        confirmation = confirm_bulk_action(
            action=action,
            selected_count=len(
                selected_mods
            ),
            parent=self,
        )

        if confirmation is None:
            return

        # WICHTIG:
        # Controller zuerst starten.
        # _set_bulk_ui_running() darf erst danach
        # ausgeführt werden.

        started = self.bulk_controller.start(
            mods=selected_mods,
            action=action,
        )

        if not started:
            QMessageBox.warning(
                self,
                tr(
                    "library.dialog."
                    "bulk.title"
                ),
                tr(
                    "library.status."
                    "bulk_start_failed"
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
        }[action]

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

        self.selection_controller.refresh()

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

        message = format_bulk_result(
            result
        )

        title = tr(
            "library.dialog."
            "bulk.completed"
        )

        if bulk_result_requires_warning(
            result
        ):
            QMessageBox.warning(
                self,
                title,
                message,
            )

        else:
            QMessageBox.information(
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
                "library.dialog."
                "bulk.failed"
            ),
            message,
        )

        self.operation_status.set_status(
            tr(
                "library.status."
                "bulk_failed"
            )
        )

    def cancel_bulk_action(
        self,
    ) -> None:
        if not self.bulk_controller.cancel():
            return

        self.mod_list_widget.mark_bulk_cancel_requested()

        self.operation_status.set_status(
            tr(
                "library.status."
                "bulk_cancelling"
            )
        )

    # ==================================================
    # Einzelnen Mod aktivieren / deaktivieren
    # ==================================================

    def _toggle_selected_mod(
        self,
    ) -> None:
        mod = (
            self.selection_controller.selected_mod()
        )

        if mod is None:
            return

        try:
            result = (
                self.mod_action_controller.toggle(
                    mod
                )
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "library.dialog."
                    "mod_management_failed"
                ),
                str(error),
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

    # ==================================================
    # Stylesheet
    # ==================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        style_path = (
            Path(__file__).resolve().parents[1]
            / "styles"
            / "library.qss"
        )

        try:
            stylesheet = style_path.read_text(
                encoding="utf-8"
            )

        except OSError as error:
            raise RuntimeError(
                tr(
                    "library.error."
                    "stylesheet_load",
                    path=style_path,
                )
            ) from error

        self.setStyleSheet(
            stylesheet
        )