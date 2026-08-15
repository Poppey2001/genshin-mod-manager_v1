from __future__ import annotations

import logging
from app.controllers.update_controller import (
    UpdateController,
)

from app.widgets.settings.update_settings_group import (
    UpdateSettingsGroup,
)
from pathlib import Path

from PySide6.QtCore import (
    QUrl,
)

from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
)

from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.dialogs.settings_dialog import (
    SettingsDialog,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.pages.conflicts_page import (
    ConflictsPage,
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
)

from app.version import (
    APP_NAME,
    APP_VERSION_DISPLAY,
)


logger = logging.getLogger(
    __name__
)


class MainWindow(
    QMainWindow
):
    """
    Hauptfenster des XXMI Mod Managers.

    MainWindowUI:
        reine sichtbare Oberfläche

    MainWindow:
        Navigation
        Game-Wechsel
        Seiten
        Settings
        Konflikte
        GameBanana -> Library
        Lifecycle
    """

    # ========================================================
    # Init
    # ========================================================

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        super().__init__()

        self.config = config
        self.update_controller: (
            UpdateController
            | None
        ) = None
        self._settings_dialog: (
            SettingsDialog
            | None
        ) = None

        # ====================================================
        # Fenster
        # ====================================================

        self.setMinimumSize(
            1050,
            650,
        )

        self.resize(
            self.config.window_width,
            self.config.window_height,
        )

        # ====================================================
        # UI Shell
        # ====================================================

        self.ui = (
            MainWindowUI(
                config=self.config,
                parent=self,
            )
        )

        self.setCentralWidget(
            self.ui
        )

        # ====================================================
        # Workspace
        #
        # Der QStackedWidget wird ausschließlich
        # von MainWindowUI erzeugt.
        # ====================================================

        self.workspace_stack = (
            self.ui.page_stack
        )

        # ====================================================
        # Seiten
        # ====================================================

        self.library_page = (
            LibraryPage(
                config=self.config,
                parent=self,
            )
        )

        self.gamebanana_page = (
            GameBananaPage(
                config=self.config,
                parent=self,
            )
        )

        self.profiles_page = (
            self._create_profiles_page()
        )

        self.conflicts_page = (
            ConflictsPage(
                library_paths_provider=(
                    self.library_page
                    .library_mod_paths
                ),
                game_id_provider=(
                    self.library_page
                    .current_game_id
                ),
                active_root_provider=(
                    self.library_page
                    .active_mods_root
                ),
                parent=self,
            )
        )
        # ====================================================
        # Seiten in den sichtbaren Stack
        #
        # 0 = Library
        # 1 = GameBanana
        # 2 = Profiles
        # 3 = Conflicts
        # ====================================================

        self.workspace_stack.addWidget(
            self.library_page
        )

        self.workspace_stack.addWidget(
            self.gamebanana_page
        )

        self.workspace_stack.addWidget(
            self.profiles_page
        )

        self.workspace_stack.addWidget(
            self.conflicts_page
        )

        # ====================================================
        # Signale
        # ====================================================

        self._connect_signals()

        self._connect_ui_navigation()
        # ====================================================
        # Auto Updater
        # ====================================================

        self.update_controller = (
            UpdateController(
                config=self.config,
                parent_window=self,
            )
        )

        self.update_controller.start_auto_check()
        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        # ====================================================
        # Initialer Zustand
        # ====================================================

        self.ui.set_active_game(
            self.config.selected_game
        )

        self._show_library()

        self._set_conflict_count(
            0
        )

        self.retranslate_ui()

    # ========================================================
    # Interne Signale
    # ========================================================

    def _connect_signals(
        self,
    ) -> None:
        # ----------------------------------------------------
        # GameBanana -> Library
        #
        # Unterstützt aktuell sowohl:
        #
        # path, game_id
        #
        # als auch:
        #
        # path, game_id, mod_id
        # ----------------------------------------------------

        self.gamebanana_page.install_requested.connect(
            self._install_gamebanana_download
        )

        # ----------------------------------------------------
        # Library -> Conflict Badge
        # ----------------------------------------------------

        self.library_page.conflict_count_changed.connect(
            self._set_conflict_count
        )

        # ----------------------------------------------------
        # Library -> Konfliktseite
        # ----------------------------------------------------

        self.library_page.conflict_report_changed.connect(
            self.conflicts_page.set_report
        )

        # ----------------------------------------------------
        # Konfliktseite -> Library
        # ----------------------------------------------------

        self.conflicts_page.refresh_requested.connect(
            self.library_page.refresh_conflicts
        )

        self.conflicts_page.adopt_requested.connect(
            self.library_page.adopt_conflict
        )

        self.conflicts_page.open_requested.connect(
            self._open_conflict_path
        )
        
        self.conflicts_page.copy_to_library_requested.connect(
            self._copy_conflict_to_library
        )

        self.conflicts_page.rescan_requested.connect(
            self.library_page.scan_mods
        )

    # ========================================================
    # MainWindowUI Navigation
    # ========================================================

    def _connect_ui_navigation(
        self,
    ) -> None:
        """
        Verbindet exakt die drei Signale,
        die MainWindowUI bereitstellt.
        """

        # ----------------------------------------------------
        # Linke Game-Sidebar
        # ----------------------------------------------------

        self.ui.game_selected.connect(
            self._request_game_change
        )

        # ----------------------------------------------------
        # Obere Navigation
        # ----------------------------------------------------

        self.ui.page_selected.connect(
            self._on_page_selected
        )

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        self.ui.settings_requested.connect(
            self._open_settings
        )

    # ========================================================
    # Navigation Dispatcher
    # ========================================================

    def _on_page_selected(
        self,
        page_id: str,
    ) -> None:
        """
        Reagiert auf:

        library
        gamebanana
        profiles
        conflicts
        """

        if (
            page_id
            == self.ui.PAGE_LIBRARY
        ):
            self._show_library()

        elif (
            page_id
            == self.ui.PAGE_GAMEBANANA
        ):
            self._show_gamebanana()

        elif (
            page_id
            == self.ui.PAGE_PROFILES
        ):
            self._show_profiles()

        elif (
            page_id
            == self.ui.PAGE_CONFLICTS
        ):
            self._show_conflicts()

        else:
            logger.warning(
                (
                    "Unbekannte Workspace-Seite "
                    "angefordert: %s"
                ),
                page_id,
            )

    # ========================================================
    # Library
    # ========================================================

    def _show_library(
        self,
        *_args,
    ) -> None:
        self.workspace_stack.setCurrentWidget(
            self.library_page
        )

        self.ui.set_active_page(
            self.ui.PAGE_LIBRARY
        )

    # ========================================================
    # GameBanana
    # ========================================================

    def _show_gamebanana(
        self,
        *_args,
    ) -> None:
        self.workspace_stack.setCurrentWidget(
            self.gamebanana_page
        )

        self.ui.set_active_page(
            self.ui.PAGE_GAMEBANANA
        )

    # ========================================================
    # Profiles
    # ========================================================

    def _show_profiles(
        self,
        *_args,
    ) -> None:
        self.workspace_stack.setCurrentWidget(
            self.profiles_page
        )

        self.ui.set_active_page(
            self.ui.PAGE_PROFILES
        )

    # ========================================================
    # Conflicts
    # ========================================================

    def _show_conflicts(
        self,
        *_args,
    ) -> None:
        # ----------------------------------------------------
        # Vor dem Öffnen aktuell prüfen.
        # ----------------------------------------------------

        try:
            self.library_page.refresh_conflicts()

        except Exception:
            logger.exception(
                (
                    "Konflikte konnten vor dem Öffnen "
                    "der Konfliktseite nicht aktualisiert werden."
                )
            )

        self.workspace_stack.setCurrentWidget(
            self.conflicts_page
        )

        self.ui.set_active_page(
            self.ui.PAGE_CONFLICTS
        )

    # ========================================================
    # Game Change
    # ========================================================

    def _request_game_change(
        self,
        game_id: str,
        *_args,
    ) -> None:
        """
        Wechselt das aktive XXMI-Spiel.

        Ein Spielwechsel wird verhindert, wenn
        Library oder GameBanana aktuell beschäftigt sind.
        """

        game_id = str(
            game_id
        )

        old_game_id = (
            self.config.selected_game
        )

        # ----------------------------------------------------
        # Gleiches Spiel
        # ----------------------------------------------------

        if (
            game_id
            == old_game_id
        ):
            self.ui.set_active_game(
                old_game_id
            )

            return

        # ----------------------------------------------------
        # Library beschäftigt?
        # ----------------------------------------------------

        if not (
            self.library_page
            .can_change_game()
        ):
            self._show_game_change_blocked()

            self.ui.set_active_game(
                old_game_id
            )

            return

        # ----------------------------------------------------
        # GameBanana beschäftigt?
        # ----------------------------------------------------

        can_change_game = getattr(
            self.gamebanana_page,
            "can_change_game",
            None,
        )

        if (
            callable(
                can_change_game
            )
            and not can_change_game()
        ):
            self._show_game_change_blocked()

            self.ui.set_active_game(
                old_game_id
            )

            return

        # ====================================================
        # Config aktualisieren
        # ====================================================

        self.config.selected_game = (
            game_id
        )

        try:
            # ------------------------------------------------
            # Library
            # ------------------------------------------------

            self.library_page.on_game_changed(
                game_id
            )

            # ------------------------------------------------
            # GameBanana
            # ------------------------------------------------

            gamebanana_change = getattr(
                self.gamebanana_page,
                "on_game_changed",
                None,
            )

            if callable(
                gamebanana_change
            ):
                gamebanana_change(
                    game_id
                )

            # ------------------------------------------------
            # Profiles
            # ------------------------------------------------

            profile_change = getattr(
                self.profiles_page,
                "on_game_changed",
                None,
            )

            if callable(
                profile_change
            ):
                profile_change(
                    game_id
                )

            # ------------------------------------------------
            # Settings Dialog
            # ------------------------------------------------

            if (
                self._settings_dialog
                is not None
            ):
                settings_change = getattr(
                    self._settings_dialog,
                    "on_game_changed",
                    None,
                )

                if callable(
                    settings_change
                ):
                    settings_change(
                        game_id
                    )

            # ------------------------------------------------
            # Sidebar
            # ------------------------------------------------

            self.ui.set_active_game(
                game_id
            )

            # ------------------------------------------------
            # Speichern
            # ------------------------------------------------

            self.config.save()

        except Exception as error:
            # =================================================
            # Rollback
            # =================================================

            logger.exception(
                (
                    "Spielwechsel von %s nach %s "
                    "ist fehlgeschlagen."
                ),
                old_game_id,
                game_id,
            )

            self.config.selected_game = (
                old_game_id
            )

            self.ui.set_active_game(
                old_game_id
            )

            QMessageBox.critical(
                self,
                tr(
                    "game.change.failed.title"
                ),
                str(
                    error
                ),
            )

            return

        # ====================================================
        # Status
        # ====================================================

        game_name = (
            self._current_game_name()
        )

        self.statusBar().showMessage(
            tr(
                "game.status.changed",
                game=game_name,
            ),
            5000,
        )

    # ========================================================
    # Game Name
    # ========================================================

    def _current_game_name(
        self,
    ) -> str:
        current_game = getattr(
            self.config,
            "current_game",
            None,
        )

        if current_game is None:
            return (
                self.config.selected_game
            )

        name = getattr(
            current_game,
            "name",
            None,
        )

        if name:
            return str(
                name
            )

        return (
            self.config.selected_game
        )

    # ========================================================
    # Game Switch Blocked
    # ========================================================

    def _show_game_change_blocked(
        self,
    ) -> None:
        QMessageBox.information(
            self,
            tr(
                "game.change.blocked.title"
            ),
            tr(
                "game.change.blocked.message"
            ),
        )

    # ========================================================
    # Conflict Badge
    # ========================================================

    def _set_conflict_count(
        self,
        count: int,
    ) -> None:
        self.ui.set_conflict_count(
            max(
                0,
                int(
                    count
                ),
            )
        )

    # ========================================================
    # Conflict Folder öffnen
    # ========================================================

    def _open_conflict_path(
        self,
        conflict,
    ) -> None:
        try:
            path = (
                Path(
                    conflict.path
                )
                .expanduser()
                .absolute()
            )

        except (
            AttributeError,
            TypeError,
        ):
            return

        target = (
            path
            if path.is_dir()
            else path.parent
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(
                    target
                )
            )
        )

    # ========================================================
    # GameBanana -> Library
    # ========================================================

    def _install_gamebanana_download(
        self,
        path,
        game_id: str,
        mod_id: int | None = None,
    ) -> None:
        """
        Unterstützt beide derzeit möglichen
        GameBanana-Signalvarianten:

            install_requested(path, game_id)

        und:

            install_requested(path, game_id, mod_id)

        Sobald überall die neue 3-Argument-Signatur
        verwendet wird, kann der Fallback später weg.
        """

        download_path = (
            Path(
                path
            )
            .expanduser()
            .absolute()
        )

        # ----------------------------------------------------
        # Spiel wurde zwischenzeitlich gewechselt
        # ----------------------------------------------------

        if (
            game_id
            != self.config.selected_game
        ):
            QMessageBox.warning(
                self,
                tr(
                    "gamebanana.error.install.title"
                ),
                tr(
                    "gamebanana.error.install.game_changed"
                ),
            )

            return

        # ====================================================
        # Neue Variante mit GameBanana-ID
        # ====================================================

        if (
            mod_id is not None
            and int(
                mod_id
            ) > 0
        ):
            request = getattr(
                self.library_page,
                "request_gamebanana_import",
                None,
            )

            if callable(
                request
            ):
                started = request(
                    path=download_path,
                    game_id=game_id,
                    mod_id=int(
                        mod_id
                    ),
                )

                if started:
                    self._show_library()

                return

        # ====================================================
        # Legacy-Fallback
        #
        # Import funktioniert auch dann, wenn die
        # GameBananaPage die Mod-ID noch nicht mitsendet.
        # ====================================================

        request_external = getattr(
            self.library_page,
            "request_external_import",
            None,
        )

        if not callable(
            request_external
        ):
            QMessageBox.warning(
                self,
                "GameBanana",
                (
                    "Der Download wurde abgeschlossen, "
                    "konnte aber nicht an die Library "
                    "übergeben werden."
                ),
            )

            return

        started = request_external(
            [
                download_path
            ]
        )

        if started:
            self._show_library()

    # ========================================================
    # Settings
    # ========================================================

    def _open_settings(
        self,
        *_args,
    ) -> None:
        # ----------------------------------------------------
        # Bereits geöffnet
        # ----------------------------------------------------

        if (
            self._settings_dialog
            is not None
        ):
            try:
                self._settings_dialog.raise_()

                self._settings_dialog.activateWindow()

                return

            except RuntimeError:
                self._settings_dialog = None

        # ====================================================
        # Dialog erstellen
        # ====================================================

        self._settings_dialog = (
            SettingsDialog(
                config=self.config,
                parent=self,
            )
        )

        # ====================================================
        # Update Settings
        # ====================================================

        update_group = (
            self._settings_dialog
            .findChild(
                UpdateSettingsGroup
            )
        )

        if (
            update_group is not None
            and self.update_controller
            is not None
        ):
            update_group.check_requested.connect(
                self.update_controller
                .check_now
            )

        # ----------------------------------------------------
        # Aktuelles Spiel
        # ----------------------------------------------------

        game_change = getattr(
            self._settings_dialog,
            "on_game_changed",
            None,
        )

        if callable(
            game_change
        ):
            game_change(
                self.config.selected_game
            )

        # ----------------------------------------------------
        # Settings gespeichert
        # ----------------------------------------------------

        for signal_name in (
            "settings_saved",
            "saved",
        ):
            signal = getattr(
                self._settings_dialog,
                signal_name,
                None,
            )

            if signal is None:
                continue

            connect = getattr(
                signal,
                "connect",
                None,
            )

            if callable(
                connect
            ):
                connect(
                    self._on_settings_saved
                )

                break

        # ----------------------------------------------------
        # Dialog geschlossen / zerstört
        # ----------------------------------------------------

        self._settings_dialog.destroyed.connect(
            self._on_settings_dialog_destroyed
        )

        self._settings_dialog.show()

    # ========================================================
    # Settings gespeichert
    # ========================================================

    def _on_settings_saved(
        self,
        *_args,
    ) -> None:
        """
        Pfade oder globale Optionen könnten sich
        geändert haben.
        """

        # ----------------------------------------------------
        # Library neu scannen
        # ----------------------------------------------------

        self.library_page.scan_mods()

        # ----------------------------------------------------
        # GameBanana Context aktualisieren
        # ----------------------------------------------------

        gamebanana_change = getattr(
            self.gamebanana_page,
            "on_game_changed",
            None,
        )

        if callable(
            gamebanana_change
        ):
            gamebanana_change(
                self.config.selected_game
            )

        # ----------------------------------------------------
        # Konflikte neu prüfen
        # ----------------------------------------------------

        try:
            self.library_page.refresh_conflicts()

        except Exception:
            logger.exception(
                (
                    "Konflikte konnten nach dem "
                    "Speichern der Einstellungen "
                    "nicht aktualisiert werden."
                )
            )

        self.statusBar().showMessage(
            tr(
                "settings.status.saved"
            ),
            5000,
        )

    def _on_settings_dialog_destroyed(
        self,
        *_args,
    ) -> None:
        self._settings_dialog = None

    # ========================================================
    # Profiles Placeholder
    # ========================================================

    def _create_profiles_page(
        self,
    ) -> QWidget:
        page = QWidget(
            self
        )

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            32,
            28,
            32,
            28,
        )

        layout.setSpacing(
            10
        )

        self.profiles_title_label = (
            QLabel()
        )

        self.profiles_title_label.setObjectName(
            "pageTitle"
        )

        self.profiles_description_label = (
            QLabel()
        )

        self.profiles_description_label.setObjectName(
            "pageDescription"
        )

        self.profiles_description_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.profiles_title_label
        )

        layout.addWidget(
            self.profiles_description_label
        )

        layout.addStretch(
            1
        )

        return page

    # ========================================================
    # Launcher
    # ========================================================

    def launch_game(
        self,
    ) -> None:
        launcher_path = getattr(
            self.config,
            "launcher_path",
            None,
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
        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        self.setWindowTitle(
            (
                f"{APP_NAME} "
                f"{APP_VERSION_DISPLAY}"
            )
        )

        # ----------------------------------------------------
        # MainWindowUI
        # ----------------------------------------------------

        self.ui.retranslate_ui()

        # ----------------------------------------------------
        # Profile Placeholder
        # ----------------------------------------------------

        self.profiles_title_label.setText(
            tr(
                "navigation.profiles"
            )
        )

        # Noch Placeholder bis Profile implementiert wird.
        self.profiles_description_label.setText(
            (
                "Profile für das aktuell ausgewählte "
                "Spiel werden hier verwaltet."
            )
        )

    # ========================================================
    # Close
    # ========================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        # ----------------------------------------------------
        # Library Worker
        # ----------------------------------------------------

        try:
            self.library_page.cancel_scan()

        except Exception:
            logger.exception(
                "Scan konnte beim Beenden nicht abgebrochen werden."
            )

        try:
            self.library_page.cancel_import()

        except Exception:
            logger.exception(
                "Import konnte beim Beenden nicht abgebrochen werden."
            )

        try:
            self.library_page.cancel_bulk_action()

        except Exception:
            logger.exception(
                (
                    "Bulk-Aktion konnte beim Beenden "
                    "nicht abgebrochen werden."
                )
            )

        # ----------------------------------------------------
        # GameBanana Download
        # ----------------------------------------------------

        controller = getattr(
            self.gamebanana_page,
            "controller",
            None,
        )

        if controller is not None:
            cancel_download = getattr(
                controller,
                "cancel_download",
                None,
            )

            if callable(
                cancel_download
            ):
                try:
                    cancel_download()

                except Exception:
                    logger.exception(
                        (
                            "GameBanana-Download konnte "
                            "beim Beenden nicht abgebrochen werden."
                        )
                    )

        # ----------------------------------------------------
        # Fenstergröße speichern
        # ----------------------------------------------------

        self.config.window_width = (
            self.width()
        )

        self.config.window_height = (
            self.height()
        )

        try:
            self.config.save()

        except OSError as error:
            logger.exception(
                (
                    "Konfiguration konnte beim "
                    "Beenden nicht gespeichert werden: %s"
                ),
                error,
            )
        if (
            self.update_controller
            is not None
        ):
            self.update_controller.shutdown()
        event.accept()

    # ========================================================
    # Conflict -> Library
    # ========================================================

    def _copy_conflict_to_library(
        self,
        conflict,
    ) -> None:
        path = (
            Path(
                conflict.path
            )
            .expanduser()
            .absolute()
        )

        if not path.exists():
            QMessageBox.warning(
                self,
                tr(
                    "conflicts.copy.failed.title"
                ),
                tr(
                    "conflicts.copy.missing"
                ),
            )

            return

        started = (
            self.library_page
            .request_external_import(
                [
                    path
                ]
            )
        )

        if started:
            self._show_library()
__all__ = [
    "MainWindow",
]