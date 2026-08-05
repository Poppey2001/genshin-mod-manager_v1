from __future__ import annotations

import threading
from datetime import datetime
from functools import partial
from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    QEvent,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QMessageBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,  
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
    ModScanner,
    ScanCancelledError,
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
class ScanSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(
        int,
        int,
        str,
    )


class ScanTask(QRunnable):
    """Führt den Ordnerscan außerhalb des UI-Threads aus."""

    def __init__(
        self,
        root_path,
    ) -> None:
        super().__init__()

        self.root_path = root_path
        self.signals = ScanSignals()

        self._cancel_event = (
            threading.Event()
        )

        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        scanner = ModScanner(
            calculate_network_sizes=False
        )

        try:
            result = scanner.scan(
                root_path=self.root_path,
                progress_callback=(
                    self.signals.progress.emit
                ),
                cancel_callback=(
                    self.is_cancelled
                ),
            )

        except ScanCancelledError:
            self.signals.cancelled.emit()
            return

        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: {error}"
            )
            return

        self.signals.finished.emit(result)


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
        
        self.mods_by_path: dict[str, ModInfo] = {}
        


        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.current_task: ScanTask | None = None
        self.scan_again = False

        self.path_label = QLabel()
        self.location_label = QLabel()
        self.status_label = QLabel()

        self.character_filter = QComboBox()
        
        self.character_filter.addItem(
            "Alle Charaktere",
            userData=None,
        )
        
        self.character_filter.addItem(
            "Unbekannt",
            userData="__unknown__"
        )
        
        self.mod_type_filter = QComboBox()
        
        self.mod_type_filter.addItem(
            "Alle Mod-Typen",
            userData=None,
        )
        self.ignore_conflict_button = QPushButton(
            "Konflikt übernehmen"
        )

        self.ignore_conflict_button.setEnabled(
            False
        )

        self.ignore_conflict_button.setToolTip(
            "Übernimmt einen vorhandenen Mod-Ordner, "
            "ohne seine Dateien zu überschreiben."
        )

        self.ignore_conflict_button.clicked.connect(
            self._ignore_selected_conflict
        )
        
        self.refresh_button = QPushButton(
            "Neu scannen"
        )

        self.progress_bar = QProgressBar()
        
        self.current_import_task: ImportWorker | None = None

        self.mod_table = QTableWidget()

        self._build_ui()

        QTimer.singleShot(
            0,
            self.scan_mods,
        )

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            40,
            36,
            40,
            36,
        )
        main_layout.setSpacing(18)

        title_label = QLabel(
            "Mod-Bibliothek"
        )
        title_label.setObjectName(
            "pageTitle"
        )

        description_label = QLabel(
            "Gefundene Mod-Ordner aus dem "
            "eingestellten Mods-Verzeichnis."
        )
        description_label.setObjectName(
            "pageDescription"
        )

        main_layout.addWidget(title_label)
        main_layout.addWidget(
            description_label
        )

        toolbar = QFrame()
        toolbar.setObjectName(
            "libraryToolbar"
        )

        toolbar_layout = QHBoxLayout(
            toolbar
        )
        toolbar_layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )
        toolbar_layout.setSpacing(12)

        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.path_label.setObjectName(
            "libraryPath"
        )

        self.location_label.setObjectName(
            "locationBadge"
        )

        self.refresh_button.clicked.connect(
            self.scan_mods
        )
        character_filter_label = QLabel(
            "Charakter:"
        )
        
        character_filter_label.setObjectName(
            "characterFilterLabel"
        )
        
        self.character_filter.setMinimumWidth(
            180
        )
        mod_type_filter_label= QLabel(
            "Mod-Typ:"
        )
        
        mod_type_filter_label.setObjectName(
            "modTypeFilterLabel"
        )
        
        self.mod_type_filter.setMinimumWidth(
            170
        )
        
        self.mod_type_filter.currentIndexChanged.connect(
            self._apply_mod_filters
        )
        
        self.character_filter.currentIndexChanged.connect(
            self._apply_mod_filters
        )
        
        self.toggle_button = QPushButton(
            "Aktivieren"
        )
        
        self.toggle_button.setEnabled(
            False
        )
        
        self.toggle_button.clicked.connect(
            self._toggle_selected_mod
        )

        self.import_button = QToolButton()
        self.import_button.setObjectName(
            "importButton"
        )
        self.import_button.setText(
            "Importieren"
        )

        self.import_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

        import_menu = QMenu(
            self.import_button
        )

        import_menu.addAction(
            "ZIP oder Archiv auswählen",
            self._choose_import_archives,
        )

        import_menu.addAction(
            "Mod-Ordner auswählen",
            self._choose_import_directory,
        )

        self.import_button.setMenu(
            import_menu
        )

        self.import_button.clicked.connect(
            self._choose_import_archives
        )

        self.cancel_import_button = QPushButton(
            "Import abbrechen"
        )

        self.cancel_import_button.setVisible(
            False
        )

        self.cancel_import_button.clicked.connect(
            self.cancel_import
        )
                
        toolbar_layout.addWidget(
            self.path_label,
            stretch=1,
        )
        toolbar_layout.addWidget(
            self.location_label
        )
        toolbar_layout.addWidget(
            character_filter_label
        )
        toolbar_layout.addWidget(
            self.character_filter
        )
        
        toolbar_layout.addWidget(
            mod_type_filter_label
        )
        
        toolbar_layout.addWidget(
            self.mod_type_filter
        )
        toolbar_layout.addWidget(
            self.ignore_conflict_button
        )

        toolbar_layout.addWidget(
            self.toggle_button
        )

        toolbar_layout.addWidget(
            self.import_button
        )

        toolbar_layout.addWidget(
            self.cancel_import_button
        )

        toolbar_layout.addWidget(
            self.refresh_button
        )

        main_layout.addWidget(toolbar)

        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)

        main_layout.addWidget(
            self.progress_bar
        )

        self.mod_table.setColumnCount(9)

        headers =[
                "Mod",
                "Charakter",
                "Mod-Typ",
                "Status"
                "Speicherort",
                "Dateien",
                "INI-Dateien",
                "Größe",
                "Geändert",
                "Pfad",
            ]
        

        self.mod_table.setColumnCount(
            len(headers)
        )
        
        self.mod_table.setHorizontalHeaderLabels(
            headers
        )
        
        header = self.mod_table.horizontalHeader()
        
        # Die Mod-Spalte enthält ein eigenes Widget.
        # ResizeToContents funktioniert dafür nicht zuverlässig.
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Interactive,
        )       
         
        self.mod_table.setColumnWidth(
            0,
            420,
        )
            
        for column in range (
            1,
            self.mod_table.columnCount() - 1,
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        
        # Die letzte Pfad-Spalte nutzt den restlichen Platz.
        header.setSectionResizeMode(
            self.mod_table.columnCount() - 1,
            QHeaderView.ResizeMode.Stretch,
        )
                
        main_layout.addWidget(
            self.mod_table,
            stretch=1,
        )
        
        self.mod_table.itemSelectionChanged.connect(
            self._update_toggle_button
        )

        self.status_label.setObjectName(
            "libraryStatus"
        )

        main_layout.addWidget(
            self.status_label
        )

        self._apply_stylesheet()
        
        self.setAcceptDrops(
            True
        )

        self.mod_table.setAcceptDrops(
            True
        )

        self.mod_table.viewport().setAcceptDrops(
            True
        )

        self.mod_table.viewport().installEventFilter(
            self
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
        self.thread_pool.start(task)


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

        self._finish_task()

    def _on_scan_cancelled(self) -> None:
        self.status_label.setText(
            "Scan wurde abgebrochen."
        )

        self._finish_task()

    def _finish_task(self) -> None:
        self.current_task = None

        self.refresh_button.setEnabled(
            True
        )

        self.progress_bar.setVisible(
            False
        )

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
        self.mods_by_path = {
            str(mod.path): mod
            for mod in result.mods
        }

        self.mod_table.setSortingEnabled(
            False
        )

        self.mod_table.setRowCount(
            len(result.mods)
        )

        for row, mod in enumerate(
            result.mods
        ):
            self._set_mod_row(
                row,
                mod,
            )

        self.mod_table.setSortingEnabled(
            True
        )
        
        self.mod_table.verticalHeader().setVisible(
            False
        )

        # Legt die Höhe jeder Tabellenzeile fest.
        self.mod_table.verticalHeader().setDefaultSectionSize(
            42
        )

        header = self.mod_table.horizontalHeader()      

        self._update_character_filter(
            result.mods
        )

        self._update_mod_type_filter(
            result.mods
        )

        self._apply_mod_filters()
        self._update_toggle_button()
        
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
        _index: int | None = None,
    ) -> None:
        """Wendet Charakter- und Mod-Typ-Filter gemeinsam an."""

        selected_character = (
            self.character_filter.currentData()
        )

        selected_mod_type = (
            self.mod_type_filter.currentData()
        )

        visible_mods = 0

        for row in range(
            self.mod_table.rowCount()
        ):
            character_item = self.mod_table.item(
                row,
                1,
            )

            mod_type_item = self.mod_table.item(
                row,
                2,
            )

            if (
                character_item is None
                or mod_type_item is None
            ):
                self.mod_table.setRowHidden(
                    row,
                    True,
                )
                continue

            characters = character_item.data(
                Qt.ItemDataRole.UserRole
            )

            if not isinstance(
                characters,
                list,
            ):
                characters = []

            row_mod_type = mod_type_item.data(
                Qt.ItemDataRole.UserRole
            )

            if selected_character is None:
                matches_character = True

            elif selected_character == "__unknown__":
                matches_character = not characters

            else:
                matches_character = any(
                    character.casefold()
                    == str(selected_character).casefold()
                    for character in characters
                )

            if selected_mod_type is None:
                matches_mod_type = True
            else:
                matches_mod_type = (
                    str(row_mod_type).casefold()
                    == str(selected_mod_type).casefold()
                )

            row_visible = (
                matches_character
                and matches_mod_type
            )

            self.mod_table.setRowHidden(
                row,
                not row_visible,
            )

            if row_visible:
                visible_mods += 1

        self.status_label.setText(
            f"{visible_mods} von "
            f"{self.mod_table.rowCount()} Mods werden angezeigt."
        )
        
    def _set_mod_row(
        self,
        row: int,
        mod: ModInfo,
    ) -> None:
        state = self.mod_manager.get_state(
            mod.path
        )

        # Der sichtbare Name wird vom QLabel im Cell-Widget dargestellt.
        # Das Tabellen-Item bleibt nur für Pfad, Auswahl und Sortierung bestehen.
        name_item = QTableWidgetItem("")

        name_item.setData(
            Qt.ItemDataRole.UserRole,
            str(mod.path),
        )

        if mod.error:
            name_item.setToolTip(
                mod.error
            )

        character_text = (
            ", ".join(mod.characters)
            if mod.characters
            else "Unbekannt"
        )

        character_item = QTableWidgetItem(
            character_text
        )   

        character_item.setData(
            Qt.ItemDataRole.UserRole,
            list(mod.characters),
        )

        mod_type_item = QTableWidgetItem(
            mod.mod_type
        )

        mod_type_item.setData(
            Qt.ItemDataRole.UserRole,
            mod.mod_type,
        )

        state_item = QTableWidgetItem(
            mod_state_label(state)
        )

        state_item.setData(
            Qt.ItemDataRole.UserRole,
            state.value,
        )

        location_parts = [
            "Netzwerk"
            if mod.is_network
            else "Lokal"
        ]

        if mod.is_symlink:
            location_parts.append(
                "Symlink"
            )

        location_item = QTableWidgetItem(
            " · ".join(location_parts)
        )

        file_count_item = QTableWidgetItem(
            str(mod.file_count)
        )   

        ini_count_item = QTableWidgetItem(
            str(mod.ini_file_count)
        )

        size_item = QTableWidgetItem(
            format_file_size(
                mod.total_size
            )
        )

        modified_item = QTableWidgetItem(
            format_timestamp(
                mod.modified_at
            )
        )

        path_item = QTableWidgetItem(
            mod.relative_path
            or str(mod.path)
        )

        path_item.setToolTip(
            str(mod.path)
        )

        items = (
            name_item,
            character_item,
            mod_type_item,
            state_item,
            location_item,
            file_count_item,
            ini_count_item,
            size_item,
            modified_item,
            path_item,
        )

        for column, item in enumerate(items):
            self.mod_table.setItem(
                row,
                column,
                item,
            )
        
        self._set_mod_name_widget(
            row=row,
            mod=mod,
        )

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
     
    def _set_mod_name_widget(
        self,
        row: int,
        mod: ModInfo,
    ) -> None:
        """Zeigt den Modnamen und den Info-Button in einer Zelle."""
        container = QWidget()
        container.setObjectName("modNameContainer")
        container.setAutoFillBackground(False)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            8,
            2,
            6,
            2,
        )
        layout.setSpacing(6)

        name_label = QLabel(mod.name)
        name_label.setObjectName("modNameLabel")
        name_label.setToolTip(str(mod.path))
        
        name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        name_label.setMinimumWidth(0)

        # Der Labeltext soll keine Mausklicks abfangen.
        name_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        


        info_button = QToolButton()
        info_button.setObjectName("modInfoButton")
        info_button.setText("?")
        info_button.setFixedSize(24, 24)
        info_button.setToolTip(
            "Merge- und Master-INI analysieren"
        )

        info_button.clicked.connect(
            partial(
                self._show_mod_info,
                mod,
            )
        )

        layout.addWidget(
            name_label,
            stretch=1,
        )
        layout.addWidget(info_button)

        self.mod_table.setCellWidget(
            row,
            0,
            container,
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
        row = self.mod_table.currentRow()

        if row < 0:
            return None

        name_item = self.mod_table.item(
            row,
            0,
        )

        if name_item is None:
            return None

        mod_path = name_item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(mod_path, str):
            return None

        return self.mods_by_path.get(
            mod_path
        )

    def _update_toggle_button(
        self,
    ) -> None:
        """Aktualisiert die Aktionen für den ausgewählten Mod."""
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

        self.mod_table.setSortingEnabled(
            False
        )

        for row in range(
            self.mod_table.rowCount()
        ):
            name_item = self.mod_table.item(
                row,
                0,
            )

            if name_item is None:
                continue

            item_path = name_item.data(
                Qt.ItemDataRole.UserRole
            )

            if item_path != str(mod.path):
                continue

            state_item = self.mod_table.item(
                row,
                3,
            )

            if state_item is None:
                state_item = QTableWidgetItem()
                self.mod_table.setItem(
                    row,
                    3,
                    state_item,
                )

            state_item.setText(
                mod_state_label(state)
            )

            state_item.setData(
                Qt.ItemDataRole.UserRole,
                state.value,
            )

            break

        self.mod_table.setSortingEnabled(
            True
        )

        self._update_toggle_button()
               
    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(
            """
            QFrame#libraryToolbar {
                background-color: #20232a;
                border: 1px solid #30343d;
                border-radius: 8px;
            }

            QLabel#libraryPath {
                color: #cbd0d8;
            }

            QLabel#locationBadge {
                background-color: #30343d;
                border-radius: 5px;
                padding: 6px 10px;
                color: #cbd0d8;
            }

            QLabel#libraryStatus {
                color: #969ca8;
                font-size: 13px;
            }

            QTableWidget {
                background-color: #20232a;
                alternate-background-color: #242830;
                border: 1px solid #30343d;
                border-radius: 8px;
                gridline-color: #30343d;
            }

            QTableWidget::item {
                padding: 7px;
            }

            QTableWidget::item:selected {
                background-color: #7c5cff;
                color: #ffffff;
            }

            QHeaderView::section {
                background-color: #292d35;
                color: #d6d9df;
                border: none;
                border-right: 1px solid #383d47;
                border-bottom: 1px solid #383d47;
                padding: 8px;
                font-weight: bold;
            }

            QProgressBar {
                min-height: 20px;
                background-color: #20232a;
                border: 1px solid #30343d;
                border-radius: 5px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #7c5cff;
                border-radius: 4px;
            }
            
            
            QWidget#modNameContainer {
                background-color: transparent;
                border: none;
            }

            QLabel#modNameLabel {
                background-color: transparent;
                border: none;
                color: #f1f1f1;
                background-color: transparent;
            }

            QToolButton#modInfoButton {
                background-color: #353a44;
                color: #d8dce5;
                border: 1px solid #4a505d;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }

            QToolButton#modInfoButton:hover {
                background-color: #7c5cff;
                color: #ffffff;
                border-color: #8b70ff;
            }
            
            QToolButton#importButton {
                min-height: 36px;
                padding: 0 14px;
                background-color: #7c5cff;
                color: #ffffff;
                border: 1px solid #8b70ff;
                border-radius: 6px;
                font-weight: bold;
            }

            QToolButton#importButton:hover {
                background-color: #8b70ff;
            }

            QToolButton#importButton:disabled {
                background-color: #343742;
                color: #777d89;
                border-color: #414651;
            }
                        
            """           
        )

def format_file_size(
    size: int | None,
) -> str:
    if size is None:
        return "Nicht berechnet"

    units = (
        "B",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
    )

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"

            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"

def format_timestamp(
    timestamp: float | None,
) -> str:
    if timestamp is None:
        return "Unbekannt"

    return datetime.fromtimestamp(
        timestamp
    ).strftime(
        "%d.%m.%Y %H:%M"
    )