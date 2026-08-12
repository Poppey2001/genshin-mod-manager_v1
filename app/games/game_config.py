from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(
    slots=True,
)
class GameConfig:
    """
    Benutzerabhängige Konfiguration
    eines einzelnen Spiels.

    GameDefinition beschreibt das Spiel selbst.

    GameConfig enthält dagegen Pfade und andere
    Einstellungen des Benutzers.
    """

    library_path: str | None = None

    active_mods_path: str | None = None

    launcher_path: str | None = None

    enabled: bool = True

    # Später können hier weitere spielbezogene
    # Optionen ergänzt werden, beispielsweise:
    #
    # xxmi_path
    # executable_path
    # gamebanana preferences
    # profile
    # etc.

    @property
    def library_directory(
        self,
    ) -> Path | None:
        if not self.library_path:
            return None

        return Path(
            self.library_path
        ).expanduser()

    @property
    def active_mods_directory(
        self,
    ) -> Path | None:
        if not self.active_mods_path:
            return None

        return Path(
            self.active_mods_path
        ).expanduser()

    @property
    def launcher_file(
        self,
    ) -> Path | None:
        if not self.launcher_path:
            return None

        return Path(
            self.launcher_path
        ).expanduser()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "library_path": (
                self.library_path
            ),
            "active_mods_path": (
                self.active_mods_path
            ),
            "launcher_path": (
                self.launcher_path
            ),
            "enabled": (
                self.enabled
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[
            str,
            Any,
        ],
    ) -> GameConfig:
        config = cls()

        for field_name in (
            "library_path",
            "active_mods_path",
            "launcher_path",
        ):
            value = data.get(
                field_name
            )

            if (
                value is None
                or isinstance(
                    value,
                    str,
                )
            ):
                setattr(
                    config,
                    field_name,
                    value,
                )

        enabled = data.get(
            "enabled"
        )

        if isinstance(
            enabled,
            bool,
        ):
            config.enabled = enabled

        return config