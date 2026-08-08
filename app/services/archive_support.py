from __future__ import annotations

from pathlib import Path
import tarfile
import zipfile

import py7zr
import rarfile


SUPPORTED_ARCHIVE_EXTENSIONS = (
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".7z",
    ".rar",
)


class UnsupportedArchiveError(Exception):
    pass


def is_supported_archive(
    path: Path,
) -> bool:
    name = path.name.casefold()

    return any(
        name.endswith(extension)
        for extension
        in SUPPORTED_ARCHIVE_EXTENSIONS
    )


def extract_archive(
    source: Path,
    destination: Path,
) -> None:
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    name = source.name.casefold()

    if name.endswith(".zip"):
        _extract_zip(
            source,
            destination,
        )
        return

    if name.endswith(
        (
            ".tar",
            ".tar.gz",
            ".tgz",
            ".tar.bz2",
            ".tbz2",
            ".tar.xz",
            ".txz",
        )
    ):
        _extract_tar(
            source,
            destination,
        )
        return

    if name.endswith(".7z"):
        _extract_7z(
            source,
            destination,
        )
        return

    if name.endswith(".rar"):
        _extract_rar(
            source,
            destination,
        )
        return

    raise UnsupportedArchiveError(
        f"Nicht unterstütztes Archiv: "
        f"{source.name}"
    )


def _extract_zip(
    source: Path,
    destination: Path,
) -> None:
    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:
        _validate_members(
            archive.namelist(),
            destination,
        )

        archive.extractall(
            destination
        )


def _extract_tar(
    source: Path,
    destination: Path,
) -> None:
    with tarfile.open(
        source,
        "r:*",
    ) as archive:
        names = [
            member.name
            for member
            in archive.getmembers()
        ]

        _validate_members(
            names,
            destination,
        )

        archive.extractall(
            destination,
            filter="data",
        )


def _extract_7z(
    source: Path,
    destination: Path,
) -> None:
    with py7zr.SevenZipFile(
        source,
        mode="r",
    ) as archive:
        _validate_members(
            archive.getnames(),
            destination,
        )

        archive.extractall(
            path=destination
        )


def _extract_rar(
    source: Path,
    destination: Path,
) -> None:
    with rarfile.RarFile(
        source,
        mode="r",
    ) as archive:
        _validate_members(
            archive.namelist(),
            destination,
        )

        archive.extractall(
            path=destination
        )


def _validate_members(
    names: list[str],
    destination: Path,
) -> None:
    destination_root = (
        destination.resolve()
    )

    for name in names:
        target = (
            destination
            / name
        ).resolve()

        try:
            target.relative_to(
                destination_root
            )

        except ValueError as error:
            raise ValueError(
                "Unsicherer Pfad im Archiv: "
                f"{name}"
            ) from error