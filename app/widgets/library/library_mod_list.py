from __future__ import annotations
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    Signal,
)
from dataclasses import dataclass
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.models.mod import ModInfo

from app.services.mod_manager import (
    ModState,
    mod_state_label,
)

from app.utils.formatters import (
    format_file_size,
    format_timestamp,
)

MOD_OBJECT_ROLE = (
    int(Qt.ItemDataRole.UserRole) + 10
)

@dataclass(frozen=True, slots=True)
class ModListStatistics:
    total: int
    active: int
    conflicts: int
    characters: int
class LibraryModListWidget(QFrame):
    """
    Linker Tabellenbereich der Mod-Bibliothek.

    Enthält:
    - Auswahlaktionen
    - Mod-Tabelle
    - UI-Signale

    Die eigentliche Mod- und Bulk-Logik bleibt
    weiterhin in LibraryPage.
    """

    enable_requested = Signal()
    disable_requested = Signal()
    adopt_requested = Signal()
    cancel_requested = Signal()
    selection_changed = Signal()
    info_requested = Signal(object)
    
    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName(
            "listPanel"
        )

        self.bulk_enable_button = QPushButton(
            "Auswahl aktivieren"
        )

        self.bulk_disable_button = QPushButton(
            "Auswahl deaktivieren"
        )

        self.bulk_adopt_button = QPushButton(
            "Konflikte übernehmen"
        )

        self.cancel_bulk_button = QPushButton(
            "Sammelaktion abbrechen"
        )

        self.table = QTableWidget()

        self._configure_buttons()
        self._configure_table()
        self._build_ui()
        self._connect_signals()

    def statistics(
        self,
    ) -> ModListStatistics:
        """
        Berechnet die Statistik über alle Mods
        in der Tabelle.

        Gefilterte bzw. versteckte Zeilen zählen
        weiterhin zur Gesamtstatistik.
        """
        total = self.table.rowCount()

        active = 0
        conflicts = 0

        characters: set[str] = set()

        for row in range(total):
            name_item = self.table.item(
                row,
                0,
            )

            state_item = self.table.item(
                row,
                3,
            )

            if state_item is not None:
                state_value = state_item.data(
                    Qt.ItemDataRole.UserRole
                )

                if (
                    state_value
                    == ModState.ENABLED.value
                ):
                    active += 1

                elif (
                    state_value
                    == ModState.CONFLICT.value
                ):
                    conflicts += 1

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

            characters.update(
                mod.characters
            )

        return ModListStatistics(
            total=total,
            active=active,
            conflicts=conflicts,
            characters=len(characters),
        )

    def _configure_buttons(self) -> None:
        self.bulk_enable_button.setObjectName(
            "bulkEnableButton"
        )
        self.bulk_enable_button.setEnabled(
            False
        )

        self.bulk_disable_button.setObjectName(
            "bulkDisableButton"
        )
        self.bulk_disable_button.setEnabled(
            False
        )

        self.bulk_adopt_button.setObjectName(
            "bulkAdoptButton"
        )
        self.bulk_adopt_button.setEnabled(
            False
        )

        self.cancel_bulk_button.setObjectName(
            "dangerButton"
        )
        self.cancel_bulk_button.setVisible(
            False
        )

    def _configure_table(self) -> None:
        self.table.setObjectName(
            "modTable"
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.setShowGrid(
            False
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.verticalHeader().setDefaultSectionSize(
            44
        )

        self.table.setColumnCount(
            10
        )

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

        self.table.setHorizontalHeaderLabels(
            headers
        )

        header = self.table.horizontalHeader()

        header.setHighlightSections(
            False
        )

        header.setStretchLastSection(
            False
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in (
            1,
            2,
            3,
            7,
            8,
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        # Diese technischen Spalten bleiben in der Tabelle,
        # werden aber hauptsächlich im Detailpanel angezeigt.
        for column in (
            4,
            5,
            6,
            9,
        ):
            self.table.setColumnHidden(
                column,
                True,
            )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            0
        )

        actions = QFrame()
        actions.setObjectName(
            "selectionToolbar"
        )

        actions_layout = QHBoxLayout(
            actions
        )

        actions_layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        actions_layout.setSpacing(
            8
        )

        selection_label = QLabel(
            "Auswahlaktionen"
        )

        selection_label.setObjectName(
            "sectionLabel"
        )

        actions_layout.addWidget(
            selection_label
        )

        actions_layout.addStretch()

        actions_layout.addWidget(
            self.bulk_enable_button
        )

        actions_layout.addWidget(
            self.bulk_disable_button
        )

        actions_layout.addWidget(
            self.bulk_adopt_button
        )

        actions_layout.addWidget(
            self.cancel_bulk_button
        )

        layout.addWidget(
            actions
        )

        layout.addWidget(
            self.table,
            stretch=1,
        )

    def _connect_signals(self) -> None:
        self.bulk_enable_button.clicked.connect(
            self._emit_enable_requested
        )

        self.bulk_disable_button.clicked.connect(
            self._emit_disable_requested
        )

        self.bulk_adopt_button.clicked.connect(
            self._emit_adopt_requested
        )

        self.cancel_bulk_button.clicked.connect(
            self._emit_cancel_requested
        )

        self.table.itemSelectionChanged.connect(
            self.selection_changed.emit
        )

    def set_mods(
        self,
        mods: list[ModInfo],
        state_provider: Callable[
            [Path],
            ModState,
        ],
    ) -> None:
        """
        Ersetzt den gesamten Tabelleninhalt.

        Der state_provider liefert den aktuellen
        Verwaltungsstatus eines Mods.
        """
        self.table.setSortingEnabled(
            False
        )

        self.table.setRowCount(
            len(mods)
        )

        for row, mod in enumerate(
            mods
        ):
            state = state_provider(
                mod.path
            )

            self._set_mod_row(
                row=row,
                mod=mod,
                state=state,
            )

        self.table.setSortingEnabled(
            True
        )

    def _set_mod_row(
        self,
        *,
        row: int,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        name_item = QTableWidgetItem(
            ""
        )

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
            or "Unbekannt"
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
            " · ".join(
                location_parts
            )
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

        for column, item in enumerate(
            items
        ):
            self.table.setItem(
                row,
                column,
                item,
            )

        self._set_mod_name_widget(
            row=row,
            mod=mod,
        )

    def _set_mod_name_widget(
        self,
        *,
        row: int,
        mod: ModInfo,
    ) -> None:
        """
        Erstellt die sichtbare Namenszelle
        einschließlich Info-Button.
        """
        container = QWidget()

        container.setObjectName(
            "modNameContainer"
        )

        container.setAutoFillBackground(
            False
        )

        layout = QHBoxLayout(
            container
        )

        layout.setContentsMargins(
            8,
            2,
            6,
            2,
        )

        layout.setSpacing(
            6
        )

        name_label = QLabel(
            mod.name
        )

        name_label.setObjectName(
            "modNameLabel"
        )

        name_label.setToolTip(
            str(mod.path)
        )

        name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        name_label.setMinimumWidth(
            0
        )

        name_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        info_button = QToolButton()

        info_button.setObjectName(
            "modInfoButton"
        )

        info_button.setText(
            "?"
        )

        info_button.setFixedSize(
            24,
            24,
        )

        info_button.setToolTip(
            "Merge- und Master-INI analysieren"
        )

        info_button.clicked.connect(
            lambda _checked=False, current_mod=mod:
            self.info_requested.emit(
                current_mod
            )
        )

        layout.addWidget(
            name_label,
            stretch=1,
        )

        layout.addWidget(
            info_button
        )

        self.table.setCellWidget(
            row,
            0,
            container,
        )

    def selected_mod(
        self,
    ) -> ModInfo | None:
        row = self.table.currentRow()

        if row < 0:
            return None

        name_item = self.table.item(
            row,
            0,
        )

        if name_item is None:
            return None

        mod = name_item.data(
            MOD_OBJECT_ROLE
        )

        if not isinstance(
            mod,
            ModInfo,
        ):
            return None

        return mod

    def selected_mods(
        self,
    ) -> list[ModInfo]:
        """
        Gibt alle ausgewählten sichtbaren Mods zurück.
        """
        selection_model = (
            self.table.selectionModel()
        )

        if selection_model is None:
            return []

        selected_rows = sorted(
            {
                index.row()
                for index
                in selection_model.selectedRows()
                if not self.table.isRowHidden(
                    index.row()
                )
            }
        )

        selected_mods: list[ModInfo] = []

        for row in selected_rows:
            name_item = self.table.item(
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
    
    def update_mod_state(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        """
        Aktualisiert nur den Status eines vorhandenen Mods.
        """
        self.table.setSortingEnabled(
            False
        )

        try:
            for row in range(
                self.table.rowCount()
            ):
                name_item = self.table.item(
                    row,
                    0,
                )

                if name_item is None:
                    continue

                row_mod = name_item.data(
                    MOD_OBJECT_ROLE
                )

                if not isinstance(
                    row_mod,
                    ModInfo,
                ):
                    continue

                if row_mod.path != mod.path:
                    continue

                state_item = self.table.item(
                    row,
                    3,
                )

                if state_item is None:
                    state_item = QTableWidgetItem()

                    self.table.setItem(
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

        finally:
            self.table.setSortingEnabled(
                True
            )    

    def row_count(
        self,
    ) -> int:
        return self.table.rowCount()

    def apply_filters(
        self,
        *,
        search_term: str = "",
        character: object | None = None,
        mod_type: object | None = None,
        status: object | None = None,
    ) -> int:
        """
        Wendet die aktuellen Filter auf die Tabelle an.

        Rückgabewert:
            Anzahl der sichtbaren Mods.
        """
        normalized_search = (
            search_term
            .strip()
            .casefold()
        )

        visible_mods = 0

        for row in range(
            self.table.rowCount()
        ):
            name_item = self.table.item(
                row,
                0,
            )

            character_item = self.table.item(
                row,
                1,
            )

            mod_type_item = self.table.item(
                row,
                2,
            )

            state_item = self.table.item(
                row,
                3,
            )

            if (
                name_item is None
                or character_item is None
                or mod_type_item is None
                or state_item is None
            ):
                self.table.setRowHidden(
                    row,
                    True,
                )
                continue

            mod = name_item.data(
                MOD_OBJECT_ROLE
            )

            if not isinstance(
                mod,
                ModInfo,
            ):
                self.table.setRowHidden(
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

            row_status = state_item.data(
                Qt.ItemDataRole.UserRole
            )

            # Charakter
            if character is None:
                matches_character = True

            elif character == "__unknown__":
                matches_character = (
                    not characters
                )

            else:
                matches_character = any(
                    current_character.casefold()
                    == str(character).casefold()
                    for current_character
                    in characters
                )

            # Mod-Typ
            matches_mod_type = (
                mod_type is None
                or str(row_mod_type).casefold()
                == str(mod_type).casefold()
            )

            # Status
            matches_status = (
                status is None
                or row_status == status
            )

            # Suche
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
                not normalized_search
                or normalized_search
                in searchable_text
            )

            row_visible = (
                matches_character
                and matches_mod_type
                and matches_status
                and matches_search
            )

            self.table.setRowHidden(
                row,
                not row_visible,
            )

            if row_visible:
                visible_mods += 1

        return visible_mods

    def _emit_enable_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.enable_requested.emit()

    def _emit_disable_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.disable_requested.emit()

    def _emit_adopt_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.adopt_requested.emit()

    def _emit_cancel_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.cancel_requested.emit()