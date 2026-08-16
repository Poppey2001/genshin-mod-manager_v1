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

from app.i18n import (
    tr,
    translation_manager,
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
MOD_STATE_TRANSLATION_KEYS = {
    ModState.ENABLED.value:
        "mod.state.enabled",

    ModState.DISABLED.value:
        "mod.state.disabled",

    ModState.CONFLICT.value:
        "mod.state.conflict",

    ModState.BROKEN.value:
        "mod.state.broken",

    ModState.NOT_CONFIGURED.value:
        "mod.state.not_configured",
}
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

        self.bulk_enable_button = QPushButton()
        self.bulk_disable_button = QPushButton()
        self.bulk_adopt_button = QPushButton()
        self.cancel_bulk_button = QPushButton()
                
        self.table = QTableWidget()

        self._configure_buttons()
        self._configure_table()
        self._build_ui()
        self._connect_signals()
        
        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

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

    def _configure_table(
        self,
    ) -> None:
        self.table.setObjectName(
            "modTable"
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.setShowGrid(
            False
        )

        self.table.setWordWrap(
            False
        )

        self.table.setTextElideMode(
            Qt.TextElideMode.ElideRight
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

        # Kompaktere Zeilen
        self.table.verticalHeader().setDefaultSectionSize(
            42
        )

        self.table.setColumnCount(
            10
        )

        headers = [
            tr("library.column.mod"),
            tr("library.column.character"),
            tr("library.column.mod_type"),
            tr("library.column.status"),
            tr("library.column.location"),
            tr("library.column.files"),
            tr("library.column.ini_files"),
            tr("library.column.size"),
            tr("library.column.modified"),
            tr("library.column.path"),
        ]

        self.table.setHorizontalHeaderLabels(
            headers
        )

        header = (
            self.table.horizontalHeader()
        )

        header.setHighlightSections(
            False
        )

        header.setStretchLastSection(
            False
        )

        # --------------------------------------------------------
        # Hauptspalten
        # --------------------------------------------------------

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        # Status bekommt eine stabile Breite
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Fixed,
        )

        self.table.setColumnWidth(
            3,
            118,
        )

        header.setSectionResizeMode(
            7,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        # --------------------------------------------------------
        # Technische Informationen liegen im Detailpanel.
        #
        # Sichtbar bleiben:
        # Mod | Character | Type | Status | Size
        # --------------------------------------------------------

        for column in (
            4,  # Location
            5,  # Files
            6,  # INI files
            8,  # Modified
            9,  # Path
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

        self.selection_label = QLabel()
        self.selection_label.setObjectName(
            "sectionLabel"
        )

        actions_layout.addWidget(
            self.selection_label
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
            else tr("common.unknown")
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
            or tr("common.unknown")
        )

        mod_type_item.setData(
            Qt.ItemDataRole.UserRole,
            mod.mod_type,
        )

        state_item = QTableWidgetItem(
            ""
        )

        # Der eigentliche Status bleibt unsichtbar im Item gespeichert.
        # Filter und interne Logik können ihn weiterhin benutzen.
        state_item.setData(
            Qt.ItemDataRole.UserRole,
            state.value,
        )

        state_item.setToolTip(
            tr(
                MOD_STATE_TRANSLATION_KEYS[
                    state.value
                ]
            )
        )

        location_parts = [
            tr("common.network")
            if mod.is_network
            else tr("common.local")
        ]

        if mod.is_symlink:
            location_parts.append(
                tr("common.symlink")
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

        self._set_mod_state_widget(
            row=row,
            state=state,
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

        # ----------------------------------------------------
        # Mod Name
        # ----------------------------------------------------

        name_label = QLabel(
            mod.name
        )

        name_label.setObjectName(
            "modNameLabel"
        )

        name_label.setToolTip(
            str(
                mod.path
            )
        )

        name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        name_label.setMinimumWidth(
            0
        )

        # Klicks sollen weiterhin bei der Tabellenzeile landen.
        name_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        # ----------------------------------------------------
        # Info Button
        # ----------------------------------------------------

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
            tr(
                "library.list.info_tooltip"
            )
        )

        info_button.clicked.connect(
            lambda _checked=False, current_mod=mod: (
                self.info_requested.emit(
                    current_mod
                )
            )
        )

        # ----------------------------------------------------
        # Layout
        # ----------------------------------------------------

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

    def _set_mod_state_widget(
        self,
        *,
        row: int,
        state: ModState,
    ) -> None:
        """
        Erstellt die sichtbare Status-Badge.
        """

        container = QWidget()

        container.setObjectName(
            "modStateContainer"
        )

        container.setAutoFillBackground(
            False
        )

        layout = QHBoxLayout(
            container
        )

        layout.setContentsMargins(
            8,
            0,
            8,
            0,
        )

        layout.setSpacing(
            0
        )

        # ----------------------------------------------------
        # Status Text
        # ----------------------------------------------------

        translation_key = (
            MOD_STATE_TRANSLATION_KEYS.get(
                state.value
            )
        )

        if translation_key:
            state_text = tr(
                translation_key
            )
        else:
            state_text = (
                state.value
            )

        # ----------------------------------------------------
        # Badge
        # ----------------------------------------------------

        badge = QLabel(
            state_text
        )

        badge.setObjectName(
            "modStateBadge"
        )

        badge.setProperty(
            "modState",
            state.value,
        )

        badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        badge.setMinimumWidth(
            82
        )

        badge.setMinimumHeight(
            23
        )

        badge.setToolTip(
            state_text
        )

        layout.addWidget(
            badge,
            alignment=(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        layout.addStretch(
            1
        )

        self.table.setCellWidget(
            row,
            3,
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
        Aktualisiert Statusdaten und sichtbare Status-Badge.
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
                    state_item = (
                        QTableWidgetItem()
                    )

                    self.table.setItem(
                        row,
                        3,
                        state_item,
                    )
                # Kein sichtbarer Text mehr im normalen Item.
                state_item.setText(
                    ""
                )

                # Interner Status bleibt erhalten.
                state_item.setData(
                    Qt.ItemDataRole.UserRole,
                    state.value,
                )

                state_item.setToolTip(
                    tr(
                        MOD_STATE_TRANSLATION_KEYS[
                            state.value
                        ]
                    )
                )

                state_item.setData(
                    Qt.ItemDataRole.UserRole,
                    state.value,
                )

                self._set_mod_state_widget(
                    row=row,
                    state=state,
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


    def set_bulk_operation_running(
        self,
        running: bool,
    ) -> None:
        self.table.setEnabled(
            not running
        )

        self.cancel_bulk_button.setVisible(
            running
        )

        self.cancel_bulk_button.setEnabled(
            running
        )

    def mark_bulk_cancel_requested(
        self,
    ) -> None:
        self.cancel_bulk_button.setEnabled(
            False
        )

    def drop_target(
        self,
    ):
        return self.table.viewport()
    
    def retranslate_ui(
    self,
    _language: str | None = None,
    ) -> None:
        self.selection_label.setText(
            tr("library.list.selection_actions")
        )

        self.bulk_enable_button.setText(
            tr("library.list.enable_selected")
        )

        self.bulk_disable_button.setText(
            tr("library.list.disable_selected")
        )

        self.bulk_adopt_button.setText(
            tr("library.list.adopt_selected")
        )

        self.cancel_bulk_button.setText(
            tr("library.list.cancel_bulk")
        )

        headers = [
            tr("library.column.mod"),
            tr("library.column.character"),
            tr("library.column.mod_type"),
            tr("library.column.status"),
            tr("library.column.location"),
            tr("library.column.files"),
            tr("library.column.ini_files"),
            tr("library.column.size"),
            tr("library.column.modified"),
            tr("library.column.path"),
        ]

        for column, text in enumerate(
            headers
        ):
            header_item = (
                self.table.horizontalHeaderItem(
                    column
                )
            )

            if header_item is not None:
                header_item.setText(
                    text
                )

        sorting_enabled = (
            self.table.isSortingEnabled()
        )

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

                mod = name_item.data(
                    MOD_OBJECT_ROLE
                )

                if not isinstance(
                    mod,
                    ModInfo,
                ):
                    continue

                character_item = (
                    self.table.item(
                        row,
                        1,
                    )
                )

                if character_item is not None:
                    character_item.setText(
                        (
                            ", ".join(
                                mod.characters
                            )
                            if mod.characters
                            else tr(
                                "common.unknown"
                            )
                        )
                    )

                mod_type_item = (
                    self.table.item(
                        row,
                        2,
                    )
                )

                if mod_type_item is not None:
                    mod_type_item.setText(
                        mod.mod_type
                        or tr("common.unknown")
                    )

                state_item = (
                    self.table.item(
                        row,
                        3,
                    )
                )

                if state_item is not None:
                    state_value = (
                        state_item.data(
                            Qt.ItemDataRole.UserRole
                        )
                    )

                    translation_key = (
                        MOD_STATE_TRANSLATION_KEYS.get(
                            str(state_value)
                        )
                    )

                    if translation_key is not None:
                        state_item.setText(
                            tr(translation_key)
                        )

                location_item = (
                    self.table.item(
                        row,
                        4,
                    )
                )

                if location_item is not None:
                    location_parts = [
                        (
                            tr("common.network")
                            if mod.is_network
                            else tr("common.local")
                        )
                    ]

                    if mod.is_symlink:
                        location_parts.append(
                            tr("common.symlink")
                        )

                    location_item.setText(
                        " · ".join(
                            location_parts
                        )
                    )

                name_widget = (
                    self.table.cellWidget(
                        row,
                        0,
                    )
                )

                if name_widget is not None:
                    info_button = (
                        name_widget.findChild(
                            QToolButton,
                            "modInfoButton",
                        )
                    )

                    if info_button is not None:
                        info_button.setToolTip(
                            tr(
                                "library.list."
                                "info_tooltip"
                            )
                        )

        finally:
            self.table.setSortingEnabled(
                sorting_enabled
            )

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
        