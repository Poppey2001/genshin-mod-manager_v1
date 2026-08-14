from __future__ import annotations

from dataclasses import (
    dataclass,
)

from pathlib import Path


IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
}

DIRECT_NAMES = (
    "preview",
    "cover",
    "thumbnail",
    "thumb",
)

PREVIEW_DIRECTORIES = (
    "preview",
    "previews",
    "screenshots",
)


@dataclass(
    frozen=True,
    slots=True,
)
class LibraryPreviewResult:
    local_images: tuple[
        Path,
        ...,
    ] = ()

    remote_images: tuple[
        str,
        ...,
    ] = ()

    gamebanana_mod_id: int | None = None

    @property
    def has_images(
        self,
    ) -> bool:
        return bool(
            self.local_images
            or self.remote_images
        )


def find_local_preview_images(
    mod_directory: Path | str,
    *,
    configured_preview: str | None = None,
) -> tuple[
    Path,
    ...,
]:
    root = (
        Path(
            mod_directory
        )
        .expanduser()
        .absolute()
    )

    if not root.is_dir():
        return ()

    images: list[
        Path
    ] = []

    seen: set[
        str
    ] = set()

    def add(
        path: Path,
    ) -> None:
        if not path.is_file():
            return

        if (
            path.suffix.casefold()
            not in IMAGE_SUFFIXES
        ):
            return

        key = str(
            path.absolute()
        )

        if key in seen:
            return

        seen.add(
            key
        )

        images.append(
            path
        )

    # ========================================================
    # Explizit konfigurierte Preview zuerst
    # ========================================================

    if configured_preview:
        candidate = (
            root
            / configured_preview
        )

        try:
            candidate.relative_to(
                root
            )

        except ValueError:
            candidate = root

        if candidate != root:
            add(
                candidate
            )

    # ========================================================
    # preview.png, cover.jpg usw.
    # ========================================================

    try:
        root_entries = tuple(
            root.iterdir()
        )

    except OSError:
        root_entries = ()

    for entry in root_entries:
        if not entry.is_file():
            continue

        stem = (
            entry.stem
            .casefold()
        )

        if stem in DIRECT_NAMES:
            add(
                entry
            )

    # ========================================================
    # preview/, previews/, screenshots/
    #
    # Nur direkt darin suchen.
    # Nicht rekursiv durch den gesamten Mod,
    # damit Texturdateien nicht als Preview
    # interpretiert werden.
    # ========================================================

    for directory_name in (
        PREVIEW_DIRECTORIES
    ):
        directory = (
            root
            / directory_name
        )

        if not directory.is_dir():
            continue

        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda item: (
                    item.name.casefold()
                ),
            )

        except OSError:
            continue

        for entry in entries:
            add(
                entry
            )

    return tuple(
        images
    )


__all__ = [
    "LibraryPreviewResult",
    "find_local_preview_images",
]