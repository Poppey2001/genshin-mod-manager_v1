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
    GameBanana-Mod.
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
            Path(
                self.name
            )
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
class GameBananaModSummary:
    """
    Kompakte Daten für die
    Browser-Ergebnisliste.
    """

    id: int

    name: str

    author: str | None = None

    game_name: str | None = None

    category: str | None = None

    profile_url: str | None = None

    preview_url: str | None = None

    downloads: int | None = None

    likes: int | None = None

    views: int | None = None

    date_added: int | None = None

    date_updated: int | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaBrowseResult:
    """
    Ergebnis eines Latest- oder
    Search-Aufrufs.
    """

    items: tuple[
        GameBananaModSummary,
        ...,
    ]

    page: int = 1

    query: str | None = None

    has_previous: bool = False

    has_next: bool = False

    pages_scanned: int = 1

    @property
    def is_search(
        self,
    ) -> bool:
        return bool(
            self.query
        )


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaMod:
    """
    Vollständige Mod-Daten für
    Detailansicht und Download.
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
    
    image_urls: tuple[
        str,
        ...,
    ] = ()

    category: str | None = None

    downloads: int | None = None

    likes: int | None = None

    views: int | None = None

    date_added: int | None = None

    date_updated: int | None = None

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


__all__ = [
    "GameBananaFile",
    "GameBananaMod",
    "GameBananaModSummary",
    "GameBananaBrowseResult",
]