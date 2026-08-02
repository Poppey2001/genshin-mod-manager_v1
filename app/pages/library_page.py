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
    QFrame,
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

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.current_task: ScanTask | None = None
        self.scan_again = False

        self.path_label = QLabel()
        self.location_label = QLabel()
        self.status_label = QLabel()

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

        toolbar_layout.addWidget(
            self.path_label,
            stretch=1,
        )
        toolbar_layout.addWidget(
            self.location_label
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

        self.mod_table.setColumnCount(7)

        self.mod_table.setHorizontalHeaderLabels(
            [
                "Mod",
                "Speicherort",
                "Dateien",
                "INI-Dateien",
                "Größe",
                "Geändert",
                "Pfad",
            ]
        )

        self.mod_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.mod_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.mod_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.mod_table.setAlternatingRowColors(
            True
        )

        self.mod_table.setSortingEnabled(
            True
        )

        self.mod_table.verticalHeader().setVisible(
            False
        )

        header = (
            self.mod_table.horizontalHeader()
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.Stretch,
        )

        main_layout.addWidget(
            self.mod_table,
            stretch=1,
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
            self.config.active_mods_directory
        )

        if mods_directory is None:
            self.path_label.setText(
                "Kein Mods-Ordner eingestellt"
            )

            self.location_label.setText(
                "Nicht konfiguriert"
            )

            self.status_label.setText(
                "Wähle zuerst unter Einstellungen "
                "einen Mods-Ordner aus."
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

    def _set_mod_row(
        self,
        row: int,
        mod: ModInfo,
    ) -> None:
        name_item = QTableWidgetItem(
            mod.name
        )

        if mod.error:
            name_item.setToolTip(
                mod.error
            )

        location_parts: list[str] = []

        location_parts.append(
            "Netzwerk"
            if mod.is_network
            else "Lokal"
        )

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
            str(mod.path)
        )

        path_item.setToolTip(
            str(mod.path)
        )

        self.mod_table.setItem(
            row,
            0,
            name_item,
        )
        self.mod_table.setItem(
            row,
            1,
            location_item,
        )
        self.mod_table.setItem(
            row,
            2,
            file_count_item,
        )
        self.mod_table.setItem(
            row,
            3,
            ini_count_item,
        )
        self.mod_table.setItem(
            row,
            4,
            size_item,
        )
        self.mod_table.setItem(
            row,
            5,
            modified_item,
        )
        self.mod_table.setItem(
            row,
            6,
            path_item,
        )

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