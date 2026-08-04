from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.pages.settings_page import SettingsPage
from app.pages.library_page import LibraryPage

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Hauptfenster des Genshin Mod Managers."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()

        self.config = config

        self.setWindowTitle("Genshin Mod Manager")
        self.setMinimumSize(900, 550)

        self.resize(
            self.config.window_width,
            self.config.window_height,
        )

        self.navigation_list = QListWidget()
        self.page_stack = QStackedWidget()

        self._build_ui()
        self._connect_signals()

        self.navigation_list.setCurrentRow(0)

    def _build_ui(self) -> None:
        """Erstellt die komplette Grundoberfläche."""
        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)

        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        sidebar = self._create_sidebar()

        central_layout.addWidget(sidebar)
        central_layout.addWidget(self.page_stack, stretch=1)

        self.setCentralWidget(central_widget)

        self._create_pages()
        self._apply_stylesheet()

        self.statusBar().showMessage(
            f"Aktives Profil: {self.config.selected_profile}"
        )

    def _create_sidebar(self) -> QWidget:
        """Erstellt die linke Navigation."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(16)

        title_label = QLabel("Genshin")
        title_label.setObjectName("appTitle")

        subtitle_label = QLabel("Mod Manager")
        subtitle_label.setObjectName("appSubtitle")

        sidebar_layout.addWidget(title_label)
        sidebar_layout.addWidget(subtitle_label)

        self.navigation_list.setObjectName("navigationList")
        self.navigation_list.setFrameShape(QFrame.Shape.NoFrame)
        self.navigation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.navigation_list.setSpacing(4)

        navigation_items = [
            "Bibliothek",
            "Profile",
            "Konflikte",
            "Einstellungen",
        ]

        for item_name in navigation_items:
            item = QListWidgetItem(item_name)
            item.setSizeHint(item.sizeHint().expandedTo(
                self.navigation_list.sizeHint()
            ))
            self.navigation_list.addItem(item)

        sidebar_layout.addWidget(self.navigation_list)
        sidebar_layout.addStretch()

        version_label = QLabel("Version 0.3.0")
        version_label.setObjectName("versionLabel")

        sidebar_layout.addWidget(version_label)

        return sidebar

    def _create_pages(self) -> None:
        """Erstellt die Seiten des Managers."""
        self.library_page = LibraryPage(
                config=self.config
            )

        self.page_stack.addWidget(
                self.library_page
            )
        self.page_stack.addWidget(
            self._create_placeholder_page(
                title="Profile",
                description=(
                    "Hier kannst du später verschiedene "
                    "Mod-Zusammenstellungen speichern."
                ),
            )
        )

        self.page_stack.addWidget(
            self._create_placeholder_page(
                title="Konflikte",
                description=(
                    "Hier zeigt der Manager später mögliche "
                    "Datei- und Mod-Konflikte an."
                ),
            )
        )

        self.settings_page = SettingsPage(
            config=self.config
        )   
        self.settings_page.settings_saved.connect(
            self._on_settings_saved
        )
        self.page_stack.addWidget(
            self.settings_page
        )

    def _create_placeholder_page(
        self,
        title: str,
        description: str,
    ) -> QWidget:
        """Erstellt eine einfache Platzhalterseite."""
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")

        description_label = QLabel(description)
        description_label.setObjectName("pageDescription")
        description_label.setWordWrap(True)
        description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()

        return page

    def _connect_signals(self) -> None:
        """Verbindet die Navigation mit dem Seitenbereich."""
        self.navigation_list.currentRowChanged.connect(
            self._change_page
        )

    def _change_page(self, index: int) -> None:
        """Wechselt zur ausgewählten Seite."""
        if 0 <= index < self.page_stack.count():
            self.page_stack.setCurrentIndex(index)

    def _apply_stylesheet(self) -> None:
        """Wendet ein erstes dunkles Design an."""
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #16181d;
            }

            QWidget {
                color: #f1f1f1;
                font-family: Sans-Serif;
                font-size: 14px;
            }

            QFrame#sidebar {
                background-color: #20232a;
                border-right: 1px solid #30343d;
            }

            QLabel#appTitle {
                font-size: 25px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#appSubtitle {
                font-size: 16px;
                color: #9ca3af;
                margin-bottom: 15px;
            }

            QLabel#versionLabel {
                color: #737987;
                font-size: 12px;
            }

            QListWidget#navigationList {
                background-color: transparent;
                border: none;
                outline: none;
            }

            QListWidget#navigationList::item {
                min-height: 44px;
                padding-left: 14px;
                border-radius: 7px;
                color: #c4c8d0;
            }

            QListWidget#navigationList::item:hover {
                background-color: #2b2f38;
                color: #ffffff;
            }

            QListWidget#navigationList::item:selected {
                background-color: #7c5cff;
                color: #ffffff;
            }

            QLabel#pageTitle {
                font-size: 28px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#pageDescription {
                color: #a8adb7;
                font-size: 15px;
            }

            QStatusBar {
                background-color: #20232a;
                color: #a8adb7;
                border-top: 1px solid #30343d;
            }
            """
        )

    def _on_settings_saved(
        self,
        message: str,
    ) -> None:
        """Aktualisiert die Oberfläche nach dem Speichern."""
        self.statusBar().showMessage(
            message,
            5000,
        )
         
        self.library_page.scan_mods()
        self.library_page.cancel_scan()
        
        
    def closeEvent(self, event: QCloseEvent) -> None:
        """Speichert die Fenstergröße vor dem Beenden."""
        self.config.window_width = self.width()
        self.config.window_height = self.height()

        try:
            self.config.save()
            logger.info(
                "Fenstergröße gespeichert: %sx%s",
                self.config.window_width,
                self.config.window_height,
            )

        except OSError as error:
            logger.exception(
                "Konfiguration konnte beim Beenden nicht gespeichert werden: %s",
                error,
            )

        event.accept()
        
    