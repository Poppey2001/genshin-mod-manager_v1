from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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


@dataclass(slots=True)
class AppConfig:
    """
    Enthält alle veränderbaren Programmeinstellungen.

    Pfade werden als Strings gespeichert, damit die Konfiguration
    problemlos als JSON geschrieben werden kann.
    """
    library_path: str | None = None
    active_mods_path: str | None = None
    launcher_path: str | None = None

    selected_profile: str = "Default"

    use_symlinks: bool = True
    create_backups: bool = True

    theme: str = "dark"

    window_width: int = 1200
    window_height: int = 760

    first_start: bool = True

    @property
    def active_mods_directory(self) -> Path | None:
        """Gibt den aktiven Mods-Ordner als Path-Objekt zurück."""
        if not self.active_mods_path:
            return None

        return Path(self.active_mods_path).expanduser()

    @property
    def launcher_file(self) -> Path | None:
        """Gibt den eingestellten Launcher als Path-Objekt zurück."""
        if not self.launcher_path:
            return None

        return Path(self.launcher_path).expanduser()
    @property
    def mod_library_directory(self) -> Path:
        """
        Gibt den Bibliotheksordner zurück.

        Ohne benutzerdefinierten Pfad wird der normale
        XDG-Datenordner verwendet.
        """
        if not self.library_path:
            return MOD_LIBRARY_DIR

        return Path(
            self.library_path
        ).expanduser()
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

        if self.window_width < 800:
            self.window_width = 800

        if self.window_height < 500:
            self.window_height = 500

        if not self.selected_profile.strip():
            self.selected_profile = "Default"

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert die Konfiguration in ein JSON-kompatibles Dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """
        Erstellt eine Konfiguration aus einem Dictionary.

        Unbekannte Werte werden ignoriert. Dadurch bleiben ältere
        Konfigurationsdateien mit neuen Programmversionen kompatibel.
        """
        config = cls()

        string_or_none_fields = (
            "library_path",
            "active_mods_path",
            "launcher_path",
        )

        string_fields = (
            "selected_profile",
            "theme",
        )

        boolean_fields = (
            "use_symlinks",
            "create_backups",
            "first_start",
        )

        integer_fields = (
            "window_width",
            "window_height",
        )

        for field_name in string_or_none_fields:
            value = data.get(field_name)

            if value is None or isinstance(value, str):
                setattr(config, field_name, value)

        for field_name in string_fields:
            value = data.get(field_name)

            if isinstance(value, str):
                setattr(config, field_name, value)

        for field_name in boolean_fields:
            value = data.get(field_name)

            if isinstance(value, bool):
                setattr(config, field_name, value)

        for field_name in integer_fields:
            value = data.get(field_name)

            # bool ist in Python eine Unterklasse von int.
            if isinstance(value, int) and not isinstance(value, bool):
                setattr(config, field_name, value)

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