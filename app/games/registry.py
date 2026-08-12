from __future__ import annotations

from collections.abc import Iterable

from app.games.game_definition import (
    GameDefinition,
    GameId,
)


# ============================================================
# Unterstützte Spiele
# ============================================================

GENSHIN_IMPACT = GameDefinition(
    id=GameId.GENSHIN_IMPACT,
    name="Genshin Impact",
    short_name="Genshin",
    importer="GIMI",
    library_folder="genshin-impact",
    gamebanana_game_id=8552,
)


HONKAI_STAR_RAIL = GameDefinition(
    id=GameId.HONKAI_STAR_RAIL,
    name="Honkai: Star Rail",
    short_name="Star Rail",
    importer="SRMI",
    library_folder="honkai-star-rail",
    gamebanana_game_id=18366,
)


ZENLESS_ZONE_ZERO = GameDefinition(
    id=GameId.ZENLESS_ZONE_ZERO,
    name="Zenless Zone Zero",
    short_name="ZZZ",
    importer="ZZMI",
    library_folder="zenless-zone-zero",
    gamebanana_game_id=19567,
)


WUTHERING_WAVES = GameDefinition(
    id=GameId.WUTHERING_WAVES,
    name="Wuthering Waves",
    short_name="Wuthering Waves",
    importer="WWMI",
    library_folder="wuthering-waves",
    gamebanana_game_id=20357,
)


HONKAI_IMPACT_3RD = GameDefinition(
    id=GameId.HONKAI_IMPACT_3RD,
    name="Honkai Impact 3rd",
    short_name="Honkai Impact 3rd",
    importer="HIMI",
    library_folder="honkai-impact-3rd",
    gamebanana_game_id=10349,
)


ARKNIGHTS_ENDFIELD = GameDefinition(
    id=GameId.ARKNIGHTS_ENDFIELD,
    name="Arknights: Endfield",
    short_name="Endfield",
    importer="EFMI",
    library_folder="arknights-endfield",
    gamebanana_game_id=24320,
)


# ============================================================
# Registry
# ============================================================

SUPPORTED_GAMES: tuple[
    GameDefinition,
    ...,
] = (
    GENSHIN_IMPACT,
    HONKAI_STAR_RAIL,
    ZENLESS_ZONE_ZERO,
    WUTHERING_WAVES,
    HONKAI_IMPACT_3RD,
    ARKNIGHTS_ENDFIELD,
)


GAMES_BY_ID: dict[
    GameId,
    GameDefinition,
] = {
    game.id: game
    for game in SUPPORTED_GAMES
}


GAMES_BY_IMPORTER: dict[
    str,
    GameDefinition,
] = {
    game.importer.casefold(): game
    for game in SUPPORTED_GAMES
}


GAMES_BY_GAMEBANANA_ID: dict[
    int,
    GameDefinition,
] = {
    game.gamebanana_game_id: game
    for game in SUPPORTED_GAMES
}


# ============================================================
# Zugriff
# ============================================================

def all_games(
) -> tuple[
    GameDefinition,
    ...,
]:
    return SUPPORTED_GAMES


def game_ids(
) -> tuple[
    GameId,
    ...,
]:
    return tuple(
        game.id
        for game in SUPPORTED_GAMES
    )


def get_game(
    game_id: (
        GameId
        | str
    ),
) -> GameDefinition:
    normalized_id = normalize_game_id(
        game_id
    )

    try:
        return GAMES_BY_ID[
            normalized_id
        ]

    except KeyError as error:
        raise ValueError(
            (
                "Nicht unterstütztes Spiel: "
                f"{game_id}"
            )
        ) from error


