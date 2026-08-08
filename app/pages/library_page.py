from __future__ import annotations

from functools import partial
from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
    QEvent,
)

from app.widgets.library.library_filter_bar import (
    LibraryFilterBar,
)
from app.widgets.library.library_stats import (
    LibraryStatsWidget,
)
from app.widgets.library.library_header import (
    LibraryHeader,
)
from app.widgets.library.mod_details_panel import (
    ModDetailsPanel,
)
from app.widgets.library.library_mod_list import (
    LibraryModListWidget,
)
from app.workers.library_scan_worker import (
    ScanTask,
)
from app.controllers.library_scan_controller import (
    LibraryScanController,
    ScanRequestStatus,
)
from app.controllers.library_import_controller import (
    LibraryImportController,
)
from app.dialogs.library_import_picker import (
    choose_import_archives,
    choose_import_directory,
)
from app.dialogs.library_bulk_confirmation import (
    confirm_bulk_action,
)
from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
)

from app.controllers.library_bulk_controller import (
    LibraryBulkController,
)
from app.dialogs.library_import_request import (
    prepare_import_request,
)
from app.utils.import_result_formatter import(
    format_import_result,
    format_import_status,
)

from app.services.mod_importer import (
    ImportBatchResult,

    is_supported_import_source,
)

from app.config import AppConfig
from app.models.mod import ModInfo
from app.services.mod_scanner import ( 
    ScanResult,
)

from app.utils.bulk_result_formatter import (
    bulk_result_requires_warning,
    format_bulk_result,
    format_bulk_status,
)

from app.services.mod_manager import (
    ModManager,
    ModManagerError,
    ModState,
)
from app.dialogs.mod_info_dialog import ModInfoDialog
from app.services.ini_analyzer import analyze_mod_ini
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

MOD_OBJECT_ROLE = (
    int(Qt.ItemDataRole.UserRole) + 10
)

