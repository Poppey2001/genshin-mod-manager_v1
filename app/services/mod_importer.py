from __future__ import annotations

import os
import re
import shutil
import stat
import tarfile
import tempfile
import time
import uuid
import zipfile

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable


MAX_ARCHIVE_FILES = 30_000
MAX_UNPACKED_SIZE = 20 * 1024 * 1024 * 1024
COPY_BUFFER_SIZE = 1024 * 1024

MANAGER_MARKER = ".gmm-managed.json"

SUPPORTED_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
)


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


class ConflictPolicy(str, Enum):
    """Verhalten bei bereits vorhandenen Zielordnern."""

    RENAME = "rename"
    SKIP = "skip"


class ImportStatus(str, Enum):
    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"


class ModImportError(Exception):
    """Grundfehler des Mod-Imports."""


class ImportCancelledError(ModImportError):
    """Der Import wurde vom Benutzer abgebrochen."""


class UnsafeArchiveError(ModImportError):
    """Das Archiv enthält unsichere Einträge."""


class UnsupportedArchiveError(ModImportError):
    """Das Archivformat wird nicht unterstützt."""


@dataclass(slots=True, frozen=True)
class ImportOptions:
    character: str | None = None
    mod_type: str | None = None
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME


@dataclass(slots=True, frozen=True)
class ImportItemResult:
    source: Path
    destination: Path | None
    status: ImportStatus
    message: str


@dataclass(slots=True, frozen=True)
class ImportBatchResult:
    items: tuple[ImportItemResult, ...]
    duration_seconds: float

    @property
    def imported_count(self) -> int:
        return sum(
            item.status == ImportStatus.IMPORTED
            for item in self.items
        )

    @property
    def skipped_count(self) -> int:
        return sum(
            item.status == ImportStatus.SKIPPED
            for item in self.items
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status == ImportStatus.FAILED
            for item in self.items
        )


