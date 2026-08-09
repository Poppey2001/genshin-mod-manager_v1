from __future__ import annotations

import logging

from pathlib import Path

from PySide6.QtCore import (
    QSignalBlocker,
    Signal,
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
        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            40,
            36,
            40,
            36,
        )

        main_layout.setSpacing(
            22
        )

        # --------------------------------------------------
        # Titel
        # --------------------------------------------------

        self.title_label = QLabel(
            self
        )

        self.title_label.setObjectName(
            "pageTitle"
        )

        self.description_label = QLabel(
            self
        )

        self.description_label.setObjectName(
            "pageDescription"
        )

        self.description_label.setWordWrap(
            True
        )

        main_layout.addWidget(
            self.title_label
        )

        main_layout.addWidget(
            self.description_label
        )

        # --------------------------------------------------
        # Gruppen
        # --------------------------------------------------

        main_layout.addWidget(
            self._create_library_group()
        )

        main_layout.addWidget(
            self._create_paths_group()
        )

        main_layout.addWidget(
            self._create_options_group()
        )

        main_layout.addWidget(
            self.update_settings_group
        )

        main_layout.addStretch()

        # --------------------------------------------------
        # Untere Leiste
        # --------------------------------------------------

        bottom_layout = QHBoxLayout()

        bottom_layout.setSpacing(
            12
        )

        self.status_label.setObjectName(
            "settingsStatus"
        )

        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.reset_button = QPushButton(
            self
        )

        self.reset_button.setObjectName(
            "secondaryButton"
        )

        self.reset_button.clicked.connect(
            self._reset_form
        )

        self.save_button = QPushButton(
            self
        )

        self.save_button.setObjectName(
            "primaryButton"
        )

        self.save_button.clicked.connect(
            self._save_settings
        )

        bottom_layout.addWidget(
            self.status_label
        )

        bottom_layout.addWidget(
            self.reset_button
        )

        bottom_layout.addWidget(
            self.save_button
        )

        main_layout.addLayout(
            bottom_layout
        )

        self._apply_local_stylesheet()

    # ==================================================
    # Bibliothek
    # ==================================================

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
            QGroupBox {
                background-color: #20232a;
                border: 1px solid #30343d;
                border-radius: 9px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #ffffff;
            }

            QLabel#settingsLabel {
                color: #f1f1f1;
                font-weight: bold;
            }

            QLabel#settingsDescription {
                color: #969ca8;
                font-size: 13px;
            }

            QLabel#settingsStatus {
                color: #8fd694;
                font-size: 13px;
            }

            QLineEdit {
                min-height: 36px;
                padding: 0 10px;
                background-color: #16181d;
                border: 1px solid #3a3f49;
                border-radius: 6px;
                color: #f1f1f1;
            }

            QLineEdit:focus {
                border-color: #7c5cff;
            }

            QPushButton {
                min-height: 36px;
                padding: 0 14px;
                background-color: #30343d;
                border: 1px solid #414651;
                border-radius: 6px;
                color: #f1f1f1;
            }

            QPushButton:hover {
                background-color: #3a3f49;
            }

            QPushButton#primaryButton {
                background-color: #7c5cff;
                border-color: #7c5cff;
                font-weight: bold;
            }

            QPushButton#primaryButton:hover {
                background-color: #8b70ff;
            }

            QPushButton#secondaryButton {
                background-color: transparent;
            }

            QCheckBox {
                spacing: 10px;
                color: #f1f1f1;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }

            QComboBox {
                min-width: 170px;
                min-height: 36px;
                padding: 0 10px;
                background-color: #16181d;
                border: 1px solid #3a3f49;
                border-radius: 6px;
                color: #f1f1f1;
            }

            QComboBox QAbstractItemView {
                background-color: #20232a;
                color: #f1f1f1;
                selection-background-color: #7c5cff;
            }

            QFrame#settingsSeparator {
                background-color: #30343d;
                border: none;
                max-height: 1px;
            }
            """
        )