class LibraryPage(QWidget):
    """Zeigt die erkannten Mod-Ordner an."""

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config
        self.mod_manager = ModManager(
            config=self.config
        )
        
        self.scan_controller = (
            LibraryScanController(
                parent=self
            )
        )

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
                
        self.bulk_controller = (
            LibraryBulkController(
                mod_manager=self.mod_manager,
                parent=self,
            )
        )

        self.bulk_controller.progress.connect(
            self._on_bulk_progress
        )

        self.bulk_controller.finished.connect(
            self._on_bulk_finished
        )

        self.bulk_controller.failed.connect(
            self._on_bulk_failed
        )
               
        self.thread_pool = (
            QThreadPool.globalInstance()
        )



        self.import_controller = (
            LibraryImportController(
                parent=self
            )
        )
        
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

        self.path_label = QLabel()
        self.location_label = QLabel()
        self.status_label = QLabel()

        self.status_label = QLabel()

        self.mod_list_widget = LibraryModListWidget(
            parent=self
        )

        self.mod_table = (
            self.mod_list_widget.table
        )

        self.bulk_enable_button = (
            self.mod_list_widget.bulk_enable_button
        )

        self.bulk_disable_button = (
            self.mod_list_widget.bulk_disable_button
        )

        self.bulk_adopt_button = (
            self.mod_list_widget.bulk_adopt_button
        )

        self.cancel_bulk_button = (
            self.mod_list_widget.cancel_bulk_button
        )
        
        self.mod_list_widget.info_requested.connect(
            self._show_mod_info
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
            self._on_mod_selection_changed
        )

        self.filter_bar = LibraryFilterBar(
            parent=self
        )

        # Vorläufige Aliase:
        # Dadurch funktionieren die vorhandenen Filtermethoden weiter,
        # ohne dass wir ihre Logik schon umbauen müssen.
        self.path_label = (
            self.filter_bar.path_label
        )
        self.location_label = (
            self.filter_bar.location_label
        )
        self.search_input = (
            self.filter_bar.search_input
        )
        self.character_filter = (
            self.filter_bar.character_filter
        )
        self.mod_type_filter = (
            self.filter_bar.mod_type_filter
        )
        self.status_filter = (
            self.filter_bar.status_filter
        )

        self.header_widget = LibraryHeader(
            parent=self
        )

        self.import_button = (
            self.header_widget.import_button
        )

        self.refresh_button = (
            self.header_widget.refresh_button
        )

        self.cancel_import_button = (
            self.header_widget.cancel_import_button
        )

        self.stats_widget = LibraryStatsWidget(
            parent=self
        )
     
        self.mod_type_filter.addItem(
            "Alle Mod-Typen",
            userData=None,
        )

        self.details_panel = ModDetailsPanel(
            parent=self
        )
        
        self.toggle_button = (
            self.details_panel.toggle_button
        )

        self.ignore_conflict_button = (
            self.details_panel.adopt_button
        )

        self.detail_info_button = (
            self.details_panel.info_button
        )
        
        self.details_panel.toggle_requested.connect(
            self._toggle_selected_mod
        )

        self.details_panel.adopt_requested.connect(
            self._ignore_selected_conflict
        )

        self.details_panel.info_requested.connect(
            self._show_selected_mod_info
        )       
                        
        self.progress_bar = QProgressBar()

        
        self.filter_bar.filters_changed.connect(
            self._apply_mod_filters
        )
        
        self.header_widget.import_archives_requested.connect(
            self._choose_import_archives
        )

        self.header_widget.import_directory_requested.connect(
            self._choose_import_directory
        )

        self.header_widget.scan_requested.connect(
            self.scan_mods
        )

        self.header_widget.cancel_import_requested.connect(
            self.cancel_import
        )

        self._build_ui()

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

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
        

        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_label.setObjectName("libraryStatus")
        main_layout.addWidget(self.status_label)

        self._apply_stylesheet()

        self.setAcceptDrops(True)
        self.mod_table.setAcceptDrops(True)
        self.mod_table.viewport().setAcceptDrops(True)
        self.mod_table.viewport().installEventFilter(self)

    def _create_content_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("librarySplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.mod_list_widget)
        splitter.addWidget(self.details_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 330])

        return splitter

    def _show_selected_mod_info(self) -> None:
        mod = self._selected_mod()
        if mod is not None:
            self._show_mod_info(mod)

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

    def _update_details_panel(
        self,
    ) -> None:
        selected_mods = self._selected_mods()

        if len(selected_mods) > 1:
            self.details_panel.show_multiple(
                len(selected_mods)
            )
            return

        mod = self._selected_mod()

        if mod is None:
            self.details_panel.show_empty()
            return

        state = self.mod_manager.get_state(
            mod.path
        )

        self.details_panel.show_mod(
            mod=mod,
            state=state,
        )
        
    def dragEnterEvent(
        self,
        event,
    ) -> None:
        paths = self._import_paths_from_mime(
            event.mimeData()
        )

        if paths:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(
        self,
        event,
    ) -> None:
        paths = self._import_paths_from_mime(
            event.mimeData()
        )

        if paths:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(
        self,
        event,
    ) -> None:
        paths = self._import_paths_from_mime(
            event.mimeData()
        )

        if not paths:
            event.ignore()
            return

        event.acceptProposedAction()

        self._request_import(
            paths
        )

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        if watched is self.mod_table.viewport():
            event_type = event.type()

            if event_type in {
                QEvent.Type.DragEnter,
                QEvent.Type.DragMove,
            }:
                paths = self._import_paths_from_mime(
                    event.mimeData()
                )

                if paths:
                    event.acceptProposedAction()
                    return True

            elif event_type == QEvent.Type.Drop:
                paths = self._import_paths_from_mime(
                    event.mimeData()
                )

                if paths:
                    event.acceptProposedAction()

                    self._request_import(
                        paths
                    )

                    return True

        return super().eventFilter(
            watched,
            event,
        )
        
    def _set_import_ui_running(
        self,
        running: bool,
        source_count: int = 0,
    ) -> None:
        self.import_button.setEnabled(
            not running
        )

        self.refresh_button.setEnabled(
            not running
        )

        self.cancel_import_button.setVisible(
            running
        )

        if running:
            self.progress_bar.setVisible(
                True
            )

            self.progress_bar.setRange(
                0,
                max(source_count, 1),
            )

            self.progress_bar.setValue(
                0
            )

            self.progress_bar.setFormat(
                "Import wird vorbereitet …"
            )

        else:
            self.progress_bar.setVisible(
                False
            )

            self._update_bulk_buttons()
            
    def _import_paths_from_mime(
        self,
        mime_data,
    ) -> list[Path]:
        if not mime_data.hasUrls():
            return []

        paths: list[Path] = []
        known_paths: set[str] = set()

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            path = Path(
                url.toLocalFile()
            ).expanduser()

            if not is_supported_import_source(
                path
            ):
                continue

            path_key = str(
                path.absolute()
            )

            if path_key in known_paths:
                continue

            known_paths.add(
                path_key
            )

            paths.append(
                path
            )

        return paths
        
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

    def _request_import(
        self,
        paths: list[Path],
    ) -> None:
        if self.bulk_controller.is_running:
            QMessageBox.information(
                self,
                "Sammelaktion läuft",
                (
                    "Während einer Sammelaktion können "
                    "keine Mods importiert werden."
                ),
            )
            return

        if self.import_controller.is_running:
            QMessageBox.information(
                self,
                "Import läuft",
                "Es läuft bereits ein Mod-Import.",
            )
            return

        if self.scan_controller.is_running:
            QMessageBox.information(
                self,
                "Scan läuft",
                (
                    "Warte bitte, bis der aktuelle "
                    "Bibliotheks-Scan abgeschlossen ist."
                ),
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
        self._set_import_ui_running(
            True,
            source_count=len(
                prepared_import.sources
            ),
        )

        started = self.import_controller.start(
            sources=prepared_import.sources,
            library_root=(
                self.config.mod_library_directory
            ),
            options=prepared_import.options,
        )

        if not started:
            self._set_import_ui_running(
                False
            )
            return

        self.status_label.setText(
            "Mod-Import wurde gestartet."
        )

    def _on_import_progress(
        self,
        current: int,
        total: int,
        source_name: str,
    ) -> None:
        self.progress_bar.setRange(
            0,
            max(total, 1),
        )

        self.progress_bar.setValue(
            current
        )

        self.progress_bar.setFormat(
            f"{current}/{total} – {source_name}"
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

        if result.failed_count:
            QMessageBox.warning(
                self,
                "Mod-Import abgeschlossen",
                message,
            )
        else:
            QMessageBox.information(
                self,
                "Mod-Import abgeschlossen",
                message,
            )

        self.status_label.setText(
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
            "Mod-Import fehlgeschlagen",
            message,
        )

        self.status_label.setText(
            "Der Mod-Import ist fehlgeschlagen."
        )

    def _on_import_cancelled(
        self,
    ) -> None:
        self._set_import_ui_running(
            False
        )

        self.status_label.setText(
            "Der Mod-Import wurde abgebrochen."
        )

    def cancel_import(
        self,
    ) -> None:
        if self.import_controller.cancel:
            self.status_label.setText(
                "Import wird abgebrochen …"
            )

    def scan_mods(
        self,
    ) -> None:
        if not self._prepare_scan_start():
            return

        mods_directory = (
            self.config.mod_library_directory
        )

        if not mods_directory.exists():
            self.status_label.setText(
                (
                    "Das Mod-Bibliotheksverzeichnis "
                    "existiert nicht."
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
            self.status_label.setText(
                (
                    "Der Bibliotheks-Scan konnte "
                    "nicht gestartet werden."
                )
            )
            return

        if (
            request_status
            == ScanRequestStatus.RESTART_QUEUED
        ):
            self.status_label.setText(
                (
                    "Laufender Scan wird "
                    "abgebrochen und anschließend "
                    "neu gestartet …"
                )
            )
            return

        self._set_scan_ui_running(
            True
        )

        self.path_label.setText(
            str(mods_directory)
        )

        self.location_label.setText(
            "Wird geprüft"
        )

        self.status_label.setText(
            "Ordner wird gescannt …"
        )

    def _set_scan_ui_running(
        self,
        running: bool,
    ) -> None:
        self.refresh_button.setEnabled(
            not running
        )

        self.import_button.setEnabled(
            not running
        )

        if running:
            self.progress_bar.setVisible(
                True
            )

            self.progress_bar.setRange(
                0,
                0,
            )

            self.progress_bar.setValue(
                0
            )

            self.progress_bar.setFormat(
                "Bibliothek wird gescannt …"
            )

            return

        self.progress_bar.setVisible(
            False
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            ""
        )

        self._update_bulk_buttons()
        self._update_toggle_button()
        self._update_details_panel()

    def cancel_scan(self) -> None:
        self.scan_controller.cancel()

    def _prepare_scan_start(
        self,
    ) -> bool:
        if self.bulk_controller.is_running:
            self.status_label.setText(
                (
                    "Während einer Sammelaktion "
                    "kann die Bibliothek nicht "
                    "gescannt werden."
                )
            )
            return False

        if self.import_controller.is_running:
            self.status_label.setText(
                (
                    "Während eines Imports kann "
                    "die Bibliothek nicht "
                    "gescannt werden."
                )
            )
            return False

        return True
        
    def _on_scan_progress(
        self,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        if total > 0:
            self.progress_bar.setRange(
                0,
                total,
            )

            self.progress_bar.setValue(
                current
            )

            self.progress_bar.setFormat(
                f"{current}/{total} – {mod_name}"
            )
        else:
            self.progress_bar.setRange(
                0,
                0,
            )

            self.progress_bar.setFormat(
                f"Scanne – {mod_name}"
            )

        self.status_label.setText(
            f"Scanne „{mod_name}“ …"
        )

    def _on_scan_finished(
        self,
        result: ScanResult,
    ) -> None:
        self._display_result(result)

        location = (
            "Netzlaufwerk"
            if result.is_network
            else "Lokaler Ordner"
        )

        self.location_label.setText(
            location
        )

        self.status_label.setText(
            f"{len(result.mods)} Mods in "
            f"{result.duration_seconds:.2f} Sekunden gefunden."
        )

        self._finish_task()

    def _on_scan_failed(
        self,
        message: str,
    ) -> None:
        self._finish_task()

        self.status_label.setText(
            "Der Bibliotheks-Scan ist fehlgeschlagen."
        )

        QMessageBox.critical(
            self,
            "Scan fehlgeschlagen",
            message,
        )

    def _on_scan_cancelled(
        self,
    ) -> None:
        self._finish_task()

        self.status_label.setText(
            "Der Bibliotheks-Scan wurde abgebrochen."
        )

    def _finish_task(
        self,
    ) -> None:
        self._set_scan_ui_running(
            False
        )

    def _display_result(
        self,
        result: ScanResult,
    ) -> None:
        self.mod_list_widget.set_mods(
            mods=result.mods,
            state_provider=self.mod_manager.get_state,
        )

        self.filter_bar.set_mods(
            result.mods
        )

        self._apply_mod_filters()
        self._update_stats()
        self._update_toggle_button()
        self._update_details_panel()
        
    def _ignore_selected_conflict(
        self,
    ) -> None:
        """
        Übernimmt einen vorhandenen Mod-Ordner in die Verwaltung.

        Der Ordnerinhalt wird nicht überschrieben.
        """
        mod = self._selected_mod()

        if mod is None:
            return

        state = self.mod_manager.get_state(
            mod.path
        )

        if state != ModState.CONFLICT:
            QMessageBox.information(
                self,
                "Kein Konflikt",
                "Der ausgewählte Mod besitzt aktuell keinen Konflikt.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Vorhandenen Mod übernehmen",
            (
                f"Der vorhandene Ordner für „{mod.name}“ wird als "
                "vom Genshin Mod Manager verwaltet markiert.\n\n"
                "Dabei werden keine Mod-Dateien überschrieben, "
                "verschoben oder gelöscht.\n\n"
                "Danach kann der Manager den Ordner durch Umbenennen "
                "aktivieren und deaktivieren.\n\n"
                "Möchtest du fortfahren?"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            resulting_state = self.mod_manager.adopt_existing(
                mod.path
            )

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                "Konflikt konnte nicht übernommen werden",
                str(error),
            )
            return

        if resulting_state == ModState.ENABLED:
            state_text = "aktiviert"
        else:
            state_text = "deaktiviert"

        self.status_label.setText(
            f"„{mod.name}“ wurde als vorhandener "
            f"{state_text}er Mod übernommen."
        )

        self._refresh_mod_state(
            mod
        )

    def _apply_mod_filters(
        self,
        _value: object | None = None,
    ) -> None:
        visible_mods = (
            self.mod_list_widget.apply_filters(
                search_term=(
                    self.search_input.text()
                ),
                character=(
                    self.character_filter.currentData()
                ),
                mod_type=(
                    self.mod_type_filter.currentData()
                ),
                status=(
                    self.status_filter.currentData()
                ),
            )
        )

        total_mods = (
            self.mod_list_widget.row_count()
        )

        self.status_label.setText(
            f"{visible_mods} von "
            f"{total_mods} Mods werden angezeigt."
        )

        self._update_bulk_buttons()

    def _show_mod_info(
        self,
        mod: ModInfo,
        _checked: bool = False,
    ) -> None:
        """Analysiert die Steuerungs-INI des ausgewählten Mods."""
        inspection_path = (
            self.mod_manager.inspection_path_for(
                mod.path
            )
        )

        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )

        try:
            analysis = analyze_mod_ini(
                inspection_path
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "INI-Analyse fehlgeschlagen",
                (
                    "Die Merge- oder Master-INI konnte "
                    "nicht analysiert werden.\n\n"
                    f"{type(error).__name__}: {error}"
                ),
            )
            return

        finally:
            QApplication.restoreOverrideCursor()

        dialog = ModInfoDialog(
            mod_name=mod.name,
            analysis=analysis,
            parent=self,
        )

        dialog.exec()
            
    def _selected_mods(
        self,
    ) -> list[ModInfo]:
        return (
            self.mod_list_widget.selected_mods()
        )
            
    def _on_mod_selection_changed(
        self,
    ) -> None:
        self._update_toggle_button()
        self._update_bulk_buttons()
        self._update_details_panel()

    def _update_bulk_buttons(
        self,
    ) -> None:
        selected_mods = self._selected_mods()

        operation_running = any(
            (
                self.scan_controller.is_running,
                self.import_controller.is_running,
                self.bulk_controller.is_running,
            )
        )

        has_selection = bool(
            selected_mods
        )

        enabled = (
            has_selection
            and not operation_running
        )

        self.bulk_enable_button.setEnabled(
            enabled
        )

        self.bulk_disable_button.setEnabled(
            enabled
        )

        self.bulk_adopt_button.setEnabled(
            enabled
        )

    def _can_start_bulk_action(
        self,
        selected_mods: list[ModInfo],
    ) -> bool:
        if self.bulk_controller.is_running:
            QMessageBox.information(
                self,
                "Sammelaktion läuft",
                (
                    "Es wird bereits eine "
                    "Sammelaktion ausgeführt."
                ),
            )
            return False

        if self.scan_controller.is_running:
            QMessageBox.information(
                self,
                "Scan läuft",
                (
                    "Warte bitte, bis der "
                    "Bibliotheks-Scan abgeschlossen ist."
                ),
            )
            return False

        if self.import_controller.is_running:
            QMessageBox.information(
                self,
                "Import läuft",
                (
                    "Warte bitte, bis der "
                    "Mod-Import abgeschlossen ist."
                ),
            )
            return False

        if not selected_mods:
            QMessageBox.information(
                self,
                "Keine Mods ausgewählt",
                (
                    "Wähle mindestens einen Mod "
                    "in der Tabelle aus."
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
            self._selected_mods()
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

        started = self.bulk_controller.start(
            mods=selected_mods,
            action=action,
        )

        if not started:
            QMessageBox.warning(
                self,
                "Sammelaktion",
                (
                    "Die Sammelaktion konnte "
                    "nicht gestartet werden."
                ),
            )
            return

        self._set_bulk_ui_running(
            running=True,
            item_count=len(
                selected_mods
            ),
        )

        self.status_label.setText(
            f"{confirmation.title} wurde gestartet."
        )
            
    def _set_bulk_ui_running(
        self,
        running: bool,
        item_count: int = 0,
    ) -> None:
        # Hauptbereiche während einer Sammelaktion sperren.
        self.mod_table.setEnabled(
            not running
        )

        self.refresh_button.setEnabled(
            not running
        )

        self.import_button.setEnabled(
            not running
        )

        # Einzel- und Bulk-Aktionen zunächst deaktivieren.
        self.toggle_button.setEnabled(
            False
        )

        self.ignore_conflict_button.setEnabled(
            False
        )

        self.bulk_enable_button.setEnabled(
            False
        )

        self.bulk_disable_button.setEnabled(
            False
        )

        self.bulk_adopt_button.setEnabled(
            False
        )

        # Abbrechen ist ausschließlich während
        # einer laufenden Sammelaktion verfügbar.
        self.cancel_bulk_button.setVisible(
            running
        )

        self.cancel_bulk_button.setEnabled(
            running
        )

        if running:
            self.progress_bar.setVisible(
                True
            )

            self.progress_bar.setRange(
                0,
                max(item_count, 1),
            )

            self.progress_bar.setValue(
                0
            )

            self.progress_bar.setFormat(
                "Sammelaktion wird vorbereitet …"
            )

            return

        # Sammelaktion beendet.
        self.progress_bar.setVisible(
            False
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            ""
        )

        # Buttons anhand des aktuellen Zustands
        # und der aktuellen Auswahl neu berechnen.
        self._update_toggle_button()
        self._update_bulk_buttons()
        self._update_details_panel()

    def _on_bulk_progress(
        self,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.progress_bar.setRange(
            0,
            max(total, 1),
        )

        self.progress_bar.setValue(
            current
        )

        self.progress_bar.setFormat(
            f"{current}/{total} – {mod_name}"
        )

        self.status_label.setText(
            f"Bearbeite „{mod_name}“ …"
        )

    def _on_bulk_finished(
        self,
        result: BulkBatchResult,
    ) -> None:
        self._set_bulk_ui_running(
            running=False
        )

        self.progress_bar.setVisible(
            False
        )

        message = format_bulk_result(
            result
        )

        if bulk_result_requires_warning(
            result
        ):
            QMessageBox.warning(
                self,
                "Sammelaktion abgeschlossen",
                message,
            )
        else:
            QMessageBox.information(
                self,
                "Sammelaktion abgeschlossen",
                message,
            )

        self.status_label.setText(
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
            "Sammelaktion fehlgeschlagen",
            message,
        )

        self.status_label.setText(
            "Die Sammelaktion ist fehlgeschlagen."
        )

    def cancel_bulk_action(
        self,
    ) -> None:
        if not self.bulk_controller.cancel():
            return

        self.cancel_bulk_button.setEnabled(
            False
        )

        self.status_label.setText(
            (
                "Sammelaktion wird nach dem "
                "aktuell bearbeiteten Mod "
                "abgebrochen …"
            )
        )
    
    def _selected_mod(
        self,
    ) -> ModInfo | None:
        return (
            self.mod_list_widget.selected_mod()
        )

    def _update_toggle_button(
        self,
    ) -> None:
        """Aktualisiert die Aktionen für den ausgewählten Mod."""
        selected_mods = self._selected_mods()

        if len(selected_mods) > 1:
            self.toggle_button.setText(
                f"{len(selected_mods)} Mods ausgewählt"
            )

            self.toggle_button.setEnabled(
                False
            )

            self.ignore_conflict_button.setEnabled(
                False
            )

            return
        
        mod = self._selected_mod()

        self.ignore_conflict_button.setEnabled(
            False
        )

        if mod is None:
            self.toggle_button.setText(
                "Aktivieren"
            )
            self.toggle_button.setEnabled(
                False
            )
            return

        state = self.mod_manager.get_state(
            mod.path
        )

        if state == ModState.DISABLED:
            self.toggle_button.setText(
                "Aktivieren"
            )
            self.toggle_button.setEnabled(
                True
            )

        elif state == ModState.ENABLED:
            self.toggle_button.setText(
                "Deaktivieren"
            )
            self.toggle_button.setEnabled(
                True
            )

        elif state == ModState.BROKEN:
            self.toggle_button.setText(
                "Defekten Link entfernen"
            )
            self.toggle_button.setEnabled(
                True
            )

        elif state == ModState.NOT_CONFIGURED:
            self.toggle_button.setText(
                "Mods-Ordner fehlt"
            )
            self.toggle_button.setEnabled(
                False
            )

        elif state == ModState.CONFLICT:
            self.toggle_button.setText(
                "Konflikt"
            )
            self.toggle_button.setEnabled(
                False
            )

            self.ignore_conflict_button.setEnabled(
                True
            )

    def _toggle_selected_mod(
        self,
    ) -> None:
        mod = self._selected_mod()

        if mod is None:
            return

        state = self.mod_manager.get_state(
            mod.path
        )

        try:
            if state == ModState.DISABLED:
                destination = self.mod_manager.enable(
                    mod.path
                )

                self.status_label.setText(
                    f"„{mod.name}“ wurde aktiviert: {destination}"
                )

            elif state in {
                ModState.ENABLED,
                ModState.BROKEN,
            }:
                self.mod_manager.disable(
                    mod.path
                )

                self.status_label.setText(
                    f"„{mod.name}“ wurde deaktiviert und "
                    "die reparierte Version wurde gespeichert."
                )

            elif state == ModState.NOT_CONFIGURED:
                QMessageBox.warning(
                    self,
                    "Aktiver Mods-Ordner fehlt",
                    (
                        "Wähle unter Einstellungen zuerst "
                        "den aktiven Mods-Ordner aus."
                    ),
                )
                return

            else:
                QMessageBox.warning(
                    self,
                    "Mod-Konflikt",
                    (
                        "Am Ziel befindet sich bereits ein fremder "
                        "Ordner oder eine fremde Verknüpfung.\n\n"
                        "Der Manager überschreibt diese Daten nicht."
                    ),
                )
                return

        except ModManagerError as error:
            QMessageBox.critical(
                self,
                "Mod-Verwaltung fehlgeschlagen",
                str(error),
            )
            return

        self._refresh_mod_state(
            mod
        )

    def _refresh_mod_state(
        self,
        mod: ModInfo,
    ) -> None:
        state = self.mod_manager.get_state(
            mod.path
        )

        self.mod_list_widget.update_mod_state(
            mod=mod,
            state=state,
        )

        self._update_stats()
        self._update_toggle_button()
        self._update_details_panel()
               
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
                "Das Stylesheet der Mod-Bibliothek "
                f"konnte nicht geladen werden: {style_path}"
            ) from error

        self.setStyleSheet(
            stylesheet
        )