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
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
    BulkItemStatus,
    BulkModWorker,
)

from app.dialogs.import_options_dialog import (
    ImportOptionsDialog,
)

from app.services.mod_importer import (
    ImportBatchResult,
    ImportStatus,
    is_supported_import_source,
)

from app.workers.import_worker import (
    ImportWorker,
)

from app.config import AppConfig
from app.models.mod import ModInfo
from app.services.mod_scanner import ( 
    ScanResult,
)

from app.services.mod_manager import (
    ModManager,
    ModManagerError,
    ModState,
    mod_state_label,
)

from app.dialogs.mod_info_dialog import ModInfoDialog
from app.services.ini_analyzer import analyze_mod_ini
from pathlib import Path

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
              
        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.current_task: ScanTask | None = None
        self.current_import_task: ImportWorker | None = None
        self.current_bulk_task: BulkModWorker | None = None

        self.scan_again = False

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
        selected_files, _selected_filter = (
            QFileDialog.getOpenFileNames(
                self,
                "Mod-Archive auswählen",
                str(Path.home()),
                (
                    "Unterstützte Archive "
                    "(*.zip *.tar *.tar.gz *.tgz "
                    "*.tar.bz2 *.tbz2 *.tar.xz *.txz);;"
                    "ZIP-Archive (*.zip);;"
                    "TAR-Archive "
                    "(*.tar *.tar.gz *.tgz "
                    "*.tar.bz2 *.tbz2 *.tar.xz *.txz);;"
                    "Alle Dateien (*)"
                ),
            )
        )

        if not selected_files:
            return

        self._request_import(
            [
                Path(file_path)
                for file_path in selected_files
            ]
        )

    def _choose_import_directory(
        self,
    ) -> None:
        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                "Mod-Ordner auswählen",
                str(Path.home()),
            )
        )

        if not selected_directory:
            return

        self._request_import(
            [
                Path(selected_directory)
            ]
        )

    def _request_import(
        self,
        paths: list[Path],
    ) -> None:
        if self.current_bulk_task is not None:
            QMessageBox.information(
                self,
                "Sammelaktion läuft",
                (
                    "Während einer Sammelaktion können keine "
                    "Mods importiert werden."
                ),
            )
            return
                
        if self.current_import_task is not None:
            QMessageBox.information(
                self,
                "Import läuft",
                "Es läuft bereits ein Mod-Import.",
            )
            return

        if self.current_task is not None:
            QMessageBox.information(
                self,
                "Scan läuft",
                (
                    "Warte bitte, bis der aktuelle Bibliotheks-Scan "
                    "abgeschlossen ist."
                ),
            )
            return

        supported_paths = [
            path
            for path in paths
            if is_supported_import_source(path)
        ]

        if not supported_paths:
            QMessageBox.warning(
                self,
                "Keine unterstützten Dateien",
                (
                    "Es wurden keine unterstützten Mod-Ordner "
                    "oder Archive ausgewählt."
                ),
            )
            return

        dialog = ImportOptionsDialog(
            sources=supported_paths,
            parent=self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        options = dialog.selected_options()

        worker = ImportWorker(
            sources=supported_paths,
            library_root=(
                self.config.mod_library_directory
            ),
            options=options,
        )

        worker.signals.progress.connect(
            self._on_import_progress
        )

        worker.signals.finished.connect(
            self._on_import_finished
        )

        worker.signals.failed.connect(
            self._on_import_failed
        )

        worker.signals.cancelled.connect(
            self._on_import_cancelled
        )

        self.current_import_task = worker

        self.import_button.setEnabled(
            False
        )

        self.refresh_button.setEnabled(
            False
        )

        self.cancel_import_button.setVisible(
            True
        )
        
        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            len(supported_paths),
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            "Import wird vorbereitet …"
        )

        self.status_label.setText(
            "Mod-Import wurde gestartet."
        )

        self.thread_pool.start(
            worker
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
        self._finish_import_ui()

        summary_lines: list[str] = []

        for item in result.items[:12]:
            if item.status == ImportStatus.IMPORTED:
                destination_name = (
                    item.destination.name
                    if item.destination is not None
                    else "Unbekannt"
                )

                summary_lines.append(
                    f"✓ {item.source.name} → {destination_name}"
                )

            elif item.status == ImportStatus.SKIPPED:
                summary_lines.append(
                    f"– {item.source.name}: {item.message}"
                )

            else:
                summary_lines.append(
                    f"✗ {item.source.name}: {item.message}"
                )

        if len(result.items) > 12:
            summary_lines.append(
                f"… und {len(result.items) - 12} weitere"
            )

        summary_text = "\n".join(
            summary_lines
        )

        message = (
            f"Importiert: {result.imported_count}\n"
            f"Übersprungen: {result.skipped_count}\n"
            f"Fehlgeschlagen: {result.failed_count}\n"
            f"Dauer: {result.duration_seconds:.1f} Sekunden\n\n"
            f"{summary_text}"
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
            f"{result.imported_count} Mod(s) importiert."
        )

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    def _on_import_failed(
        self,
        message: str,
    ) -> None:
        self._finish_import_ui()

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
        self._finish_import_ui()

        self.status_label.setText(
            "Der Mod-Import wurde abgebrochen."
        )

    def _finish_import_ui(
        self,
    ) -> None:
        self.current_import_task = None

        self.import_button.setEnabled(
            True
        )

        self.refresh_button.setEnabled(
            True
        )

        self.cancel_import_button.setVisible(
            False
        )

        self.progress_bar.setVisible(
            False
        )

    def cancel_import(
        self,
    ) -> None:
        if self.current_import_task is not None:
            self.current_import_task.cancel()

            self.status_label.setText(
                "Import wird abgebrochen …"
            )

    def scan_mods(self) -> None:
        """Startet einen asynchronen Scan."""
        if self.current_bulk_task is not None:
            self.status_label.setText(
                (
                    "Während einer Sammelaktion kann die "
                    "Bibliothek nicht gescannt werden."
                )
            )
            return
                
        
        if self.current_import_task is not None:
            self.status_label.setText(
                "Während eines Imports kann nicht gescannt werden."
            )
            return
        
        if self.current_task is not None:
            self.scan_again = True
            self.current_task.cancel()
            return

        mods_directory = (
            self.config.mod_library_directory
        )
        if not mods_directory.exists():
            self.path_label.setText(
                str(mods_directory)
            )

            self.location_label.setText(
                "Nicht erreichbar"
            )

            self.status_label.setText(
                "Die Mod-Bibliothek existiert nicht oder "
                "das Netzlaufwerk ist momentan nicht eingehängt."
            )

            self.mod_table.setRowCount(0)
            self._update_stats()
            self._update_details_panel()
            return
        self.path_label.setText(
            str(mods_directory)
        )

        self.location_label.setText(
            "Wird geprüft"
        )

        self.status_label.setText(
            "Ordner wird gescannt …"
        )

        self.refresh_button.setEnabled(
            False
        )

        self.progress_bar.setVisible(
            True
        )
        self.progress_bar.setRange(
            0,
            0,
        )

        task = ScanTask(
            root_path=mods_directory
        )

        task.signals.progress.connect(
            self._on_scan_progress
        )
        task.signals.finished.connect(
            self._on_scan_finished
        )
        task.signals.failed.connect(
            self._on_scan_failed
        )
        task.signals.cancelled.connect(
            self._on_scan_cancelled
        )

        self.current_task = task

        self._update_bulk_buttons()

        self.thread_pool.start(
            task
        )

    def cancel_scan(self) -> None:
        if self.current_task is not None:
            self.current_task.cancel()

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
        else:
            self.progress_bar.setRange(
                0,
                0,
            )

        if mod_name:
            self.progress_bar.setFormat(
                f"{current}/{total} – {mod_name}"
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
        self.location_label.setText(
            "Nicht erreichbar"
        )

        self.status_label.setText(
            f"Scan fehlgeschlagen: {message}"
        )

        self.mod_table.setRowCount(0)
        self._update_stats()
        self._update_details_panel()

        self._finish_task()

    def _on_scan_cancelled(self) -> None:
        self.status_label.setText(
            "Scan wurde abgebrochen."
        )

        self._finish_task()

    def _finish_task(
        self,
    ) -> None:
        self.current_task = None

        self.refresh_button.setEnabled(
            True
        )

        self.progress_bar.setVisible(
            False
        )

        # Nach dem Scan müssen die Auswahlaktionen
        # erneut anhand des aktuellen Zustands gesetzt werden.
        self._update_bulk_buttons()
        self._update_toggle_button()
        self._update_details_panel()

        if self.scan_again:
            self.scan_again = False

            QTimer.singleShot(
                0,
                self.scan_mods,
            )

    def _display_result(
        self,
        result: ScanResult,
    ) -> None:
        self.mod_list_widget.set_mods(
            mods=result.mods,
            state_provider=self.mod_manager.get_state,
        )

        self._update_character_filter(
            result.mods
        )

        self._update_mod_type_filter(
            result.mods
        )

        self._apply_mod_filters()
        self._update_stats()
        self._update_toggle_button()
        self._update_details_panel()
        
    def _update_character_filter(
        self,
        mods: list[ModInfo],
    ) -> None:
        """Erzeugt die Charakterliste aus den gefundenen Mods."""
        selected_character = (
            self.character_filter.currentData()
        )

        characters: set[str] = set()
        has_unknown_mods = False

        for mod in mods:
            if mod.characters:
                characters.update(
                    mod.characters
                )
            else:
                has_unknown_mods = True

        self.character_filter.blockSignals(
            True
        )

        self.character_filter.clear()

        self.character_filter.addItem(
            "Alle Charaktere",
            userData=None,
        )

        if has_unknown_mods:
            self.character_filter.addItem(
                "Unbekannt",
                userData="__unknown__",
            )

        for character in sorted(
            characters,
            key=str.casefold,
        ):
            self.character_filter.addItem(
                character,
                userData=character,
            )

        selected_index = (
            self.character_filter.findData(
                selected_character
            )
        )

        if selected_index >= 0:
            self.character_filter.setCurrentIndex(
                selected_index
            )
        else:
            self.character_filter.setCurrentIndex(
                0
            )

        self.character_filter.blockSignals(
            False
        )

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
                self.current_task is not None,
                self.current_import_task is not None,
                self.current_bulk_task is not None,
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
 
    def _start_bulk_action(
        self,
        action: BulkAction,
        _checked: bool = False,
    ) -> None:
        if self.current_bulk_task is not None:
            QMessageBox.information(
                self,
                "Sammelaktion läuft",
                (
                    "Es wird bereits eine Sammelaktion "
                    "ausgeführt."
                ),
            )
            return

        if self.current_task is not None:
            QMessageBox.information(
                self,
                "Scan läuft",
                (
                    "Warte bitte, bis der Bibliotheks-Scan "
                    "abgeschlossen ist."
                ),
            )
            return

        if self.current_import_task is not None:
            QMessageBox.information(
                self,
                "Import läuft",
                (
                    "Warte bitte, bis der Mod-Import "
                    "abgeschlossen ist."
                ),
            )
            return

        selected_mods = self._selected_mods()

        if not selected_mods:
            QMessageBox.information(
                self,
                "Keine Mods ausgewählt",
                (
                    "Wähle mindestens einen Mod in der "
                    "Tabelle aus."
                ),
            )
            return

        action_title = {
            BulkAction.ENABLE: "Mods aktivieren",
            BulkAction.DISABLE: "Mods deaktivieren",
            BulkAction.ADOPT: "Konflikte übernehmen",
        }[action]

        action_description = {
            BulkAction.ENABLE: (
                "Die ausgewählten deaktivierten Mods werden "
                "aktiviert. Bereits aktive Mods werden übersprungen."
            ),
            BulkAction.DISABLE: (
                "Die ausgewählten aktiven Mods werden deaktiviert. "
                "Bereits deaktivierte Mods werden übersprungen."
            ),
            BulkAction.ADOPT: (
                "Vorhandene Konflikt-Ordner werden in die Verwaltung "
                "aufgenommen. Mod-Dateien werden nicht überschrieben."
            ),
        }[action]

        answer = QMessageBox.question(
            self,
            action_title,
            (
                f"Ausgewählte Mods: {len(selected_mods)}\n\n"
                f"{action_description}\n\n"
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

        worker = BulkModWorker(
            mods=selected_mods,
            action=action,
            mod_manager=self.mod_manager,
        )

        worker.signals.progress.connect(
            self._on_bulk_progress
        )

        worker.signals.finished.connect(
            self._on_bulk_finished
        )

        worker.signals.failed.connect(
            self._on_bulk_failed
        )

        self.current_bulk_task = worker

        self._set_bulk_ui_running(
            running=True
        )


        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            len(selected_mods),
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            "Sammelaktion wird vorbereitet …"
        )

        self.status_label.setText(
            f"{action_title} wurde gestartet."
        )

        self.thread_pool.start(
            worker
        )
       
    def _set_bulk_ui_running(
        self,
        running: bool,
    ) -> None:
        self.mod_table.setEnabled(
            not running
        )

        self.refresh_button.setEnabled(
            not running
        )

        self.import_button.setEnabled(
            not running
        )

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

        self.cancel_bulk_button.setVisible(
            running
        )

        if running:
            self.cancel_bulk_button.setEnabled(
                True
        )

 
 
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
        self.current_bulk_task = None

        self._set_bulk_ui_running(
            running=False
        )

        self.progress_bar.setVisible(
            False
        )

        action_text = {
            BulkAction.ENABLE: "Aktivieren",
            BulkAction.DISABLE: "Deaktivieren",
            BulkAction.ADOPT: "Übernehmen",
        }[result.action]

        detail_lines: list[str] = []

        for item in result.items[:15]:
            if item.status == BulkItemStatus.SUCCESS:
                symbol = "✓"

            elif item.status == BulkItemStatus.SKIPPED:
                symbol = "–"

            elif item.status == BulkItemStatus.CONFLICT:
                symbol = "!"

            else:
                symbol = "✗"

            detail_lines.append(
                f"{symbol} {item.mod_name}: {item.message}"
            )

        if len(result.items) > 15:
            detail_lines.append(
                f"… und {len(result.items) - 15} weitere"
            )

        details = "\n".join(
            detail_lines
        )

        cancelled_text = ""

        if result.cancelled:
            cancelled_text = (
                "\n\nDie Sammelaktion wurde vorzeitig abgebrochen."
            )

        message = (
            f"Aktion: {action_text}\n\n"
            f"Erfolgreich: {result.success_count}\n"
            f"Übersprungen: {result.skipped_count}\n"
            f"Konflikte: {result.conflict_count}\n"
            f"Fehlgeschlagen: {result.failed_count}\n"
            f"Dauer: {result.duration_seconds:.1f} Sekunden"
            f"{cancelled_text}\n\n"
            f"{details}"
        )

        if (
            result.failed_count > 0
            or result.conflict_count > 0
            or result.cancelled
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

        if result.cancelled:
            self.status_label.setText(
                "Die Sammelaktion wurde abgebrochen."
            )
        else:
            self.status_label.setText(
                (
                    "Sammelaktion abgeschlossen: "
                    f"{result.success_count} erfolgreich."
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
        self.current_bulk_task = None

        self._set_bulk_ui_running(
            running=False
        )

        self.progress_bar.setVisible(
            False
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
        if self.current_bulk_task is None:
            return

        self.current_bulk_task.cancel()

        self.cancel_bulk_button.setEnabled(
            False
        )

        self.status_label.setText(
            (
                "Sammelaktion wird nach dem aktuell "
                "bearbeiteten Mod abgebrochen …"
            )
        )
            
    def _update_mod_type_filter(
        self,
        mods: list[ModInfo],
    ) -> None:
        selected_mod_type = (
            self.mod_type_filter.currentData()
        )

        mod_types = {
            mod.mod_type
            for mod in mods
            if mod.mod_type
        }

        self.mod_type_filter.blockSignals(
            True
        )

        self.mod_type_filter.clear()

        self.mod_type_filter.addItem(
            "Alle Mod-Typen",
            userData=None,
        )

        for mod_type in sorted(
            mod_types,
            key=str.casefold,
        ):
            self.mod_type_filter.addItem(
                mod_type,
                userData=mod_type,
            )

        selected_index = (
            self.mod_type_filter.findData(
                selected_mod_type
            )
        )

        if selected_index >= 0:
            self.mod_type_filter.setCurrentIndex(
                selected_index
            )
        else:
            self.mod_type_filter.setCurrentIndex(
                0
            )

        self.mod_type_filter.blockSignals(
            False
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