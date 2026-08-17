from __future__ import annotations

from PySide6.QtCore import (
    QSignalBlocker,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.mod_manager import (
    ModState,
    mod_state_label,
)
from app.i18n import (
    tr,
    translation_manager,
)
from app.models.mod import ModInfo

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

class LibraryFilterBar(QFrame):
    """
    Filterleiste der Mod-Bibliothek.

    Dieses Widget enthält ausschließlich die sichtbaren
    Filterelemente und meldet Änderungen über ein Signal.
    Die eigentliche Tabellenfilterung bleibt in LibraryPage.
    """

    filters_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("filterCard")

        self._responsive_mode = ""
        self._full_path_text = ""

        self.path_label = QLabel()
        self.location_label = QLabel()

        self.search_input = QLineEdit()
        self.character_filter = QComboBox()
        self.mod_type_filter = QComboBox()
        self.status_filter = QComboBox()

        self.reset_button = QPushButton()

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        
    def _configure_widgets(self) -> None:
        self.path_label.setObjectName(
            "libraryPath"
        )
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.path_label.setMinimumWidth(
            0
        )

        self.location_label.setObjectName(
            "locationBadge"
        )

        self.search_input.setObjectName(
            "searchInput"
        )

        self.search_input.setClearButtonEnabled(
            True
        )
        self.search_input.setMinimumWidth(
            280
        )

        self.character_filter.setObjectName(
            "filterCombo"
        )
        self.character_filter.setMinimumWidth(
            135
        )
        self.character_filter.addItem(
            tr("library.filter.all_characters"),
            userData=None,
        )

        self.character_filter.addItem(
            tr("common.unknown"),
            userData="__unknown__",
        )
        self.mod_type_filter.setObjectName(
            "filterCombo"
        )
        self.mod_type_filter.setMinimumWidth(
            135
        )
        self.mod_type_filter.addItem(
            tr("library.filter.all_mod_types"),
            userData=None,
        )

        self.status_filter.setObjectName(
            "filterCombo"
        )

        self.status_filter.setMinimumWidth(
            125
        )

        self.status_filter.addItem(
            tr("library.filter.all_statuses"),
            userData=None,
        )

        for state in (
            ModState.ENABLED,
            ModState.DISABLED,
            ModState.CONFLICT,
            ModState.BROKEN,
            ModState.NOT_CONFIGURED,
        ):
            translation_key = (
                MOD_STATE_TRANSLATION_KEYS[
                    state.value
                ]
            )

            self.status_filter.addItem(
                tr(translation_key),
                userData=state.value,
            )

        self.reset_button.setObjectName(
            "secondaryButton"
        )
    
    def set_mods(
        self,
        mods: list[ModInfo],
    ) -> None:
        """
        Aktualisiert die dynamischen Filtereinträge
        anhand der gefundenen Mods.
        """
        self._update_character_options(
            mods
        )

        self._update_mod_type_options(
            mods
        )
    
    def _update_character_options(
        self,
        mods: list[ModInfo],
    ) -> None:
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

        blocker = QSignalBlocker(
            self.character_filter
        )

        self.character_filter.clear()
        
        self.character_filter.addItem(
            tr("library.filter.all_characters"),
            userData=None,
        )

        if has_unknown_mods:
            self.character_filter.addItem(
                tr("common.unknown"),
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

        del blocker
        
    def _update_mod_type_options(
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

        blocker = QSignalBlocker(
            self.mod_type_filter
        )

        self.mod_type_filter.clear()

        self.mod_type_filter.addItem(
            tr("library.filter.all_mod_types"),
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

        del blocker

    def _build_ui(
        self,
    ) -> None:
        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        root_layout.setSpacing(
            8
        )

        # ========================================================
        # LIBRARY LOCATION
        # ========================================================

        location_layout = QHBoxLayout()

        location_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        location_layout.setSpacing(
            8
        )

        self.folder_caption = QLabel()

        self.folder_caption.setObjectName(
            "fieldCaption"
        )

        self.folder_caption.setMinimumWidth(
            52
        )

        location_layout.addWidget(
            self.folder_caption
        )

        location_layout.addWidget(
            self.path_label,
            stretch=1,
        )

        location_layout.addWidget(
            self.location_label
        )

        # ========================================================
        # FILTER TOOLBAR
        # ========================================================

        self.filter_layout = QGridLayout()

        self.filter_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.filter_layout.setHorizontalSpacing(
            8
        )

        self.filter_layout.setVerticalSpacing(
            8
        )

        root_layout.addLayout(
            location_layout
        )

        root_layout.addLayout(
            self.filter_layout
        )

        self._update_responsive_layout(
            force=True
        )

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(
            self._emit_filters_changed
        )

        self.character_filter.currentIndexChanged.connect(
            self._emit_filters_changed
        )

        self.mod_type_filter.currentIndexChanged.connect(
            self._emit_filters_changed
        )

        self.status_filter.currentIndexChanged.connect(
            self._emit_filters_changed
        )

        self.reset_button.clicked.connect(
            self.reset_filters
        )

    def _emit_filters_changed(
        self,
        _value: object | None = None,
    ) -> None:
        self.filters_changed.emit()

    def reset_filters(
        self,
        _checked: bool = False,
    ) -> None:
        """
        Setzt alle Filter zurück und löst nur eine Aktualisierung aus.
        """
        widgets = (
            self.search_input,
            self.character_filter,
            self.mod_type_filter,
            self.status_filter,
        )

        blockers = [
            QSignalBlocker(widget)
            for widget in widgets
        ]

        self.search_input.clear()
        self.character_filter.setCurrentIndex(
            0
        )
        self.mod_type_filter.setCurrentIndex(
            0
        )
        self.status_filter.setCurrentIndex(
            0
        )

        # Die Blocker müssen bis nach allen Änderungen existieren.
        del blockers

        self.filters_changed.emit()

    def search_term(
        self,
    ) -> str:
        return (
            self.search_input.text().strip()
        )

    def selected_character(
        self,
    ) -> str | None:
        value = (
            self.character_filter.currentData()
        )

        if value is None:
            return None

        return str(value)

    def selected_mod_type(
        self,
    ) -> str | None:
        value = (
            self.mod_type_filter.currentData()
        )

        if value is None:
            return None

        return str(value)

    def selected_status(
        self,
    ) -> str | None:
        value = (
            self.status_filter.currentData()
        )

        if value is None:
            return None

        return str(value)

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._update_responsive_layout()
        self._refresh_path_display()

    def _update_responsive_layout(
        self,
        *,
        force: bool = False,
    ) -> None:
        width = self.width()

        if width < 620:
            mode = "tight"
        elif width < 920:
            mode = "compact"
        else:
            mode = "wide"

        if (
            not force
            and mode == self._responsive_mode
        ):
            return

        self._responsive_mode = mode
        self.setProperty(
            "responsiveMode",
            mode,
        )

        widgets = (
            self.search_input,
            self.character_filter,
            self.mod_type_filter,
            self.status_filter,
            self.reset_button,
        )

        for widget in widgets:
            self.filter_layout.removeWidget(
                widget
            )

        for column in range(5):
            self.filter_layout.setColumnStretch(
                column,
                0,
            )

        if mode == "wide":
            self.search_input.setMinimumWidth(280)
            self.character_filter.setMinimumWidth(135)
            self.mod_type_filter.setMinimumWidth(135)
            self.status_filter.setMinimumWidth(125)

            self.filter_layout.addWidget(
                self.search_input, 0, 0
            )
            self.filter_layout.addWidget(
                self.character_filter, 0, 1
            )
            self.filter_layout.addWidget(
                self.mod_type_filter, 0, 2
            )
            self.filter_layout.addWidget(
                self.status_filter, 0, 3
            )
            self.filter_layout.addWidget(
                self.reset_button, 0, 4
            )
            self.filter_layout.setColumnStretch(
                0, 1
            )

        elif mode == "compact":
            self.search_input.setMinimumWidth(0)
            self.character_filter.setMinimumWidth(120)
            self.mod_type_filter.setMinimumWidth(120)
            self.status_filter.setMinimumWidth(110)

            self.filter_layout.addWidget(
                self.search_input,
                0, 0, 1, 4,
            )
            self.filter_layout.addWidget(
                self.character_filter, 1, 0
            )
            self.filter_layout.addWidget(
                self.mod_type_filter, 1, 1
            )
            self.filter_layout.addWidget(
                self.status_filter, 1, 2
            )
            self.filter_layout.addWidget(
                self.reset_button, 1, 3
            )

            for column in range(4):
                self.filter_layout.setColumnStretch(
                    column, 1
                )

        else:
            self.search_input.setMinimumWidth(0)
            self.character_filter.setMinimumWidth(0)
            self.mod_type_filter.setMinimumWidth(0)
            self.status_filter.setMinimumWidth(0)

            self.filter_layout.addWidget(
                self.search_input,
                0, 0, 1, 2,
            )
            self.filter_layout.addWidget(
                self.character_filter, 1, 0
            )
            self.filter_layout.addWidget(
                self.mod_type_filter, 1, 1
            )
            self.filter_layout.addWidget(
                self.status_filter, 2, 0
            )
            self.filter_layout.addWidget(
                self.reset_button, 2, 1
            )

            self.filter_layout.setColumnStretch(
                0, 1
            )
            self.filter_layout.setColumnStretch(
                1, 1
            )

        self.folder_caption.setVisible(
            mode != "tight"
        )

        style = self.style()
        style.unpolish(self)
        style.polish(self)

        self._refresh_path_display()

    def set_path_text(
        self,
        text: str,
    ) -> None:
        self._full_path_text = str(text)
        self.path_label.setToolTip(
            self._full_path_text
        )
        self._refresh_path_display()

    def _refresh_path_display(
        self,
    ) -> None:
        text = self._full_path_text

        if not text:
            self.path_label.setText("")
            return

        available = max(
            80,
            self.path_label.width() - 20,
        )

        self.path_label.setText(
            self.path_label.fontMetrics().elidedText(
                text,
                Qt.TextElideMode.ElideMiddle,
                available,
            )
        )

    def set_location_text(
        self,
        text: str,
    ) -> None:
        self.location_label.setText(
            text
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.folder_caption.setText(
            tr("library.filter.library")
        )

        self.search_input.setPlaceholderText(
            tr(
                "library.filter."
                "search_placeholder"
            )
        )

        self.reset_button.setText(
            tr("library.filter.reset")
        )

        character_blocker = QSignalBlocker(
            self.character_filter
        )

        for index in range(
            self.character_filter.count()
        ):
            value = (
                self.character_filter.itemData(
                    index
                )
            )

            if value is None:
                self.character_filter.setItemText(
                    index,
                    tr(
                        "library.filter."
                        "all_characters"
                    ),
                )

            elif value == "__unknown__":
                self.character_filter.setItemText(
                    index,
                    tr("common.unknown"),
                )

        del character_blocker

        mod_type_blocker = QSignalBlocker(
            self.mod_type_filter
        )

        for index in range(
            self.mod_type_filter.count()
        ):
            value = (
                self.mod_type_filter.itemData(
                    index
                )
            )

            if value is None:
                self.mod_type_filter.setItemText(
                    index,
                    tr(
                        "library.filter."
                        "all_mod_types"
                    ),
                )

        del mod_type_blocker

        status_blocker = QSignalBlocker(
            self.status_filter
        )

        for index in range(
            self.status_filter.count()
        ):
            value = (
                self.status_filter.itemData(
                    index
                )
            )

            if value is None:
                self.status_filter.setItemText(
                    index,
                    tr(
                        "library.filter."
                        "all_statuses"
                    ),
                )
                continue

            translation_key = (
                MOD_STATE_TRANSLATION_KEYS.get(
                    str(value)
                )
            )

            if translation_key is None:
                continue

            self.status_filter.setItemText(
                index,
                tr(translation_key),
            )

        del status_blocker
