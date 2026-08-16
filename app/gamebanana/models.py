from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from pathlib import Path

from typing import Any


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaFile:
    """
    Eine herunterladbare Datei einer
    GameBanana-Mod-Submission.
    """

    id: int | None

    name: str

    download_url: str

    size: int | None = None

    description: str | None = None

    date_added: int | None = None

    raw: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    @property
    def suffix(
        self,
    ) -> str:
        return (
            Path(self.name)
            .suffix
            .casefold()
        )

    @property
    def size_megabytes(
        self,
    ) -> float | None:
        if self.size is None:
            return None

        return (
            self.size
            / 1024
            / 1024
        )


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaBrowseResult:
    """
    Gemeinsames Ergebnis einer GameBanana-Browse-/Suchanfrage.

    Controller, Browser-Service, Worker und UI verwenden damit
    denselben Datentyp.
    """

    game_id: str

    page: int

    query: str

    mods: tuple[
        "GameBananaMod",
        ...,
    ]

    has_previous: bool

    has_next: bool


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaMod:
    """
    Repräsentiert die für den Mod Manager
    relevanten GameBanana-Daten.
    """

    id: int

    name: str

    author: str | None

    game_name: str | None

    profile_url: str | None

    preview_url: str | None

    description: str | None

    files: tuple[
        GameBananaFile,
        ...,
    ]

    # Vollständige Preview-/Screenshot-Liste.
    #
    # Das Feld liegt absichtlich am Ende und besitzt einen Default,
    # damit bestehender Code, der GameBananaMod bisher ohne
    # preview_urls erzeugt, weiterhin funktioniert.
    preview_urls: tuple[
        str,
        ...,
    ] = ()

    @property
    def has_previews(
        self,
    ) -> bool:
        return bool(
            self.preview_urls
            or self.preview_url
        )

    @property
    def all_preview_urls(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Liefert alle Preview-URLs dedupliziert.

        preview_urls ist die neue vollständige Liste.
        preview_url bleibt als Legacy-/Fallback-Feld erhalten.
        """

        result: list[str] = []
        seen: set[str] = set()

        for value in (
            *self.preview_urls,
            self.preview_url,
        ):
            if not value:
                continue

            normalized = str(
                value
            ).strip()

            if (
                not normalized
                or normalized in seen
            ):
                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return tuple(
            result
        )

    @property
    def has_files(
        self,
    ) -> bool:
        return bool(
            self.files
        )

    def default_file(
        self,
    ) -> GameBananaFile | None:
        """
        Bevorzugt die zuletzt hinzugefügte
        herunterladbare Datei.
        """

        if not self.files:
            return None

        return max(
            self.files,
            key=lambda file: (
                file.date_added or 0,
                file.id or 0,
            ),
        )