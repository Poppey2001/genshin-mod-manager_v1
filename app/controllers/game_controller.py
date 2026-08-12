from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    Signal,
)

from app.config import AppConfig

from app.games import (
    GameDefinition,
    get_game,
)


GameChangeGuard = Callable[
    [],
    bool,
]


class GameController(QObject):
    """
    Verwaltet das global ausgewählte Spiel.

    Änderungen laufen zentral über diesen Controller,
    damit Library, Settings und später GameBanana
    synchron bleiben.
    """

    game_changed = Signal(str)

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.config = config

        self._change_guard: (
            GameChangeGuard
            | None
        ) = None

    @property
    def current_game(
        self,
    ) -> GameDefinition:
        return (
            self.config.current_game
        )

    def set_change_guard(
        self,
        guard: GameChangeGuard | None,
    ) -> None:
        self._change_guard = guard

    def can_change_game(
        self,
    ) -> bool:
        if self._change_guard is None:
            return True

        return bool(
            self._change_guard()
        )

    def request_game_change(
        self,
        game_id: str,
    ) -> bool:
        game = get_game(
            game_id
        )

        if (
            game.id.value
            == self.config.selected_game
        ):
            return True

        if not self.can_change_game():
            return False

        self.config.set_selected_game(
            game.id
        )

        self.config.save()

        self.game_changed.emit(
            game.id.value
        )

        return True