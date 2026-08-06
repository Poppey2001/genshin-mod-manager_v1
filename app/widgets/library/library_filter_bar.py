from __future__ import annotations

from PySide6.QtCore import (
    QSignalBlocker,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
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

        self.path_label = QLabel()
        self.location_label = QLabel()

        self.search_input = QLineEdit()
        self.character_filter = QComboBox()
        self.mod_type_filter = QComboBox()
        self.status_filter = QComboBox()

        self.reset_button = QPushButton(
            "Zurücksetzen"
        )

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()

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

        self.location_label.setObjectName(
            "locationBadge"
        )

        self.search_input.setObjectName(
            "searchInput"
        )
        self.search_input.setPlaceholderText(
            "Mods, Charaktere oder Pfade durchsuchen …"
        )
        self.search_input.setClearButtonEnabled(
            True
        )
        self.search_input.setMinimumWidth(
            290
        )

        self.character_filter.setObjectName(
            "filterCombo"
        )
        self.character_filter.setMinimumWidth(
            170
        )
        self.character_filter.addItem(
            "Alle Charaktere",
            userData=None,
        )
        self.character_filter.addItem(
            "Unbekannt",
            userData="__unknown__",
        )

        self.mod_type_filter.setObjectName(
            "filterCombo"
        )
        self.mod_type_filter.setMinimumWidth(
            160
        )
        self.mod_type_filter.addItem(
            "Alle Mod-Typen",
            userData=None,
        )

        self.status_filter.setObjectName(
            "filterCombo"
        )
        self.status_filter.setMinimumWidth(
            150
        )
        self.status_filter.addItem(
            "Alle Status",
            userData=None,
        )

        for state in (
            ModState.ENABLED,
            ModState.DISABLED,
            ModState.CONFLICT,
            ModState.BROKEN,
            ModState.NOT_CONFIGURED,
        ):
            self.status_filter.addItem(
                mod_state_label(state),
                userData=state.value,
            )

        self.reset_button.setObjectName(
            "secondaryButton"
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        root_layout.setSpacing(
            12
        )

        location_layout = QHBoxLayout()
        location_layout.setSpacing(
            10
        )

        folder_caption = QLabel(
            "Bibliothek"
        )
        folder_caption.setObjectName(
            "fieldCaption"
        )

        location_layout.addWidget(
            folder_caption
        )
        location_layout.addWidget(
            self.path_label,
            stretch=1,
        )
        location_layout.addWidget(
            self.location_label
        )

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(
            10
        )

        filter_layout.addWidget(
            self.search_input,
            stretch=1,
        )
        filter_layout.addWidget(
            self.character_filter
        )
        filter_layout.addWidget(
            self.mod_type_filter
        )
        filter_layout.addWidget(
            self.status_filter
        )
        filter_layout.addWidget(
            self.reset_button
        )

        root_layout.addLayout(
            location_layout
        )
        root_layout.addLayout(
            filter_layout
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

    def search_text(self) -> str:
        return self.search_input.text().strip()

    def selected_character(
        self,
    ) -> str | None:
        value = self.character_filter.currentData()

        if value is None:
            return None

        return str(value)

    def selected_mod_type(
        self,
    ) -> str | None:
        value = self.mod_type_filter.currentData()

        if value is None:
            return None

        return str(value)

    def selected_status(
        self,
    ) -> str | None:
        value = self.status_filter.currentData()

        if value is None:
            return None

        return str(value)