from __future__ import annotations

import logging

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtGui import (
    QCloseEvent,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig

from app.i18n import (
    tr,
    translation_manager,
)

from app.pages.library_page import (
    LibraryPage,
)

from app.pages.settings_page import (
    SettingsPage,
)

from app.platform_support import (
    PlatformSupportError,
    launch_program,
)


logger = logging.getLogger(
    __name__
)


APP_VERSION = "0.4.0"


class MainWindow(QMainWindow):
    """Hauptfenster des Genshin Mod Managers."""

    NAVIGATION_TRANSLATION_KEYS = (
        "main.navigation.library",
        "main.navigation.profiles",
        "main.navigation.conflicts",
        "main.navigation.settings",
    )

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config

        # --------------------------------------------------
        # Fenster
        # --------------------------------------------------

        self.setMinimumSize(
            900,
            550,
        )

        self.resize(
            self.config.window_width,
            self.config.window_height,
        )

        # --------------------------------------------------
        # Hauptwidgets
        # --------------------------------------------------

        self.navigation_list = QListWidget(
            self
        )

        self.page_stack = QStackedWidget(
            self
        )

        # --------------------------------------------------
        # Sidebar-Labels
        #
        # Als Attribute speichern, damit sie bei einem
        # Sprachwechsel aktualisiert werden können.
        # --------------------------------------------------

        self.sidebar_title_label: QLabel | None = None
        self.sidebar_subtitle_label: QLabel | None = None
        self.version_label: QLabel | None = None

        # --------------------------------------------------
        # Platzhalterseiten
        # --------------------------------------------------

        self.profiles_title_label: QLabel | None = None
        self.profiles_description_label: QLabel | None = None

        self.conflicts_title_label: QLabel | None = None
        self.conflicts_description_label: QLabel | None = None

        # --------------------------------------------------
        # Oberfläche
        # --------------------------------------------------

        self._build_ui()
        self._connect_signals()

        # --------------------------------------------------
        # Runtime-Übersetzung
        # --------------------------------------------------

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        # --------------------------------------------------
        # Startseite
        # --------------------------------------------------

        self.navigation_list.setCurrentRow(
            0
        )

    # ==================================================
    # Spiel starten
    # ==================================================

    def launch_game(
        self,
    ) -> None:
        launcher_path = (
            self.config.launcher_path
        )

        if not launcher_path:
            QMessageBox.warning(
                self,
                tr(
                    "main.launcher."
                    "missing.title"
                ),
                tr(
                    "main.launcher."
                    "missing.message"
                ),
            )

            return

        try:
            launch_program(
                launcher_path
            )

        except PlatformSupportError as error:
            QMessageBox.critical(
                self,
                tr(
                    "main.launcher."
                    "start_failed.title"
                ),
                str(error),
            )

    # ==================================================
    # Hauptoberfläche
    # ==================================================

    def _build_ui(
        self,
    ) -> None:
        """Erstellt die komplette Grundoberfläche."""

        central_widget = QWidget(
            self
        )

        central_layout = QHBoxLayout(
            central_widget
        )

        central_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        central_layout.setSpacing(
            0
        )

        sidebar = (
            self._create_sidebar()
        )

        central_layout.addWidget(
            sidebar
        )

        central_layout.addWidget(
            self.page_stack,
            stretch=1,
        )

        self.setCentralWidget(
            central_widget
        )

        self._create_pages()
        self._apply_stylesheet()

    # ==================================================
    # Sidebar
    # ==================================================

    def _create_sidebar(
        self,
    ) -> QWidget:
        """Erstellt die linke Navigation."""

        sidebar = QFrame(
            self
        )

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            230
        )

        sidebar_layout = QVBoxLayout(
            sidebar
        )

        sidebar_layout.setContentsMargins(
            16,
            20,
            16,
            20,
        )

        sidebar_layout.setSpacing(
            16
        )

        # --------------------------------------------------
        # App-Titel
        # --------------------------------------------------

        self.sidebar_title_label = QLabel(
            sidebar
        )

        self.sidebar_title_label.setObjectName(
            "appTitle"
        )

        self.sidebar_subtitle_label = QLabel(
            sidebar
        )

        self.sidebar_subtitle_label.setObjectName(
            "appSubtitle"
        )

        sidebar_layout.addWidget(
            self.sidebar_title_label
        )

        sidebar_layout.addWidget(
            self.sidebar_subtitle_label
        )

        # --------------------------------------------------
        # Navigation
        # --------------------------------------------------

        self.navigation_list.setObjectName(
            "navigationList"
        )

        self.navigation_list.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.navigation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.navigation_list.setSpacing(
            4
        )

        for _translation_key in (
            self.NAVIGATION_TRANSLATION_KEYS
        ):
            item = QListWidgetItem()

            item.setSizeHint(
                item.sizeHint().expandedTo(
                    self.navigation_list.sizeHint()
                )
            )

            self.navigation_list.addItem(
                item
            )

        sidebar_layout.addWidget(
            self.navigation_list
        )

        sidebar_layout.addStretch()

        # --------------------------------------------------
        # Version
        # --------------------------------------------------

        self.version_label = QLabel(
            sidebar
        )

        self.version_label.setObjectName(
            "versionLabel"
        )

        sidebar_layout.addWidget(
            self.version_label
        )

        return sidebar

    # ==================================================
    # Seiten
    # ==================================================

    def _create_pages(
        self,
    ) -> None:
        """Erstellt die Seiten des Managers."""

        # --------------------------------------------------
        # Bibliothek
        # --------------------------------------------------

        self.library_page = (
            LibraryPage(
                config=self.config
            )
        )

        self.page_stack.addWidget(
            self.library_page
        )

        # --------------------------------------------------
        # Profile
        # --------------------------------------------------

        (
            profiles_page,
            self.profiles_title_label,
            self.profiles_description_label,
        ) = self._create_placeholder_page()

        self.page_stack.addWidget(
            profiles_page
        )

        # --------------------------------------------------
        # Konflikte
        # --------------------------------------------------

        (
            conflicts_page,
            self.conflicts_title_label,
            self.conflicts_description_label,
        ) = self._create_placeholder_page()

        self.page_stack.addWidget(
            conflicts_page
        )

        # --------------------------------------------------
        # Einstellungen
        # --------------------------------------------------

        self.settings_page = (
            SettingsPage(
                config=self.config
            )
        )

        self.settings_page.settings_saved.connect(
            self._on_settings_saved
        )

        self.page_stack.addWidget(
            self.settings_page
        )

    def _create_placeholder_page(
        self,
    ) -> tuple[
        QWidget,
        QLabel,
        QLabel,
    ]:
        """Erstellt eine einfache Platzhalterseite."""

        page = QWidget(
            self.page_stack
        )

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            40,
            36,
            40,
            36,
        )

        layout.setSpacing(
            12
        )

        title_label = QLabel(
            page
        )

        title_label.setObjectName(
            "pageTitle"
        )

        description_label = QLabel(
            page
        )

        description_label.setObjectName(
            "pageDescription"
        )

        description_label.setWordWrap(
            True
        )

        description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            description_label
        )

        layout.addStretch()

        return (
            page,
            title_label,
            description_label,
        )

    # ==================================================
    # Signale
    # ==================================================

    def _connect_signals(
        self,
    ) -> None:
        """Verbindet die Navigation mit dem Seitenbereich."""

        self.navigation_list.currentRowChanged.connect(
            self._change_page
        )

    # ==================================================
    # Navigation
    # ==================================================

    def _change_page(
        self,
        index: int,
    ) -> None:
        """Wechselt zur ausgewählten Seite."""

        if (
            0
            <= index
            < self.page_stack.count()
        ):
            self.page_stack.setCurrentIndex(
                index
            )

    # ==================================================
    # Übersetzung
    # ==================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        """
        Aktualisiert alle sichtbaren Texte des
        Hauptfensters.

        Navigation und aktuelle Seite werden dabei
        nicht neu aufgebaut.
        """

        # --------------------------------------------------
        # Fenstertitel
        # --------------------------------------------------

        self.setWindowTitle(
            tr(
                "main.window_title"
            )
        )

        # --------------------------------------------------
        # Sidebar
        # --------------------------------------------------

        if (
            self.sidebar_title_label
            is not None
        ):
            self.sidebar_title_label.setText(
                tr(
                    "main.sidebar.title"
                )
            )

        if (
            self.sidebar_subtitle_label
            is not None
        ):
            self.sidebar_subtitle_label.setText(
                tr(
                    "main.sidebar.subtitle"
                )
            )

        if (
            self.version_label
            is not None
        ):
            self.version_label.setText(
                tr(
                    "main.sidebar.version",
                    version=APP_VERSION,
                )
            )

        # --------------------------------------------------
        # Navigation
        #
        # Nur Text ändern.
        # Nicht löschen oder neu aufbauen, damit der
        # aktuelle Navigationsindex erhalten bleibt.
        # --------------------------------------------------

        for index, translation_key in enumerate(
            self.NAVIGATION_TRANSLATION_KEYS
        ):
            item = (
                self.navigation_list.item(
                    index
                )
            )

            if item is None:
                continue

            item.setText(
                tr(
                    translation_key
                )
            )

        # --------------------------------------------------
        # Profile-Platzhalter
        # --------------------------------------------------

        if (
            self.profiles_title_label
            is not None
        ):
            self.profiles_title_label.setText(
                tr(
                    "main.page."
                    "profiles.title"
                )
            )

        if (
            self.profiles_description_label
            is not None
        ):
            self.profiles_description_label.setText(
                tr(
                    "main.page."
                    "profiles.description"
                )
            )

        # --------------------------------------------------
        # Konflikt-Platzhalter
        # --------------------------------------------------

        if (
            self.conflicts_title_label
            is not None
        ):
            self.conflicts_title_label.setText(
                tr(
                    "main.page."
                    "conflicts.title"
                )
            )

        if (
            self.conflicts_description_label
            is not None
        ):
            self.conflicts_description_label.setText(
                tr(
                    "main.page."
                    "conflicts.description"
                )
            )

        # --------------------------------------------------
        # Statusbar
        # --------------------------------------------------

        self._show_active_profile()

    def _show_active_profile(
        self,
    ) -> None:
        self.statusBar().showMessage(
            tr(
                "main.status.active_profile",
                profile=(
                    self.config.selected_profile
                ),
            )
        )

    # ==================================================
    # Stylesheet
    # ==================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        """Wendet das dunkle Hauptfenster-Design an."""

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

    # ==================================================
    # Einstellungen gespeichert
    # ==================================================

    def _on_settings_saved(
        self,
        message: str,
    ) -> None:
        """
        Aktualisiert die Oberfläche nach dem
        Speichern der Einstellungen.
        """

        self.statusBar().showMessage(
            message,
            5000,
        )

        # scan_mods() kümmert sich selbst darum,
        # einen bereits laufenden Scan kontrolliert
        # neu zu starten.
        self.library_page.scan_mods()

    # ==================================================
    # Beenden
    # ==================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Speichert die Fenstergröße vor dem Beenden."""

        self.library_page.cancel_scan()
        self.library_page.cancel_import()
        self.library_page.cancel_bulk_action()

        self.config.window_width = (
            self.width()
        )

        self.config.window_height = (
            self.height()
        )

        try:
            self.config.save()

            logger.info(
                "Fenstergröße gespeichert: %sx%s",
                self.config.window_width,
                self.config.window_height,
            )

        except OSError as error:
            logger.exception(
                (
                    "Konfiguration konnte beim Beenden "
                    "nicht gespeichert werden: %s"
                ),
                error,
            )

        event.accept()