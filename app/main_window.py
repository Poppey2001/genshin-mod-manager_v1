from __future__ import annotations

import logging

from pathlib import Path

from PySide6.QtGui import (
    QCloseEvent,
)

from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
)

from app.config import (
    AppConfig,
)

from app.controllers.game_controller import (
    GameController,
)

from app.dialogs.settings_dialog import (
    SettingsDialog,
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

from app.platform_support import (
    PlatformSupportError,
    launch_program,
)

from app.ui.main_window_ui import (
    MainWindowUI,
    create_placeholder_page,
)


logger = logging.getLogger(
    __name__
)


class MainWindow(
    QMainWindow
):
    """
    Hauptfenster.

    Diese Klasse enthält nur noch
    Anwendungslogik und verbindet die
    einzelnen UI-Komponenten.
    """

    PAGE_INDEX = {
        MainWindowUI.PAGE_LIBRARY: 0,
        MainWindowUI.PAGE_GAMEBANANA: 1,
        MainWindowUI.PAGE_PROFILES: 2,
        MainWindowUI.PAGE_CONFLICTS: 3,
    }

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        self.setMinimumSize(
            1100,
            650,
        )

        self.resize(
            self.config.window_width,
            self.config.window_height,
        )

        # ----------------------------------------------------
        # Game Controller
        # ----------------------------------------------------

        self.game_controller = (
            GameController(
                config=self.config,
                parent=self,
            )
        )

        # ----------------------------------------------------
        # Reine UI
        # ----------------------------------------------------

        self.ui = (
            MainWindowUI(
                config=self.config,
                parent=self,
            )
        )

        self.setCentralWidget(
            self.ui
        )

        # ----------------------------------------------------
        # Pages
        # ----------------------------------------------------

        self._create_pages()

        # ----------------------------------------------------
        # Settings Dialog
        # ----------------------------------------------------

        self.settings_dialog = (
            SettingsDialog(
                config=self.config,
                parent=self,
            )
        )

        # Erst nach dem Erstellen der Pages,
        # da der Guard auf deren Status zugreift.
        self.game_controller.set_change_guard(
            self._can_change_game
        )

        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self._switch_page(
            MainWindowUI.PAGE_LIBRARY
        )

        self._on_game_changed(
            self.config.selected_game
        )

        self._refresh_conflict_badge()

    # ========================================================
    # Pages
    # ========================================================

    def _create_pages(
        self,
    ) -> None:
        self.library_page = (
            LibraryPage(
                config=self.config
            )
        )

        self.gamebanana_page = (
            GameBananaPage(
                config=self.config
            )
        )

        self.profiles_page = (
            create_placeholder_page(
                title="Profile",
                description=(
                    "Hier werden später spielbezogene "
                    "Mod-Profile verwaltet."
                ),
            )
        )

        self.conflicts_page = (
            create_placeholder_page(
                title="Konflikte",
                description=(
                    "Hier werden alle Konflikte des "
                    "aktuell ausgewählten Spiels angezeigt."
                ),
            )
        )

        self.ui.page_stack.addWidget(
            self.library_page
        )

        self.ui.page_stack.addWidget(
            self.gamebanana_page
        )

        self.ui.page_stack.addWidget(
            self.profiles_page
        )

        self.ui.page_stack.addWidget(
            self.conflicts_page
        )

    # ========================================================
    # Signals
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        # ----------------------------------------------------
        # Main UI
        # ----------------------------------------------------

        self.ui.game_selected.connect(
            self._request_game_change
        )

        self.ui.page_selected.connect(
            self._switch_page
        )

        self.ui.settings_requested.connect(
            self._open_settings
        )

        # ----------------------------------------------------
        # Game Controller
        # ----------------------------------------------------

        self.game_controller.game_changed.connect(
            self._on_game_changed
        )

        self.game_controller.game_change_blocked.connect(
            self._on_game_change_blocked
        )

        # ----------------------------------------------------
        # GameBanana -> Library Import
        # ----------------------------------------------------

        self.gamebanana_page.install_requested.connect(
            self._install_gamebanana_download
        )

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        self.settings_dialog.settings_saved.connect(
            self._on_settings_saved
        )

        # ----------------------------------------------------
        # Conflict Badge
        # ----------------------------------------------------

        scan_controller = getattr(
            self.library_page,
            "scan_controller",
            None,
        )

        if scan_controller is not None:
            scan_controller.finished.connect(
                self._refresh_conflict_badge
            )

        import_controller = getattr(
            self.library_page,
            "import_controller",
            None,
        )

        if import_controller is not None:
            import_controller.finished.connect(
                self._refresh_conflict_badge
            )

        bulk_controller = getattr(
            self.library_page,
            "bulk_controller",
            None,
        )

        if bulk_controller is not None:
            bulk_controller.finished.connect(
                self._refresh_conflict_badge
            )

    # ========================================================
    # Navigation
    # ========================================================

    def _switch_page(
        self,
        page_id: str,
    ) -> None:
        index = (
            self.PAGE_INDEX.get(
                page_id
            )
        )

        if index is None:
            return

        self.ui.page_stack.setCurrentIndex(
            index
        )

        self.ui.set_active_page(
            page_id
        )

        # GameBanana kann beim Anzeigen
        # automatisch seine aktuelle Liste laden.
        if (
            page_id
            == MainWindowUI.PAGE_GAMEBANANA
        ):
            self.gamebanana_page.update()

    # ========================================================
    # Game Change
    # ========================================================

    def _request_game_change(
        self,
        game_id: str,
    ) -> None:
        changed = (
            self.game_controller
            .request_game_change(
                game_id
            )
        )

        if not changed:
            self.ui.set_active_game(
                self.config.selected_game
            )

    def _can_change_game(
        self,
    ) -> bool:
        library_handler = getattr(
            self.library_page,
            "can_change_game",
            None,
        )

        if (
            callable(
                library_handler
            )
            and not library_handler()
        ):
            return False

        gamebanana_handler = getattr(
            self.gamebanana_page,
            "can_change_game",
            None,
        )

        if (
            callable(
                gamebanana_handler
            )
            and not gamebanana_handler()
        ):
            return False

        return True

    def _on_game_change_blocked(
        self,
        _game_id: str,
    ) -> None:
        self.ui.set_active_game(
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
        self.ui.set_active_game(
            game_id
        )

        # ----------------------------------------------------
        # Library
        # ----------------------------------------------------

        library_handler = getattr(
            self.library_page,
            "on_game_changed",
            None,
        )

        if callable(
            library_handler
        ):
            library_handler(
                game_id
            )

        # ----------------------------------------------------
        # GameBanana
        # ----------------------------------------------------

        gamebanana_handler = getattr(
            self.gamebanana_page,
            "on_game_changed",
            None,
        )

        if callable(
            gamebanana_handler
        ):
            gamebanana_handler(
                game_id
            )

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        self.settings_dialog.on_game_changed(
            game_id
        )

        self.statusBar().showMessage(
            tr(
                "game.status.changed",
                game=(
                    self.config
                    .current_game
                    .name
                ),
            ),
            4000,
        )

        self._refresh_conflict_badge()

    # ========================================================
    # Conflict Badge
    # ========================================================

    def _refresh_conflict_badge(
        self,
        *_args,
    ) -> None:
        try:
            stats = (
                self.library_page
                .mod_list_widget
                .statistics()
            )

            count = int(
                stats.conflicts
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ):
            count = 0

        self.ui.set_conflict_count(
            count
        )

    # ========================================================
    # Settings
    # ========================================================

    def _open_settings(
        self,
    ) -> None:
        self.settings_dialog.on_game_changed(
            self.config.selected_game
        )

        self.settings_dialog.open_game_settings()

    def _on_settings_saved(
        self,
        message: str,
    ) -> None:
        self.statusBar().showMessage(
            message,
            5000,
        )

        scan_method = getattr(
            self.library_page,
            "scan_mods",
            None,
        )

        if callable(
            scan_method
        ):
            scan_method()

    # ========================================================
    # GameBanana Download -> Import
    # ========================================================

    def _install_gamebanana_download(
        self,
        path,
        game_id: str,
        mod_id: int,
    ) -> None:
        download_path = (
            Path(
                path
            )
            .expanduser()
        )

        # ----------------------------------------------------
        # Download gehört nicht mehr zum aktuellen Spiel
        # ----------------------------------------------------

        if (
            game_id
            != self.config.selected_game
        ):
            QMessageBox.warning(
                self,
                "GameBanana",
                (
                    "Das aktive Spiel wurde seit dem "
                    "Download geändert. Der Mod wird "
                    "nicht automatisch importiert."
                ),
            )

            return

        if not download_path.is_file():
            QMessageBox.warning(
                self,
                "GameBanana",
                (
                    "Die heruntergeladene Datei "
                    "existiert nicht mehr."
                    "\n\n"
                    f"{download_path}"
                ),
            )

            return

        self._switch_page(
            MainWindowUI.PAGE_LIBRARY
        )

        importer = getattr(
            self.library_page,
            "request_external_import",
            None,
        )

        if callable(
            importer
        ):
            importer = getattr(
                self.library_page,
                "request_gamebanana_import",
                None,
            )

            if callable(
                importer
            ):
                importer(
                    path=download_path,
                    game_id=game_id,
                    mod_id=mod_id,
                )

                return

            # Nur noch als Fallback.
            fallback = getattr(
                self.library_page,
                "request_external_import",
                None,
            )

            if callable(
                fallback
            ):
                fallback(
                    [
                        download_path
                    ]
                )

            return

        # Fallback für ältere LibraryPage.
        fallback = getattr(
            self.library_page,
            "_request_import",
            None,
        )

        if callable(
            fallback
        ):
            fallback(
                [
                    download_path
                ]
            )

    # ========================================================
    # Launcher
    # ========================================================

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
                    "main.launcher.missing.title"
                ),
                tr(
                    "main.launcher.missing.message"
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
                    "main.launcher.start_failed.title"
                ),
                str(
                    error
                ),
            )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.setWindowTitle(
            tr(
                "main.window_title"
            )
        )

    # ========================================================
    # Close
    # ========================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        cancel_scan = getattr(
            self.library_page,
            "cancel_scan",
            None,
        )

        if callable(
            cancel_scan
        ):
            cancel_scan()

        cancel_import = getattr(
            self.library_page,
            "cancel_import",
            None,
        )

        if callable(
            cancel_import
        ):
            cancel_import()

        cancel_bulk = getattr(
            self.library_page,
            "cancel_bulk_action",
            None,
        )

        if callable(
            cancel_bulk
        ):
            cancel_bulk()

        shutdown_gamebanana = getattr(
            self.gamebanana_page,
            "shutdown",
            None,
        )

        if callable(
            shutdown_gamebanana
        ):
            shutdown_gamebanana()

        self.config.window_width = (
            self.width()
        )

        self.config.window_height = (
            self.height()
        )

        try:
            self.config.save()

        except OSError:
            logger.exception(
                (
                    "Konfiguration konnte beim "
                    "Beenden nicht gespeichert werden."
                )
            )

        event.accept()