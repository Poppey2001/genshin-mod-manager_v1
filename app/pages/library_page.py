from __future__ import annotations

import threading
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
from app.utils.formatters import (
    format_file_size,
    format_timestamp,
)
from app.widgets.library.library_filter_bar import (
    LibraryFilterBar,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
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

MOD_OBJECT_ROLE = (
    int(Qt.ItemDataRole.UserRole) + 10
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
        self.current_import_task: ImportWorker | None = None
        self.current_bulk_task: BulkModWorker | None = None

        self.scan_again = False

        self.path_label = QLabel()
        self.location_label = QLabel()
        self.status_label = QLabel()

        self.status_label = QLabel()

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

        self.total_stat_value = QLabel("0")
        self.active_stat_value = QLabel("0")
        self.conflict_stat_value = QLabel("0")
        self.character_stat_value = QLabel("0")
        
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
        self.mod_table = QTableWidget()
        
        self.filter_bar.filters_changed.connect(
            self._apply_mod_filters
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
            self._create_header_section()
        )
        main_layout.addWidget(
            self._create_stats_section()
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

    def _create_header_section(self) -> QWidget:
        header = QFrame()
        header.setObjectName("libraryHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(16)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        title_label = QLabel("Mod-Bibliothek")
        title_label.setObjectName("pageTitle")

        description_label = QLabel(
            "Verwalte, filtere und organisiere deine Genshin-Mods."
        )
        description_label.setObjectName("pageDescription")

        title_layout.addWidget(title_label)
        title_layout.addWidget(description_label)

        self.import_button = QToolButton()
        self.import_button.setObjectName("importButton")
        self.import_button.setText("＋  Importieren")
        self.import_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

        import_menu = QMenu(self.import_button)
        import_menu.addAction(
            "ZIP oder Archiv auswählen",
            self._choose_import_archives,
        )
        import_menu.addAction(
            "Mod-Ordner auswählen",
            self._choose_import_directory,
        )
        self.import_button.setMenu(import_menu)
        self.import_button.clicked.connect(
            self._choose_import_archives
        )

        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.scan_mods)

        self.cancel_import_button = QPushButton(
            "Import abbrechen"
        )
        self.cancel_import_button.setObjectName(
            "dangerButton"
        )
        self.cancel_import_button.setVisible(False)
        self.cancel_import_button.clicked.connect(
            self.cancel_import
        )

        layout.addLayout(title_layout, stretch=1)
        layout.addWidget(self.cancel_import_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.import_button)

        return header

    def _create_stats_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            self._create_stat_card(
                "Mods gesamt",
                self.total_stat_value,
                "totalStatCard",
                "Bibliothek",
            )
        )
        layout.addWidget(
            self._create_stat_card(
                "Aktiviert",
                self.active_stat_value,
                "activeStatCard",
                "Im Spiel geladen",
            )
        )
        layout.addWidget(
            self._create_stat_card(
                "Konflikte",
                self.conflict_stat_value,
                "conflictStatCard",
                "Benötigen Aufmerksamkeit",
            )
        )
        layout.addWidget(
            self._create_stat_card(
                "Charaktere",
                self.character_stat_value,
                "characterStatCard",
                "Erkannte Zuordnungen",
            )
        )

        return container

    def _create_stat_card(
        self,
        title: str,
        value_label: QLabel,
        object_name: str,
        subtitle: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setProperty("statCard", True)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        card.setMinimumHeight(94)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("statTitle")

        value_label.setObjectName("statValue")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("statSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)

        return card

    def _create_content_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("librarySplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._create_list_panel())
        splitter.addWidget(self._create_details_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 330])

        return splitter

    def _create_list_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("listPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        actions = QFrame()
        actions.setObjectName("selectionToolbar")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(14, 10, 14, 10)
        actions_layout.setSpacing(8)

        selection_label = QLabel("Auswahlaktionen")
        selection_label.setObjectName("sectionLabel")

        self.bulk_enable_button = QPushButton(
            "Auswahl aktivieren"
        )
        self.bulk_enable_button.setObjectName(
            "bulkEnableButton"
        )
        self.bulk_enable_button.setEnabled(False)
        self.bulk_enable_button.clicked.connect(
            partial(
                self._start_bulk_action,
                BulkAction.ENABLE,
            )
        )

        self.bulk_disable_button = QPushButton(
            "Auswahl deaktivieren"
        )
        self.bulk_disable_button.setObjectName(
            "bulkDisableButton"
        )
        self.bulk_disable_button.setEnabled(False)
        self.bulk_disable_button.clicked.connect(
            partial(
                self._start_bulk_action,
                BulkAction.DISABLE,
            )
        )

        self.bulk_adopt_button = QPushButton(
            "Konflikte übernehmen"
        )
        self.bulk_adopt_button.setObjectName(
            "bulkAdoptButton"
        )
        self.bulk_adopt_button.setEnabled(False)
        self.bulk_adopt_button.clicked.connect(
            partial(
                self._start_bulk_action,
                BulkAction.ADOPT,
            )
        )

        self.cancel_bulk_button = QPushButton(
            "Sammelaktion abbrechen"
        )
        self.cancel_bulk_button.setObjectName("dangerButton")
        self.cancel_bulk_button.setVisible(False)
        self.cancel_bulk_button.clicked.connect(
            self.cancel_bulk_action
        )

        actions_layout.addWidget(selection_label)
        actions_layout.addStretch()
        actions_layout.addWidget(self.bulk_enable_button)
        actions_layout.addWidget(self.bulk_disable_button)
        actions_layout.addWidget(self.bulk_adopt_button)
        actions_layout.addWidget(self.cancel_bulk_button)

        self.mod_table.setObjectName("modTable")
        self.mod_table.setAlternatingRowColors(True)
        self.mod_table.setShowGrid(False)
        self.mod_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.mod_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.verticalHeader().setDefaultSectionSize(44)
        self.mod_table.setColumnCount(10)

        headers = [
            "Mod",
            "Charakter",
            "Mod-Typ",
            "Status",
            "Speicherort",
            "Dateien",
            "INI-Dateien",
            "Größe",
            "Geändert",
            "Pfad",
        ]
        self.mod_table.setHorizontalHeaderLabels(headers)

        header = self.mod_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (1, 2, 3, 7, 8):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        # Technische Detailspalten bleiben im Modell erhalten,
        # werden aber im rechten Detailbereich übersichtlicher gezeigt.
        for column in (4, 5, 6, 9):
            self.mod_table.setColumnHidden(column, True)

        self.mod_table.itemSelectionChanged.connect(
            self._on_mod_selection_changed
        )

        layout.addWidget(actions)
        layout.addWidget(self.mod_table, stretch=1)

        return panel

    def _create_details_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("detailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(300)
        scroll.setMaximumWidth(430)

        panel = QFrame()
        panel.setObjectName("detailsPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        eyebrow = QLabel("MOD-DETAILS")
        eyebrow.setObjectName("detailEyebrow")

        self.details_title_label = QLabel(
            "Kein Mod ausgewählt"
        )
        self.details_title_label.setObjectName("detailTitle")
        self.details_title_label.setWordWrap(True)

        self.details_subtitle_label = QLabel(
            "Wähle links einen Mod aus, um Details und Aktionen zu sehen."
        )
        self.details_subtitle_label.setObjectName("detailSubtitle")
        self.details_subtitle_label.setWordWrap(True)

        self.details_status_label = QLabel("Keine Auswahl")
        self.details_status_label.setObjectName("detailStatusBadge")
        self.details_status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        divider = QFrame()
        divider.setObjectName("detailDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(12)
        detail_grid.setVerticalSpacing(11)
        detail_grid.setColumnStretch(1, 1)

        self.detail_character_value = self._create_detail_value()
        self.detail_type_value = self._create_detail_value()
        self.detail_location_value = self._create_detail_value()
        self.detail_files_value = self._create_detail_value()
        self.detail_ini_value = self._create_detail_value()
        self.detail_size_value = self._create_detail_value()
        self.detail_modified_value = self._create_detail_value()
        self.detail_path_value = self._create_detail_value(
            word_wrap=True,
            selectable=True,
        )

        detail_rows = (
            ("Charakter", self.detail_character_value),
            ("Mod-Typ", self.detail_type_value),
            ("Speicherort", self.detail_location_value),
            ("Dateien", self.detail_files_value),
            ("INI-Dateien", self.detail_ini_value),
            ("Größe", self.detail_size_value),
            ("Geändert", self.detail_modified_value),
            ("Pfad", self.detail_path_value),
        )

        for row, (caption, value_label) in enumerate(
            detail_rows
        ):
            caption_label = QLabel(caption)
            caption_label.setObjectName("detailCaption")
            caption_label.setAlignment(
                Qt.AlignmentFlag.AlignTop
            )
            detail_grid.addWidget(caption_label, row, 0)
            detail_grid.addWidget(value_label, row, 1)

        action_title = QLabel("Aktionen")
        action_title.setObjectName("detailSectionTitle")

        self.toggle_button = QPushButton("Aktivieren")
        self.toggle_button.setObjectName("primaryActionButton")
        self.toggle_button.setEnabled(False)
        self.toggle_button.clicked.connect(
            self._toggle_selected_mod
        )

        self.ignore_conflict_button.setObjectName(
            "warningActionButton"
        )

        self.detail_info_button = QPushButton(
            "INI-Steuerung analysieren"
        )
        self.detail_info_button.setObjectName(
            "secondaryActionButton"
        )
        self.detail_info_button.setEnabled(False)
        self.detail_info_button.clicked.connect(
            self._show_selected_mod_info
        )

        layout.addWidget(eyebrow)
        layout.addWidget(self.details_title_label)
        layout.addWidget(self.details_subtitle_label)
        layout.addWidget(
            self.details_status_label,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(divider)
        layout.addLayout(detail_grid)
        layout.addStretch()
        layout.addWidget(action_title)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.ignore_conflict_button)
        layout.addWidget(self.detail_info_button)

        scroll.setWidget(panel)
        return scroll

    def _create_detail_value(
        self,
        *,
        word_wrap: bool = False,
        selectable: bool = False,
    ) -> QLabel:
        label = QLabel("—")
        label.setObjectName("detailValue")
        label.setWordWrap(word_wrap)

        if selectable:
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

        return label

    def _show_selected_mod_info(self) -> None:
        mod = self._selected_mod()
        if mod is not None:
            self._show_mod_info(mod)

    def _update_stats(self) -> None:
        total = self.mod_table.rowCount()
        active = 0
        conflicts = 0
        characters: set[str] = set()

        for row in range(total):
            name_item = self.mod_table.item(row, 0)
            state_item = self.mod_table.item(row, 3)

            if state_item is not None:
                state_value = state_item.data(
                    Qt.ItemDataRole.UserRole
                )
                if state_value == ModState.ENABLED.value:
                    active += 1
                elif state_value == ModState.CONFLICT.value:
                    conflicts += 1

            if name_item is None:
                continue

            mod = name_item.data(MOD_OBJECT_ROLE)
            if isinstance(mod, ModInfo):
                characters.update(mod.characters)

        self.total_stat_value.setText(str(total))
        self.active_stat_value.setText(str(active))
        self.conflict_stat_value.setText(str(conflicts))
        self.character_stat_value.setText(
            str(len(characters))
        )

    def _update_details_panel(self) -> None:
        selected_mods = self._selected_mods()

        if len(selected_mods) > 1:
            self.details_title_label.setText(
                f"{len(selected_mods)} Mods ausgewählt"
            )
            self.details_subtitle_label.setText(
                "Nutze die Auswahlaktionen oberhalb der Liste."
            )
            self.details_status_label.setText("Mehrfachauswahl")
            self._set_detail_status_style("multiple")
            self._clear_detail_values()
            self.detail_info_button.setEnabled(False)
            return

        mod = self._selected_mod()
        if mod is None:
            self.details_title_label.setText(
                "Kein Mod ausgewählt"
            )
            self.details_subtitle_label.setText(
                "Wähle links einen Mod aus, um Details und Aktionen zu sehen."
            )
            self.details_status_label.setText("Keine Auswahl")
            self._set_detail_status_style("none")
            self._clear_detail_values()
            self.detail_info_button.setEnabled(False)
            return

        state = self.mod_manager.get_state(mod.path)
        character_text = (
            ", ".join(mod.characters)
            if mod.characters
            else "Unbekannt"
        )
        location_text = (
            "Netzwerk" if mod.is_network else "Lokal"
        )
        if mod.is_symlink:
            location_text += " · Symlink"

        self.details_title_label.setText(mod.name)
        self.details_subtitle_label.setText(
            mod.relative_path or str(mod.path)
        )
        self.details_status_label.setText(
            mod_state_label(state)
        )
        self._set_detail_status_style(state.value)

        self.detail_character_value.setText(character_text)
        self.detail_type_value.setText(mod.mod_type or "Unbekannt")
        self.detail_location_value.setText(location_text)
        self.detail_files_value.setText(str(mod.file_count))
        self.detail_ini_value.setText(str(mod.ini_file_count))
        self.detail_size_value.setText(
            format_file_size(mod.total_size)
        )
        self.detail_modified_value.setText(
            format_timestamp(mod.modified_at)
        )
        self.detail_path_value.setText(str(mod.path))
        self.detail_info_button.setEnabled(True)

    def _clear_detail_values(self) -> None:
        for label in (
            self.detail_character_value,
            self.detail_type_value,
            self.detail_location_value,
            self.detail_files_value,
            self.detail_ini_value,
            self.detail_size_value,
            self.detail_modified_value,
            self.detail_path_value,
        ):
            label.setText("—")

    def _set_detail_status_style(self, state: str) -> None:
        colors = {
            ModState.ENABLED.value: ("#163d2a", "#67e8a5"),
            ModState.DISABLED.value: ("#28303d", "#b7c0cf"),
            ModState.CONFLICT.value: ("#4a2f12", "#ffc56d"),
            ModState.BROKEN.value: ("#4a2027", "#ff8d9a"),
            ModState.NOT_CONFIGURED.value: ("#3d314c", "#d8b4fe"),
            "multiple": ("#30275b", "#c4b5fd"),
            "none": ("#282c34", "#9299a6"),
        }
        background, foreground = colors.get(
            state,
            colors["none"],
        )
        self.details_status_label.setStyleSheet(
            "background-color: "
            f"{background}; color: {foreground}; "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 10px; padding: 5px 10px; "
            "font-weight: 700;"
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
        self._update_stats()
        self._update_details_panel()

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
        """Wendet Suche, Charakter-, Typ- und Statusfilter an."""
        selected_character = self.character_filter.currentData()
        selected_mod_type = self.mod_type_filter.currentData()
        selected_status = self.status_filter.currentData()
        search_term = self.search_input.text().strip().casefold()

        visible_mods = 0

        for row in range(self.mod_table.rowCount()):
            name_item = self.mod_table.item(row, 0)
            character_item = self.mod_table.item(row, 1)
            mod_type_item = self.mod_table.item(row, 2)
            state_item = self.mod_table.item(row, 3)

            if (
                name_item is None
                or character_item is None
                or mod_type_item is None
                or state_item is None
            ):
                self.mod_table.setRowHidden(row, True)
                continue

            mod = name_item.data(MOD_OBJECT_ROLE)
            if not isinstance(mod, ModInfo):
                self.mod_table.setRowHidden(row, True)
                continue

            characters = character_item.data(
                Qt.ItemDataRole.UserRole
            )
            if not isinstance(characters, list):
                characters = []

            row_mod_type = mod_type_item.data(
                Qt.ItemDataRole.UserRole
            )
            row_status = state_item.data(
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

            matches_mod_type = (
                selected_mod_type is None
                or str(row_mod_type).casefold()
                == str(selected_mod_type).casefold()
            )

            matches_status = (
                selected_status is None
                or row_status == selected_status
            )

            searchable_text = " ".join(
                (
                    mod.name,
                    " ".join(mod.characters),
                    mod.mod_type or "",
                    mod.relative_path or "",
                    str(mod.path),
                )
            ).casefold()
            matches_search = (
                not search_term
                or search_term in searchable_text
            )

            row_visible = (
                matches_character
                and matches_mod_type
                and matches_status
                and matches_search
            )
            self.mod_table.setRowHidden(row, not row_visible)

            if row_visible:
                visible_mods += 1

        self.status_label.setText(
            f"{visible_mods} von "
            f"{self.mod_table.rowCount()} Mods werden angezeigt."
        )
        self._update_bulk_buttons()

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

        name_item.setData(
            MOD_OBJECT_ROLE,
            mod,
        )

        name_item.setToolTip(
            str(mod.path)
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
        
    def _selected_mods(
        self,
    ) -> list[ModInfo]:
        """
        Liefert alle ausgewählten und sichtbaren Mods.

        Versteckte Zeilen werden nicht in Sammelaktionen
        aufgenommen.
        """
        selection_model = (
            self.mod_table.selectionModel()
        )

        if selection_model is None:
            return []

        selected_rows = sorted(
            {
                index.row()
                for index in selection_model.selectedRows()
                if not self.mod_table.isRowHidden(
                    index.row()
                )
            }
        )

        selected_mods: list[ModInfo] = []

        for row in selected_rows:
            name_item = self.mod_table.item(
                row,
                0,
            )

            if name_item is None:
                continue

            mod = name_item.data(
                MOD_OBJECT_ROLE
            )

            if not isinstance(
                mod,
                ModInfo,
            ):
                continue

            selected_mods.append(
                mod
            )

        return selected_mods
        
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

        if not running:
            self._update_toggle_button()
            self._update_bulk_buttons()       
 
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