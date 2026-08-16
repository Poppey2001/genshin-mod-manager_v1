from __future__ import annotations

import json
import logging
from dataclasses import (
    dataclass,
    field,
    asdict,
)
from datetime import datetime
from pathlib import Path
from typing import Any
from app.games import (
    GameConfig,
    GameId,
    all_games,
    find_game,
    get_game,
)
from platformdirs import (
    user_cache_path,
    user_config_path,
    user_data_path,
)


logger = logging.getLogger(__name__)

APP_NAME = "genshin-mod-manager"
CONFIG_FILENAME = "config.json"


# XDG-Verzeichnisse unter Linux:
# ~/.config/genshin-mod-manager
# ~/.local/share/genshin-mod-manager
# ~/.cache/genshin-mod-manager
CONFIG_DIR = user_config_path(
    appname=APP_NAME,
    appauthor=False,
)

DATA_DIR = user_data_path(
    appname=APP_NAME,
    appauthor=False,
)

CACHE_DIR = user_cache_path(
    appname=APP_NAME,
    appauthor=False,
)

CONFIG_FILE = CONFIG_DIR / CONFIG_FILENAME

MOD_LIBRARY_DIR = DATA_DIR / "mods"
PROFILE_DIR = DATA_DIR / "profiles"
PREVIEW_DIR = DATA_DIR / "previews"
BACKUP_DIR = DATA_DIR / "backups"
FIXED_MODS_DIR = DATA_DIR / "fixed-mods"

def create_default_game_configs(
) -> dict[
    str,
    GameConfig,
]:
    """
    Erstellt für jedes unterstützte XXMI-Spiel
    eine eigene Konfiguration.
    """

    return {
        game.id.value: GameConfig()
        for game in all_games()
    }

