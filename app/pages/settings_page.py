from __future__ import annotations

import logging

from pathlib import Path

from PySide6.QtCore import (
    QSignalBlocker,
    Signal,
    Qt,
)

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)
from app.widgets.settings.update_settings_group import (
    UpdateSettingsGroup,
)

from app.config import AppConfig

from app.i18n import (
    set_language,
    tr,
    translation_manager,
)

from app.platform_support import (
    launcher_file_filter,
)


logger = logging.getLogger(
    __name__
)


class SettingsPage(QWidget):
    """Einstellungsseite des Genshin Mod Managers."""

    settings_saved = Signal(str)
    check_updates_requested = Signal()
    
    THEME_TRANSLATION_KEYS = {
        "dark": "settings.theme.dark",
        "light": "settings.theme.light",
        "system": "settings.theme.system",
    }

    LANGUAGE_TRANSLATION_KEYS = {
        "de": "settings.language.de",
        "en": "settings.language.en",
    }

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.setObjectName(
            "settingsPage"
        )

        self.config = config

        # --------------------------------------------------
        # Eingabefelder
        # --------------------------------------------------

        self.library_input = QLineEdit(
            self
        )

        self.active_mods_input = QLineEdit(
            self
        )

        self.launcher_input = QLineEdit(
            self
        )

        # --------------------------------------------------
        # Optionen
        # --------------------------------------------------

        self.use_symlinks_checkbox = QCheckBox(
            self
        )

        self.create_backups_checkbox = QCheckBox(
            self
        )

        self.theme_combobox = QComboBox(
            self
        )

        self.language_combobox = QComboBox(
            self
        )

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        self.status_label = QLabel(
            self
        )

        # --------------------------------------------------
        # Übersetzbare Widgets
        # --------------------------------------------------

        self.title_label: QLabel
        self.description_label: QLabel

        self.library_group: QGroupBox
        self.library_description_label: QLabel
        self.library_choose_button: QPushButton
        self.library_default_button: QPushButton

        self.paths_group: QGroupBox
        self.active_mods_label: QLabel
        self.active_mods_description_label: QLabel
        self.active_mods_choose_button: QPushButton
        self.active_mods_clear_button: QPushButton

        self.launcher_label: QLabel
        self.launcher_description_label: QLabel
        self.launcher_choose_button: QPushButton
        self.launcher_clear_button: QPushButton

        self.options_group: QGroupBox
        self.symlink_description_label: QLabel
        self.backup_description_label: QLabel
        self.theme_label: QLabel
        self.language_label: QLabel

        self.reset_button: QPushButton
        self.save_button: QPushButton
        
        self.update_settings_group = (
            UpdateSettingsGroup(
                config=self.config,
                parent=self,
            )
        )

        self.update_settings_group.check_requested.connect(
            self.check_updates_requested.emit
        )

        # --------------------------------------------------
        # Aufbau
        # --------------------------------------------------

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self._load_config_values()

    # ==================================================
    # UI
    # ==================================================

    def _build_ui(
        self,
    ) -> None:
        self.setObjectName(
            "settingsPage"
        )

        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            22,
            20,
            22,
            16,
        )

        root_layout.setSpacing(
            14
        )

        # ========================================================
        # Header
        # ========================================================

        header = QVBoxLayout()

        header.setContentsMargins(
            2,
            2,
            2,
            2,
        )

        header.setSpacing(
            3
        )

        title_label = QLabel(
            "Einstellungen"
        )

        title_label.setObjectName(
            "pageTitle"
        )

        description_label = QLabel(
            (
                "Konfiguriere den Mod Manager, "
                "deine Bibliothek und deine Spielumgebung."
            )
        )

        description_label.setObjectName(
            "pageDescription"
        )

        description_label.setWordWrap(
            True
        )

        header.addWidget(
            title_label
        )

        header.addWidget(
            description_label
        )

        root_layout.addLayout(
            header
        )

        # ========================================================
        # Scroll Area
        # ========================================================

        scroll_area = QScrollArea(
            self
        )

        scroll_area.setObjectName(
            "settingsScrollArea"
        )

        scroll_area.setWidgetResizable(
            True
        )

        scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll_content = QWidget()

        scroll_content.setObjectName(
            "settingsScrollContent"
        )

        content_layout = QVBoxLayout(
            scroll_content
        )

        content_layout.setContentsMargins(
            0,
            4,
            8,
            8,
        )

        content_layout.setSpacing(
            12
        )

        # ========================================================
        # Sections
        # ========================================================

        content_layout.addWidget(
            self._create_options_group()
        )

        content_layout.addWidget(
            self._create_library_group()
        )

        content_layout.addWidget(
            self._create_paths_group()
        )

        content_layout.addStretch(
            1
        )

        scroll_area.setWidget(
            scroll_content
        )

        root_layout.addWidget(
            scroll_area,
            stretch=1,
        )

        # ========================================================
        # Footer
        # ========================================================

        footer = QFrame(
            self
        )

        footer.setObjectName(
            "settingsFooter"
        )

        footer_layout = QHBoxLayout(
            footer
        )

        footer_layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )

        footer_layout.setSpacing(
            8
        )

        self.status_label.setObjectName(
            "settingsStatus"
        )

        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        footer_layout.addWidget(
            self.status_label,
            stretch=1,
        )

        reset_button = QPushButton(
            "Zurücksetzen"
        )

        reset_button.setObjectName(
            "settingsResetButton"
        )

        reset_button.setMinimumHeight(
            38
        )

        reset_button.clicked.connect(
            self._reset_form
        )

        footer_layout.addWidget(
            reset_button
        )

        save_button = QPushButton(
            "Einstellungen speichern"
        )

        save_button.setObjectName(
            "settingsSaveButton"
        )

        save_button.setMinimumHeight(
            38
        )

        save_button.clicked.connect(
            self._save_settings
        )

        footer_layout.addWidget(
            save_button
        )

        root_layout.addWidget(
            footer
        )

        # ========================================================
        # Style
        # ========================================================

        self._apply_local_stylesheet()

    def _create_library_group(
        self,
    ) -> QGroupBox:
        self.library_group = QGroupBox(
            self
        )

        layout = QVBoxLayout(
            self.library_group
        )

        layout.setContentsMargins(
            18,
            24,
            18,
            18,
        )

        layout.setSpacing(
            12
        )

        self.library_description_label = QLabel(
            self.library_group
        )

        self.library_description_label.setObjectName(
            "settingsDescription"
        )

        self.library_description_label.setWordWrap(
            True
        )

        self.library_input.setReadOnly(
            False
        )

        self.library_choose_button = QPushButton(
            self.library_group
        )

        self.library_choose_button.clicked.connect(
            self._choose_library_directory
        )

        self.library_default_button = QPushButton(
            self.library_group
        )

        self.library_default_button.clicked.connect(
            self.library_input.clear
        )

        path_layout = QHBoxLayout()

        path_layout.setSpacing(
            8
        )

        path_layout.addWidget(
            self.library_input,
            stretch=1,
        )

        path_layout.addWidget(
            self.library_choose_button
        )

        path_layout.addWidget(
            self.library_default_button
        )

        layout.addWidget(
            self.library_description_label
        )

        layout.addLayout(
            path_layout
        )

        return self.library_group

    def _choose_library_directory(
        self,
    ) -> None:
        current_path = (
            self.library_input.text().strip()
        )

        if current_path:
            start_directory = current_path

        else:
            start_directory = str(
                self.config.mod_library_directory
            )

        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                tr(
                    "settings.dialog."
                    "choose_library"
                ),
                start_directory,
            )
        )

        if not selected_directory:
            return

        self.library_input.setText(
            selected_directory
        )

        self.status_label.clear()

    # ==================================================
    # Pfade
    # ==================================================

    def _create_paths_group(
        self,
    ) -> QGroupBox:
        self.paths_group = QGroupBox(
            self
        )

        layout = QGridLayout(
            self.paths_group
        )

        layout.setContentsMargins(
            18,
            24,
            18,
            18,
        )

        layout.setHorizontalSpacing(
            12
        )

        layout.setVerticalSpacing(
            16
        )

        # --------------------------------------------------
        # Aktiver Mods-Ordner
        # --------------------------------------------------

        self.active_mods_label = QLabel(
            self.paths_group
        )

        self.active_mods_label.setObjectName(
            "settingsLabel"
        )

        self.active_mods_description_label = QLabel(
            self.paths_group
        )

        self.active_mods_description_label.setObjectName(
            "settingsDescription"
        )

        self.active_mods_description_label.setWordWrap(
            True
        )

        self.active_mods_input.setReadOnly(
            False
        )

        self.active_mods_choose_button = QPushButton(
            self.paths_group
        )

        self.active_mods_choose_button.clicked.connect(
            self._choose_active_mods_directory
        )

        self.active_mods_clear_button = QPushButton(
            self.paths_group
        )

        self.active_mods_clear_button.clicked.connect(
            self.active_mods_input.clear
        )

        mods_button_layout = QHBoxLayout()

        mods_button_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        mods_button_layout.setSpacing(
            8
        )

        mods_button_layout.addWidget(
            self.active_mods_choose_button
        )

        mods_button_layout.addWidget(
            self.active_mods_clear_button
        )

        # --------------------------------------------------
        # Launcher
        # --------------------------------------------------

        self.launcher_label = QLabel(
            self.paths_group
        )

        self.launcher_label.setObjectName(
            "settingsLabel"
        )

        self.launcher_description_label = QLabel(
            self.paths_group
        )

        self.launcher_description_label.setObjectName(
            "settingsDescription"
        )

        self.launcher_description_label.setWordWrap(
            True
        )

        self.launcher_input.setReadOnly(
            True
        )

        self.launcher_choose_button = QPushButton(
            self.paths_group
        )

        self.launcher_choose_button.clicked.connect(
            self._choose_launcher
        )

        self.launcher_clear_button = QPushButton(
            self.paths_group
        )

        self.launcher_clear_button.clicked.connect(
            self.launcher_input.clear
        )

        launcher_button_layout = QHBoxLayout()

        launcher_button_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        launcher_button_layout.setSpacing(
            8
        )

        launcher_button_layout.addWidget(
            self.launcher_choose_button
        )

        launcher_button_layout.addWidget(
            self.launcher_clear_button
        )

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        layout.addWidget(
            self.active_mods_label,
            0,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.active_mods_description_label,
            1,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.active_mods_input,
            2,
            0,
        )

        layout.addLayout(
            mods_button_layout,
            2,
            1,
        )

        separator = QFrame(
            self.paths_group
        )

        separator.setFrameShape(
            QFrame.Shape.HLine
        )

        separator.setObjectName(
            "settingsSeparator"
        )

        layout.addWidget(
            separator,
            3,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.launcher_label,
            4,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.launcher_description_label,
            5,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.launcher_input,
            6,
            0,
        )

        layout.addLayout(
            launcher_button_layout,
            6,
            1,
        )

        layout.setColumnStretch(
            0,
            1,
        )

        return self.paths_group

    def _choose_active_mods_directory(
        self,
    ) -> None:
        current_path = (
            self.active_mods_input.text().strip()
        )

        if current_path:
            start_directory = current_path

        else:
            start_directory = str(
                Path.home()
            )

        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                tr(
                    "settings.dialog."
                    "choose_active_mods"
                ),
                start_directory,
            )
        )

        if not selected_directory:
            return

        self.active_mods_input.setText(
            selected_directory
        )

        self.status_label.clear()

    def _choose_launcher(
        self,
    ) -> None:
        current_path = (
            self.launcher_input.text().strip()
        )

        if current_path:
            current_file = Path(
                current_path
            ).expanduser()

            if current_file.is_file():
                start_directory = str(
                    current_file.parent
                )

            else:
                start_directory = str(
                    Path.home()
                )

        else:
            start_directory = str(
                Path.home()
            )

        selected_file, _selected_filter = (
            QFileDialog.getOpenFileName(
                self,
                tr(
                    "settings.dialog."
                    "choose_launcher"
                ),
                start_directory,
                launcher_file_filter(),
            )
        )

        if not selected_file:
            return

        self.launcher_input.setText(
            selected_file
        )

        self.status_label.clear()

    # ==================================================
    # Verhalten / Sprache
    # ==================================================

    def _create_options_group(
        self,
    ) -> QGroupBox:
        self.options_group = QGroupBox(
            self
        )

        layout = QVBoxLayout(
            self.options_group
        )

        layout.setContentsMargins(
            18,
            24,
            18,
            18,
        )

        layout.setSpacing(
            14
        )

        self.symlink_description_label = QLabel(
            self.options_group
        )

        self.symlink_description_label.setObjectName(
            "settingsDescription"
        )

        self.symlink_description_label.setWordWrap(
            True
        )

        self.backup_description_label = QLabel(
            self.options_group
        )

        self.backup_description_label.setObjectName(
            "settingsDescription"
        )

        self.backup_description_label.setWordWrap(
            True
        )

        # --------------------------------------------------
        # Theme
        # --------------------------------------------------

        theme_layout = QHBoxLayout()

        self.theme_label = QLabel(
            self.options_group
        )

        self.theme_label.setObjectName(
            "settingsLabel"
        )

        self.theme_combobox.addItem(
            "",
            userData="dark",
        )

        self.theme_combobox.addItem(
            "",
            userData="light",
        )

        self.theme_combobox.addItem(
            "",
            userData="system",
        )

        theme_layout.addWidget(
            self.theme_label
        )

        theme_layout.addStretch()

        theme_layout.addWidget(
            self.theme_combobox
        )

        # --------------------------------------------------
        # Sprache
        # --------------------------------------------------

        language_layout = QHBoxLayout()

        self.language_label = QLabel(
            self.options_group
        )

        self.language_label.setObjectName(
            "settingsLabel"
        )

        self.language_combobox.addItem(
            "",
            userData="de",
        )

        self.language_combobox.addItem(
            "",
            userData="en",
        )

        language_layout.addWidget(
            self.language_label
        )

        language_layout.addStretch()

        language_layout.addWidget(
            self.language_combobox
        )

        # --------------------------------------------------
        # Gruppenlayout
        # --------------------------------------------------

        layout.addWidget(
            self.use_symlinks_checkbox
        )

        layout.addWidget(
            self.symlink_description_label
        )

        layout.addSpacing(
            8
        )

        layout.addWidget(
            self.create_backups_checkbox
        )

        layout.addWidget(
            self.backup_description_label
        )

        layout.addSpacing(
            8
        )

        layout.addLayout(
            theme_layout
        )

        layout.addSpacing(
            8
        )

        layout.addLayout(
            language_layout
        )

        return self.options_group

    # ==================================================
    # Übersetzung
    # ==================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr("settings.title")
        )

        self.description_label.setText(
            tr("settings.description")
        )

        self.library_group.setTitle(
            tr("settings.group.library")
        )

        self.paths_group.setTitle(
            tr("settings.group.paths")
        )

        self.options_group.setTitle(
            tr("settings.group.behavior")
        )

        self.library_description_label.setText(
            tr(
                "settings.library."
                "description"
            )
        )

        self.library_input.setPlaceholderText(
            tr(
                "settings.library."
                "placeholder"
            )
        )

        self.active_mods_label.setText(
            tr(
                "settings.active_mods."
                "label"
            )
        )

        self.active_mods_description_label.setText(
            tr(
                "settings.active_mods."
                "description"
            )
        )

        self.active_mods_input.setPlaceholderText(
            tr(
                "settings.active_mods."
                "placeholder"
            )
        )

        self.launcher_label.setText(
            tr(
                "settings.launcher."
                "label"
            )
        )

        self.launcher_description_label.setText(
            tr(
                "settings.launcher."
                "description"
            )
        )

        self.launcher_input.setPlaceholderText(
            tr(
                "settings.launcher."
                "placeholder"
            )
        )

        self.use_symlinks_checkbox.setText(
            tr(
                "settings.symlinks."
                "label"
            )
        )

        self.symlink_description_label.setText(
            tr(
                "settings.symlinks."
                "description"
            )
        )

        self.create_backups_checkbox.setText(
            tr(
                "settings.backups."
                "label"
            )
        )

        self.backup_description_label.setText(
            tr(
                "settings.backups."
                "description"
            )
        )

        self.theme_label.setText(
            tr(
                "settings.appearance."
                "label"
            )
        )

        self.language_label.setText(
            tr(
                "settings.language."
                "label"
            )
        )

        self.library_choose_button.setText(
            tr("settings.button.choose")
        )

        self.library_default_button.setText(
            tr("settings.button.default")
        )

        self.active_mods_choose_button.setText(
            tr("settings.button.choose")
        )

        self.active_mods_clear_button.setText(
            tr("settings.button.clear")
        )

        self.launcher_choose_button.setText(
            tr("settings.button.choose")
        )

        self.launcher_clear_button.setText(
            tr("settings.button.clear")
        )

        self.reset_button.setText(
            tr("settings.button.reset")
        )

        self.save_button.setText(
            tr("settings.button.save")
        )

        # --------------------------------------------------
        # Theme-Combobox
        # --------------------------------------------------

        theme_blocker = QSignalBlocker(
            self.theme_combobox
        )

        for index in range(
            self.theme_combobox.count()
        ):
            value = (
                self.theme_combobox.itemData(
                    index
                )
            )

            key = (
                self.THEME_TRANSLATION_KEYS.get(
                    str(value)
                )
            )

            if key is not None:
                self.theme_combobox.setItemText(
                    index,
                    tr(key),
                )

        del theme_blocker

        # --------------------------------------------------
        # Sprach-Combobox
        # --------------------------------------------------

        language_blocker = QSignalBlocker(
            self.language_combobox
        )

        for index in range(
            self.language_combobox.count()
        ):
            value = (
                self.language_combobox.itemData(
                    index
                )
            )

            key = (
                self.LANGUAGE_TRANSLATION_KEYS.get(
                    str(value)
                )
            )

            if key is not None:
                self.language_combobox.setItemText(
                    index,
                    tr(key),
                )

        del language_blocker

    # ==================================================
    # Config laden
    # ==================================================

    def _load_config_values(
        self,
    ) -> None:
        self.library_input.setText(
            self.config.library_path
            or ""
        )

        self.active_mods_input.setText(
            self.config.active_mods_path
            or ""
        )

        self.launcher_input.setText(
            self.config.launcher_path
            or ""
        )

        # Symlinks sind aktuell keine
        # Aktivierungsstrategie des Managers.
        self.use_symlinks_checkbox.setChecked(
            False
        )

        self.create_backups_checkbox.setChecked(
            self.config.create_backups
        )

        theme_index = (
            self.theme_combobox.findData(
                self.config.theme
            )
        )

        if theme_index >= 0:
            self.theme_combobox.setCurrentIndex(
                theme_index
            )

        language_index = (
            self.language_combobox.findData(
                self.config.language
            )
        )

        if language_index >= 0:
            self.language_combobox.setCurrentIndex(
                language_index
            )
        self.update_settings_group.load_from_config()
        self.status_label.clear()

    # ==================================================
    # Speichern
    # ==================================================

    def _save_settings(
        self,
    ) -> None:
        library_path_text = (
            self.library_input.text().strip()
        )

        mods_path_text = (
            self.active_mods_input.text().strip()
        )

        launcher_path_text = (
            self.launcher_input.text().strip()
        )

        # --------------------------------------------------
        # Keine smb:// / nfs:// URLs
        # --------------------------------------------------

        if (
            "://" in library_path_text
            or "://" in mods_path_text
        ):
            QMessageBox.warning(
                self,
                tr(
                    "settings.warning."
                    "network.title"
                ),
                tr(
                    "settings.warning."
                    "network.message"
                ),
            )

            return

        # --------------------------------------------------
        # Aktiver Mods-Ordner
        # --------------------------------------------------

        if mods_path_text:
            mods_path = Path(
                mods_path_text
            ).expanduser()

            if not mods_path.exists():
                QMessageBox.warning(
                    self,
                    tr(
                        "settings.warning."
                        "invalid_mods.title"
                    ),
                    tr(
                        "settings.warning."
                        "mods_missing"
                    ),
                )

                return

            if not mods_path.is_dir():
                QMessageBox.warning(
                    self,
                    tr(
                        "settings.warning."
                        "invalid_mods.title"
                    ),
                    tr(
                        "settings.warning."
                        "mods_not_directory"
                    ),
                )

                return

        # --------------------------------------------------
        # Bibliothek
        # --------------------------------------------------

        if library_path_text:
            library_path = Path(
                library_path_text
            ).expanduser()

            if not library_path.exists():
                answer = QMessageBox.question(
                    self,
                    tr(
                        "settings."
                        "library_create.title"
                    ),
                    tr(
                        "settings."
                        "library_create.message"
                    ),
                    (
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No
                    ),
                    QMessageBox.StandardButton.Yes,
                )

                if (
                    answer
                    != QMessageBox.StandardButton.Yes
                ):
                    return

                try:
                    library_path.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                except OSError as error:
                    QMessageBox.critical(
                        self,
                        tr(
                            "settings.error."
                            "create_directory.title"
                        ),
                        str(error),
                    )

                    return

            if not library_path.is_dir():
                QMessageBox.warning(
                    self,
                    tr(
                        "settings.warning."
                        "invalid_library.title"
                    ),
                    tr(
                        "settings.warning."
                        "invalid_library.message"
                    ),
                )

                return

        # --------------------------------------------------
        # Launcher
        # --------------------------------------------------

        if launcher_path_text:
            launcher_path = Path(
                launcher_path_text
            ).expanduser()

            if not launcher_path.exists():
                QMessageBox.warning(
                    self,
                    tr(
                        "settings.warning."
                        "invalid_launcher.title"
                    ),
                    tr(
                        "settings.warning."
                        "launcher_missing"
                    ),
                )

                return

            if not launcher_path.is_file():
                QMessageBox.warning(
                    self,
                    tr(
                        "settings.warning."
                        "invalid_launcher.title"
                    ),
                    tr(
                        "settings.warning."
                        "launcher_not_file"
                    ),
                )

                return

        # --------------------------------------------------
        # Config übernehmen
        # --------------------------------------------------

        selected_theme = (
            self.theme_combobox.currentData()
        )

        selected_language = (
            self.language_combobox.currentData()
        )

        try:
            self.config.set_mod_library_directory(
                library_path_text or None
            )

            self.config.set_active_mods_directory(
                mods_path_text or None
            )

            self.config.set_launcher_file(
                launcher_path_text or None
            )

            self.config.use_symlinks = False

            self.config.create_backups = (
                self.create_backups_checkbox.isChecked()
            )

            if isinstance(
                selected_theme,
                str,
            ):
                self.config.theme = (
                    selected_theme
                )

            if isinstance(
                selected_language,
                str,
            ):
                self.config.language = (
                    selected_language
                )
                
            self.update_settings_group.apply_to_config()
            
            self.config.first_start = False

            self.config.save()

        except OSError as error:
            logger.exception(
                "Einstellungen konnten nicht gespeichert werden."
            )

            QMessageBox.critical(
                self,
                tr(
                    "settings.error."
                    "save.title"
                ),
                tr(
                    "settings.error."
                    "save.message",
                    error=error,
                ),
            )

            return

        # --------------------------------------------------
        # Sprache SOFORT anwenden
        # --------------------------------------------------

        set_language(
            self.config.language
        )

        message = tr(
            "settings.status.saved"
        )

        self.status_label.setText(
            message
        )

        self.settings_saved.emit(
            message
        )

        logger.info(
            "Einstellungen erfolgreich gespeichert."
        )

    # ==================================================
    # Formular zurücksetzen
    # ==================================================

    def _reset_form(
        self,
    ) -> None:
        self._load_config_values()

        self.status_label.setText(
            tr(
                "settings.status.reset"
            )
        )

    # ==================================================
    # Stylesheet
    # ==================================================

    def _apply_local_stylesheet(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QWidget#settingsPage {
                background-color: #101319;
                color: #e7e9ef;
            }

            QWidget#settingsPage QLabel#pageTitle {
                background-color: transparent;
                color: #f5f6f8;
                font-size: 27px;
                font-weight: 850;
            }

            QWidget#settingsPage QLabel#pageDescription {
                background-color: transparent;
                color: #838d9b;
                font-size: 12px;
            }

            QScrollArea#settingsScrollArea {
                background-color: transparent;
                border: none;
            }

            QScrollArea#settingsScrollArea > QWidget,
            QScrollArea#settingsScrollArea > QWidget > QWidget,
            QWidget#settingsScrollContent {
                background-color: #101319;
            }


            /* ====================================================
            Section Cards
            ==================================================== */

            QGroupBox {
                background-color: #171c22;

                border: 1px solid #2b323b;
                border-radius: 11px;

                margin-top: 16px;

                padding-top: 12px;

                color: #f1f3f6;

                font-size: 12px;
                font-weight: 850;
            }

            QGroupBox::title {
                subcontrol-origin: margin;

                left: 14px;

                padding-left: 6px;
                padding-right: 6px;

                color: #aeb6c2;
            }


            /* ====================================================
            Labels
            ==================================================== */

            QLabel#settingsLabel {
                background-color: transparent;

                color: #edf0f4;

                font-size: 11px;
                font-weight: 800;
            }

            QLabel#settingsDescription {
                background-color: transparent;

                color: #7f8997;

                font-size: 10px;
            }

            QLabel#settingsStatus {
                background-color: transparent;

                color: #72dca3;

                font-size: 10px;
                font-weight: 700;
            }


            /* ====================================================
            Input
            ==================================================== */

            QLineEdit {
                min-height: 36px;

                padding-left: 10px;
                padding-right: 10px;

                background-color: #11151a;

                color: #e5e8ed;

                border: 1px solid #303742;
                border-radius: 7px;

                selection-background-color: #7157e8;
            }

            QLineEdit:hover {
                border-color: #3d4652;
            }

            QLineEdit:focus {
                border-color: #8067ff;
            }


            /* ====================================================
            Combo
            ==================================================== */

            QComboBox {
                min-width: 170px;
                min-height: 36px;

                padding-left: 10px;
                padding-right: 10px;

                background-color: #11151a;

                color: #e5e8ed;

                border: 1px solid #303742;
                border-radius: 7px;
            }

            QComboBox:hover {
                border-color: #3d4652;
            }

            QComboBox:focus {
                border-color: #8067ff;
            }

            QComboBox QAbstractItemView {
                background-color: #191e25;

                color: #e1e5ea;

                border: 1px solid #333a45;

                selection-background-color: #2e2948;
            }


            /* ====================================================
            CheckBox
            ==================================================== */

            QCheckBox {
                background-color: transparent;

                color: #e2e6eb;

                spacing: 10px;

                font-size: 11px;
                font-weight: 700;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }


            /* ====================================================
            Normal Buttons
            ==================================================== */

            QWidget#settingsPage QPushButton {
                min-height: 34px;

                padding-left: 13px;
                padding-right: 13px;

                background-color: #20262e;

                color: #ccd2da;

                border: 1px solid #303843;
                border-radius: 7px;

                font-size: 10px;
                font-weight: 750;
            }

            QWidget#settingsPage QPushButton:hover {
                background-color: #29313a;

                color: #ffffff;

                border-color: #424c59;
            }


            /* ====================================================
            Footer
            ==================================================== */

            QFrame#settingsFooter {
                background-color: #15191f;

                border: 1px solid #292f38;
                border-radius: 11px;
            }


            /* Reset */

            QPushButton#settingsResetButton {
                background-color: #20262e;

                color: #c8ced7;

                border-color: #303843;
            }


            /* Save */

            QPushButton#settingsSaveButton {
                min-width: 170px;

                background-color: #6651d7;

                color: #ffffff;

                border: 1px solid #7b66eb;

                font-weight: 850;
            }

            QPushButton#settingsSaveButton:hover {
                background-color: #7560ea;

                border-color: #9180f5;
            }


            /* ====================================================
            Separator
            ==================================================== */

            QFrame#settingsSeparator {
                background-color: #2a313a;

                border: none;

                max-height: 1px;
            }
            """
        )
        
    def on_game_changed(
        self,
        _game_id: str,
    ) -> None:
        """
        Lädt die Pfade des neu ausgewählten Spiels.
        """

        game_config = (
            self.config.current_game_config
        )

        self.library_input.setText(
            game_config.library_path
            or str(
                self.config
                .mod_library_directory
            )
        )

        self.active_mods_input.setText(
            game_config.active_mods_path
            or ""
        )

        self.launcher_input.setText(
            game_config.launcher_path
            or ""
        )

        self.status_label.clear()