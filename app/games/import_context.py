from __future__ import annotations

from dataclasses import dataclass

from app.games.game_definition import (
    GameDefinition,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ImportGameContext:
    game_id: str
    game_name: str
    importer: str
    gamebanana_game_id: int

    @classmethod
    def from_game(
        cls,
        game: GameDefinition,
    ) -> ImportGameContext:
        return cls(
            game_id=(
                game.id.value
            ),
            game_name=(
                game.name
            ),
            importer=(
                game.importer
            ),
            gamebanana_game_id=(
                game.gamebanana_game_id
            ),
        )