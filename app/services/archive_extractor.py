from __future__ import annotations

import shutil
import stat
import tarfile
import zipfile

from collections.abc import (
    Callable,
)

from pathlib import Path

import py7zr
import rarfile

from app.services.archive_security import (
    ArchiveKind,
    ArchiveSecurityError,
    MAX_ARCHIVE_ENTRIES,
    MAX_SINGLE_FILE_SIZE,
    MAX_TOTAL_UNCOMPRESSED,
    detect_archive_kind,
    inspect_archive,
    safe_member_relative_path,
)


CancelCallback = Callable[
    [],
    bool,
]


CHUNK_SIZE = (
    1024
    * 1024
)


class ArchiveExtractionError(
    RuntimeError
):
    """Archiv konnte nicht sicher extrahiert werden."""


class ArchiveExtractionCancelled(
    ArchiveExtractionError
):
    """Extraktion wurde abgebrochen."""


def extract_archive_securely(
    *,
    source: Path | str,
    destination: Path | str,
    cancel_callback: (
        CancelCallback
        | None
    ) = None,
) -> Path:
    source = (
        Path(source)
        .expanduser()
        .absolute()
    )

    destination = (
        Path(destination)
        .expanduser()
        .absolute()
    )

    # --------------------------------------------------
    # Sicherheitsprüfung erneut durchführen.
    #
    # Nicht darauf vertrauen, dass die UI bereits
    # eine Prüfung ausgeführt hat.
    # --------------------------------------------------

    report = inspect_archive(
        source
    )

    if report.blocked:
        messages = [
            issue.message
            for issue
            in report.blocking_issues
        ]

        raise ArchiveExtractionError(
            (
                "Das Archiv wurde aus "
                "Sicherheitsgründen blockiert.\n\n"
                + "\n".join(
                    messages[:10]
                )
            )
        )

    _prepare_destination(
        destination
    )

    kind = detect_archive_kind(
        source
    )

    try:
        if kind == ArchiveKind.ZIP:
            _extract_zip(
                source=source,
                destination=destination,
                cancel_callback=(
                    cancel_callback
                ),
            )

        elif kind == ArchiveKind.TAR:
            _extract_tar(
                source=source,
                destination=destination,
                cancel_callback=(
                    cancel_callback
                ),
            )

        elif (
            kind
            == ArchiveKind.SEVEN_ZIP
        ):
            _extract_7z(
                source=source,
                destination=destination,
                cancel_callback=(
                    cancel_callback
                ),
            )

        elif kind == ArchiveKind.RAR:
            _extract_rar(
                source=source,
                destination=destination,
                cancel_callback=(
                    cancel_callback
                ),
            )

        _verify_extracted_tree(
            destination
        )

    except ArchiveExtractionCancelled:
        _cleanup_destination(
            destination
        )

        raise

    except ArchiveExtractionError:
        _cleanup_destination(
            destination
        )

        raise

    except Exception as error:
        _cleanup_destination(
            destination
        )

        raise ArchiveExtractionError(
            (
                "Das Archiv konnte nicht "
                "extrahiert werden.\n\n"
                f"{type(error).__name__}: "
                f"{error}"
            )
        ) from error

    return destination


# ============================================================
# Destination
# ============================================================

def _prepare_destination(
    destination: Path,
) -> None:
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        has_content = next(
            destination.iterdir(),
            None,
        )

    except OSError as error:
        raise ArchiveExtractionError(
            (
                "Das temporäre Zielverzeichnis "
                "konnte nicht geprüft werden.\n\n"
                f"{error}"
            )
        ) from error

    if has_content is not None:
        raise ArchiveExtractionError(
            (
                "Das Zielverzeichnis für die "
                "Archivextraktion muss leer sein."
            )
        )


def _cleanup_destination(
    destination: Path,
) -> None:
    try:
        shutil.rmtree(
            destination
        )

    except OSError:
        pass


