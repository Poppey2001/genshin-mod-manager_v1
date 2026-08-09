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
from app.i18n import (
    tr,
    translation_manager,
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

        self._display_mode = "empty"

        self._current_mod: ModInfo | None = None
        self._current_state: ModState | None = None
        self._multiple_count = 0

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

        self.toggle_button = QPushButton()
        self.adopt_button = QPushButton()
        self.info_button = QPushButton()

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.show_empty()
        self.retranslate_ui()
        
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

        self.eyebrow_label = QLabel()

        self.eyebrow_label.setObjectName(
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
                "character",
                self.character_value,
            ),
            (
                "mod_type",
                self.type_value,
            ),
            (
                "location",
                self.location_value,
            ),
            (
                "files",
                self.files_value,
            ),
            (
                "ini_files",
                self.ini_value,
            ),
            (
                "size",
                self.size_value,
            ),
            (
                "modified",
                self.modified_value,
            ),
            (
                "path",
                self.path_value,
            ),
        )

        self.caption_labels: dict[
            str,
            QLabel,
        ] = {}

        for row, (
            caption_key,
            value_label,
        ) in enumerate(detail_rows):
            caption_label = QLabel()

            self.caption_labels[
                caption_key
            ] = caption_label
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

        self.action_title_label = QLabel()

        self.action_title_label.setObjectName(
            "detailSectionTitle"
        )
        self.eyebrow_label = QLabel()

        layout.addWidget(
            self.eyebrow_label
        )
        layout.addWidget(
            self.action_title_label
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
            self.action_title_label
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

    def show_empty(
        self,
    ) -> None:
        self._display_mode = "empty"
        self._current_mod = None
        self._current_state = None
        self._multiple_count = 0

        self.title_label.setText(
            tr("library.details.empty_title")
        )

        self.subtitle_label.setText(
            tr(
                "library.details."
                "empty_description"
            )
        )

        self.status_label.setText(
            tr("library.details.no_selection")
        )

        self.toggle_button.setText(
            tr("library.details.action.enable")
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
        self._display_mode = "multiple"
        self._current_mod = None
        self._current_state = None
        self._multiple_count = count

        self.title_label.setText(
            tr(
                "library.details.multiple_title",
                count=count,
            )
        )

        self.subtitle_label.setText(
            tr(
                "library.details."
                "multiple_description"
            )
        )

        self.status_label.setText(
            tr(
                "library.details."
                "multiple_status"
            )
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
        self._display_mode = "mod"
        self._current_mod = mod
        self._current_state = state
        self._multiple_count = 0

        character_text = (
            ", ".join(mod.characters)
            if mod.characters
            else tr("common.unknown")
        )

        location_text = (
            tr("common.network")
            if mod.is_network
            else tr("common.local")
        )

        if mod.is_symlink:
            location_text += (
                f" · {tr('common.symlink')}"
            )

        self.title_label.setText(
            mod.name
        )

        self.subtitle_label.setText(
            mod.relative_path
            or str(mod.path)
        )

        translation_key = (
            MOD_STATE_TRANSLATION_KEYS[
                state.value
            ]
        )

        self.status_label.setText(
            tr(translation_key)
        )

        self._set_status_style(
            state.value
        )

        self.character_value.setText(
            character_text
        )

        self.type_value.setText(
            mod.mod_type
            or tr("common.unknown")
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

        toggle_key = {
            ModState.DISABLED:
                "library.details.action.enable",

            ModState.ENABLED:
                "library.details.action.disable",

            ModState.BROKEN:
                "library.details.action.remove_broken",

            ModState.NOT_CONFIGURED:
                "library.details.action.not_configured",

            ModState.CONFLICT:
                "library.details.action.conflict",
        }.get(
            state,
            "library.details.action.enable",
        )

        self.toggle_button.setText(
            tr(toggle_key)
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

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.eyebrow_label.setText(
            tr("library.details.eyebrow")
        )

        caption_keys = {
            "character":
                "library.details.character",

            "mod_type":
                "library.details.mod_type",

            "location":
                "library.details.location",

            "files":
                "library.details.files",

            "ini_files":
                "library.details.ini_files",

            "size":
                "library.details.size",

            "modified":
                "library.details.modified",

            "path":
                "library.details.path",
        }

        for name, translation_key in (
            caption_keys.items()
        ):
            label = self.caption_labels.get(
                name
            )

            if label is not None:
                label.setText(
                    tr(translation_key)
                )

        self.action_title_label.setText(
            tr("library.details.actions")
        )

        self.adopt_button.setText(
            tr(
                "library.details."
                "action.adopt"
            )
        )

        self.adopt_button.setToolTip(
            tr(
                "library.details."
                "action.adopt_tooltip"
            )
        )

        self.info_button.setText(
            tr(
                "library.details."
                "action.info"
            )
        )

        if (
            self._display_mode == "mod"
            and self._current_mod is not None
            and self._current_state is not None
        ):
            self.show_mod(
                self._current_mod,
                self._current_state,
            )
            return

        if self._display_mode == "multiple":
            self.show_multiple(
                self._multiple_count
            )
            return

        self.show_empty()

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