from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GameId(StrEnum):
    GENSHIN_IMPACT = "genshin-impact"

    HONKAI_STAR_RAIL = "honkai-star-rail"

    ZENLESS_ZONE_ZERO = "zenless-zone-zero"

    WUTHERING_WAVES = "wuthering-waves"

    HONKAI_IMPACT_3RD = "honkai-impact-3rd"

    ARKNIGHTS_ENDFIELD = "arknights-endfield"


@dataclass(
    frozen=True,
    slots=True,
)
class GameDefinition:
    """
    Beschreibt ein vom XXMI Mod Manager
    unterstütztes Spiel.

    Diese Klasse enthält absichtlich keine
    Pfade des Benutzers.

    Benutzerabhängige Pfade kommen später
    aus der AppConfig.
    """

    id: GameId

    name: str

    importer: str

    library_folder: str

    gamebanana_game_id: int

    short_name: str

    @property
    def game_id(
        self,
    ) -> str:
        return self.id.value

    @property
    def importer_name(
        self,
    ) -> str:
        return self.importer

    @property
    def gamebanana_id(
        self,
    ) -> int:
        return self.gamebanana_game_id

    def __str__(
        self,
    ) -> str:
        return self.name