class ModImporter:
    """Importiert Ordner und Archive in die Mod-Bibliothek."""

    def import_sources(
        self,
        sources: list[Path | str],
        library_root: Path | str,
        options: ImportOptions,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> ImportBatchResult:
        started_at = time.monotonic()

        library = Path(
            library_root
        ).expanduser().absolute()

        try:
            library.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            raise ModImportError(
                "Die Mod-Bibliothek konnte nicht erstellt werden.\n\n"
                f"Pfad: {library}\n\n"
                f"{error}"
            ) from error

        target_root = self._build_target_root(
            library_root=library,
            options=options,
        )

        try:
            target_root.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            raise ModImportError(
                "Der Import-Zielordner konnte nicht erstellt werden.\n\n"
                f"Pfad: {target_root}\n\n"
                f"{error}"
            ) from error

        normalized_sources = [
            Path(source).expanduser().absolute()
            for source in sources
        ]

        results: list[ImportItemResult] = []
        total_sources = len(normalized_sources)

        for index, source in enumerate(
            normalized_sources,
            start=1,
        ):
            self._check_cancelled(
                cancel_callback
            )

            if progress_callback:
                progress_callback(
                    index - 1,
                    total_sources,
                    f"Importiere {source.name}",
                )

            try:
                result = self._import_source(
                    source=source,
                    library_root=library,
                    target_root=target_root,
                    options=options,
                    cancel_callback=cancel_callback,
                )

            except ImportCancelledError:
                raise

            except Exception as error:
                result = ImportItemResult(
                    source=source,
                    destination=None,
                    status=ImportStatus.FAILED,
                    message=(
                        f"{type(error).__name__}: {error}"
                    ),
                )

            results.append(result)

            if progress_callback:
                progress_callback(
                    index,
                    total_sources,
                    source.name,
                )

        return ImportBatchResult(
            items=tuple(results),
            duration_seconds=(
                time.monotonic() - started_at
            ),
        )

    def _import_source(
        self,
        source: Path,
        library_root: Path,
        target_root: Path,
        options: ImportOptions,
        cancel_callback: CancelCallback | None,
    ) -> ImportItemResult:
        if not source.exists():
            return ImportItemResult(
                source=source,
                destination=None,
                status=ImportStatus.FAILED,
                message="Die Quelle existiert nicht.",
            )

        if source.is_dir():
            if self._paths_overlap(
                source,
                library_root,
            ):
                return ImportItemResult(
                    source=source,
                    destination=None,
                    status=ImportStatus.SKIPPED,
                    message=(
                        "Der Ordner liegt bereits innerhalb der "
                        "Mod-Bibliothek oder enthält diese."
                    ),
                )

            return self._import_directory(
                source=source,
                target_root=target_root,
                options=options,
                cancel_callback=cancel_callback,
            )

        if source.is_file() and has_supported_archive_suffix(
            source
        ):
            return self._import_archive(
                archive_path=source,
                target_root=target_root,
                options=options,
                cancel_callback=cancel_callback,
            )

        return ImportItemResult(
            source=source,
            destination=None,
            status=ImportStatus.SKIPPED,
            message="Nicht unterstützter Dateityp.",
        )

    def _import_directory(
        self,
        source: Path,
        target_root: Path,
        options: ImportOptions,
        cancel_callback: CancelCallback | None,
    ) -> ImportItemResult:
        destination = self._select_destination(
            target_root=target_root,
            requested_name=source.name,
            conflict_policy=options.conflict_policy,
        )

        if destination is None:
            return ImportItemResult(
                source=source,
                destination=None,
                status=ImportStatus.SKIPPED,
                message=(
                    "Ein gleichnamiger Mod existiert bereits."
                ),
            )

        self._copy_tree_atomic(
            source=source,
            destination=destination,
            cancel_callback=cancel_callback,
        )

        return ImportItemResult(
            source=source,
            destination=destination,
            status=ImportStatus.IMPORTED,
            message="Mod-Ordner wurde importiert.",
        )

    def _import_archive(
        self,
        archive_path: Path,
        target_root: Path,
        options: ImportOptions,
        cancel_callback: CancelCallback | None,
    ) -> ImportItemResult:
        with tempfile.TemporaryDirectory(
            prefix="gmm-import-"
        ) as temporary_directory:
            extraction_root = Path(
                temporary_directory
            )

            self._extract_archive(
                archive_path=archive_path,
                extraction_root=extraction_root,
                cancel_callback=cancel_callback,
            )

            import_source, requested_name = (
                self._select_extracted_root(
                    extraction_root=extraction_root,
                    archive_path=archive_path,
                )
            )

            destination = self._select_destination(
                target_root=target_root,
                requested_name=requested_name,
                conflict_policy=options.conflict_policy,
            )

            if destination is None:
                return ImportItemResult(
                    source=archive_path,
                    destination=None,
                    status=ImportStatus.SKIPPED,
                    message=(
                        "Ein gleichnamiger Mod existiert bereits."
                    ),
                )

            self._copy_tree_atomic(
                source=import_source,
                destination=destination,
                cancel_callback=cancel_callback,
            )

        return ImportItemResult(
            source=archive_path,
            destination=destination,
            status=ImportStatus.IMPORTED,
            message="Archiv wurde importiert.",
        )

    def _extract_archive(
        self,
        archive_path: Path,
        extraction_root: Path,
        cancel_callback: CancelCallback | None,
    ) -> None:
        if zipfile.is_zipfile(
            archive_path
        ):
            self._extract_zip(
                archive_path=archive_path,
                extraction_root=extraction_root,
                cancel_callback=cancel_callback,
            )
            return

        if tarfile.is_tarfile(
            archive_path
        ):
            self._extract_tar(
                archive_path=archive_path,
                extraction_root=extraction_root,
                cancel_callback=cancel_callback,
            )
            return

        raise UnsupportedArchiveError(
            f"Nicht unterstütztes Archiv: {archive_path.name}"
        )

    def _extract_zip(
        self,
        archive_path: Path,
        extraction_root: Path,
        cancel_callback: CancelCallback | None,
    ) -> None:
        total_written = 0

        with zipfile.ZipFile(
            archive_path,
            mode="r",
        ) as archive:
            entries = archive.infolist()

            if len(entries) > MAX_ARCHIVE_FILES:
                raise UnsafeArchiveError(
                    "Das Archiv enthält zu viele Dateien.\n\n"
                    f"Maximum: {MAX_ARCHIVE_FILES}"
                )

            declared_size = sum(
                entry.file_size
                for entry in entries
                if not entry.is_dir()
            )

            if declared_size > MAX_UNPACKED_SIZE:
                raise UnsafeArchiveError(
                    "Das Archiv ist entpackt zu groß.\n\n"
                    f"Maximum: {format_size(MAX_UNPACKED_SIZE)}"
                )

            for entry in entries:
                self._check_cancelled(
                    cancel_callback
                )

                if self._zip_entry_is_symlink(
                    entry
                ):
                    raise UnsafeArchiveError(
                        "Das ZIP-Archiv enthält eine "
                        "symbolische Verknüpfung.\n\n"
                        f"Eintrag: {entry.filename}"
                    )

                destination = self._safe_archive_target(
                    extraction_root=extraction_root,
                    member_name=entry.filename,
                )

                if destination is None:
                    continue

                if entry.is_dir():
                    destination.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    continue

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with archive.open(
                    entry,
                    mode="r",
                ) as source_file:
                    with destination.open(
                        "wb"
                    ) as destination_file:
                        total_written = self._copy_stream(
                            source=source_file,
                            destination=destination_file,
                            current_total=total_written,
                            cancel_callback=cancel_callback,
                        )

                mode = (
                    entry.external_attr >> 16
                ) & 0o777

                if mode:
                    try:
                        destination.chmod(mode)
                    except OSError:
                        pass

    def _extract_tar(
        self,
        archive_path: Path,
        extraction_root: Path,
        cancel_callback: CancelCallback | None,
    ) -> None:
        total_written = 0

        with tarfile.open(
            archive_path,
            mode="r:*",
        ) as archive:
            members = archive.getmembers()

            if len(members) > MAX_ARCHIVE_FILES:
                raise UnsafeArchiveError(
                    "Das Archiv enthält zu viele Einträge.\n\n"
                    f"Maximum: {MAX_ARCHIVE_FILES}"
                )

            declared_size = sum(
                member.size
                for member in members
                if member.isfile()
            )

            if declared_size > MAX_UNPACKED_SIZE:
                raise UnsafeArchiveError(
                    "Das Archiv ist entpackt zu groß.\n\n"
                    f"Maximum: {format_size(MAX_UNPACKED_SIZE)}"
                )

            for member in members:
                self._check_cancelled(
                    cancel_callback
                )

                if (
                    member.issym()
                    or member.islnk()
                    or member.isdev()
                    or member.isfifo()
                ):
                    raise UnsafeArchiveError(
                        "Das TAR-Archiv enthält einen nicht "
                        "erlaubten Link oder Gerätedatei-Eintrag.\n\n"
                        f"Eintrag: {member.name}"
                    )

                destination = self._safe_archive_target(
                    extraction_root=extraction_root,
                    member_name=member.name,
                )

                if destination is None:
                    continue

                if member.isdir():
                    destination.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    continue

                if not member.isfile():
                    continue

                extracted_file = archive.extractfile(
                    member
                )

                if extracted_file is None:
                    continue

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with extracted_file:
                    with destination.open(
                        "wb"
                    ) as destination_file:
                        total_written = self._copy_stream(
                            source=extracted_file,
                            destination=destination_file,
                            current_total=total_written,
                            cancel_callback=cancel_callback,
                        )

                try:
                    destination.chmod(
                        member.mode & 0o777
                    )
                except OSError:
                    pass

    def _copy_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        current_total: int,
        cancel_callback: CancelCallback | None,
    ) -> int:
        total_written = current_total

        while True:
            self._check_cancelled(
                cancel_callback
            )

            chunk = source.read(
                COPY_BUFFER_SIZE
            )

            if not chunk:
                break

            total_written += len(chunk)

            if total_written > MAX_UNPACKED_SIZE:
                raise UnsafeArchiveError(
                    "Das Archiv überschreitet beim Entpacken "
                    "die erlaubte Gesamtgröße."
                )

            destination.write(chunk)

        return total_written

    def _copy_tree_atomic(
        self,
        source: Path,
        destination: Path,
        cancel_callback: CancelCallback | None,
    ) -> None:
        self._check_cancelled(
            cancel_callback
        )

        temporary_destination = (
            destination.parent
            / (
                f".{destination.name}."
                f"gmm-import-{uuid.uuid4().hex}.tmp"
            )
        )

        try:
            shutil.copytree(
                source,
                temporary_destination,
                symlinks=False,
                ignore=self._copy_ignore,
                copy_function=shutil.copy2,
            )

            self._check_cancelled(
                cancel_callback
            )

            if (
                destination.exists()
                or destination.is_symlink()
            ):
                raise ModImportError(
                    "Das Importziel wurde während des Imports "
                    "von einem anderen Vorgang erstellt."
                )

            temporary_destination.rename(
                destination
            )

        except Exception:
            if temporary_destination.exists():
                shutil.rmtree(
                    temporary_destination,
                    ignore_errors=True,
                )

            raise

    def _select_extracted_root(
        self,
        extraction_root: Path,
        archive_path: Path,
    ) -> tuple[Path, str]:
        entries = [
            path
            for path in extraction_root.iterdir()
            if path.name not in {
                "__MACOSX",
                ".DS_Store",
            }
        ]

        if not entries:
            raise ModImportError(
                "Das Archiv enthält keine importierbaren Dateien."
            )

        if (
            len(entries) == 1
            and entries[0].is_dir()
        ):
            return (
                entries[0],
                sanitize_path_segment(
                    entries[0].name
                ),
            )

        return (
            extraction_root,
            archive_name_without_suffix(
                archive_path
            ),
        )

    def _select_destination(
        self,
        target_root: Path,
        requested_name: str,
        conflict_policy: ConflictPolicy,
    ) -> Path | None:
        safe_name = sanitize_path_segment(
            requested_name
        )

        destination = target_root / safe_name

        if not (
            destination.exists()
            or destination.is_symlink()
        ):
            return destination

        if conflict_policy == ConflictPolicy.SKIP:
            return None

        counter = 2

        while True:
            candidate = (
                target_root
                / f"{safe_name} ({counter})"
            )

            if not (
                candidate.exists()
                or candidate.is_symlink()
            ):
                return candidate

            counter += 1

    def _build_target_root(
        self,
        library_root: Path,
        options: ImportOptions,
    ) -> Path:
        target_root = library_root

        character = (
            options.character.strip()
            if options.character
            else ""
        )

        mod_type = (
            options.mod_type.strip()
            if options.mod_type
            else ""
        )

        if mod_type and not character:
            raise ModImportError(
                "Für einen Mod-Typ muss auch ein Charakter "
                "angegeben werden."
            )

        if character:
            target_root /= sanitize_path_segment(
                character
            )

        if mod_type:
            target_root /= sanitize_path_segment(
                mod_type
            )

        return target_root

    @staticmethod
    def _safe_archive_target(
        extraction_root: Path,
        member_name: str,
    ) -> Path | None:
        normalized_name = member_name.replace(
            "\\",
            "/",
        )

        if "\x00" in normalized_name:
            raise UnsafeArchiveError(
                "Das Archiv enthält einen ungültigen Dateinamen."
            )

        archive_path = PurePosixPath(
            normalized_name
        )

        if archive_path.is_absolute():
            raise UnsafeArchiveError(
                "Das Archiv enthält einen absoluten Pfad.\n\n"
                f"Eintrag: {member_name}"
            )

        parts = [
            part
            for part in archive_path.parts
            if part not in {
                "",
                ".",
            }
        ]

        if not parts:
            return None

        if any(
            part == ".."
            for part in parts
        ):
            raise UnsafeArchiveError(
                "Das Archiv versucht, außerhalb des "
                "Importordners zu schreiben.\n\n"
                f"Eintrag: {member_name}"
            )

        if re.match(
            r"^[A-Za-z]:$",
            parts[0],
        ):
            raise UnsafeArchiveError(
                "Das Archiv enthält einen Windows-Laufwerkspfad.\n\n"
                f"Eintrag: {member_name}"
            )

        return extraction_root.joinpath(
            *parts
        )

    @staticmethod
    def _zip_entry_is_symlink(
        entry: zipfile.ZipInfo,
    ) -> bool:
        unix_mode = (
            entry.external_attr >> 16
        )

        return stat.S_ISLNK(
            unix_mode
        )

    @staticmethod
    def _copy_ignore(
        _directory: str,
        names: list[str],
    ) -> set[str]:
        ignored = {
            MANAGER_MARKER,
            f"{MANAGER_MARKER}.tmp",
        }

        return {
            name
            for name in names
            if name in ignored
        }

    @staticmethod
    def _paths_overlap(
        first: Path,
        second: Path,
    ) -> bool:
        return (
            first == second
            or path_is_inside(first, second)
            or path_is_inside(second, first)
        )

    @staticmethod
    def _check_cancelled(
        cancel_callback: CancelCallback | None,
    ) -> None:
        if (
            cancel_callback is not None
            and cancel_callback()
        ):
            raise ImportCancelledError(
                "Der Import wurde abgebrochen."
            )


