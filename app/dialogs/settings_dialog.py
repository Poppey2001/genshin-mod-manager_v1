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

        self.setWindowTitle(
            "XXMI Mod Manager – Einstellungen"
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

        self.on_game_changed(
            self.config.selected_game
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

        self.navigation.setFixedWidth(
            190
        )

        game_item = QListWidgetItem(
            "Spiel"
        )

        game_item.setIcon(
            self.style()
            .standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )
        )

        global_item = QListWidgetItem(
            "Global"
        )

        global_item.setIcon(
            self.style()
            .standardIcon(
                QStyle.StandardPixmap.SP_FileDialogDetailedView
            )
        )

        self.navigation.addItem(
            game_item
        )

        self.navigation.addItem(
            global_item
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

    def _apply_style(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #12151b;
                color: #f1f1f1;
            }

            QFrame#settingsNavigation {
                background: #191d25;
                border-right: 1px solid #2d3340;
            }

            QListWidget#settingsNavigationList {
                background: transparent;
                border: none;
                outline: none;
            }

            QListWidget#settingsNavigationList::item {
                height: 46px;
                padding-left: 12px;
                border-radius: 8px;
                color: #aeb5c1;
            }

            QListWidget#settingsNavigationList::item:hover {
                background: #252b36;
            }

            QListWidget#settingsNavigationList::item:selected {
                background: #30284b;
                color: #ffffff;
            }
            """
        )