# ============================================================
# ZIP
# ============================================================

def _extract_zip(
    *,
    source: Path,
    destination: Path,
    cancel_callback: (
        CancelCallback
        | None
    ),
) -> None:
    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:
        for info in (
            archive.infolist()
        ):
            _check_cancelled(
                cancel_callback
            )

            relative_path = (
                safe_member_relative_path(
                    info.filename
                )
            )

            target = (
                destination
                / relative_path
            )

            if info.is_dir():
                target.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                continue

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with archive.open(
                info,
                "r",
            ) as input_file:
                with target.open(
                    "xb"
                ) as output_file:
                    _copy_stream(
                        input_file=input_file,
                        output_file=output_file,
                        expected_size=(
                            info.file_size
                        ),
                        cancel_callback=(
                            cancel_callback
                        ),
                    )


# ============================================================
# TAR
# ============================================================

def _extract_tar(
    *,
    source: Path,
    destination: Path,
    cancel_callback: (
        CancelCallback
        | None
    ),
) -> None:
    with tarfile.open(
        source,
        "r:*",
    ) as archive:
        for member in (
            archive.getmembers()
        ):
            _check_cancelled(
                cancel_callback
            )

            relative_path = (
                safe_member_relative_path(
                    member.name
                )
            )

            target = (
                destination
                / relative_path
            )

            if member.isdir():
                target.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                continue

            if not member.isfile():
                raise ArchiveExtractionError(
                    (
                        "TAR enthält einen nicht "
                        "erlaubten Dateityp:\n"
                        f"{member.name}"
                    )
                )

            input_file = (
                archive.extractfile(
                    member
                )
            )

            if input_file is None:
                raise ArchiveExtractionError(
                    (
                        "TAR-Datei konnte nicht "
                        "gelesen werden:\n"
                        f"{member.name}"
                    )
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with input_file:
                with target.open(
                    "xb"
                ) as output_file:
                    _copy_stream(
                        input_file=input_file,
                        output_file=output_file,
                        expected_size=(
                            member.size
                        ),
                        cancel_callback=(
                            cancel_callback
                        ),
                    )


# ============================================================
# RAR
# ============================================================

def _extract_rar(
    *,
    source: Path,
    destination: Path,
    cancel_callback: (
        CancelCallback
        | None
    ),
) -> None:
    try:
        archive = rarfile.RarFile(
            source,
            mode="r",
            errors="strict",
        )

    except rarfile.Error as error:
        raise ArchiveExtractionError(
            (
                "RAR-Archiv konnte nicht "
                f"geöffnet werden:\n{error}"
            )
        ) from error

    with archive:
        for info in archive.infolist():
            _check_cancelled(
                cancel_callback
            )

            relative_path = (
                safe_member_relative_path(
                    info.filename
                )
            )

            target = (
                destination
                / relative_path
            )

            if info.is_dir():
                target.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                continue

            if not info.is_file():
                raise ArchiveExtractionError(
                    (
                        "RAR enthält einen nicht "
                        "erlaubten Dateityp:\n"
                        f"{info.filename}"
                    )
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            try:
                input_file = archive.open(
                    info,
                    "r",
                )

            except rarfile.RarCannotExec as error:
                raise ArchiveExtractionError(
                    (
                        "RAR kann nicht entpackt werden, "
                        "weil kein unterstütztes "
                        "RAR-Backend gefunden wurde."
                    )
                ) from error

            with input_file:
                with target.open(
                    "xb"
                ) as output_file:
                    _copy_stream(
                        input_file=input_file,
                        output_file=output_file,
                        expected_size=(
                            info.file_size
                        ),
                        cancel_callback=(
                            cancel_callback
                        ),
                    )


# ============================================================
# 7-Zip
# ============================================================

def _extract_7z(
    *,
    source: Path,
    destination: Path,
    cancel_callback: (
        CancelCallback
        | None
    ),
) -> None:
    _check_cancelled(
        cancel_callback
    )

    try:
        with py7zr.SevenZipFile(
            source,
            mode="r",
            max_extract_size=(
                MAX_TOTAL_UNCOMPRESSED
            ),
        ) as archive:
            archive.extractall(
                path=destination
            )

    except Exception as error:
        raise ArchiveExtractionError(
            (
                "7-Zip-Archiv konnte nicht "
                f"extrahiert werden:\n{error}"
            )
        ) from error

    _check_cancelled(
        cancel_callback
    )


# ============================================================
# Stream-Copy
# ============================================================

def _copy_stream(
    *,
    input_file,
    output_file,
    expected_size: int,
    cancel_callback: (
        CancelCallback
        | None
    ),
) -> None:
    written = 0

    while True:
        _check_cancelled(
            cancel_callback
        )

        chunk = input_file.read(
            CHUNK_SIZE
        )

        if not chunk:
            break

        written += len(
            chunk
        )

        if (
            written
            > MAX_SINGLE_FILE_SIZE
        ):
            raise ArchiveExtractionError(
                (
                    "Eine extrahierte Datei "
                    "überschreitet das "
                    "Sicherheitslimit."
                )
            )

        output_file.write(
            chunk
        )

    if (
        expected_size >= 0
        and written
        != expected_size
    ):
        raise ArchiveExtractionError(
            (
                "Eine Archivdatei wurde "
                "nicht vollständig extrahiert."
            )
        )


# ============================================================
# Nachkontrolle
# ============================================================

def _verify_extracted_tree(
    root: Path,
) -> None:
    root_resolved = (
        root.resolve()
    )

    entry_count = 0

    total_size = 0

    for path in root.rglob(
        "*"
    ):
        entry_count += 1

        if (
            entry_count
            > MAX_ARCHIVE_ENTRIES
        ):
            raise ArchiveExtractionError(
                (
                    "Zu viele Dateien wurden "
                    "extrahiert."
                )
            )

        try:
            file_stat = (
                path.lstat()
            )

        except OSError as error:
            raise ArchiveExtractionError(
                (
                    "Extrahierte Datei konnte "
                    f"nicht geprüft werden:\n{path}"
                )
            ) from error

        mode = (
            file_stat.st_mode
        )

        if stat.S_ISLNK(
            mode
        ):
            raise ArchiveExtractionError(
                (
                    "Nach der Extraktion wurde "
                    "ein symbolischer Link gefunden:\n"
                    f"{path}"
                )
            )

        if not (
            stat.S_ISDIR(
                mode
            )
            or stat.S_ISREG(
                mode
            )
        ):
            raise ArchiveExtractionError(
                (
                    "Nach der Extraktion wurde "
                    "ein nicht erlaubter "
                    f"Dateityp gefunden:\n{path}"
                )
            )

        try:
            path.resolve().relative_to(
                root_resolved
            )

        except ValueError as error:
            raise ArchiveExtractionError(
                (
                    "Extrahierter Pfad liegt "
                    "außerhalb des Zielverzeichnisses."
                )
            ) from error

        if stat.S_ISREG(
            mode
        ):
            total_size += (
                file_stat.st_size
            )

            if (
                file_stat.st_size
                > MAX_SINGLE_FILE_SIZE
            ):
                raise ArchiveExtractionError(
                    (
                        "Extrahierte Datei ist "
                        "zu groß."
                    )
                )

            if (
                total_size
                > MAX_TOTAL_UNCOMPRESSED
            ):
                raise ArchiveExtractionError(
                    (
                        "Extrahierte Gesamtgröße "
                        "überschreitet das Limit."
                    )
                )


def _check_cancelled(
    callback: (
        CancelCallback
        | None
    ),
) -> None:
    if (
        callback is not None
        and callback()
    ):
        raise ArchiveExtractionCancelled(
            "Archivextraktion wurde abgebrochen."
        )