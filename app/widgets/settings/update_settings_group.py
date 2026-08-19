from __future__ import annotations

from PySide6.QtCore import (
    QSignalBlocker,
    Signal,
)

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.config import AppConfig

from app.i18n import (
    tr,
    translation_manager,
)

from app.services.appimage_updater import (
    is_appimage_runtime,
)

from app.services.windows_installer_updater import (
    is_windows_installer_runtime,
)

from app.services.update_agent_client import (
    configure_update_agent,
    is_update_agent_installed,
    update_agent_settings,
)

from app.version import (
    APP_VERSION_DISPLAY,
)


class UpdateSettingsGroup(
    QGroupBox
):
    check_requested = Signal()

    CHANNEL_TRANSLATION_KEYS = {
        "stable": (
            "updates.channel.stable"
        ),
        "prerelease": (
            "updates.channel.prerelease"
        ),
    }

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

        self.auto_check_checkbox = (
            QCheckBox(
                self
            )
        )

        self.channel_label = QLabel(
            self
        )

        self.channel_combobox = (
            QComboBox(
                self
            )
        )

        self.version_title_label = (
            QLabel(
                self
            )
        )

        self.version_value_label = (
            QLabel(
                self
            )
        )

        self.runtime_label = QLabel(
            self
        )
        self.runtime_label.setWordWrap(
            True
        )

        self.agent_autostart_checkbox = (
            QCheckBox(
                self
            )
        )

        self.agent_components_checkbox = (
            QCheckBox(
                self
            )
        )

        self.agent_language_label = QLabel(
            self
        )
        self.agent_language_label.setWordWrap(
            True
        )

        self.agent_interval_label = QLabel(
            self
        )

        self.agent_interval_spinbox = (
            QSpinBox(
                self
            )
        )
        self.agent_interval_spinbox.setRange(
            15,
            1440,
        )
        self.agent_interval_spinbox.setSuffix(
            " min"
        )

        self.skipped_version_label = QLabel(
            self
        )
        self.skipped_version_label.setWordWrap(
            True
        )

        self.reset_skipped_button = (
            QPushButton(
                self
            )
        )

        self.check_button = (
            QPushButton(
                self
            )
        )

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self.load_from_config()

    def _build_ui(
        self,
    ) -> None:
        layout = QGridLayout(
            self
        )

        layout.setContentsMargins(
            18,
            24,
            18,
            18,
        )

        layout.setHorizontalSpacing(
            16
        )

        layout.setVerticalSpacing(
            12
        )

        self.channel_combobox.addItem(
            "",
            userData="stable",
        )

        self.channel_combobox.addItem(
            "",
            userData="prerelease",
        )

        self.check_button.clicked.connect(
            self.check_requested.emit
        )

        self.reset_skipped_button.clicked.connect(
            self._reset_skipped_version
        )

        layout.addWidget(
            self.auto_check_checkbox,
            0,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.channel_label,
            1,
            0,
        )

        layout.addWidget(
            self.channel_combobox,
            1,
            1,
        )

        layout.addWidget(
            self.version_title_label,
            2,
            0,
        )

        layout.addWidget(
            self.version_value_label,
            2,
            1,
        )

        layout.addWidget(
            self.runtime_label,
            3,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.agent_autostart_checkbox,
            4,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.agent_components_checkbox,
            5,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.agent_language_label,
            6,
            0,
            1,
            2,
        )

        layout.addWidget(
            self.agent_interval_label,
            7,
            0,
        )

        layout.addWidget(
            self.agent_interval_spinbox,
            7,
            1,
        )

        layout.addWidget(
            self.skipped_version_label,
            8,
            0,
        )

        layout.addWidget(
            self.reset_skipped_button,
            8,
            1,
        )

        layout.addWidget(
            self.check_button,
            9,
            1,
        )

        layout.setColumnStretch(
            0,
            1,
        )

    def load_from_config(
        self,
    ) -> None:
        self.auto_check_checkbox.setChecked(
            getattr(
                self.config,
                "auto_check_updates",
                True,
            )
        )

        channel = getattr(
            self.config,
            "update_channel",
            "prerelease",
        )

        index = (
            self.channel_combobox.findData(
                channel
            )
        )

        if index < 0:
            index = (
                self.channel_combobox.findData(
                    "prerelease"
                )
            )

        if index >= 0:
            self.channel_combobox.setCurrentIndex(
                index
            )

        agent_installed = (
            is_update_agent_installed()
        )

        self.agent_autostart_checkbox.setVisible(
            agent_installed
        )
        self.agent_components_checkbox.setVisible(
            agent_installed
        )
        self.agent_language_label.setVisible(
            agent_installed
        )
        self.agent_interval_label.setVisible(
            agent_installed
        )
        self.agent_interval_spinbox.setVisible(
            agent_installed
        )
        self.skipped_version_label.setVisible(
            agent_installed
        )
        self.reset_skipped_button.setVisible(
            agent_installed
        )

        if not agent_installed:
            return

        settings = update_agent_settings()

        self.agent_autostart_checkbox.setChecked(
            bool(
                settings.get(
                    "autostart_enabled",
                    False,
                )
            )
        )

        self.agent_components_checkbox.setChecked(
            bool(
                settings.get(
                    "component_updates_enabled",
                    True,
                )
            )
        )

        try:
            interval = int(
                settings.get(
                    "interval_minutes",
                    20,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            interval = 20

        self.agent_interval_spinbox.setValue(
            max(
                15,
                min(
                    1440,
                    interval,
                ),
            )
        )

        skipped = str(
            settings.get(
                "skipped_version",
                "",
            )
            or ""
        )

        self.skipped_version_label.setProperty(
            "skippedVersion",
            skipped,
        )

        self._refresh_skipped_label()

    def apply_to_config(
        self,
    ) -> None:
        self.config.auto_check_updates = (
            self.auto_check_checkbox
            .isChecked()
        )

        channel = (
            self.channel_combobox
            .currentData()
        )

        if isinstance(
            channel,
            str,
        ):
            self.config.update_channel = (
                channel
            )

        if is_update_agent_installed():
            configure_update_agent(
                autostart=(
                    self.agent_autostart_checkbox
                    .isChecked()
                ),
                interval_minutes=(
                    self.agent_interval_spinbox
                    .value()
                ),
                component_updates=(
                    self.agent_components_checkbox
                    .isChecked()
                ),
                language=str(
                    getattr(
                        self.config,
                        "language",
                        "en",
                    )
                ),
            )

    def _reset_skipped_version(
        self,
    ) -> None:
        if not is_update_agent_installed():
            return

        if configure_update_agent(
            reset_skipped_version=True
        ):
            self.skipped_version_label.setProperty(
                "skippedVersion",
                "",
            )

            self._refresh_skipped_label()

    def _refresh_skipped_label(
        self,
    ) -> None:
        skipped = str(
            self.skipped_version_label
            .property(
                "skippedVersion"
            )
            or ""
        )

        if skipped:
            self.skipped_version_label.setText(
                tr(
                    "updates.settings.skipped_version",
                    version=skipped,
                )
            )

            self.reset_skipped_button.setEnabled(
                True
            )

            return

        self.skipped_version_label.setText(
            tr(
                "updates.settings.no_skipped_version"
            )
        )

        self.reset_skipped_button.setEnabled(
            False
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.setTitle(
            tr(
                "updates.settings.title"
            )
        )

        self.auto_check_checkbox.setText(
            tr(
                "updates.settings.auto_check"
            )
        )

        self.channel_label.setText(
            tr(
                "updates.settings.channel"
            )
        )

        blocker = QSignalBlocker(
            self.channel_combobox
        )

        for index in range(
            self.channel_combobox.count()
        ):
            value = (
                self.channel_combobox
                .itemData(
                    index
                )
            )

            key = (
                self.CHANNEL_TRANSLATION_KEYS
                .get(
                    str(value)
                )
            )

            if key:
                self.channel_combobox.setItemText(
                    index,
                    tr(key),
                )

        del blocker

        self.version_title_label.setText(
            tr(
                "updates.settings.version"
            )
        )

        self.version_value_label.setText(
            APP_VERSION_DISPLAY
        )

        if is_update_agent_installed():
            runtime_text = tr(
                "updates.settings.runtime.agent"
            )

        elif is_windows_installer_runtime():
            runtime_text = tr(
                "updates.settings.runtime.windows_installer"
            )

        elif is_appimage_runtime():
            runtime_text = tr(
                "updates.settings.runtime.appimage"
            )

        else:
            runtime_text = tr(
                "updates.settings.runtime.dev"
            )

        self.runtime_label.setText(
            runtime_text
        )

        self.agent_autostart_checkbox.setText(
            tr(
                "updates.settings.agent_autostart"
            )
        )

        self.agent_components_checkbox.setText(
            tr(
                "updates.settings.agent_components"
            )
        )

        language_value = str(
            getattr(
                self.config,
                "language",
                "en",
            )
        )
        language_name = (
            "Deutsch"
            if language_value.casefold().startswith(
                "de"
            )
            else "English"
        )
        self.agent_language_label.setText(
            tr(
                "updates.settings.agent_language",
                language=language_name,
            )
        )

        self.agent_interval_label.setText(
            tr(
                "updates.settings.agent_interval"
            )
        )

        self.reset_skipped_button.setText(
            tr(
                "updates.settings.reset_skipped"
            )
        )

        self.check_button.setText(
            tr(
                "updates.settings.check_now"
            )
        )

        if is_update_agent_installed():
            self._refresh_skipped_label()
