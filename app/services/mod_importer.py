from __future__ import annotations

import shutil
import tempfile
import time
import uuid

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from app.platform_support import (
    paths_overlap,
    sanitize_path_segment,
)

from app.services.archive_extractor import (
    ArchiveExtractionCancelled,
    ArchiveExtractionError,
    extract_archive_securely,
)

from app.services.archive_security import (
    is_supported_archive,
)


MANAGER_MARKER = ".gmm-managed.json"

SUPPORTED_ARCHIVE_SUFFIXES = (
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tbz2",
    ".tgz",
    ".txz",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
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
    """Das Archiv konnte nicht sicher verarbeitet werden."""


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

        library = (
            Path(library_root)
            .expanduser()
            .absolute()
        )

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

            if progress_callback is not None:
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

            results.append(
                result
            )

            if progress_callback is not None:
                progress_callback(
                    index,
                    total_sources,
                    source.name,
                )

        return ImportBatchResult(
            items=tuple(results),
            duration_seconds=(
                time.monotonic()
                - started_at
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
            if paths_overlap(
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

        if (
            source.is_file()
            and is_supported_archive(source)
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
        self._check_cancelled(cancel_callback)

        try:
            import_source = self._select_mod_source(
                root=source,
                display_name=source.name,
                cancel_callback=cancel_callback,
            )
        except ModImportError as error:
            return ImportItemResult(
                source=source,
                destination=None,
                status=ImportStatus.FAILED,
                message=str(error),
            )

        destination = self._select_destination(
            target_root=target_root,
            requested_name=import_source.name,
            conflict_policy=options.conflict_policy,
        )
        if destination is None:
            return ImportItemResult(
                source=source,
                destination=None,
                status=ImportStatus.SKIPPED,
                message="Ein gleichnamiger Mod existiert bereits.",
            )

        self._copy_tree_atomic(
            source=import_source,
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
        self._check_cancelled(
            cancel_callback
        )

        with tempfile.TemporaryDirectory(
            prefix="xxmimm-import-"
        ) as temporary_directory:
            extraction_root = Path(
                temporary_directory
            )

            self._extract_archive(
                archive_path=archive_path,
                extraction_root=extraction_root,
                cancel_callback=cancel_callback,
            )

            self._check_cancelled(
                cancel_callback
            )

            (
                import_source,
                requested_name,
            ) = self._select_extracted_root(
                extraction_root=extraction_root,
                archive_path=archive_path,
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
        if not is_supported_archive(
            archive_path
        ):
            raise UnsupportedArchiveError(
                "Nicht unterstütztes Archiv: "
                f"{archive_path.name}"
            )

        self._check_cancelled(
            cancel_callback
        )

        try:
            extract_archive_securely(
                source=archive_path,
                destination=extraction_root,
                cancel_callback=cancel_callback,
            )

        except ArchiveExtractionCancelled as error:
            raise ImportCancelledError(
                "Der Import wurde abgebrochen."
            ) from error

        except ArchiveExtractionError as error:
            raise UnsafeArchiveError(
                str(error)
            ) from error

        self._check_cancelled(
            cancel_callback
        )

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
                f"xxmimm-import-{uuid.uuid4().hex}.tmp"
            )
        )

        try:
            if (
                temporary_destination.exists()
                or temporary_destination.is_symlink()
            ):
                self._remove_path(
                    temporary_destination
                )

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
            try:
                if (
                    temporary_destination.exists()
                    or temporary_destination.is_symlink()
                ):
                    self._remove_path(
                        temporary_destination
                    )
            except OSError:
                pass

            raise

    def _select_extracted_root(
        self,
        extraction_root: Path,
        archive_path: Path,
    ) -> tuple[Path, str]:
        """
        Wählt aus einem entpackten Archiv ausschließlich den eigentlichen
        Mod-Ordner aus. README-Dateien, Screenshots und sonstige Dateien
        neben dem Mod werden dadurch nicht mehr in die Library kopiert.
        """
        import_source = self._select_mod_source(
            root=extraction_root,
            display_name=archive_path.name,
            cancel_callback=None,
        )

        if import_source == extraction_root:
            requested_name = archive_name_without_suffix(
                archive_path
            )
        else:
            requested_name = import_source.name

        return (
            import_source,
            sanitize_path_segment(requested_name),
        )

    def _select_mod_source(
        self,
        *,
        root: Path,
        display_name: str,
        cancel_callback: CancelCallback | None,
    ) -> Path:
        """Findet einen eindeutigen Mod-Ordner innerhalb von *root*."""
        if not root.is_dir():
            raise ModImportError(
                f"Die Mod-Quelle ist kein Ordner: {root}"
            )

        if self._has_direct_mod_marker(root):
            return root

        candidates = self._find_mod_candidates(
            root=root,
            cancel_callback=cancel_callback,
        )

        if not candidates:
            raise ModImportError(
                "Es wurde kein gültiger Mod-Ordner mit einer INI- oder "
                f"Metadaten-Datei gefunden: {display_name}"
            )

        if len(candidates) == 1:
            return candidates[0]

        common_parent = self._common_parent(candidates)
        if common_parent is not None and common_parent != root:
            # Mehrere INI-Unterordner können zu EINEM Mod gehören, z. B.
            # ModName/Body/*.ini + ModName/Head/*.ini. In diesem Fall ist
            # der gemeinsame Unterordner der tatsächliche Mod-Root.
            return common_parent

        names = ", ".join(
            candidate.relative_to(root).as_posix()
            for candidate in candidates[:8]
        )
        if len(candidates) > 8:
            names += ", ..."

        raise ModImportError(
            "Die Quelle enthält mehrere voneinander getrennte Mod-Ordner. "
            "Aus Sicherheitsgründen wird nicht der komplette Ordner "
            "kopiert. Importiere die Mods einzeln.\n\n"
            f"Gefunden: {names}"
        )

    def _find_mod_candidates(
        self,
        *,
        root: Path,
        cancel_callback: CancelCallback | None,
        max_depth: int = 6,
    ) -> list[Path]:
        candidates: list[Path] = []
        root_depth = len(root.parts)

        def scan(directory: Path) -> None:
            self._check_cancelled(cancel_callback)

            depth = len(directory.parts) - root_depth
            if depth > max_depth:
                return

            if directory != root and self._has_direct_mod_marker(directory):
                candidates.append(directory)
                return

            try:
                children = [
                    child
                    for child in directory.iterdir()
                    if (
                        child.is_dir()
                        and not child.is_symlink()
                        and not child.name.startswith(".")
                        and child.name != "__MACOSX"
                    )
                ]
            except OSError:
                return

            children.sort(key=lambda path: path.name.casefold())
            for child in children:
                scan(child)

        scan(root)
        return candidates

    @staticmethod
    def _has_direct_mod_marker(directory: Path) -> bool:
        try:
            for entry in directory.iterdir():
                if not entry.is_file():
                    continue

                lower_name = entry.name.casefold()
                if (
                    lower_name.endswith(".ini")
                    or lower_name in {
                        "mod.json",
                        "metadata.json",
                        "character.txt",
                        "characters.txt",
                    }
                ):
                    return True
        except OSError:
            return False

        return False

    @staticmethod
    def _common_parent(paths: list[Path]) -> Path | None:
        if not paths:
            return None

        common_parts = list(paths[0].parts)
        for path in paths[1:]:
            new_length = 0
            for left, right in zip(common_parts, path.parts):
                if left != right:
                    break
                new_length += 1
            common_parts = common_parts[:new_length]
            if not common_parts:
                return None

        return Path(*common_parts)
    def _select_destination(
        self,
        target_root: Path,
        requested_name: str,
        conflict_policy: ConflictPolicy,
    ) -> Path | None:
        safe_name = sanitize_path_segment(
            requested_name
        )

        if not safe_name:
            raise ModImportError(
                "Für den Mod konnte kein gültiger "
                "Zielname erzeugt werden."
            )

        destination = (
            target_root
            / safe_name
        )

        if not (
            destination.exists()
            or destination.is_symlink()
        ):
            return destination

        if (
            conflict_policy
            == ConflictPolicy.SKIP
        ):
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

        if (
            mod_type
            and not character
        ):
            raise ModImportError(
                "Für einen Mod-Typ muss auch ein Charakter "
                "angegeben werden."
            )

        if character:
            safe_character = sanitize_path_segment(
                character
            )

            if not safe_character:
                raise ModImportError(
                    "Der angegebene Charaktername ist ungültig."
                )

            target_root /= (
                safe_character
            )

        if mod_type:
            safe_mod_type = sanitize_path_segment(
                mod_type
            )

            if not safe_mod_type:
                raise ModImportError(
                    "Der angegebene Mod-Typ ist ungültig."
                )

            target_root /= (
                safe_mod_type
            )

        return target_root

    @staticmethod
    def _copy_ignore(
        _directory: str,
        names: list[str],
    ) -> set[str]:
        ignored = {
            MANAGER_MARKER,
            f"{MANAGER_MARKER}.tmp",
            ".xxmimm-managed.json",
            ".xxmimm-managed.json.tmp",
        }

        return {
            name
            for name in names
            if name in ignored
        }

    @staticmethod
    def _remove_path(
        path: Path,
    ) -> None:
        if (
            path.is_dir()
            and not path.is_symlink()
        ):
            shutil.rmtree(
                path
            )
            return

        path.unlink(
            missing_ok=True
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
    """
    Legacy-kompatibler Alias.
    """

    return is_supported_archive(
        path
    )


def is_supported_import_source(
    path: Path | str,
) -> bool:
    path = (
        Path(path)
        .expanduser()
    )

    if path.is_dir():
        return True

    if not path.is_file():
        return False

    return is_supported_archive(
        path
    )


def archive_name_without_suffix(
    path: Path,
) -> str:
    name = path.name
    lower_name = name.casefold()

    for suffix in sorted(
        SUPPORTED_ARCHIVE_SUFFIXES,
        key=len,
        reverse=True,
    ):
        if not lower_name.endswith(
            suffix
        ):
            continue

        name = name[
            : -len(suffix)
        ]

        break

    safe_name = sanitize_path_segment(
        name
    )

    if not safe_name:
        return "Imported Mod"

    return safe_name
