from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Signal,
)

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.i18n import (
    set_language,
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


class GlobalSettingsPage(
    QWidget
):
    settings_saved = Signal(
        str
    )

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config

        self.cache_settings = (
            load_gamebanana_image_cache_settings()
        )

        # ----------------------------------------------------
        # Global
        # ----------------------------------------------------

        self.language_combo = (
            QComboBox()
        )

        self.theme_combo = (
            QComboBox()
        )

        self.auto_updates_checkbox = (
            QCheckBox(
                "Automatisch nach Updates suchen"
            )
        )

        self.update_channel_combo = (
            QComboBox()
        )

        # ----------------------------------------------------
        # GameBanana Cache
        # ----------------------------------------------------

        self.cache_enabled_checkbox = (
            QCheckBox(
                (
                    "GameBanana-Bildcache "
                    "aktivieren"
                )
            )
        )

        self.cache_path_input = (
            QLineEdit()
        )

        self.cache_max_size_spinbox = (
            QSpinBox()
        )

        self.cache_size_label = (
            QLabel()
        )

        self.status_label = QLabel()

        self._build_ui()

        self.load_values()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            28,
            26,
            28,
            26,
        )

        layout.setSpacing(
            18
        )

        title = QLabel(
            "Globale Einstellungen"
        )

        title.setObjectName(
            "pageTitle"
        )

        description = QLabel(
            (
                "Diese Optionen gelten für "
                "den gesamten XXMI Mod Manager."
            )
        )

        description.setWordWrap(
            True
        )

        layout.addWidget(
            title
        )

        layout.addWidget(
            description
        )

        # ====================================================
        # Anwendung
        # ====================================================

        application_group = (
            QGroupBox(
                "Anwendung"
            )
        )

        application_form = (
            QFormLayout(
                application_group
            )
        )

        self.language_combo.addItem(
            "Deutsch",
            userData="de",
        )

        self.language_combo.addItem(
            "English",
            userData="en",
        )

        self.theme_combo.addItem(
            "Dunkel",
            userData="dark",
        )

        self.theme_combo.addItem(
            "Hell",
            userData="light",
        )

        self.theme_combo.addItem(
            "System",
            userData="system",
        )

        application_form.addRow(
            "Sprache",
            self.language_combo,
        )

        application_form.addRow(
            "Darstellung",
            self.theme_combo,
        )

        layout.addWidget(
            application_group
        )

        # ====================================================
        # Updates
        # ====================================================

        update_group = (
            QGroupBox(
                "Updates"
            )
        )

        update_form = (
            QFormLayout(
                update_group
            )
        )

        self.update_channel_combo.addItem(
            "Stable",
            userData="stable",
        )

        self.update_channel_combo.addItem(
            "Alpha / Prerelease",
            userData="prerelease",
        )

        update_form.addRow(
            self.auto_updates_checkbox
        )

        update_form.addRow(
            "Update-Kanal",
            self.update_channel_combo,
        )

        layout.addWidget(
            update_group
        )

        # ====================================================
        # GameBanana Cache
        # ====================================================

        cache_group = (
            QGroupBox(
                "GameBanana Bild-Cache"
            )
        )

        cache_layout = (
            QVBoxLayout(
                cache_group
            )
        )

        cache_layout.setSpacing(
            12
        )

        cache_description = QLabel(
            (
                "Vorschaubilder und Screenshots "
                "können lokal gespeichert werden, "
                "damit sie nicht bei jedem Öffnen "
                "erneut heruntergeladen werden."
            )
        )

        cache_description.setWordWrap(
            True
        )

        cache_layout.addWidget(
            cache_description
        )

        cache_layout.addWidget(
            self.cache_enabled_checkbox
        )

        # ----------------------------------------------------
        # Pfad
        # ----------------------------------------------------

        cache_path_label = QLabel(
            "Cache-Verzeichnis"
        )

        cache_layout.addWidget(
            cache_path_label
        )

        path_row = QHBoxLayout()

        self.cache_path_input.setPlaceholderText(
            str(
                DEFAULT_CACHE_DIRECTORY
            )
        )

        choose_cache_button = (
            QPushButton(
                "Auswählen"
            )
        )

        choose_cache_button.clicked.connect(
            self._choose_cache_directory
        )

        default_cache_button = (
            QPushButton(
                "Standard"
            )
        )

        default_cache_button.clicked.connect(
            self._use_default_cache_directory
        )

        path_row.addWidget(
            self.cache_path_input,
            stretch=1,
        )

        path_row.addWidget(
            choose_cache_button
        )

        path_row.addWidget(
            default_cache_button
        )

        cache_layout.addLayout(
            path_row
        )

        # ----------------------------------------------------
        # Max size
        # ----------------------------------------------------

        size_row = QHBoxLayout()

        max_size_label = QLabel(
            "Maximale Cache-Größe"
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

        size_row.addWidget(
            max_size_label
        )

        size_row.addStretch(
            1
        )

        size_row.addWidget(
            self.cache_max_size_spinbox
        )

        cache_layout.addLayout(
            size_row
        )

        # ----------------------------------------------------
        # Current size / clear
        # ----------------------------------------------------

        cache_action_row = (
            QHBoxLayout()
        )

        cache_action_row.addWidget(
            self.cache_size_label
        )

        cache_action_row.addStretch(
            1
        )

        refresh_cache_button = (
            QPushButton(
                "Größe aktualisieren"
            )
        )

        refresh_cache_button.clicked.connect(
            self._refresh_cache_size
        )

        clear_cache_button = (
            QPushButton(
                "Cache leeren"
            )
        )

        clear_cache_button.clicked.connect(
            self._clear_cache
        )

        cache_action_row.addWidget(
            refresh_cache_button
        )

        cache_action_row.addWidget(
            clear_cache_button
        )

        cache_layout.addLayout(
            cache_action_row
        )

        layout.addWidget(
            cache_group
        )

        layout.addStretch(
            1
        )

        # ====================================================
        # Bottom
        # ====================================================

        bottom = QHBoxLayout()

        bottom.addWidget(
            self.status_label
        )

        bottom.addStretch(
            1
        )

        reset_button = QPushButton(
            "Zurücksetzen"
        )

        reset_button.clicked.connect(
            self.load_values
        )

        save_button = QPushButton(
            "Speichern"
        )

        save_button.setObjectName(
            "primaryButton"
        )

        save_button.clicked.connect(
            self.save_values
        )

        bottom.addWidget(
            reset_button
        )

        bottom.addWidget(
            save_button
        )

        layout.addLayout(
            bottom
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

        index = (
            self.language_combo.findData(
                language
            )
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

        index = (
            self.theme_combo.findData(
                theme
            )
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

        index = (
            self.update_channel_combo.findData(
                channel
            )
        )

        if index >= 0:
            self.update_channel_combo.setCurrentIndex(
                index
            )

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

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
        language = (
            self.language_combo
            .currentData()
        )

        theme = (
            self.theme_combo
            .currentData()
        )

        update_channel = (
            self.update_channel_combo
            .currentData()
        )

        if isinstance(
            language,
            str,
        ):
            self.config.language = (
                language
            )

        if isinstance(
            theme,
            str,
        ):
            self.config.theme = (
                theme
            )

        self.config.auto_check_updates = (
            self.auto_updates_checkbox
            .isChecked()
        )

        if isinstance(
            update_channel,
            str,
        ):
            self.config.update_channel = (
                update_channel
            )

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

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
                "Einstellungen",
                str(
                    error
                ),
            )

            return

        self.cache_settings = (
            cache_settings
        )

        # Neue Einstellungen sollen bei
        # neuen Bildern direkt greifen.
        GameBananaPreviewImage.clear_memory_cache()

        if isinstance(
            language,
            str,
        ):
            set_language(
                language
            )

        self._refresh_cache_size()

        message = (
            "Globale Einstellungen wurden gespeichert."
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

        selected = (
            QFileDialog
            .getExistingDirectory(
                self,
                "Cache-Verzeichnis auswählen",
                start_directory,
            )
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

        return (
            GameBananaImageCache(
                settings=settings
            )
        )

    # ========================================================
    # Size
    # ========================================================

    def _refresh_cache_size(
        self,
    ) -> None:
        cache = (
            self._current_cache()
        )

        size = (
            cache.size_bytes()
        )

        self.cache_size_label.setText(
            (
                "Aktuelle Größe: "
                f"{self._format_bytes(size)}"
            )
        )

    # ========================================================
    # Clear
    # ========================================================

    def _clear_cache(
        self,
    ) -> None:
        cache = (
            self._current_cache()
        )

        answer = QMessageBox.question(
            self,
            "GameBanana Cache leeren",
            (
                "Alle gespeicherten "
                "GameBanana-Vorschaubilder "
                "löschen?\n\n"
                f"{cache.directory}"
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
            (
                f"{deleted} Cache-Dateien "
                "wurden gelöscht."
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