from __future__ import annotations

from pathlib import Path

from app.games.game_config import (
    GameConfig,
)

from app.games.game_definition import (
    GameDefinition,
    GameId,
)

from app.games.registry import (
    get_game,
)


class GameScope:
    """
    Bindet Dateisystemoperationen an genau
    ein bestimmtes XXMI-Spiel.

    Der Scope kann kontrolliert gewechselt werden,
    aber er hängt NICHT implizit von
    AppConfig.selected_game ab.
    """

    def __init__(
        self,
        *,
        config,
        game_id: GameId | str,
    ) -> None:
        self._config = config

        self._game_id: str = ""

        self.set_game(
            game_id
        )

    # ========================================================
    # Spiel
    # ========================================================

    @property
    def game_id(
        self,
    ) -> str:
        return self._game_id

    @property
    def game(
        self,
    ) -> GameDefinition:
        return get_game(
            self._game_id
        )

    @property
    def importer(
        self,
    ) -> str:
        return self.game.importer

    @property
    def game_config(
        self,
    ) -> GameConfig:
        return self._config.get_game_config(
            self._game_id
        )

    def set_game(
        self,
        game_id: GameId | str,
    ) -> None:
        game = get_game(
            game_id
        )

        self._game_id = (
            game.id.value
        )

    # ========================================================
    # Pfade
    # ========================================================

    @property
    def mod_library_directory(
        self,
    ) -> Path:
        return (
            self._config
            .mod_library_directory_for(
                self._game_id
            )
        )

    @property
    def active_mods_directory(
        self,
    ) -> Path | None:
        return (
            self._config
            .active_mods_directory_for(
                self._game_id
            )
        )

    @property
    def launcher_file(
        self,
    ) -> Path | None:
        return (
            self._config
            .launcher_file_for(
                self._game_id
            )
        )

    # ========================================================
    # Legacy-kompatible String-Properties
    # ========================================================

    @property
    def library_path(
        self,
    ) -> str | None:
        return self.game_config.library_path

    @library_path.setter
    def library_path(
        self,
        value: str | None,
    ) -> None:
        self.game_config.library_path = value

    @property
    def active_mods_path(
        self,
    ) -> str | None:
        return self.game_config.active_mods_path

    @active_mods_path.setter
    def active_mods_path(
        self,
        value: str | None,
    ) -> None:
        self.game_config.active_mods_path = value

    @property
    def launcher_path(
        self,
    ) -> str | None:
        return self.game_config.launcher_path

    @launcher_path.setter
    def launcher_path(
        self,
        value: str | None,
    ) -> None:
        self.game_config.launcher_path = value

    # ========================================================
    # Globale Einstellungen
    # ========================================================

    @property
    def create_backups(
        self,
    ) -> bool:
        return self._config.create_backups

    @property
    def use_symlinks(
        self,
    ) -> bool:
        return self._config.use_symlinks

    # ========================================================
    # Zugriff auf weitere globale AppConfig-Werte
    # ========================================================

    def __getattr__(
        self,
        name: str,
    ):
        """
        Globale Einstellungen, die nicht spielbezogen
        sind, werden an AppConfig weitergereicht.

        Die spielbezogenen Pfade sind oben explizit
        definiert und können dadurch nicht versehentlich
        vom aktuell ausgewählten Spiel gelesen werden.
        """

        return getattr(
            self._config,
            name,
        )