from __future__ import annotations

import hashlib
import os
import shutil
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]

# Manager metadata exists only on Active-Mods copies and must not make an
# otherwise identical Library mod appear different.
IGNORED_FILE_NAMES = frozenset(
    {
        ".gmm-managed.json",
        ".xxmimm-managed.json",
    }
)

CHUNK_SIZE = 1024 * 1024


class DuplicateCheckError(RuntimeError):
    """A duplicate scan could not be completed safely."""


class DuplicateCheckCancelled(DuplicateCheckError):
    """The user cancelled the duplicate scan."""


@dataclass(frozen=True, slots=True)
class DirectoryFingerprint:
    crc32: str
    sha256: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class DuplicateCheckResult:
    source: Path
    source_fingerprint: DirectoryFingerprint
    duplicate_path: Path | None = None
    duplicate_fingerprint: DirectoryFingerprint | None = None

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_path is not None


@dataclass(frozen=True, slots=True)
class _Entry:
    path: Path
    relative: str
    kind: str
    size: int
    link_target: str = ""


class ModDuplicateService:
    """Pure-Python CRC32/SHA256 duplicate checker.

    No ORFix, external SHA256 executable or normalizer is used here. That is
    intentional: a duplicate check must work in Windows and Linux/AppImage
    even when no optional repair tool is configured.
    """

    def check_for_duplicate(
        self,
        *,
        source: Path | str,
        library_paths: Iterable[Path | str],
        game_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> DuplicateCheckResult:
        del game_id  # reserved for future game-specific policies

        source_path = self._validated_directory(source, label="source")
        candidates: list[Path] = []
        source_key = self._resolved_key(source_path)

        for value in library_paths:
            candidate = Path(value).expanduser().absolute()
            if not candidate.is_dir() or candidate.is_symlink():
                continue
            if self._resolved_key(candidate) == source_key:
                continue
            candidates.append(candidate)

        source_entries = self._entries(source_path)
        candidate_entries = [
            (candidate, self._entries(candidate))
            for candidate in candidates
        ]

        total_work = len(source_entries) + sum(
            len(entries)
            for _candidate, entries in candidate_entries
        )
        total_work = max(total_work, 1)
        current = 0

        source_fingerprint, current = self._fingerprint_entries(
            source_path,
            source_entries,
            current=current,
            total=total_work,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

        for candidate, entries in candidate_entries:
            self._check_cancelled(cancel_callback)

            candidate_count = len(entries)
            candidate_size = sum(entry.size for entry in entries)

            if (
                candidate_count != source_fingerprint.file_count
                or candidate_size != source_fingerprint.total_bytes
            ):
                current += candidate_count
                if progress_callback is not None:
                    progress_callback(
                        min(current, total_work),
                        total_work,
                        candidate.name,
                    )
                continue

            candidate_fingerprint, current = self._fingerprint_entries(
                candidate,
                entries,
                current=current,
                total=total_work,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )

            if (
                candidate_fingerprint.sha256 == source_fingerprint.sha256
                and candidate_fingerprint.crc32 == source_fingerprint.crc32
            ):
                return DuplicateCheckResult(
                    source=source_path,
                    source_fingerprint=source_fingerprint,
                    duplicate_path=candidate,
                    duplicate_fingerprint=candidate_fingerprint,
                )

        return DuplicateCheckResult(
            source=source_path,
            source_fingerprint=source_fingerprint,
        )

    # Compatibility aliases for older workers / development builds.
    def check_duplicate(self, **kwargs) -> DuplicateCheckResult:
        return self.check_for_duplicate(**kwargs)

    def check(self, **kwargs) -> DuplicateCheckResult:
        return self.check_for_duplicate(**kwargs)

    def delete_confirmed_duplicate(
        self,
        *,
        result: DuplicateCheckResult,
        active_root: Path | str,
    ) -> None:
        """Delete only the redundant Active-Mods source after re-verifying it.

        The Library copy is never deleted. Both sides are hashed again directly
        before deletion so a stale UI result cannot remove a changed folder.
        """

        if not result.is_duplicate or result.duplicate_path is None:
            raise DuplicateCheckError("No confirmed duplicate is available.")

        source = self._validated_directory(result.source, label="source")
        library_copy = self._validated_directory(
            result.duplicate_path,
            label="library duplicate",
        )
        root = Path(active_root).expanduser().absolute()

        if not root.is_dir():
            raise DuplicateCheckError(
                f"Active Mods directory does not exist: {root}"
            )

        if not self._is_within(source, root):
            raise DuplicateCheckError(
                "Refusing to delete a duplicate outside the Active Mods directory."
            )

        source_now = self._fingerprint_directory(source)
        library_now = self._fingerprint_directory(library_copy)

        if (
            source_now.sha256 != library_now.sha256
            or source_now.crc32 != library_now.crc32
        ):
            raise DuplicateCheckError(
                "The folders changed after the duplicate check. Nothing was deleted."
            )

        if source.is_symlink():
            raise DuplicateCheckError("Refusing to delete a symbolic-link directory.")

        try:
            shutil.rmtree(source)
        except OSError as error:
            raise DuplicateCheckError(
                f"The confirmed duplicate could not be deleted: {error}"
            ) from error

    def _fingerprint_directory(self, root: Path) -> DirectoryFingerprint:
        entries = self._entries(root)
        fingerprint, _current = self._fingerprint_entries(
            root,
            entries,
            current=0,
            total=max(len(entries), 1),
            progress_callback=None,
            cancel_callback=None,
        )
        return fingerprint

    def _fingerprint_entries(
        self,
        root: Path,
        entries: list[_Entry],
        *,
        current: int,
        total: int,
        progress_callback: ProgressCallback | None,
        cancel_callback: CancelCallback | None,
    ) -> tuple[DirectoryFingerprint, int]:
        sha = hashlib.sha256()
        crc = 0
        total_bytes = 0

        # Versioned domain separator makes future format changes explicit.
        header = b"GMM-DIRECTORY-FINGERPRINT-V2\0"
        sha.update(header)
        crc = zlib.crc32(header, crc)

        for entry in entries:
            self._check_cancelled(cancel_callback)

            metadata = (
                f"{entry.kind}\0{entry.relative}\0{entry.size}\0"
            ).encode("utf-8", errors="surrogateescape")
            sha.update(metadata)
            crc = zlib.crc32(metadata, crc)

            if entry.kind == "link":
                link_data = entry.link_target.encode(
                    "utf-8",
                    errors="surrogateescape",
                )
                sha.update(link_data)
                crc = zlib.crc32(link_data, crc)
            else:
                try:
                    with entry.path.open("rb") as handle:
                        while True:
                            self._check_cancelled(cancel_callback)
                            chunk = handle.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            sha.update(chunk)
                            crc = zlib.crc32(chunk, crc)
                except OSError as error:
                    raise DuplicateCheckError(
                        f"Could not read file: {entry.path}\n\n{error}"
                    ) from error

            total_bytes += entry.size
            current += 1
            if progress_callback is not None:
                progress_callback(
                    min(current, total),
                    total,
                    entry.relative,
                )

        return (
            DirectoryFingerprint(
                crc32=f"{crc & 0xFFFFFFFF:08x}",
                sha256=sha.hexdigest(),
                file_count=len(entries),
                total_bytes=total_bytes,
            ),
            current,
        )

    def _entries(self, root: Path) -> list[_Entry]:
        result: list[_Entry] = []

        try:
            paths = sorted(
                root.rglob("*"),
                key=lambda path: (
                    path.relative_to(root).as_posix().casefold(),
                    path.relative_to(root).as_posix(),
                ),
            )
        except OSError as error:
            raise DuplicateCheckError(
                f"Could not enumerate directory: {root}\n\n{error}"
            ) from error

        for path in paths:
            relative = path.relative_to(root).as_posix()
            if path.name in IGNORED_FILE_NAMES:
                continue

            try:
                if path.is_symlink():
                    target = os.readlink(path)
                    data_size = len(
                        target.encode("utf-8", errors="surrogateescape")
                    )
                    result.append(
                        _Entry(
                            path=path,
                            relative=relative,
                            kind="link",
                            size=data_size,
                            link_target=target,
                        )
                    )
                    continue

                if not path.is_file():
                    continue

                result.append(
                    _Entry(
                        path=path,
                        relative=relative,
                        kind="file",
                        size=path.stat().st_size,
                    )
                )
            except OSError as error:
                raise DuplicateCheckError(
                    f"Could not inspect file: {path}\n\n{error}"
                ) from error

        return result

    @staticmethod
    def _validated_directory(value: Path | str, *, label: str) -> Path:
        path = Path(value).expanduser().absolute()
        if path.is_symlink() or not path.is_dir():
            raise DuplicateCheckError(
                f"Invalid {label} directory: {path}"
            )
        return path

    @staticmethod
    def _resolved_key(path: Path) -> str:
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            resolved = path.absolute()
        return os.path.normcase(str(resolved))

    @classmethod
    def _is_within(cls, child: Path, parent: Path) -> bool:
        try:
            child_resolved = child.resolve(strict=False)
            parent_resolved = parent.resolve(strict=False)
            return os.path.commonpath(
                (str(child_resolved), str(parent_resolved))
            ) == str(parent_resolved)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _check_cancelled(cancel_callback: CancelCallback | None) -> None:
        if cancel_callback is not None and cancel_callback():
            raise DuplicateCheckCancelled("Duplicate check was cancelled.")


__all__ = [
    "DirectoryFingerprint",
    "DuplicateCheckCancelled",
    "DuplicateCheckError",
    "DuplicateCheckResult",
    "ModDuplicateService",
]
