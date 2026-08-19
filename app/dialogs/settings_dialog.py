from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QStyle,
)

from app.config import (
    AppConfig,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.pages.global_settings_page import (
    GlobalSettingsPage,
)

from app.pages.settings_page import (
    SettingsPage,
)


class SettingsDialog(
    QDialog
):
    settings_saved = Signal(
        str
    )

    def __init__(
        self,
        *,
        config: AppConfig,
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config
        self._responsive_mode = None

        self.setObjectName(
            "settingsDialog"
        )

        self.setWindowTitle(
            tr(
                "settings.dialog.window_title"
            )
        )

        self.setModal(
            False
        )

        self.resize(
            1050,
            760,
        )

        self.setMinimumSize(
            860,
            620,
        )

        self.navigation = (
            QListWidget()
        )

        self.stack = (
            QStackedWidget()
        )

        # ----------------------------------------------------
        # Game Settings
        # ----------------------------------------------------

        self.game_settings_page = (
            SettingsPage(
                config=self.config
            )
        )

        # ----------------------------------------------------
        # Global Settings
        # ----------------------------------------------------

        self.global_settings_page = (
            GlobalSettingsPage(
                config=self.config
            )
        )

        self._build_ui()

        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self.on_game_changed(
            self.config.selected_game
        )

        self._update_responsive_layout(
            force=True
        )

    def _build_ui(
        self,
    ) -> None:
        root_layout = (
            QHBoxLayout(
                self
            )
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(
            0
        )

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------

        navigation_frame = QFrame()

        navigation_frame.setObjectName(
            "settingsNavigation"
        )

        navigation_layout = QHBoxLayout(
            navigation_frame
        )

        navigation_layout.setContentsMargins(
            14,
            18,
            14,
            18,
        )

        self.navigation.setObjectName(
            "settingsNavigationList"
        )

        self.navigation.setMinimumWidth(
            160
        )
        self.navigation.setMaximumWidth(
            190
        )

        self.game_item = QListWidgetItem()

        self.game_item.setIcon(
            self.style()
            .standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )
        )

        self.global_item = QListWidgetItem()

        self.global_item.setIcon(
            self.style()
            .standardIcon(
                QStyle.StandardPixmap.SP_FileDialogDetailedView
            )
        )

        self.navigation.addItem(
            self.game_item
        )

        self.navigation.addItem(
            self.global_item
        )

        navigation_layout.addWidget(
            self.navigation
        )

        root_layout.addWidget(
            navigation_frame
        )

        # ----------------------------------------------------
        # Pages
        # ----------------------------------------------------

        self.stack.addWidget(
            self.game_settings_page
        )

        self.stack.addWidget(
            self.global_settings_page
        )

        root_layout.addWidget(
            self.stack,
            stretch=1,
        )

        self.navigation.setCurrentRow(
            0
        )

        self._apply_style()

    def _connect_signals(
        self,
    ) -> None:
        self.navigation.currentRowChanged.connect(
            self.stack.setCurrentIndex
        )

        self.game_settings_page.settings_saved.connect(
            self.settings_saved
        )

        self.global_settings_page.settings_saved.connect(
            self.settings_saved
        )

    def on_game_changed(
        self,
        game_id: str,
    ) -> None:
        """
        Aktualisiert die Game Settings
        auf das ausgewählte Spiel.
        """

        handler = getattr(
            self.game_settings_page,
            "on_game_changed",
            None,
        )

        if callable(
            handler
        ):
            handler(
                game_id
            )

            return

        # Fallback für ältere SettingsPage-Versionen.
        loader = getattr(
            self.game_settings_page,
            "_load_config_values",
            None,
        )

        if callable(
            loader
        ):
            loader()

    def open_game_settings(
        self,
    ) -> None:
        self.navigation.setCurrentRow(
            0
        )

        self.show()

        self.raise_()

        self.activateWindow()

    def open_global_settings(
        self,
    ) -> None:
        self.navigation.setCurrentRow(
            1
        )

        self.show()

        self.raise_()

        self.activateWindow()

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(
        self,
        *,
        force: bool = False,
    ) -> None:
        mode = (
            "compact"
            if self.width() < 980
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

        target_width = (
            160
            if mode == "compact"
            else 190
        )
        self.navigation.setFixedWidth(
            target_width
        )

        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.setWindowTitle(
            tr(
                "settings.dialog.window_title"
            )
        )

        self.game_item.setText(
            tr(
                "settings.dialog.nav.game"
            )
        )

        self.global_item.setText(
            tr(
                "settings.dialog.nav.global"
            )
        )

    def _apply_style(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QDialog#settingsDialog {
                background: #12151b;
                color: #f1f1f1;
            }

            QDialog#settingsDialog QStackedWidget {
                background: #12151b;
                border: none;
            }

            QFrame#settingsNavigation {
                background: #191d25;
                border-right: 1px solid #2d3340;
            }

            QListWidget#settingsNavigationList {
                background: transparent;
                color: #aeb5c1;
                border: none;
                outline: none;
            }

            QListWidget#settingsNavigationList::viewport {
                background: transparent;
            }

            QListWidget#settingsNavigationList::item {
                height: 46px;
                padding-left: 12px;
                border-radius: 8px;
                color: #aeb5c1;
            }

            QListWidget#settingsNavigationList::item:hover {
                background: #252b36;
                color: #f1f3f6;
            }

            QListWidget#settingsNavigationList::item:selected {
                background: #30284b;
                color: #ffffff;
            }

            QToolTip {
                background-color: #20242c;
                color: #f1f3f6;
                border: 1px solid #3a404b;
                padding: 5px 7px;
            }
            """
        )