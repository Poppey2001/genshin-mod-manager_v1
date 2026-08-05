from __future__ import annotations

import threading
from datetime import datetime

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QMessageBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    
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
        
        self.refresh_button = QPushButton(
            "Neu scannen"
        )

        self.progress_bar = QProgressBar()

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
            self.toggle_button
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
        
        for column in range (
            len(headers)-1
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        
        header.setSectionResizeMode(
            len(headers) -1,
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

    def scan_mods(self) -> None:
        """Startet einen asynchronen Scan."""
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

        name_item = QTableWidgetItem(
            mod.name
        )

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
        mod = self._selected_mod()

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

        else:
            self.toggle_button.setText(
                "Konflikt"
            )
            self.toggle_button.setEnabled(
                False
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