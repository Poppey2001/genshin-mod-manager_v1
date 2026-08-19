from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig

from app.i18n import (
    set_language,
    tr,
    translation_manager,
)

from app.services.gamebanana_image_cache import (
    DEFAULT_CACHE_DIRECTORY,
    GameBananaImageCache,
    GameBananaImageCacheSettings,
    load_gamebanana_image_cache_settings,
    save_gamebanana_image_cache_settings,
)

from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)


class GlobalSettingsPage(QWidget):
    settings_saved = Signal(str)

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.config = config
        self._responsive_mode = None

        self.setObjectName(
            "globalSettingsPage"
        )

        self.cache_settings = (
            load_gamebanana_image_cache_settings()
        )

        # ----------------------------------------------------
        # Global widgets
        # ----------------------------------------------------

        self.title_label = QLabel(self)
        self.title_label.setObjectName(
            "pageTitle"
        )

        self.description_label = QLabel(self)
        self.description_label.setObjectName(
            "pageDescription"
        )
        self.description_label.setWordWrap(
            True
        )

        self.application_group = QGroupBox(self)

        self.language_label = QLabel(self)
        self.language_combo = QComboBox(self)

        self.theme_label = QLabel(self)
        self.theme_combo = QComboBox(self)

        self.update_group = QGroupBox(self)

        self.auto_updates_checkbox = QCheckBox(self)
        self.update_channel_label = QLabel(self)
        self.update_channel_combo = QComboBox(self)

        # ----------------------------------------------------
        # GameBanana cache widgets
        # ----------------------------------------------------

        self.cache_group = QGroupBox(self)

        self.cache_description_label = QLabel(self)
        self.cache_description_label.setObjectName(
            "settingsMutedText"
        )
        self.cache_description_label.setWordWrap(
            True
        )

        self.cache_enabled_checkbox = QCheckBox(self)

        self.cache_path_label = QLabel(self)

        self.cache_path_input = QLineEdit(self)

        self.choose_cache_button = QPushButton(self)
        self.default_cache_button = QPushButton(self)

        self.cache_max_size_label = QLabel(self)
        self.cache_max_size_spinbox = QSpinBox(self)

        self.cache_size_label = QLabel(self)
        self.cache_size_label.setObjectName(
            "settingsCacheSize"
        )

        self.refresh_cache_button = QPushButton(self)
        self.clear_cache_button = QPushButton(self)

        self.status_label = QLabel(self)
        self.status_label.setObjectName(
            "settingsStatus"
        )
        self.status_label.setWordWrap(
            True
        )

        self.reset_button = QPushButton(self)
        self.save_button = QPushButton(self)
        self.save_button.setObjectName(
            "primaryButton"
        )

        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self.load_values()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        # ----------------------------------------------------
        # Root: footer stays visible, settings content scrolls.
        # This prevents QGroupBox content from being compressed
        # on Windows when the dialog is shorter than its sizeHint.
        # ----------------------------------------------------

        root_layout = QVBoxLayout(self)
        self._root_layout = root_layout
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName(
            "globalSettingsScrollArea"
        )
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName(
            "globalSettingsContent"
        )
        self.scroll_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        content_layout = QVBoxLayout(
            self.scroll_content
        )
        self._content_layout = content_layout
        content_layout.setContentsMargins(
            28, 26, 28, 18
        )
        content_layout.setSpacing(18)
        content_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )

        content_layout.addWidget(
            self.title_label
        )
        content_layout.addWidget(
            self.description_label
        )

        # ----------------------------------------------------
        # Application
        # ----------------------------------------------------

        application_form = QFormLayout(
            self.application_group
        )
        self._application_form = application_form
        application_form.setHorizontalSpacing(18)
        application_form.setVerticalSpacing(12)
        application_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy
            .AllNonFixedFieldsGrow
        )

        self.language_combo.addItem(
            "",
            userData="de",
        )
        self.language_combo.addItem(
            "",
            userData="en",
        )

        self.theme_combo.addItem(
            "",
            userData="dark",
        )
        self.theme_combo.addItem(
            "",
            userData="light",
        )
        self.theme_combo.addItem(
            "",
            userData="system",
        )

        application_form.addRow(
            self.language_label,
            self.language_combo,
        )
        application_form.addRow(
            self.theme_label,
            self.theme_combo,
        )

        self.application_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        content_layout.addWidget(
            self.application_group
        )

        # ----------------------------------------------------
        # Updates
        # ----------------------------------------------------

        update_form = QFormLayout(
            self.update_group
        )
        self._update_form = update_form
        update_form.setHorizontalSpacing(18)
        update_form.setVerticalSpacing(12)
        update_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy
            .AllNonFixedFieldsGrow
        )

        self.update_channel_combo.addItem(
            "",
            userData="stable",
        )
        self.update_channel_combo.addItem(
            "",
            userData="prerelease",
        )

        update_form.addRow(
            self.auto_updates_checkbox
        )
        update_form.addRow(
            self.update_channel_label,
            self.update_channel_combo,
        )

        self.update_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        content_layout.addWidget(
            self.update_group
        )

        # ----------------------------------------------------
        # GameBanana image cache
        # ----------------------------------------------------

        cache_layout = QVBoxLayout(
            self.cache_group
        )
        self._cache_layout = cache_layout
        cache_layout.setSpacing(10)

        cache_layout.addWidget(
            self.cache_description_label
        )
        cache_layout.addWidget(
            self.cache_enabled_checkbox
        )
        cache_layout.addWidget(
            self.cache_path_label
        )

        self.cache_path_input.setPlaceholderText(
            str(DEFAULT_CACHE_DIRECTORY)
        )

        self._cache_path_grid = QGridLayout()
        self._cache_path_grid.setContentsMargins(
            0, 0, 0, 0
        )
        self._cache_path_grid.setHorizontalSpacing(8)
        self._cache_path_grid.setVerticalSpacing(8)
        cache_layout.addLayout(
            self._cache_path_grid
        )

        self.cache_max_size_spinbox.setRange(
            64,
            32768,
        )
        self.cache_max_size_spinbox.setSuffix(
            " MB"
        )
        self.cache_max_size_spinbox.setSingleStep(
            128
        )

        self._cache_size_grid = QGridLayout()
        self._cache_size_grid.setContentsMargins(
            0, 0, 0, 0
        )
        self._cache_size_grid.setHorizontalSpacing(8)
        self._cache_size_grid.setVerticalSpacing(8)
        cache_layout.addLayout(
            self._cache_size_grid
        )

        self._cache_action_grid = QGridLayout()
        self._cache_action_grid.setContentsMargins(
            0, 0, 0, 0
        )
        self._cache_action_grid.setHorizontalSpacing(8)
        self._cache_action_grid.setVerticalSpacing(8)
        cache_layout.addLayout(
            self._cache_action_grid
        )

        for button in (
            self.choose_cache_button,
            self.default_cache_button,
            self.refresh_cache_button,
            self.clear_cache_button,
            self.reset_button,
            self.save_button,
        ):
            button.setMinimumWidth(0)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        self.cache_path_input.setMinimumWidth(0)
        self.cache_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        content_layout.addWidget(
            self.cache_group
        )
        content_layout.addStretch(1)

        self.scroll_area.setWidget(
            self.scroll_content
        )
        root_layout.addWidget(
            self.scroll_area,
            stretch=1,
        )

        # ----------------------------------------------------
        # Persistent footer actions
        # ----------------------------------------------------

        self.footer_frame = QFrame(self)
        self.footer_frame.setObjectName(
            "globalSettingsFooter"
        )

        self._footer_grid = QGridLayout(
            self.footer_frame
        )
        self._footer_grid.setContentsMargins(
            20, 12, 20, 12
        )
        self._footer_grid.setHorizontalSpacing(10)
        self._footer_grid.setVerticalSpacing(8)

        root_layout.addWidget(
            self.footer_frame
        )

        self._update_responsive_layout(
            force=True
        )
        self._apply_windows_safe_style()

    @staticmethod
    def _remove_from_grid(
        layout: QGridLayout,
        widgets: tuple[QWidget, ...],
    ) -> None:
        for widget in widgets:
            layout.removeWidget(widget)

    def _update_responsive_layout(
        self,
        *,
        force: bool = False,
    ) -> None:
        width = max(1, self.width())

        mode = (
            "compact"
            if width < 720
            else "wide"
        )

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

        self._remove_from_grid(
            self._cache_path_grid,
            (
                self.cache_path_input,
                self.choose_cache_button,
                self.default_cache_button,
            ),
        )
        self._remove_from_grid(
            self._cache_size_grid,
            (
                self.cache_max_size_label,
                self.cache_max_size_spinbox,
            ),
        )
        self._remove_from_grid(
            self._cache_action_grid,
            (
                self.cache_size_label,
                self.refresh_cache_button,
                self.clear_cache_button,
            ),
        )
        self._remove_from_grid(
            self._footer_grid,
            (
                self.status_label,
                self.reset_button,
                self.save_button,
            ),
        )

        if mode == "compact":
            self._content_layout.setContentsMargins(
                18, 18, 18, 14
            )
            self._content_layout.setSpacing(14)

            self._application_form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.WrapLongRows
            )
            self._update_form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.WrapLongRows
            )

            self._cache_path_grid.addWidget(
                self.cache_path_input,
                0, 0, 1, 2,
            )
            self._cache_path_grid.addWidget(
                self.choose_cache_button,
                1, 0,
            )
            self._cache_path_grid.addWidget(
                self.default_cache_button,
                1, 1,
            )
            self._cache_path_grid.setColumnStretch(
                0, 1
            )
            self._cache_path_grid.setColumnStretch(
                1, 1
            )

            self._cache_size_grid.addWidget(
                self.cache_max_size_label,
                0, 0, 1, 2,
            )
            self._cache_size_grid.addWidget(
                self.cache_max_size_spinbox,
                1, 0, 1, 2,
            )

            self._cache_action_grid.addWidget(
                self.cache_size_label,
                0, 0, 1, 2,
            )
            self._cache_action_grid.addWidget(
                self.refresh_cache_button,
                1, 0,
            )
            self._cache_action_grid.addWidget(
                self.clear_cache_button,
                1, 1,
            )
            self._cache_action_grid.setColumnStretch(
                0, 1
            )
            self._cache_action_grid.setColumnStretch(
                1, 1
            )
            self._cache_action_grid.setColumnStretch(
                2, 0
            )

            self._footer_grid.addWidget(
                self.status_label,
                0, 0, 1, 2,
            )
            self._footer_grid.addWidget(
                self.reset_button,
                1, 0,
            )
            self._footer_grid.addWidget(
                self.save_button,
                1, 1,
            )
            self._footer_grid.setColumnStretch(
                0, 1
            )
            self._footer_grid.setColumnStretch(
                1, 1
            )

        else:
            self._content_layout.setContentsMargins(
                28, 26, 28, 18
            )
            self._content_layout.setSpacing(18)

            self._application_form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.DontWrapRows
            )
            self._update_form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.DontWrapRows
            )

            self._cache_path_grid.addWidget(
                self.cache_path_input,
                0, 0,
            )
            self._cache_path_grid.addWidget(
                self.choose_cache_button,
                0, 1,
            )
            self._cache_path_grid.addWidget(
                self.default_cache_button,
                0, 2,
            )
            self._cache_path_grid.setColumnStretch(
                0, 1
            )
            self._cache_path_grid.setColumnStretch(
                1, 0
            )
            self._cache_path_grid.setColumnStretch(
                2, 0
            )

            self._cache_size_grid.addWidget(
                self.cache_max_size_label,
                0, 0,
            )
            self._cache_size_grid.addWidget(
                self.cache_max_size_spinbox,
                0, 1,
            )
            self._cache_size_grid.setColumnStretch(
                0, 1
            )

            self._cache_action_grid.addWidget(
                self.cache_size_label,
                0, 0,
            )
            self._cache_action_grid.addWidget(
                self.refresh_cache_button,
                0, 1,
            )
            self._cache_action_grid.addWidget(
                self.clear_cache_button,
                0, 2,
            )
            self._cache_action_grid.setColumnStretch(
                0, 1
            )

            self._footer_grid.addWidget(
                self.status_label,
                0, 0,
            )
            self._footer_grid.addWidget(
                self.reset_button,
                0, 1,
            )
            self._footer_grid.addWidget(
                self.save_button,
                0, 2,
            )
            self._footer_grid.setColumnStretch(
                0, 1
            )
            self._footer_grid.setColumnStretch(
                1, 0
            )
            self._footer_grid.setColumnStretch(
                2, 0
            )

        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.updateGeometry()

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _connect_signals(
        self,
    ) -> None:
        self.choose_cache_button.clicked.connect(
            self._choose_cache_directory
        )

        self.default_cache_button.clicked.connect(
            self._use_default_cache_directory
        )

        self.refresh_cache_button.clicked.connect(
            self._refresh_cache_size
        )

        self.clear_cache_button.clicked.connect(
            self._clear_cache
        )

        self.reset_button.clicked.connect(
            self.load_values
        )

        self.save_button.clicked.connect(
            self.save_values
        )

    def _apply_windows_safe_style(
        self,
    ) -> None:
        """
        Uses explicit widget colors instead of relying on the native
        Windows palette. This keeps checkbox, label and combobox text
        readable on both Windows and Linux.
        """

        self.setStyleSheet(
            """
            QWidget#globalSettingsPage {
                background-color: #12151b;
                color: #e7e9ef;
            }

            QScrollArea#globalSettingsScrollArea,
            QScrollArea#globalSettingsScrollArea > QWidget,
            QScrollArea#globalSettingsScrollArea > QWidget > QWidget,
            QWidget#globalSettingsContent {
                background-color: #12151b;
                border: none;
            }

            QFrame#globalSettingsFooter {
                background-color: #151920;
                border-top: 1px solid #2b313d;
            }

            QScrollArea#globalSettingsScrollArea QScrollBar:vertical {
                width: 10px;
                background-color: #101319;
                margin: 0px;
            }

            QScrollArea#globalSettingsScrollArea QScrollBar::handle:vertical {
                min-height: 28px;
                background-color: #343c47;
                border-radius: 5px;
            }

            QScrollArea#globalSettingsScrollArea QScrollBar::handle:vertical:hover {
                background-color: #4a5564;
            }

            QScrollArea#globalSettingsScrollArea QScrollBar::add-line:vertical,
            QScrollArea#globalSettingsScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QWidget#globalSettingsPage QLabel {
                background: transparent;
                color: #dfe3ea;
            }

            QWidget#globalSettingsPage QLabel#pageTitle {
                color: #f7f8fa;
                font-size: 26px;
                font-weight: 800;
            }

            QWidget#globalSettingsPage QLabel#pageDescription,
            QWidget#globalSettingsPage QLabel#settingsMutedText {
                color: #939cab;
            }

            QWidget#globalSettingsPage QLabel#settingsCacheSize {
                color: #b9c0cb;
                font-weight: 600;
            }

            QWidget#globalSettingsPage QLabel#settingsStatus {
                color: #a9b2bf;
            }

            QWidget#globalSettingsPage QGroupBox {
                background-color: #171b22;
                color: #f1f3f6;
                border: 1px solid #2b313d;
                border-radius: 10px;
                margin-top: 12px;
                padding: 14px 14px 12px 14px;
                font-weight: 700;
            }

            QWidget#globalSettingsPage QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                color: #f1f3f6;
                background-color: #171b22;
            }

            QWidget#globalSettingsPage QCheckBox {
                background: transparent;
                color: #e7e9ef;
                spacing: 8px;
                min-height: 28px;
            }

            QWidget#globalSettingsPage QCheckBox:disabled {
                color: #6f7784;
            }

            QWidget#globalSettingsPage QLineEdit,
            QWidget#globalSettingsPage QComboBox,
            QWidget#globalSettingsPage QSpinBox {
                min-height: 34px;
                padding: 0 9px;
                background-color: #1d222b;
                color: #f1f3f6;
                border: 1px solid #353c49;
                border-radius: 7px;
                selection-background-color: #6657c9;
                selection-color: #ffffff;
            }

            QWidget#globalSettingsPage QLineEdit:focus,
            QWidget#globalSettingsPage QComboBox:focus,
            QWidget#globalSettingsPage QSpinBox:focus {
                border: 1px solid #7668dc;
            }

            QWidget#globalSettingsPage QLineEdit:disabled,
            QWidget#globalSettingsPage QComboBox:disabled,
            QWidget#globalSettingsPage QSpinBox:disabled {
                background-color: #171b22;
                color: #727b88;
                border-color: #292f39;
            }

            QWidget#globalSettingsPage QComboBox QAbstractItemView {
                background-color: #1d222b;
                color: #f1f3f6;
                border: 1px solid #3a424f;
                selection-background-color: #6657c9;
                selection-color: #ffffff;
                outline: none;
            }

            QWidget#globalSettingsPage QPushButton {
                min-height: 34px;
                padding: 0 13px;
                background-color: #282e38;
                color: #edf0f4;
                border: 1px solid #3a424f;
                border-radius: 7px;
                font-weight: 600;
            }

            QWidget#globalSettingsPage QPushButton:hover {
                background-color: #333a46;
                border-color: #4a5463;
            }

            QWidget#globalSettingsPage QPushButton:pressed {
                background-color: #232832;
            }

            QWidget#globalSettingsPage QPushButton:disabled {
                background-color: #1a1f26;
                color: #676f7b;
                border-color: #292f38;
            }

            QWidget#globalSettingsPage QPushButton#primaryButton {
                background-color: #6758d1;
                color: #ffffff;
                border-color: #7a6de0;
            }

            QWidget#globalSettingsPage QPushButton#primaryButton:hover {
                background-color: #7566dd;
                border-color: #8a7de7;
            }

            QToolTip {
                background-color: #20242c;
                color: #f1f3f6;
                border: 1px solid #3a404b;
                padding: 5px 7px;
            }
            """
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "settings.global.title"
            )
        )

        self.description_label.setText(
            tr(
                "settings.global.description"
            )
        )

        self.application_group.setTitle(
            tr(
                "settings.global.group.application"
            )
        )

        self.language_label.setText(
            tr(
                "settings.language.label"
            )
        )

        self.theme_label.setText(
            tr(
                "settings.appearance.label"
            )
        )

        self._set_combo_text(
            self.language_combo,
            "de",
            tr(
                "settings.language.de"
            ),
        )

        self._set_combo_text(
            self.language_combo,
            "en",
            tr(
                "settings.language.en"
            ),
        )

        self._set_combo_text(
            self.theme_combo,
            "dark",
            tr(
                "settings.theme.dark"
            ),
        )

        self._set_combo_text(
            self.theme_combo,
            "light",
            tr(
                "settings.theme.light"
            ),
        )

        self._set_combo_text(
            self.theme_combo,
            "system",
            tr(
                "settings.theme.system"
            ),
        )

        self.update_group.setTitle(
            tr(
                "updates.settings.title"
            )
        )

        self.auto_updates_checkbox.setText(
            tr(
                "updates.settings.auto_check"
            )
        )

        self.update_channel_label.setText(
            tr(
                "updates.settings.channel"
            )
        )

        self._set_combo_text(
            self.update_channel_combo,
            "stable",
            tr(
                "updates.channel.stable"
            ),
        )

        self._set_combo_text(
            self.update_channel_combo,
            "prerelease",
            tr(
                "updates.channel.prerelease"
            ),
        )

        self.cache_group.setTitle(
            tr(
                "settings.global.cache.title"
            )
        )

        self.cache_description_label.setText(
            tr(
                "settings.global.cache.description"
            )
        )

        self.cache_enabled_checkbox.setText(
            tr(
                "settings.global.cache.enabled"
            )
        )

        self.cache_path_label.setText(
            tr(
                "settings.global.cache.path"
            )
        )

        self.choose_cache_button.setText(
            tr(
                "settings.button.choose"
            )
        )

        self.default_cache_button.setText(
            tr(
                "settings.button.default"
            )
        )

        self.cache_max_size_label.setText(
            tr(
                "settings.global.cache.max_size"
            )
        )

        self.refresh_cache_button.setText(
            tr(
                "settings.global.cache.refresh_size"
            )
        )

        self.clear_cache_button.setText(
            tr(
                "settings.global.cache.clear"
            )
        )

        self.reset_button.setText(
            tr(
                "settings.button.reset"
            )
        )

        self.save_button.setText(
            tr(
                "settings.button.save"
            )
        )

        self._refresh_cache_size()

    @staticmethod
    def _set_combo_text(
        combo: QComboBox,
        data: str,
        text: str,
    ) -> None:
        index = combo.findData(
            data
        )

        if index >= 0:
            combo.setItemText(
                index,
                text,
            )

    # ========================================================
    # Load
    # ========================================================

    def load_values(
        self,
    ) -> None:
        language = getattr(
            self.config,
            "language",
            translation_manager.language,
        )

        index = self.language_combo.findData(
            language
        )

        if index >= 0:
            self.language_combo.setCurrentIndex(
                index
            )

        theme = getattr(
            self.config,
            "theme",
            "dark",
        )

        index = self.theme_combo.findData(
            theme
        )

        if index >= 0:
            self.theme_combo.setCurrentIndex(
                index
            )

        self.auto_updates_checkbox.setChecked(
            bool(
                getattr(
                    self.config,
                    "auto_check_updates",
                    True,
                )
            )
        )

        channel = getattr(
            self.config,
            "update_channel",
            "prerelease",
        )

        index = self.update_channel_combo.findData(
            channel
        )

        if index >= 0:
            self.update_channel_combo.setCurrentIndex(
                index
            )

        self.cache_settings = (
            load_gamebanana_image_cache_settings()
        )

        self.cache_enabled_checkbox.setChecked(
            self.cache_settings.enabled
        )

        self.cache_path_input.setText(
            self.cache_settings.directory
            or ""
        )

        self.cache_max_size_spinbox.setValue(
            self.cache_settings.max_size_mb
        )

        self.status_label.clear()

        self._refresh_cache_size()

    # ========================================================
    # Save
    # ========================================================

    def save_values(
        self,
    ) -> None:
        language = self.language_combo.currentData()
        theme = self.theme_combo.currentData()
        update_channel = (
            self.update_channel_combo.currentData()
        )

        if isinstance(
            language,
            str,
        ):
            self.config.language = language

        if isinstance(
            theme,
            str,
        ):
            self.config.theme = theme

        self.config.auto_check_updates = (
            self.auto_updates_checkbox.isChecked()
        )

        if isinstance(
            update_channel,
            str,
        ):
            self.config.update_channel = (
                update_channel
            )

        cache_path = (
            self.cache_path_input
            .text()
            .strip()
        )

        cache_settings = (
            GameBananaImageCacheSettings(
                enabled=(
                    self.cache_enabled_checkbox
                    .isChecked()
                ),
                directory=(
                    cache_path
                    or None
                ),
                max_size_mb=(
                    self.cache_max_size_spinbox
                    .value()
                ),
            )
        )

        try:
            self.config.save()

            save_gamebanana_image_cache_settings(
                cache_settings
            )

        except OSError as error:
            QMessageBox.critical(
                self,
                tr(
                    "settings.error.save.title"
                ),
                tr(
                    "settings.error.save.message",
                    error=str(
                        error
                    ),
                ),
            )

            return

        self.cache_settings = (
            cache_settings
        )

        GameBananaPreviewImage.clear_memory_cache()

        if isinstance(
            language,
            str,
        ):
            set_language(
                language
            )

        self._refresh_cache_size()

        message = tr(
            "settings.global.status.saved"
        )

        self.status_label.setText(
            message
        )

        self.settings_saved.emit(
            message
        )

    # ========================================================
    # Cache path
    # ========================================================

    def _choose_cache_directory(
        self,
    ) -> None:
        current = (
            self.cache_path_input
            .text()
            .strip()
        )

        if current:
            start_directory = str(
                Path(
                    current
                )
                .expanduser()
            )

        else:
            start_directory = str(
                DEFAULT_CACHE_DIRECTORY
            )

        selected = QFileDialog.getExistingDirectory(
            self,
            tr(
                "settings.global.cache.choose_directory"
            ),
            start_directory,
        )

        if selected:
            self.cache_path_input.setText(
                selected
            )

    def _use_default_cache_directory(
        self,
    ) -> None:
        self.cache_path_input.clear()

        self._refresh_cache_size()

    # ========================================================
    # Cache object for current form
    # ========================================================

    def _current_cache(
        self,
    ) -> GameBananaImageCache:
        cache_path = (
            self.cache_path_input
            .text()
            .strip()
        )

        settings = (
            GameBananaImageCacheSettings(
                enabled=(
                    self.cache_enabled_checkbox
                    .isChecked()
                ),
                directory=(
                    cache_path
                    or None
                ),
                max_size_mb=(
                    self.cache_max_size_spinbox
                    .value()
                ),
            )
        )

        return GameBananaImageCache(
            settings=settings
        )

    # ========================================================
    # Size
    # ========================================================

    def _refresh_cache_size(
        self,
    ) -> None:
        cache = self._current_cache()

        size = cache.size_bytes()

        self.cache_size_label.setText(
            tr(
                "settings.global.cache.current_size",
                size=self._format_bytes(
                    size
                ),
            )
        )

    # ========================================================
    # Clear
    # ========================================================

    def _clear_cache(
        self,
    ) -> None:
        cache = self._current_cache()

        answer = QMessageBox.question(
            self,
            tr(
                "settings.global.cache.clear_title"
            ),
            tr(
                "settings.global.cache.clear_message",
                path=str(
                    cache.directory
                ),
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        deleted = cache.clear()

        GameBananaPreviewImage.clear_memory_cache()

        self._refresh_cache_size()

        self.status_label.setText(
            tr(
                "settings.global.cache.cleared",
                count=deleted,
            )
        )

    # ========================================================
    # Format
    # ========================================================

    @staticmethod
    def _format_bytes(
        value: int,
    ) -> str:
        if value < 1024:
            return f"{value} B"

        if value < 1024 ** 2:
            return (
                f"{value / 1024:.1f} KB"
            )

        if value < 1024 ** 3:
            return (
                f"{value / 1024 ** 2:.1f} MB"
            )

        return (
            f"{value / 1024 ** 3:.2f} GB"
        )
