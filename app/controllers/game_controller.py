from __future__ import annotations

from collections.abc import (
    Callable,
)

from PySide6.QtCore import (
    QObject,
    Signal,
)

from app.config import (
    AppConfig,
)

from app.games.registry import (
    get_game,
)


GameChangeGuard = Callable[
    [],
    bool,
]


class GameController(
    QObject
):
    """
    Zentrale Umschaltung des aktiven Spiels.
    """

    game_changed = Signal(
        str
    )

    game_change_blocked = Signal(
        str
    )

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

    def set_change_guard(
        self,
        guard: (
            GameChangeGuard
            | None
        ),
    ) -> None:
        self._change_guard = (
            guard
        )

    def request_game_change(
        self,
        game_id: str,
    ) -> bool:
        try:
            game = get_game(
                game_id
            )

        except (
            KeyError,
            ValueError,
        ):
            return False

        stable_id = getattr(
            game,
            "game_id",
            None,
        )

        if not stable_id:
            raw_id = getattr(
                game,
                "id",
                None,
            )

            if hasattr(
                raw_id,
                "value",
            ):
                stable_id = (
                    raw_id.value
                )

            else:
                stable_id = (
                    str(
                        raw_id
                    )
                )

        stable_id = str(
            stable_id
        )

        if (
            stable_id
            == self.config.selected_game
        ):
            return True

        if (
            self._change_guard
            is not None
            and not self._change_guard()
        ):
            self.game_change_blocked.emit(
                stable_id
            )

            return False

        self.config.set_selected_game(
            stable_id
        )

        self.config.save()

        self.game_changed.emit(
            stable_id
        )

        return True


__all__ = [
    "GameController",
]