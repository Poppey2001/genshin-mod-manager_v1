from __future__ import annotations

import logging

from pathlib import Path

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

from app.config import (
    AppConfig,
)

from app.controllers.game_controller import (
    GameController,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.pages.gamebanana_page import (
    GameBananaPage,
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

from app.version import (
    APP_VERSION_DISPLAY,
)

from app.widgets.game_selector import (
    GameSelectorWidget,
)


logger = logging.getLogger(
    __name__
)


class MainWindow(
    QMainWindow
):
    """
    Hauptfenster des XXMI Mod Managers.

    Zuständig für:

    - globale Navigation
    - globale Spielauswahl
    - Seitenverwaltung
    - Runtime-i18n
    - GameBanana -> Library Import
    - kontrolliertes Beenden
    """

    # ========================================================
    # Seiten
    # ========================================================

    PAGE_LIBRARY = 0
    PAGE_GAMEBANANA = 1
    PAGE_PROFILES = 2
    PAGE_CONFLICTS = 3
    PAGE_SETTINGS = 4

    # ========================================================
    # Navigation
    #
    # Der sichtbare Text wird vollständig über i18n geladen.
    #
    # Die Page-ID wird separat im QListWidgetItem gespeichert.
    # Dadurch hängt die Seitenzuordnung nicht direkt von der
    # sichtbaren Position des Navigationseintrags ab.
    # ========================================================

    NAVIGATION_ITEMS = (
        (
            "navigation.library",
            PAGE_LIBRARY,
        ),
        (
            "navigation.gamebanana",
            PAGE_GAMEBANANA,
        ),
        (
            "navigation.profiles",
            PAGE_PROFILES,
        ),
        (
            "navigation.conflicts",
            PAGE_CONFLICTS,
        ),
        (
            "navigation.settings",
            PAGE_SETTINGS,
        ),
    )

    NAVIGATION_PAGE_ROLE = int(
        Qt.ItemDataRole.UserRole
    )

    NAVIGATION_TRANSLATION_ROLE = (
        int(
            Qt.ItemDataRole.UserRole
        )
        + 1
    )

    # ========================================================
    # Initialisierung
    # ========================================================

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config

        # --------------------------------------------------
        # Globaler Game Controller
        # --------------------------------------------------

        self.game_controller = (
            GameController(
                config=self.config,
                parent=self,
            )
        )

        # --------------------------------------------------
        # Fenster
        # --------------------------------------------------

        self.setMinimumSize(
            1000,
            620,
        )

        self.resize(
            self.config.window_width,
            self.config.window_height,
        )

        # --------------------------------------------------
        # Hauptwidgets
        # --------------------------------------------------

        self.navigation_list = (
            QListWidget(
                self
            )
        )

        self.page_stack = (
            QStackedWidget(
                self
            )
        )

        # --------------------------------------------------
        # Sidebar
        # --------------------------------------------------

        self.sidebar_title_label: (
            QLabel
            | None
        ) = None

        self.sidebar_subtitle_label: (
            QLabel
            | None
        ) = None

        self.version_label: (
            QLabel
            | None
        ) = None

        self.game_selector: (
            GameSelectorWidget
            | None
        ) = None

        # --------------------------------------------------
        # Platzhalterseiten
        # --------------------------------------------------

        self.profiles_title_label: (
            QLabel
            | None
        ) = None

        self.profiles_description_label: (
            QLabel
            | None
        ) = None

        self.conflicts_title_label: (
            QLabel
            | None
        ) = None

        self.conflicts_description_label: (
            QLabel
            | None
        ) = None

        # --------------------------------------------------
        # UI
        # --------------------------------------------------

        self._build_ui()

        self._connect_signals()

        # --------------------------------------------------
        # Game-Wechsel darf nur stattfinden,
        # wenn alle relevanten Seiten bereit sind.
        # --------------------------------------------------

        self.game_controller.set_change_guard(
            self._can_change_game
        )

        # --------------------------------------------------
        # Runtime-i18n
        # --------------------------------------------------

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        # --------------------------------------------------
        # Startseite
        # --------------------------------------------------

        self._navigate_to_page(
            self.PAGE_LIBRARY
        )

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        """
        Erstellt die Grundstruktur des Hauptfensters.
        """

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

    # ========================================================
    # Sidebar
    # ========================================================

    def _create_sidebar(
        self,
    ) -> QWidget:
        """
        Erstellt die Sidebar mit:

        - App-Titel
        - Spielauswahl
        - Navigation
        - Version
        """

        sidebar = QFrame(
            self
        )

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            250
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
            14
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
        # Game Selector
        # --------------------------------------------------

        self.game_selector = (
            GameSelectorWidget(
                selected_game=(
                    self.config.selected_game
                ),
                parent=sidebar,
            )
        )

        sidebar_layout.addWidget(
            self.game_selector
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

        for (
            translation_key,
            page_index,
        ) in self.NAVIGATION_ITEMS:
            item = QListWidgetItem()

            item.setData(
                self.NAVIGATION_PAGE_ROLE,
                page_index,
            )

            item.setData(
                self.NAVIGATION_TRANSLATION_ROLE,
                translation_key,
            )

            item.setSizeHint(
                item.sizeHint().expandedTo(
                    self.navigation_list
                    .sizeHint()
                )
            )

            self.navigation_list.addItem(
                item
            )

        sidebar_layout.addWidget(
            self.navigation_list,
            stretch=1,
        )

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

    # ========================================================
    # Seiten
    # ========================================================

    def _create_pages(
        self,
    ) -> None:
        """
        Erstellt alle Seiten in derselben Reihenfolge
        wie die PAGE_* Konstanten.
        """

        # --------------------------------------------------
        # 0 - Library
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
        # 1 - GameBanana
        # --------------------------------------------------

        self.gamebanana_page = (
            GameBananaPage(
                config=self.config,
                parent=self,
            )
        )

        self.gamebanana_page.install_requested.connect(
            self._install_gamebanana_download
        )

        self.page_stack.addWidget(
            self.gamebanana_page
        )

        # --------------------------------------------------
        # 2 - Profile
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
        # 3 - Konflikte
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
        # 4 - Einstellungen
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

    # ========================================================
    # Platzhalter
    # ========================================================

    def _create_placeholder_page(
        self,
    ) -> tuple[
        QWidget,
        QLabel,
        QLabel,
    ]:
        """
        Erstellt eine einfache Platzhalterseite.
        """

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

        layout.addStretch(
            1
        )

        return (
            page,
            title_label,
            description_label,
        )

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        """
        Verbindet Navigation und globale Game-Auswahl.
        """

        self.navigation_list.currentItemChanged.connect(
            self._on_navigation_changed
        )

        if self.game_selector is not None:
            (
                self.game_selector
                .game_change_requested
                .connect(
                    self._request_game_change
                )
            )

        self.game_controller.game_changed.connect(
            self._on_game_changed
        )

    # ========================================================
    # Navigation
    # ========================================================

    def _on_navigation_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """
        Öffnet die zum Navigationseintrag gehörende Seite.
        """

        if current is None:
            return

        page_index = current.data(
            self.NAVIGATION_PAGE_ROLE
        )

        if not isinstance(
            page_index,
            int,
        ):
            return

        if not (
            0
            <= page_index
            < self.page_stack.count()
        ):
            return

        self.page_stack.setCurrentIndex(
            page_index
        )

    def _navigate_to_page(
        self,
        page_index: int,
    ) -> bool:
        """
        Navigiert anhand der logischen Page-ID.

        Dadurch müssen andere Komponenten nicht wissen,
        in welcher sichtbaren Sidebar-Zeile sich eine
        Seite befindet.
        """

        for row in range(
            self.navigation_list.count()
        ):
            item = (
                self.navigation_list
                .item(
                    row
                )
            )

            if item is None:
                continue

            item_page_index = item.data(
                self.NAVIGATION_PAGE_ROLE
            )

            if (
                item_page_index
                != page_index
            ):
                continue

            self.navigation_list.setCurrentItem(
                item
            )

            return True

        return False

    # ========================================================
    # Game-Wechsel
    # ========================================================

    def _can_change_game(
        self,
    ) -> bool:
        """
        Ein globaler Game-Wechsel darf nur stattfinden,
        wenn keine laufende Operation an das aktuelle
        Spiel gebunden ist.
        """

        return (
            self.library_page.can_change_game()
            and self.gamebanana_page.can_change_game()
        )

    def _request_game_change(
        self,
        game_id: str,
    ) -> None:
        """
        Wird vom GameSelector ausgelöst.
        """

        changed = (
            self.game_controller
            .request_game_change(
                game_id
            )
        )

        if changed:
            return

        # --------------------------------------------------
        # ComboBox auf das tatsächlich aktive Spiel
        # zurücksetzen.
        # --------------------------------------------------

        if self.game_selector is not None:
            self.game_selector.set_current_game(
                self.config.selected_game
            )

        QMessageBox.information(
            self,
            tr(
                "game.change.blocked.title"
            ),
            tr(
                "game.change.blocked.message"
            ),
        )

    def _on_game_changed(
        self,
        game_id: str,
    ) -> None:
        """
        Verteilt den globalen Game-Wechsel an alle
        game-abhängigen Seiten.
        """

        game = (
            self.config.current_game
        )

        # --------------------------------------------------
        # Game Selector synchron halten
        # --------------------------------------------------

        if self.game_selector is not None:
            self.game_selector.set_current_game(
                game_id
            )

        # --------------------------------------------------
        # Library
        # --------------------------------------------------

        self.library_page.on_game_changed(
            game_id
        )

        # --------------------------------------------------
        # GameBanana
        # --------------------------------------------------

        self.gamebanana_page.on_game_changed(
            game_id
        )

        # --------------------------------------------------
        # Settings
        # --------------------------------------------------

        if hasattr(
            self.settings_page,
            "on_game_changed",
        ):
            self.settings_page.on_game_changed(
                game_id
            )

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        self.statusBar().showMessage(
            tr(
                "game.status.changed",
                game=game.name,
            ),
            5000,
        )

    # ========================================================
    # GameBanana -> Library
    # ========================================================

    def _install_gamebanana_download(
        self,
        downloaded_path,
        game_id: str,
    ) -> None:
        """
        Übergibt einen fertigen GameBanana-Download
        an den bestehenden Library-Importer.
        """

        path = Path(
            downloaded_path
        ).expanduser()

        # --------------------------------------------------
        # Sicherheitsprüfung:
        # Download und aktuelle Spielauswahl müssen
        # weiterhin zusammenpassen.
        # --------------------------------------------------

        if (
            game_id
            != self.config.selected_game
        ):
            QMessageBox.warning(
                self,
                tr(
                    "gamebanana.error."
                    "game_changed.title"
                ),
                tr(
                    "gamebanana.error."
                    "game_changed.message"
                ),
            )

            return

        if not path.is_file():
            QMessageBox.warning(
                self,
                tr(
                    "gamebanana.error."
                    "download.title"
                ),
                tr(
                    "gamebanana.error."
                    "download.missing"
                ),
            )

            return

        # --------------------------------------------------
        # Zur Bibliothek wechseln
        # --------------------------------------------------

        self._navigate_to_page(
            self.PAGE_LIBRARY
        )

        # --------------------------------------------------
        # Vorhandenen Importpfad benutzen.
        # --------------------------------------------------

        self.library_page.request_external_import(
            [
                path
            ]
        )

    # ========================================================
    # Spiel / Launcher starten
    # ========================================================

    def launch_game(
        self,
    ) -> None:
        """
        Startet den aktuell konfigurierten Launcher
        des ausgewählten Spiels.
        """

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

    # ========================================================
    # Übersetzung
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        """
        Aktualisiert alle Texte des MainWindow.

        Widgets und Navigation werden dabei nicht
        neu erstellt. Dadurch bleiben Auswahl und
        Seitenzustand erhalten.
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
                    version=(
                        APP_VERSION_DISPLAY
                    ),
                )
            )

        # --------------------------------------------------
        # Navigation
        # --------------------------------------------------

        self._retranslate_navigation()

        # --------------------------------------------------
        # Profile
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
        # Konflikte
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
        # Status
        # --------------------------------------------------

        self._show_active_profile()

    def _retranslate_navigation(
        self,
    ) -> None:
        """
        Übersetzt vorhandene Navigationseinträge.

        Translation-Key wird direkt im Item gespeichert.
        Dadurch muss die Reihenfolge hier nicht noch einmal
        dupliziert werden.
        """

        for row in range(
            self.navigation_list.count()
        ):
            item = (
                self.navigation_list
                .item(
                    row
                )
            )

            if item is None:
                continue

            translation_key = item.data(
                self.NAVIGATION_TRANSLATION_ROLE
            )

            if not isinstance(
                translation_key,
                str,
            ):
                continue

            item.setText(
                tr(
                    translation_key
                )
            )

    # ========================================================
    # Statusbar
    # ========================================================

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

    # ========================================================
    # Settings
    # ========================================================

    def _on_settings_saved(
        self,
        message: str,
    ) -> None:
        """
        Aktualisiert die Anwendung nach dem
        Speichern der Einstellungen.
        """

        self.statusBar().showMessage(
            message,
            5000,
        )

        # --------------------------------------------------
        # Library erneut prüfen.
        #
        # scan_mods() kümmert sich selbst um einen
        # möglicherweise bereits laufenden Scan.
        # --------------------------------------------------

        self.library_page.scan_mods()

    # ========================================================
    # Stylesheet
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        """
        Vorläufiges Hauptfenster-Design.

        Die vollständige neue XXMI-Oberfläche wird
        nach Abschluss der Funktionsentwicklung gebaut.
        """

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

            /* ============================================
             * Sidebar
             * ============================================ */

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
                font-size: 15px;
                color: #9ca3af;
                margin-bottom: 4px;
            }

            QLabel#versionLabel {
                color: #737987;
                font-size: 12px;
                padding-top: 6px;
            }

            /* ============================================
             * Game Selector
             * ============================================ */

            QFrame#gameSelector {
                background-color: #292c34;
                border: 1px solid #353943;
                border-radius: 8px;
            }

            QComboBox#gameSelectorCombo {
                background-color: #20232a;
                border: 1px solid #3a3f49;
                border-radius: 6px;
                padding: 7px 9px;
                color: #ffffff;
            }

            QComboBox#gameSelectorCombo:hover {
                border-color: #7c5cff;
            }

            QComboBox#gameSelectorCombo:focus {
                border-color: #7c5cff;
            }

            QLabel#gameImporterLabel {
                color: #8d94a3;
                font-size: 11px;
            }

            /* ============================================
             * Navigation
             * ============================================ */

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

            /* ============================================
             * Seiten
             * ============================================ */

            QLabel#pageTitle {
                font-size: 28px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#pageSubtitle {
                color: #9ca3af;
                font-size: 14px;
            }

            QLabel#pageDescription {
                color: #a8adb7;
                font-size: 15px;
            }

            /* ============================================
             * GameBanana
             * ============================================ */

            QFrame#gameBananaModCard {
                background-color: #252830;
                border: 1px solid #363a45;
                border-radius: 10px;
            }

            QLabel#gameBananaModTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }

            /* ============================================
             * Statusbar
             * ============================================ */

            QStatusBar {
                background-color: #20232a;
                color: #a8adb7;
                border-top: 1px solid #30343d;
            }
            """
        )

    # ========================================================
    # Beenden
    # ========================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        Stoppt laufende Tasks und speichert
        die Fenstergröße.
        """

        # --------------------------------------------------
        # GameBanana
        # --------------------------------------------------

        if hasattr(
            self,
            "gamebanana_page",
        ):
            self.gamebanana_page.shutdown()

        # --------------------------------------------------
        # Library
        # --------------------------------------------------

        if hasattr(
            self,
            "library_page",
        ):
            self.library_page.cancel_scan()

            self.library_page.cancel_import()

            self.library_page.cancel_bulk_action()

        # --------------------------------------------------
        # Updater
        #
        # Falls dein UpdateController bereits eingebunden
        # wurde, sauber herunterfahren.
        # --------------------------------------------------

        if hasattr(
            self,
            "update_controller",
        ):
            shutdown = getattr(
                self.update_controller,
                "shutdown",
                None,
            )

            if callable(
                shutdown
            ):
                shutdown()

        # --------------------------------------------------
        # Fenstergröße
        # --------------------------------------------------

        self.config.window_width = (
            self.width()
        )

        self.config.window_height = (
            self.height()
        )

        try:
            self.config.save()

            logger.info(
                (
                    "Fenstergröße gespeichert: "
                    "%sx%s"
                ),
                self.config.window_width,
                self.config.window_height,
            )

        except OSError as error:
            logger.exception(
                (
                    "Konfiguration konnte beim "
                    "Beenden nicht gespeichert "
                    "werden: %s"
                ),
                error,
            )

        event.accept()