@dataclass(slots=True)
class AppConfig:
    """
    Enthält alle veränderbaren Programmeinstellungen.

    Pfade werden als Strings gespeichert, damit die Konfiguration
    problemlos als JSON geschrieben werden kann.
    """
    selected_game: str = (
        GameId.GENSHIN_IMPACT.value
    )

    games: dict[
        str,
        GameConfig,
    ] = field(
        default_factory=(
            create_default_game_configs
        )
    )

    selected_profile: str = "Default"

    use_symlinks: bool = False
    create_backups: bool = True

    theme: str = "dark"
    language: str = "de"

    # ------------------------------------------------------------
    # Library UI
    # ------------------------------------------------------------

    library_view_mode: str = "list"

    auto_check_updates: bool = True

    update_channel: str = "prerelease"
    window_width: int = 1200
    window_height: int = 760

    first_start: bool = True

    @property
    def active_mods_directory(
        self,
    ) -> Path | None:
        return self.active_mods_directory_for(
            self.selected_game
        )
        
    @property
    def launcher_file(
        self,
    ) -> Path | None:
        return self.launcher_file_for(
            self.selected_game
        )
    @property
    def mod_library_directory(
        self,
    ) -> Path:
        return self.mod_library_directory_for(
            self.selected_game
        )
        
    def set_mod_library_directory(
        self,
        path: Path | str | None,
    ) -> None:
        """Setzt den Pfad zur zentralen Mod-Bibliothek."""
        if path is None:
            self.library_path = None
            return

        candidate = Path(path).expanduser()

        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        self.library_path = str(candidate)
        
    def set_active_mods_directory(
        self,
        path: Path | str | None,
    ) -> None:
        if path is None:
            self.active_mods_path = None
            return

        candidate = Path(path).expanduser()

        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        self.active_mods_path = str(candidate)

    def set_launcher_file(self, path: Path | str | None) -> None:
        """Setzt den Pfad zum Launcher."""
        if path is None:
            self.launcher_path = None
            return

        candidate = Path(path).expanduser()

        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        self.launcher_path = str(candidate) 

    @property
    def current_game(
        self,
    ):
        """
        Gibt die Definition des aktuell
        ausgewählten Spiels zurück.
        """

        game = find_game(
            self.selected_game
        )

        if game is not None:
            return game

        return get_game(
            GameId.GENSHIN_IMPACT
        )


    @property
    def current_game_config(
        self,
    ) -> GameConfig:
        """
        Gibt die Benutzerkonfiguration
        des aktuell ausgewählten Spiels zurück.
        """

        game_id = (
            self.current_game.id.value
        )

        game_config = self.games.get(
            game_id
        )

        if game_config is None:
            game_config = GameConfig()

            self.games[
                game_id
            ] = game_config

        return game_config


    def get_game_config(
        self,
        game_id: (
            GameId
            | str
        ),
    ) -> GameConfig:
        """
        Gibt die Konfiguration eines bestimmten
        Spiels zurück.
        """

        game = get_game(
            game_id
        )

        key = game.id.value

        config = self.games.get(
            key
        )

        if config is None:
            config = GameConfig()

            self.games[
                key
            ] = config

        return config


    def set_selected_game(
        self,
        game_id: (
            GameId
            | str
        ),
    ) -> None:
        """
        Wechselt das aktuell ausgewählte Spiel.
        """

        game = get_game(
            game_id
        )

        self.selected_game = (
            game.id.value
        )

        # Sicherstellen, dass eine Config existiert.
        self.get_game_config(
            game.id
        )

    def validate(self) -> None:
        """
        Korrigiert ungültige oder unbrauchbare Einstellungen.
        """

        valid_themes = {
            "dark",
            "light",
            "system",
        }

        if self.theme not in valid_themes:
            logger.warning(
                "Ungültiges Theme '%s'. Verwende 'dark'.",
                self.theme,
            )
            self.theme = "dark"
        valid_languages = {
            "de",
            "en",
        }

        if self.language not in valid_languages:
            logger.warning(
                "Ungültige Sprache '%s'. Verwende 'de'.",
                self.language,
            )

            self.language = "de"
            
        valid_update_channels = {
            "stable",
            "prerelease",
        }

        if (
            self.update_channel
            not in valid_update_channels
        ):
            logger.warning(
                (
                    "Ungültiger Update-Kanal "
                    "'%s'. Verwende 'prerelease'."
                ),
                self.update_channel,
            )

            self.update_channel = (
                "prerelease"
            )
        if self.window_width < 800:
            self.window_width = 800

        if self.window_height < 500:
            self.window_height = 500

        if not self.selected_profile.strip():
            self.selected_profile = "Default"
            
        # --------------------------------------------------
        # Ausgewähltes Spiel
        # --------------------------------------------------

        selected_game = find_game(
            self.selected_game
        )

        if selected_game is None:
            logger.warning(
                (
                    "Ungültiges ausgewähltes Spiel "
                    "'%s'. Verwende Genshin Impact."
                ),
                self.selected_game,
            )

            self.selected_game = (
                GameId.GENSHIN_IMPACT.value
            )


        # --------------------------------------------------
        # Fehlende GameConfigs ergänzen
        # --------------------------------------------------

        for game in all_games():
            game_id = game.id.value

            if game_id not in self.games:
                self.games[
                    game_id
                ] = GameConfig()

        # --------------------------------------------------
        # Library View
        # --------------------------------------------------

        valid_library_view_modes = {
            "list",
            "gallery",
        }

        if (
            self.library_view_mode
            not in valid_library_view_modes
        ):
            logger.warning(
                (
                    "Ungültiger Library View Mode "
                    "'%s'. Verwende 'list'."
                ),
                self.library_view_mode,
            )

            self.library_view_mode = (
                "list"
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Konvertiert die komplette Konfiguration
        in ein JSON-kompatibles Dictionary.
        """

        return {
            "selected_game": (
                self.selected_game
            ),

            "games": {
                game_id: game_config.to_dict()
                for (
                    game_id,
                    game_config,
                )
                in self.games.items()
            },

            "selected_profile": (
                self.selected_profile
            ),

            "use_symlinks": (
                self.use_symlinks
            ),

            "create_backups": (
                self.create_backups
            ),

            "theme": (
                self.theme
            ),

            "language": (
                self.language
            ),

            "library_view_mode": (
                self.library_view_mode
            ),

            "auto_check_updates": (
                self.auto_check_updates
            ),

            "update_channel": (
                self.update_channel
            ),

            "window_width": (
                self.window_width
            ),

            "window_height": (
                self.window_height
            ),

            "first_start": (
                self.first_start
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[
            str,
            Any,
        ],
    ) -> AppConfig:
        """
        Lädt neue Multi-Game-Konfigurationen
        und migriert automatisch alte
        Genshin-Konfigurationen.
        """

        config = cls()

        # ==================================================
        # Neue Multi-Game-Konfiguration
        # ==================================================

        selected_game = data.get(
            "selected_game"
        )

        if isinstance(
            selected_game,
            str,
        ):
            config.selected_game = (
                selected_game
            )

        raw_games = data.get(
            "games"
        )

        if isinstance(
            raw_games,
            dict,
        ):
            for (
                game_id,
                raw_game_config,
            ) in raw_games.items():
                if not isinstance(
                    game_id,
                    str,
                ):
                    continue

                if find_game(
                    game_id
                ) is None:
                    continue

                if not isinstance(
                    raw_game_config,
                    dict,
                ):
                    continue

                config.games[
                    game_id
                ] = (
                    GameConfig.from_dict(
                        raw_game_config
                    )
                )

        # ==================================================
        # Legacy-Genshin-Migration
        # ==================================================
        #
        # Alte Config:
        #
        # {
        #     "library_path": "...",
        #     "active_mods_path": "...",
        #     "launcher_path": "..."
        # }
        #
        # wird automatisch:
        #
        # games["genshin-impact"]
        #
        # ==================================================

        if not isinstance(
            raw_games,
            dict,
        ):
            genshin_config = (
                config.get_game_config(
                    GameId.GENSHIN_IMPACT
                )
            )
            
            genshin_config.library_path = str(
                MOD_LIBRARY_DIR
            )

            legacy_library_path = (
                data.get(
                    "library_path"
                )
            )

            legacy_active_mods_path = (
                data.get(
                    "active_mods_path"
                )
            )

            legacy_launcher_path = (
                data.get(
                    "launcher_path"
                )
            )

            if isinstance(
                legacy_library_path,
                str,
            ):
                genshin_config.library_path = (
                    legacy_library_path
                )

            if (
                legacy_active_mods_path is None
                or isinstance(
                    legacy_active_mods_path,
                    str,
                )
            ):
                genshin_config.active_mods_path = (
                    legacy_active_mods_path
                )

            if (
                legacy_launcher_path is None
                or isinstance(
                    legacy_launcher_path,
                    str,
                )
            ):
                genshin_config.launcher_path = (
                    legacy_launcher_path
                )

            config.selected_game = (
                GameId.GENSHIN_IMPACT.value
            )

        # ==================================================
        # Globale Strings
        # ==================================================

        string_fields = (
            "selected_profile",
            "theme",
            "language",
            "library_view_mode",
            "update_channel",
        )

        for field_name in string_fields:
            value = data.get(
                field_name
            )

            if isinstance(
                value,
                str,
            ):
                setattr(
                    config,
                    field_name,
                    value,
                )

        # ==================================================
        # Globale boolesche Werte
        # ==================================================

        boolean_fields = (
            "use_symlinks",
            "create_backups",
            "first_start",
            "auto_check_updates",
        )

        for field_name in boolean_fields:
            value = data.get(
                field_name
            )

            if isinstance(
                value,
                bool,
            ):
                setattr(
                    config,
                    field_name,
                    value,
                )

        # ==================================================
        # Integer
        # ==================================================

        integer_fields = (
            "window_width",
            "window_height",
        )

        for field_name in integer_fields:
            value = data.get(
                field_name
            )

            if (
                isinstance(
                    value,
                    int,
                )
                and not isinstance(
                    value,
                    bool,
                )
            ):
                setattr(
                    config,
                    field_name,
                    value,
                )

        config.validate()

        return config

    def save(self) -> None:
        """
        Speichert die Konfiguration atomar.

        Zuerst wird eine temporäre Datei geschrieben. Erst danach
        ersetzt sie die eigentliche Konfigurationsdatei.
        """
        ensure_app_directories()
        self.validate()

        temporary_file = CONFIG_FILE.with_suffix(".tmp")

        config_json = json.dumps(
            self.to_dict(),
            indent=4,
            ensure_ascii=False,
        )

        temporary_file.write_text(
            config_json,
            encoding="utf-8",
        )

        temporary_file.replace(CONFIG_FILE)

        logger.info(
            "Konfiguration gespeichert: %s",
            CONFIG_FILE,
        )

    @classmethod
    def load(cls) -> AppConfig:
        """Lädt die vorhandene Konfiguration oder erstellt Standardwerte."""
        ensure_app_directories()

        if not CONFIG_FILE.exists():
            logger.info(
                "Keine Konfiguration gefunden. Standardwerte werden verwendet."
            )

            config = cls()
            config.save()

            return config
        
        for game in all_games():
            game_library_directory = (
                MOD_LIBRARY_DIR
                / game.library_folder
            )

            game_library_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        try:
            raw_content = CONFIG_FILE.read_text(
                encoding="utf-8",
            )

            data = json.loads(raw_content)

            if not isinstance(data, dict):
                raise TypeError(
                    "Die Konfigurationsdatei enthält kein JSON-Objekt."
                )

            config = cls.from_dict(data)

            logger.info(
                "Konfiguration geladen: %s",
                CONFIG_FILE,
            )

            return config

        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            logger.exception(
                "Die Konfiguration konnte nicht geladen werden: %s",
                error,
            )

            backup_broken_config()

            config = cls()
            config.save()

            return config
        
    def mod_library_directory_for(
        self,
        game_id: GameId | str,
    ) -> Path:
        """
        Gibt die Mod-Bibliothek eines bestimmten
        Spiels zurück, unabhängig von selected_game.
        """

        game = get_game(
            game_id
        )

        game_config = self.get_game_config(
            game.id
        )

        if game_config.library_path:
            return Path(
                game_config.library_path
            ).expanduser()

        return (
            MOD_LIBRARY_DIR
            / game.library_folder
        )


    def active_mods_directory_for(
        self,
        game_id: GameId | str,
    ) -> Path | None:
        """
        Gibt den aktiven XXMI-Mods-Ordner eines
        bestimmten Spiels zurück.
        """

        game_config = self.get_game_config(
            game_id
        )

        if not game_config.active_mods_path:
            return None

        return Path(
            game_config.active_mods_path
        ).expanduser()


    def launcher_file_for(
        self,
        game_id: GameId | str,
    ) -> Path | None:
        """
        Gibt den Launcher eines bestimmten
        Spiels zurück.
        """

        game_config = self.get_game_config(
            game_id
        )

        if not game_config.launcher_path:
            return None

        return Path(
            game_config.launcher_path
        ).expanduser()

    # ============================================================
    # Legacy-kompatible Pfad-Properties
    #
    # Bestehender Code darf weiterhin
    #
    # config.library_path
    # config.active_mods_path
    # config.launcher_path
    #
    # verwenden.
    #
    # Intern werden diese Werte jetzt aber aus der
    # Konfiguration des aktuell ausgewählten Spiels gelesen.
    # ============================================================

    @property
    def library_path(
        self,
    ) -> str | None:
        return (
            self.current_game_config
            .library_path
        )


    @library_path.setter
    def library_path(
        self,
        value: str | None,
    ) -> None:
        self.current_game_config.library_path = (
            value
        )


    @property
    def active_mods_path(
        self,
    ) -> str | None:
        return (
            self.current_game_config
            .active_mods_path
        )


    @active_mods_path.setter
    def active_mods_path(
        self,
        value: str | None,
    ) -> None:
        self.current_game_config.active_mods_path = (
            value
        )


    @property
    def launcher_path(
        self,
    ) -> str | None:
        return (
            self.current_game_config
            .launcher_path
        )


    @launcher_path.setter
    def launcher_path(
        self,
        value: str | None,
    ) -> None:
        self.current_game_config.launcher_path = (
            value
        )

def ensure_app_directories() -> None:
    """Erstellt alle vom Mod Manager benötigten Verzeichnisse."""
    directories = (
        CONFIG_DIR,
        DATA_DIR,
        CACHE_DIR,
        MOD_LIBRARY_DIR,
        PROFILE_DIR,
        PREVIEW_DIR,
        BACKUP_DIR,
        FIXED_MODS_DIR,
    )

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


def backup_broken_config() -> Path | None:
    """
    Verschiebt eine beschädigte Konfiguration in eine Sicherungsdatei.
    """
    if not CONFIG_FILE.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    backup_file = CONFIG_DIR / (
        f"config-broken-{timestamp}.json"
    )

    try:
        CONFIG_FILE.replace(backup_file)

        logger.warning(
            "Beschädigte Konfiguration gesichert: %s",
            backup_file,
        )

        return backup_file

    except OSError:
        logger.exception(
            "Die beschädigte Konfiguration konnte nicht gesichert werden."
        )

        return None
    
    
    

def set_mod_library_directory(
    self,
    path: Path | str | None,
) -> None:
    """Setzt einen lokalen oder eingehängten Netzwerkpfad."""
    if path is None:
        self.library_path = None
        return

    candidate = Path(path).expanduser()

    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    self.library_path = str(candidate)

def load_config() -> AppConfig:
    """Kurzfunktion zum Laden der Konfiguration."""
    return AppConfig.load()


def save_config(config: AppConfig) -> None:
    """Kurzfunktion zum Speichern der Konfiguration."""
    config.save()