def find_game(
    game_id: (
        GameId
        | str
        | None
    ),
) -> GameDefinition | None:
    if game_id is None:
        return None

    try:
        return get_game(
            game_id
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


def get_game_by_importer(
    importer: str,
) -> GameDefinition:
    normalized_importer = (
        importer
        .strip()
        .casefold()
    )

    try:
        return GAMES_BY_IMPORTER[
            normalized_importer
        ]

    except KeyError as error:
        raise ValueError(
            (
                "Nicht unterstützter "
                "XXMI-Importer: "
                f"{importer}"
            )
        ) from error


def find_game_by_importer(
    importer: str | None,
) -> GameDefinition | None:
    if not importer:
        return None

    try:
        return get_game_by_importer(
            importer
        )

    except ValueError:
        return None


def get_game_by_gamebanana_id(
    gamebanana_game_id: int,
) -> GameDefinition:
    try:
        return (
            GAMES_BY_GAMEBANANA_ID[
                gamebanana_game_id
            ]
        )

    except KeyError as error:
        raise ValueError(
            (
                "Nicht unterstützte "
                "GameBanana-Spiel-ID: "
                f"{gamebanana_game_id}"
            )
        ) from error


def find_game_by_gamebanana_id(
    gamebanana_game_id: int | None,
) -> GameDefinition | None:
    if gamebanana_game_id is None:
        return None

    return (
        GAMES_BY_GAMEBANANA_ID.get(
            gamebanana_game_id
        )
    )


# ============================================================
# Normalisierung
# ============================================================

def normalize_game_id(
    game_id: (
        GameId
        | str
    ),
) -> GameId:
    if isinstance(
        game_id,
        GameId,
    ):
        return game_id

    if not isinstance(
        game_id,
        str,
    ):
        raise TypeError(
            (
                "game_id muss ein String "
                "oder GameId sein."
            )
        )

    value = (
        game_id
        .strip()
        .casefold()
    )

    aliases: dict[
        str,
        GameId,
    ] = {
        # Genshin
        "genshin": (
            GameId.GENSHIN_IMPACT
        ),
        "genshin-impact": (
            GameId.GENSHIN_IMPACT
        ),
        "gi": (
            GameId.GENSHIN_IMPACT
        ),
        "gimi": (
            GameId.GENSHIN_IMPACT
        ),

        # Star Rail
        "star-rail": (
            GameId.HONKAI_STAR_RAIL
        ),
        "honkai-star-rail": (
            GameId.HONKAI_STAR_RAIL
        ),
        "hsr": (
            GameId.HONKAI_STAR_RAIL
        ),
        "srmi": (
            GameId.HONKAI_STAR_RAIL
        ),

        # ZZZ
        "zzz": (
            GameId.ZENLESS_ZONE_ZERO
        ),
        "zenless": (
            GameId.ZENLESS_ZONE_ZERO
        ),
        "zenless-zone-zero": (
            GameId.ZENLESS_ZONE_ZERO
        ),
        "zzmi": (
            GameId.ZENLESS_ZONE_ZERO
        ),

        # Wuthering Waves
        "wuwa": (
            GameId.WUTHERING_WAVES
        ),
        "wuthering-waves": (
            GameId.WUTHERING_WAVES
        ),
        "wwmi": (
            GameId.WUTHERING_WAVES
        ),

        # Honkai Impact
        "hi3": (
            GameId.HONKAI_IMPACT_3RD
        ),
        "honkai-impact-3rd": (
            GameId.HONKAI_IMPACT_3RD
        ),
        "himi": (
            GameId.HONKAI_IMPACT_3RD
        ),

        # Endfield
        "endfield": (
            GameId.ARKNIGHTS_ENDFIELD
        ),
        "arknights-endfield": (
            GameId.ARKNIGHTS_ENDFIELD
        ),
        "efmi": (
            GameId.ARKNIGHTS_ENDFIELD
        ),
    }

    try:
        return aliases[
            value
        ]

    except KeyError:
        pass

    try:
        return GameId(
            value
        )

    except ValueError as error:
        raise ValueError(
            (
                "Unbekannte Spiel-ID: "
                f"{game_id}"
            )
        ) from error


# ============================================================
# Validierung
# ============================================================

def validate_registry(
    games: Iterable[
        GameDefinition
    ] = SUPPORTED_GAMES,
) -> None:
    game_list = list(
        games
    )

    ids = [
        game.id
        for game in game_list
    ]

    importers = [
        game.importer.casefold()
        for game in game_list
    ]

    gamebanana_ids = [
        game.gamebanana_game_id
        for game in game_list
    ]

    library_folders = [
        game.library_folder.casefold()
        for game in game_list
    ]

    if len(ids) != len(
        set(ids)
    ):
        raise RuntimeError(
            (
                "Doppelte GameId in "
                "der Game Registry."
            )
        )

    if len(importers) != len(
        set(importers)
    ):
        raise RuntimeError(
            (
                "Doppelter XXMI-Importer "
                "in der Game Registry."
            )
        )

    if len(gamebanana_ids) != len(
        set(gamebanana_ids)
    ):
        raise RuntimeError(
            (
                "Doppelte GameBanana-ID "
                "in der Game Registry."
            )
        )

    if len(library_folders) != len(
        set(library_folders)
    ):
        raise RuntimeError(
            (
                "Doppelter Library-Ordner "
                "in der Game Registry."
            )
        )


validate_registry()