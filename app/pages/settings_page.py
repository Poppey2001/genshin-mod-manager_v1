from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
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

from app.config import AppConfig


logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Einstellungsseite des Genshin Mod Managers."""

    settings_saved = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()

        self.config = config
        self.library_input = QLineEdit()
        self.active_mods_input = QLineEdit()
        self.launcher_input = QLineEdit()

        self.use_symlinks_checkbox = QCheckBox(
            "Mods über symbolische Links aktivieren"
        )
        self.create_backups_checkbox = QCheckBox(
            "Vor Änderungen automatisch Backups erstellen"
        )

        self.theme_combobox = QComboBox()

        self.status_label = QLabel()

        self._build_ui()
        self._load_config_values()

    def _build_ui(self) -> None:
        """Erstellt die Oberfläche der Einstellungsseite."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 36, 40, 36)
        main_layout.setSpacing(22)

        title_label = QLabel("Einstellungen")
        title_label.setObjectName("pageTitle")

        description_label = QLabel(
            "Lege den aktiven Mods-Ordner, den Launcher "
            "und das Verhalten des Mod Managers fest."
        )
        description_label.setObjectName("pageDescription")
        description_label.setWordWrap(True)

        main_layout.addWidget(title_label)
        main_layout.addWidget(description_label)
        main_layout.addWidget(self._create_library_group())
                    
        main_layout.addWidget(self._create_paths_group())
        main_layout.addWidget(self._create_options_group())

        main_layout.addStretch()

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.status_label.setObjectName("settingsStatus")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        reset_button = QPushButton("Zurücksetzen")
        reset_button.setObjectName("secondaryButton")
        reset_button.clicked.connect(
            self._reset_form
        )

        save_button = QPushButton("Einstellungen speichern")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(
            self._save_settings
        )

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addWidget(reset_button)
        bottom_layout.addWidget(save_button)

        main_layout.addLayout(bottom_layout)

        self._apply_local_stylesheet()
        
    def _create_library_group(self) -> QGroupBox:
        """Erstellt die Einstellungen für die zentrale Mod-Bibliothek."""
        group = QGroupBox("Mod-Bibliothek")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(
            18,
            24,
            18,
            18,
        )
        layout.setSpacing(12)

        description_label = QLabel(
            "Hier liegen alle vom Manager verwalteten Mods. "
            "Der Ordner kann lokal oder auf einem eingehängten "
            "Netzlaufwerk liegen."
        )
        description_label.setObjectName(
            "settingsDescription"
        )
        description_label.setWordWrap(True)

        self.library_input.setReadOnly(False)
        self.library_input.setPlaceholderText(
            "Standard: ~/.local/share/genshin-mod-manager/mods"
        )

        choose_button = QPushButton(
            "Auswählen"
        )
        choose_button.clicked.connect(
            self._choose_library_directory
        )

        default_button = QPushButton(
            "Standard"
        )
        default_button.clicked.connect(
            self.library_input.clear
        )

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        path_layout.addWidget(
            self.library_input,
            stretch=1,
        )
        path_layout.addWidget(
            choose_button
        )
        path_layout.addWidget(
            default_button
        )

        layout.addWidget(
            description_label
        )
        layout.addLayout(
            path_layout
        )

        return group      
        
    def _choose_library_directory(self) -> None:
        """Wählt einen lokalen oder eingehängten Netzwerkordner."""
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
                "Mod-Bibliothek auswählen",
                start_directory,
            )
        )

        if selected_directory:
            self.library_input.setText(
                selected_directory
            )
            self.status_label.clear()
        
    def _create_paths_group(self) -> QGroupBox:
        """Erstellt den Bereich für Mods- und Launcher-Pfade."""
        group = QGroupBox("Pfade")
        layout = QGridLayout(group)

        layout.setContentsMargins(18, 24, 18, 18)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(16)

        active_mods_label = QLabel("Aktiver Mods-Ordner")
        active_mods_label.setObjectName("settingsLabel")

        active_mods_description = QLabel(
            "Der Ordner, aus dem der verwendete Mod-Loader "
            "seine Mods lädt."
        )
        active_mods_description.setObjectName(
            "settingsDescription"
        )
        active_mods_description.setWordWrap(True)

        self.active_mods_input.setReadOnly(False)
        self.active_mods_input.setPlaceholderText(
            "Noch kein Mods-Ordner ausgewählt"
        )

        choose_mods_button = QPushButton("Auswählen")
        choose_mods_button.clicked.connect(
            self._choose_active_mods_directory
        )

        clear_mods_button = QPushButton("Leeren")
        clear_mods_button.clicked.connect(
            self.active_mods_input.clear
        )

        mods_button_layout = QHBoxLayout()
        mods_button_layout.setContentsMargins(0, 0, 0, 0)
        mods_button_layout.setSpacing(8)
        mods_button_layout.addWidget(choose_mods_button)
        mods_button_layout.addWidget(clear_mods_button)

        launcher_label = QLabel("Launcher")
        launcher_label.setObjectName("settingsLabel")

        launcher_description = QLabel(
            "Optionaler Pfad zu einem AppImage, Shell-Skript, "
            "Wine-Programm oder Mod-Loader."
        )
        launcher_description.setObjectName(
            "settingsDescription"
        )
        launcher_description.setWordWrap(True)

        self.launcher_input.setReadOnly(True)
        self.launcher_input.setPlaceholderText(
            "Noch kein Launcher ausgewählt"
        )

        choose_launcher_button = QPushButton("Auswählen")
        choose_launcher_button.clicked.connect(
            self._choose_launcher
        )

        clear_launcher_button = QPushButton("Leeren")
        clear_launcher_button.clicked.connect(
            self.launcher_input.clear
        )

        launcher_button_layout = QHBoxLayout()
        launcher_button_layout.setContentsMargins(0, 0, 0, 0)
        launcher_button_layout.setSpacing(8)
        launcher_button_layout.addWidget(
            choose_launcher_button
        )
        launcher_button_layout.addWidget(
            clear_launcher_button
        )

        layout.addWidget(active_mods_label, 0, 0, 1, 2)
        layout.addWidget(
            active_mods_description,
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

        separator = QFrame()
        separator.setFrameShape(
            QFrame.Shape.HLine
        )
        separator.setObjectName("settingsSeparator")

        layout.addWidget(separator, 3, 0, 1, 2)

        layout.addWidget(launcher_label, 4, 0, 1, 2)
        layout.addWidget(
            launcher_description,
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

        layout.setColumnStretch(0, 1)

        return group
    

    def _create_options_group(self) -> QGroupBox:
        """Erstellt den Bereich für allgemeine Optionen."""
        group = QGroupBox("Verhalten")
        layout = QVBoxLayout(group)

        layout.setContentsMargins(18, 24, 18, 18)
        layout.setSpacing(14)

        symlink_description = QLabel(
            "Bei symbolischen Links bleiben die Mods in der "
            "zentralen Bibliothek und werden nicht dupliziert."
        )
        symlink_description.setObjectName(
            "settingsDescription"
        )
        symlink_description.setWordWrap(True)

        backup_description = QLabel(
            "Backups schützen vorhandene Dateien vor "
            "versehentlichem Überschreiben."
        )
        backup_description.setObjectName(
            "settingsDescription"
        )
        backup_description.setWordWrap(True)

        theme_layout = QHBoxLayout()

        theme_label = QLabel("Darstellung")
        theme_label.setObjectName("settingsLabel")

        self.theme_combobox.addItem(
            "Dunkel",
            userData="dark",
        )
        self.theme_combobox.addItem(
            "Hell",
            userData="light",
        )
        self.theme_combobox.addItem(
            "Systemeinstellung",
            userData="system",
        )

        theme_layout.addWidget(theme_label)
        theme_layout.addStretch()
        theme_layout.addWidget(self.theme_combobox)

        layout.addWidget(
            self.use_symlinks_checkbox
        )
        layout.addWidget(symlink_description)

        layout.addSpacing(8)

        layout.addWidget(
            self.create_backups_checkbox
        )
        layout.addWidget(backup_description)

        layout.addSpacing(8)
        layout.addLayout(theme_layout)

        return group

    def _load_config_values(self) -> None:
        """Übernimmt die gespeicherten Werte in das Formular."""
        self.library_input.setText(
            self.config.library_path or ""
        )
        
        self.active_mods_input.setText(
            self.config.active_mods_path or ""
        )

        self.launcher_input.setText(
            self.config.launcher_path or ""
        )

        self.use_symlinks_checkbox.setChecked(
            self.config.use_symlinks
        )

        self.create_backups_checkbox.setChecked(
            self.config.create_backups
        )

        theme_index = self.theme_combobox.findData(
            self.config.theme
        )

        if theme_index >= 0:
            self.theme_combobox.setCurrentIndex(
                theme_index
            )

        self.status_label.clear()

    def _choose_active_mods_directory(self) -> None:
        """Öffnet einen Dialog zur Auswahl des Mods-Ordners."""
        current_path = self.active_mods_input.text().strip()

        if current_path:
            start_directory = current_path
        else:
            start_directory = str(Path.home())

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Aktiven Mods-Ordner auswählen",
            start_directory,
        )

        if selected_directory:
            self.active_mods_input.setText(
                selected_directory
            )
            self.status_label.clear()

    def _choose_launcher(self) -> None:
        """Öffnet einen Dialog zur Auswahl des Launchers."""
        current_path = self.launcher_input.text().strip()

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

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Launcher auswählen",
            start_directory,
            (
                "Launcher und Programme "
                "(*.AppImage *.sh *.exe);;"
                "Alle Dateien (*)"
            ),
        )

        if selected_file:
            self.launcher_input.setText(
                selected_file
            )
            self.status_label.clear()

    def _save_settings(self) -> None:
        """Prüft und speichert die Einstellungen."""
        library_path_text = (
            self.library_input.text().strip()
        )
        
        mods_path_text = (
            self.active_mods_input.text().strip()
        )

        launcher_path_text = (
            self.launcher_input.text().strip()
        )
    
        if mods_path_text:
            mods_path = Path(
                mods_path_text
            ).expanduser()
            if ("://" in mods_path_text
                or "://" in library_path_text
            ):
                QMessageBox.warning(
                    self,
                    "Netzlaufwerk wird Benutzt",
                    (
                        "Adressen wie smb:// oder nfs:// koennnen nicht"
                        "direkt verwendet werden. \n\n"
                        "Binde das Netzlaufwerk zuerst unter /mnt /media"
                        "oder ueber deinen Dateimanager ein."
                    )
                )
            if not mods_path.exists():
                QMessageBox.warning(
                    self,
                    "Ungültiger Mods-Ordner",
                    (
                        "Der ausgewählte Mods-Ordner "
                        "existiert nicht."
                    ),
                )
                return

            if not mods_path.is_dir():
                QMessageBox.warning(
                    self,
                    "Ungültiger Mods-Ordner",
                    (
                        "Der ausgewählte Pfad ist "
                        "kein Verzeichnis."
                    ),
                )
                return
        if library_path_text:
            library_path = Path(
                library_path_text
            ).expanduser()

            if not library_path.exists():
                answer = QMessageBox.question(
                    self,
                    "Bibliothek erstellen",
                    (
                        "Der ausgewählte Bibliotheksordner existiert "
                        "noch nicht.\n\n"
                        "Soll er jetzt erstellt werden?"
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
                        "Ordner konnte nicht erstellt werden",
                        str(error),
                    )
                return

        if not library_path.is_dir():
            QMessageBox.warning(
                self,
                "Ungültige Mod-Bibliothek",
                "Der Bibliothekspfad ist kein Verzeichnis.",
            )
            return
        if launcher_path_text:
            launcher_path = Path(
                launcher_path_text
            ).expanduser()

            if not launcher_path.exists():
                QMessageBox.warning(
                    self,
                    "Ungültiger Launcher",
                    (
                        "Die ausgewählte Launcher-Datei "
                        "existiert nicht."
                    ),
                )
                return

            if not launcher_path.is_file():
                QMessageBox.warning(
                    self,
                    "Ungültiger Launcher",
                    (
                        "Der ausgewählte Launcher-Pfad "
                        "ist keine Datei."
                    ),
                )
                return

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

            self.config.use_symlinks = (
                self.use_symlinks_checkbox.isChecked()
            )

            self.config.create_backups = (
                self.create_backups_checkbox.isChecked()
            )

            selected_theme = (
                self.theme_combobox.currentData()
            )

            if isinstance(selected_theme, str):
                self.config.theme = selected_theme

            self.config.first_start = False
            self.config.save()

        except OSError as error:
            logger.exception(
                "Einstellungen konnten nicht gespeichert werden."
            )

            QMessageBox.critical(
                self,
                "Speicherfehler",
                (
                    "Die Einstellungen konnten nicht "
                    "gespeichert werden.\n\n"
                    f"{error}"
                ),
            )
            return

        self.status_label.setText(
            "Einstellungen wurden gespeichert."
        )

        self.settings_saved.emit(
            "Einstellungen wurden gespeichert."
        )

        logger.info(
            "Einstellungen erfolgreich gespeichert."
        )

    def _reset_form(self) -> None:
        """
        Setzt das Formular auf den zuletzt gespeicherten
        Konfigurationsstand zurück.
        """
        self._load_config_values()

        self.status_label.setText(
            "Nicht gespeicherte Änderungen wurden verworfen."
        )

    def _apply_local_stylesheet(self) -> None:
        """Ergänzt die Gestaltung der Einstellungsseite."""
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