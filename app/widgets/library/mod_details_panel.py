from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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


class ModDetailsPanel(QScrollArea):
    """
    Rechter Detailbereich der Mod-Bibliothek.

    Das Widget zeigt Modinformationen an und sendet
    Signale für Benutzeraktionen. Die eigentliche
    Mod-Verwaltung bleibt in LibraryPage.
    """

    toggle_requested = Signal()
    adopt_requested = Signal()
    info_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName(
            "detailsScroll"
        )
        self.setWidgetResizable(
            True
        )
        self.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.setMinimumWidth(
            300
        )
        self.setMaximumWidth(
            430
        )

        self.title_label = QLabel()
        self.subtitle_label = QLabel()
        self.status_label = QLabel()

        self.character_value = self._create_detail_value()
        self.type_value = self._create_detail_value()
        self.location_value = self._create_detail_value()
        self.files_value = self._create_detail_value()
        self.ini_value = self._create_detail_value()
        self.size_value = self._create_detail_value()
        self.modified_value = self._create_detail_value()

        self.path_value = self._create_detail_value(
            word_wrap=True,
            selectable=True,
        )

        self.toggle_button = QPushButton(
            "Aktivieren"
        )

        self.adopt_button = QPushButton(
            "Konflikt übernehmen"
        )

        self.info_button = QPushButton(
            "INI-Steuerung analysieren"
        )

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()
        self.show_empty()

    def _configure_widgets(self) -> None:
        self.title_label.setObjectName(
            "detailTitle"
        )
        self.title_label.setWordWrap(
            True
        )

        self.subtitle_label.setObjectName(
            "detailSubtitle"
        )
        self.subtitle_label.setWordWrap(
            True
        )

        self.status_label.setObjectName(
            "detailStatusBadge"
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.toggle_button.setObjectName(
            "primaryActionButton"
        )
        self.toggle_button.setEnabled(
            False
        )

        self.adopt_button.setObjectName(
            "warningActionButton"
        )
        self.adopt_button.setEnabled(
            False
        )
        self.adopt_button.setToolTip(
            "Übernimmt einen vorhandenen Mod-Ordner, "
            "ohne seine Dateien zu überschreiben."
        )

        self.info_button.setObjectName(
            "secondaryActionButton"
        )
        self.info_button.setEnabled(
            False
        )

    def _build_ui(self) -> None:
        panel = QFrame()
        panel.setObjectName(
            "detailsPanel"
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )
        layout.setSpacing(
            14
        )

        eyebrow = QLabel(
            "MOD-DETAILS"
        )
        eyebrow.setObjectName(
            "detailEyebrow"
        )

        divider = QFrame()
        divider.setObjectName(
            "detailDivider"
        )
        divider.setFrameShape(
            QFrame.Shape.HLine
        )

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        detail_grid.setHorizontalSpacing(
            12
        )
        detail_grid.setVerticalSpacing(
            11
        )
        detail_grid.setColumnStretch(
            1,
            1,
        )

        detail_rows = (
            (
                "Charakter",
                self.character_value,
            ),
            (
                "Mod-Typ",
                self.type_value,
            ),
            (
                "Speicherort",
                self.location_value,
            ),
            (
                "Dateien",
                self.files_value,
            ),
            (
                "INI-Dateien",
                self.ini_value,
            ),
            (
                "Größe",
                self.size_value,
            ),
            (
                "Geändert",
                self.modified_value,
            ),
            (
                "Pfad",
                self.path_value,
            ),
        )

        for row, (
            caption,
            value_label,
        ) in enumerate(detail_rows):
            caption_label = QLabel(
                caption
            )
            caption_label.setObjectName(
                "detailCaption"
            )
            caption_label.setAlignment(
                Qt.AlignmentFlag.AlignTop
            )

            detail_grid.addWidget(
                caption_label,
                row,
                0,
            )
            detail_grid.addWidget(
                value_label,
                row,
                1,
            )

        action_title = QLabel(
            "Aktionen"
        )
        action_title.setObjectName(
            "detailSectionTitle"
        )

        layout.addWidget(
            eyebrow
        )
        layout.addWidget(
            self.title_label
        )
        layout.addWidget(
            self.subtitle_label
        )
        layout.addWidget(
            self.status_label,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(
            divider
        )
        layout.addLayout(
            detail_grid
        )
        layout.addStretch()
        layout.addWidget(
            action_title
        )
        layout.addWidget(
            self.toggle_button
        )
        layout.addWidget(
            self.adopt_button
        )
        layout.addWidget(
            self.info_button
        )

        self.setWidget(
            panel
        )

    def _connect_signals(self) -> None:
        self.toggle_button.clicked.connect(
            self._emit_toggle_requested
        )

        self.adopt_button.clicked.connect(
            self._emit_adopt_requested
        )

        self.info_button.clicked.connect(
            self._emit_info_requested
        )

    def _emit_toggle_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.toggle_requested.emit()

    def _emit_adopt_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.adopt_requested.emit()

    def _emit_info_requested(
        self,
        _checked: bool = False,
    ) -> None:
        self.info_requested.emit()

    def _create_detail_value(
        self,
        *,
        word_wrap: bool = False,
        selectable: bool = False,
    ) -> QLabel:
        label = QLabel(
            "—"
        )
        label.setObjectName(
            "detailValue"
        )
        label.setWordWrap(
            word_wrap
        )

        if selectable:
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

        return label

    def show_empty(self) -> None:
        """
        Zeigt den Zustand ohne ausgewählten Mod.
        """
        self.title_label.setText(
            "Kein Mod ausgewählt"
        )

        self.subtitle_label.setText(
            "Wähle links einen Mod aus, um "
            "Details und Aktionen zu sehen."
        )

        self.status_label.setText(
            "Keine Auswahl"
        )

        self._set_status_style(
            "none"
        )
        self._clear_values()

        self.info_button.setEnabled(
            False
        )

    def show_multiple(
        self,
        count: int,
    ) -> None:
        """
        Zeigt den Zustand für eine Mehrfachauswahl.
        """
        self.title_label.setText(
            f"{count} Mods ausgewählt"
        )

        self.subtitle_label.setText(
            "Nutze die Auswahlaktionen "
            "oberhalb der Liste."
        )

        self.status_label.setText(
            "Mehrfachauswahl"
        )

        self._set_status_style(
            "multiple"
        )
        self._clear_values()

        self.info_button.setEnabled(
            False
        )

    def show_mod(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        """
        Zeigt die Informationen eines einzelnen Mods.
        """
        character_text = (
            ", ".join(mod.characters)
            if mod.characters
            else "Unbekannt"
        )

        location_text = (
            "Netzwerk"
            if mod.is_network
            else "Lokal"
        )

        if mod.is_symlink:
            location_text += " · Symlink"

        self.title_label.setText(
            mod.name
        )

        self.subtitle_label.setText(
            mod.relative_path
            or str(mod.path)
        )

        self.status_label.setText(
            mod_state_label(state)
        )

        self._set_status_style(
            state.value
        )

        self.character_value.setText(
            character_text
        )

        self.type_value.setText(
            mod.mod_type
            or "Unbekannt"
        )

        self.location_value.setText(
            location_text
        )

        self.files_value.setText(
            str(mod.file_count)
        )

        self.ini_value.setText(
            str(mod.ini_file_count)
        )

        self.size_value.setText(
            format_file_size(
                mod.total_size
            )
        )

        self.modified_value.setText(
            format_timestamp(
                mod.modified_at
            )
        )

        self.path_value.setText(
            str(mod.path)
        )

        self.info_button.setEnabled(
            True
        )

    def _clear_values(self) -> None:
        value_labels = (
            self.character_value,
            self.type_value,
            self.location_value,
            self.files_value,
            self.ini_value,
            self.size_value,
            self.modified_value,
            self.path_value,
        )

        for label in value_labels:
            label.setText(
                "—"
            )

    def _set_status_style(
        self,
        state: str,
    ) -> None:
        colors = {
            ModState.ENABLED.value: (
                "#163d2a",
                "#67e8a5",
            ),
            ModState.DISABLED.value: (
                "#28303d",
                "#b7c0cf",
            ),
            ModState.CONFLICT.value: (
                "#4a2f12",
                "#ffc56d",
            ),
            ModState.BROKEN.value: (
                "#4a2027",
                "#ff8d9a",
            ),
            ModState.NOT_CONFIGURED.value: (
                "#3d314c",
                "#d8b4fe",
            ),
            "multiple": (
                "#30275b",
                "#c4b5fd",
            ),
            "none": (
                "#282c34",
                "#9299a6",
            ),
        }

        background, foreground = colors.get(
            state,
            colors["none"],
        )

        self.status_label.setStyleSheet(
            "background-color: "
            f"{background}; "
            f"color: {foreground}; "
            "border: 1px solid "
            "rgba(255, 255, 255, 0.08); "
            "border-radius: 10px; "
            "padding: 5px 10px; "
            "font-weight: 700;"
        )