from __future__ import annotations

from PySide6.QtCore import Qt, Signal

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
)

from app.services.mod_metadata import (
    load_mod_metadata,
)

from app.utils.formatters import (
    format_file_size,
    format_timestamp,
)

from app.widgets.library.mod_preview_gallery import (
    ModPreviewGallery,
)


class ModDetailsPanel(
    QScrollArea
):
    """
    Detailansicht für einen ausgewählten
    Library-Mod.

    Enthält:
    - lokale Previewbilder
    - GameBanana-Fallbackbilder
    - GameBanana-ID
    - Modinformationen
    - Einzelaktionen
    """

    toggle_requested = Signal()

    adopt_requested = Signal()

    info_requested = Signal()

    gamebanana_id_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self._current_mod: (
            ModInfo
            | None
        ) = None

        self._current_state: (
            ModState
            | None
        ) = None

        self._selection_mode = (
            "empty"
        )

        self._multiple_count = 0

        self._metadata_edit_enabled = (
            False
        )

        self.setObjectName(
            "detailsScroll"
        )

        self.setWidgetResizable(
            True
        )

        self.setFrameShape(
            QFrame.Shape.NoFrame
        )

        # Etwas breiter als bisher,
        # weil wir jetzt Bilder anzeigen.
        self.setMinimumWidth(
            350
        )

        self.setMaximumWidth(
            520
        )

        # ====================================================
        # Header
        # ====================================================

        self.eyebrow_label = QLabel()

        self.title_label = QLabel()

        self.subtitle_label = QLabel()

        self.status_label = QLabel()

        # ====================================================
        # Preview
        # ====================================================

        self.preview_title_label = (
            QLabel()
        )

        self.preview_gallery = (
            ModPreviewGallery(
                parent=self
            )
        )

        # ====================================================
        # Detailwerte
        # ====================================================

        self.character_value = (
            self._value()
        )

        self.type_value = (
            self._value()
        )

        self.gamebanana_id_value = (
            self._value(
                selectable=True
            )
        )

        self.location_value = (
            self._value()
        )

        self.files_value = (
            self._value()
        )

        self.ini_value = (
            self._value()
        )

        self.size_value = (
            self._value()
        )

        self.modified_value = (
            self._value()
        )

        self.path_value = (
            self._value(
                word_wrap=True,
                selectable=True,
            )
        )

        # ====================================================
        # Captions
        # ====================================================

        self.character_caption = (
            QLabel()
        )

        self.type_caption = (
            QLabel()
        )

        self.gamebanana_id_caption = (
            QLabel()
        )

        self.location_caption = (
            QLabel()
        )

        self.files_caption = (
            QLabel()
        )

        self.ini_caption = (
            QLabel()
        )

        self.size_caption = (
            QLabel()
        )

        self.modified_caption = (
            QLabel()
        )

        self.path_caption = (
            QLabel()
        )

        self.action_title_label = (
            QLabel()
        )

        # ====================================================
        # Aktionen
        # ====================================================

        self.toggle_button = (
            QPushButton()
        )

        self.adopt_button = (
            QPushButton()
        )

        self.info_button = (
            QPushButton()
        )

        self.gamebanana_id_button = (
            QPushButton()
        )

        self._configure_widgets()

        self._build_ui()

        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.show_empty()

    # ========================================================
    # UI-Konfiguration
    # ========================================================

    def _configure_widgets(
        self,
    ) -> None:
        self.eyebrow_label.setObjectName(
            "detailEyebrow"
        )

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

        self.preview_title_label.setObjectName(
            "detailSectionTitle"
        )

        self.action_title_label.setObjectName(
            "detailSectionTitle"
        )

        for caption in (
            self._caption_labels()
        ):
            caption.setObjectName(
                "detailCaption"
            )

            caption.setAlignment(
                Qt.AlignmentFlag.AlignTop
            )

        self.toggle_button.setObjectName(
            "primaryActionButton"
        )

        self.adopt_button.setObjectName(
            "warningActionButton"
        )

        self.info_button.setObjectName(
            "secondaryActionButton"
        )

        self.gamebanana_id_button.setObjectName(
            "secondaryActionButton"
        )

        for button in (
            self.toggle_button,
            self.adopt_button,
            self.info_button,
            self.gamebanana_id_button,
        ):
            button.setEnabled(
                False
            )

    # ========================================================
    # Aufbau
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        panel = QFrame()

        panel.setObjectName(
            "detailsPanel"
        )

        layout = QVBoxLayout(
            panel
        )

        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        layout.setSpacing(
            14
        )

        # ----------------------------------------------------
        # Details Grid
        # ----------------------------------------------------

        grid = QGridLayout()

        grid.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        grid.setHorizontalSpacing(
            12
        )

        grid.setVerticalSpacing(
            11
        )

        grid.setColumnStretch(
            1,
            1,
        )

        rows = (
            (
                self.character_caption,
                self.character_value,
            ),
            (
                self.type_caption,
                self.type_value,
            ),
            (
                self.gamebanana_id_caption,
                self.gamebanana_id_value,
            ),
            (
                self.location_caption,
                self.location_value,
            ),
            (
                self.files_caption,
                self.files_value,
            ),
            (
                self.ini_caption,
                self.ini_value,
            ),
            (
                self.size_caption,
                self.size_value,
            ),
            (
                self.modified_caption,
                self.modified_value,
            ),
            (
                self.path_caption,
                self.path_value,
            ),
        )

        for (
            row,
            (
                caption,
                value,
            ),
        ) in enumerate(
            rows
        ):
            grid.addWidget(
                caption,
                row,
                0,
            )

            grid.addWidget(
                value,
                row,
                1,
            )

        # ----------------------------------------------------
        # Gesamtlayout
        # ----------------------------------------------------

        layout.addWidget(
            self.eyebrow_label
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.subtitle_label
        )

        layout.addWidget(
            self.status_label,
            alignment=(
                Qt.AlignmentFlag.AlignLeft
            ),
        )

        layout.addWidget(
            self._divider()
        )

        layout.addWidget(
            self.preview_title_label
        )

        layout.addWidget(
            self.preview_gallery
        )

        layout.addWidget(
            self._divider()
        )

        layout.addLayout(
            grid
        )

        layout.addWidget(
            self.gamebanana_id_button
        )

        layout.addStretch(
            1
        )

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

    # ========================================================
    # Signale
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        self.toggle_button.clicked.connect(
            lambda _checked=False:
            self.toggle_requested.emit()
        )

        self.adopt_button.clicked.connect(
            lambda _checked=False:
            self.adopt_requested.emit()
        )

        self.info_button.clicked.connect(
            lambda _checked=False:
            self.info_requested.emit()
        )

        self.gamebanana_id_button.clicked.connect(
            lambda _checked=False:
            self.gamebanana_id_requested.emit()
        )

    # ========================================================
    # Helpers
    # ========================================================

    def _value(
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
                (
                    Qt.TextInteractionFlag
                    .TextSelectableByMouse
                )
            )

        return label

    @staticmethod
    def _divider(
    ) -> QFrame:
        divider = QFrame()

        divider.setObjectName(
            "detailDivider"
        )

        divider.setFrameShape(
            QFrame.Shape.HLine
        )

        return divider

    def _caption_labels(
        self,
    ) -> tuple[
        QLabel,
        ...,
    ]:
        return (
            self.character_caption,
            self.type_caption,
            self.gamebanana_id_caption,
            self.location_caption,
            self.files_caption,
            self.ini_caption,
            self.size_caption,
            self.modified_caption,
            self.path_caption,
        )

    # ========================================================
    # Keine Auswahl
    # ========================================================

    def show_empty(
        self,
    ) -> None:
        self._current_mod = None

        self._current_state = None

        self._selection_mode = (
            "empty"
        )

        self._multiple_count = 0

        self.preview_gallery.clear_preview()

        self._clear_values()

        self._set_all_actions_enabled(
            False
        )

        self._set_status_style(
            "none"
        )

        self.retranslate_ui()

    # ========================================================
    # Mehrfachauswahl
    # ========================================================

    def show_multiple(
        self,
        count: int,
    ) -> None:
        self._current_mod = None

        self._current_state = None

        self._selection_mode = (
            "multiple"
        )

        self._multiple_count = max(
            0,
            int(
                count
            ),
        )

        self.preview_gallery.clear_preview()

        self._clear_values()

        self._set_all_actions_enabled(
            False
        )

        self._set_status_style(
            "multiple"
        )

        self.retranslate_ui()

    # ========================================================
    # Einzelner Mod
    # ========================================================

    def show_mod(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        self._current_mod = mod

        self._current_state = state

        self._selection_mode = (
            "mod"
        )

        self._multiple_count = 0

        metadata = (
            load_mod_metadata(
                mod.path
            )
        )

        self.title_label.setText(
            mod.name
        )

        self.subtitle_label.setText(
            mod.relative_path
            or str(
                mod.path
            )
        )

        self.character_value.setText(
            self._character_text(
                mod
            )
        )

        self.type_value.setText(
            mod.mod_type
            or tr(
                "common.unknown"
            )
        )

        if (
            metadata.gamebanana_mod_id
            is not None
        ):
            self.gamebanana_id_value.setText(
                str(
                    metadata.gamebanana_mod_id
                )
            )

        else:
            self.gamebanana_id_value.setText(
                "—"
            )

        self.location_value.setText(
            self._location_text(
                mod
            )
        )

        self.files_value.setText(
            str(
                mod.file_count
            )
        )

        self.ini_value.setText(
            str(
                mod.ini_file_count
            )
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
            str(
                mod.path
            )
        )

        # ----------------------------------------------------
        # Preview:
        #
        # lokal -> benutzen
        # sonst GameBanana-ID -> API/Cache
        # ----------------------------------------------------

        self.preview_gallery.load_mod(
            mod.path
        )

        self.info_button.setEnabled(
            True
        )

        self.gamebanana_id_button.setEnabled(
            self._metadata_edit_enabled
        )

        self._set_status_style(
            state.value
        )

        self.retranslate_ui()

    # ========================================================
    # Metadata Edit
    # ========================================================

    def set_metadata_edit_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._metadata_edit_enabled = (
            bool(
                enabled
            )
        )

        self.gamebanana_id_button.setEnabled(
            self._metadata_edit_enabled
            and self._selection_mode
            == "mod"
            and self._current_mod
            is not None
        )

    # ========================================================
    # Übersetzung
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.eyebrow_label.setText(
            tr(
                "library.details.eyebrow"
            )
        )

        self.preview_title_label.setText(
            tr(
                "library.details.preview"
            )
        )

        self.character_caption.setText(
            tr(
                "library.details.character"
            )
        )

        self.type_caption.setText(
            tr(
                "library.details.mod_type"
            )
        )

        self.gamebanana_id_caption.setText(
            tr(
                "library.details.gamebanana_id"
            )
        )

        self.location_caption.setText(
            tr(
                "library.details.location"
            )
        )

        self.files_caption.setText(
            tr(
                "library.details.files"
            )
        )

        self.ini_caption.setText(
            tr(
                "library.details.ini_files"
            )
        )

        self.size_caption.setText(
            tr(
                "library.details.size"
            )
        )

        self.modified_caption.setText(
            tr(
                "library.details.modified"
            )
        )

        self.path_caption.setText(
            tr(
                "library.details.path"
            )
        )

        self.action_title_label.setText(
            tr(
                "library.details.actions"
            )
        )

        self.adopt_button.setText(
            tr(
                "library.details.action.adopt"
            )
        )

        self.adopt_button.setToolTip(
            tr(
                (
                    "library.details.action."
                    "adopt_tooltip"
                )
            )
        )

        self.info_button.setText(
            tr(
                "library.details.action.info"
            )
        )

        self.gamebanana_id_button.setText(
            tr(
                (
                    "library.details.action."
                    "set_gamebanana_id"
                )
            )
        )

        self.gamebanana_id_button.setToolTip(
            tr(
                (
                    "library.details.action."
                    "set_gamebanana_id_tooltip"
                )
            )
        )

        # ----------------------------------------------------
        # Keine Auswahl
        # ----------------------------------------------------

        if (
            self._selection_mode
            == "empty"
        ):
            self.title_label.setText(
                tr(
                    "library.details.empty_title"
                )
            )

            self.subtitle_label.setText(
                tr(
                    (
                        "library.details."
                        "empty_description"
                    )
                )
            )

            self.status_label.setText(
                tr(
                    "library.details.no_selection"
                )
            )

            self.toggle_button.setText(
                tr(
                    (
                        "library.details.action."
                        "enable"
                    )
                )
            )

            return

        # ----------------------------------------------------
        # Mehrfachauswahl
        # ----------------------------------------------------

        if (
            self._selection_mode
            == "multiple"
        ):
            self.title_label.setText(
                tr(
                    (
                        "library.details."
                        "multiple_title"
                    ),
                    count=(
                        self._multiple_count
                    ),
                )
            )

            self.subtitle_label.setText(
                tr(
                    (
                        "library.details."
                        "multiple_description"
                    )
                )
            )

            self.status_label.setText(
                tr(
                    (
                        "library.details."
                        "multiple_status"
                    )
                )
            )

            self.toggle_button.setText(
                tr(
                    (
                        "library.details."
                        "multiple_title"
                    ),
                    count=(
                        self._multiple_count
                    ),
                )
            )

            return

        # ----------------------------------------------------
        # Einzelner Mod
        # ----------------------------------------------------

        if (
            self._current_state
            is None
        ):
            return

        self.status_label.setText(
            self._translated_state(
                self._current_state
            )
        )

        self.toggle_button.setText(
            tr(
                self._action_key(
                    self._current_state
                )
            )
        )

        if (
            self._current_mod
            is not None
        ):
            self.character_value.setText(
                self._character_text(
                    self._current_mod
                )
            )

            self.type_value.setText(
                self._current_mod.mod_type
                or tr(
                    "common.unknown"
                )
            )

            self.location_value.setText(
                self._location_text(
                    self._current_mod
                )
            )

    # ========================================================
    # State Translation
    # ========================================================

    @staticmethod
    def _action_key(
        state: ModState,
    ) -> str:
        return {
            ModState.DISABLED: (
                "library.details.action.enable"
            ),
            ModState.ENABLED: (
                "library.details.action.disable"
            ),
            ModState.BROKEN: (
                (
                    "library.details.action."
                    "remove_broken"
                )
            ),
            ModState.NOT_CONFIGURED: (
                (
                    "library.details.action."
                    "not_configured"
                )
            ),
            ModState.CONFLICT: (
                "library.details.action.conflict"
            ),
        }.get(
            state,
            (
                "library.details.action."
                "unavailable"
            ),
        )

    @staticmethod
    def _translated_state(
        state: ModState,
    ) -> str:
        key = {
            ModState.ENABLED: (
                "mod.state.enabled"
            ),
            ModState.DISABLED: (
                "mod.state.disabled"
            ),
            ModState.CONFLICT: (
                "mod.state.conflict"
            ),
            ModState.BROKEN: (
                "mod.state.broken"
            ),
            ModState.NOT_CONFIGURED: (
                "mod.state.not_configured"
            ),
        }.get(
            state
        )

        if key is None:
            return state.value

        return tr(
            key
        )

    # ========================================================
    # Dynamische Werte
    # ========================================================

    @staticmethod
    def _character_text(
        mod: ModInfo,
    ) -> str:
        if mod.characters:
            return ", ".join(
                mod.characters
            )

        return tr(
            "common.unknown"
        )

    @staticmethod
    def _location_text(
        mod: ModInfo,
    ) -> str:
        text = (
            tr(
                "common.network"
            )
            if mod.is_network
            else tr(
                "common.local"
            )
        )

        if mod.is_symlink:
            text += (
                " · "
                + tr(
                    "common.symlink"
                )
            )

        return text

    # ========================================================
    # Reset
    # ========================================================

    def _set_all_actions_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.toggle_button.setEnabled(
            enabled
        )

        self.adopt_button.setEnabled(
            enabled
        )

        self.info_button.setEnabled(
            enabled
        )

        self.gamebanana_id_button.setEnabled(
            enabled
        )

    def _clear_values(
        self,
    ) -> None:
        for label in (
            self.character_value,
            self.type_value,
            self.gamebanana_id_value,
            self.location_value,
            self.files_value,
            self.ini_value,
            self.size_value,
            self.modified_value,
            self.path_value,
        ):
            label.setText(
                "—"
            )

    # ========================================================
    # Status Style
    # ========================================================

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

        (
            background,
            foreground,
        ) = colors.get(
            state,
            colors[
                "none"
            ],
        )

        self.status_label.setStyleSheet(
            (
                "background-color: "
                f"{background}; "
                f"color: {foreground}; "
                "border: 1px solid "
                "rgba(255, 255, 255, 0.08); "
                "border-radius: 10px; "
                "padding: 5px 10px; "
                "font-weight: 700;"
            )
        )


__all__ = [
    "ModDetailsPanel",
]