def has_supported_archive_suffix(
    path: Path | str,
) -> bool:
    lower_name = Path(path).name.casefold()

    return any(
        lower_name.endswith(suffix)
        for suffix in SUPPORTED_ARCHIVE_SUFFIXES
    )


def is_supported_import_source(
    path: Path | str,
) -> bool:
    candidate = Path(path)

    return (
        candidate.is_dir()
        or (
            candidate.is_file()
            and has_supported_archive_suffix(
                candidate
            )
        )
    )


def archive_name_without_suffix(
    path: Path,
) -> str:
    name = path.name

    for suffix in sorted(
        SUPPORTED_ARCHIVE_SUFFIXES,
        key=len,
        reverse=True,
    ):
        if name.casefold().endswith(suffix):
            name = name[
                : -len(suffix)
            ]
            break

    return sanitize_path_segment(
        name
    )


def sanitize_path_segment(
    value: str,
) -> str:
    cleaned = re.sub(
        r"[\\/\x00-\x1f]",
        "_",
        value,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    cleaned = cleaned.strip(
        " ."
    )

    if cleaned in {
        "",
        ".",
        "..",
    }:
        return "Imported Mod"

    return cleaned[:180]


def path_is_inside(
    path: Path,
    parent: Path,
) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def format_size(
    size: int,
) -> str:
    value = float(size)

    for unit in (
        "B",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
    ):
        if value < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"

            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"