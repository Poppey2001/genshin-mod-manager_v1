from __future__ import annotations

from logging import root
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models.mod import ModInfo
from app.services.character_detector import detect_characters
from app.services.mod_structure_detector import (
    detect_mod_structure,
)

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]



NETWORK_FILESYSTEMS = {
    "cifs",
    "smb3",
    "nfs",
    "nfs4",
    "sshfs",
    "fuse.sshfs",
    "fuse.gvfsd-fuse",
    "davfs",
    "davfs2",
    "fuse.rclone",
    "fuse.s3fs",
    "ceph",
    "glusterfs",
    "afs",
}

IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
}

PREVIEW_FILENAMES = {
    "preview.png",
    "preview.jpg",
    "preview.jpeg",
    "thumbnail.png",
    "thumbnail.jpg",
    "cover.png",
    "cover.jpg",
    "icon.png",
    "icon.jpg",
}

MOD_MARKER_FILES = {
    "mod.json",
    "metadata.json",
    "character.txt",
    "characters.txt",
}

MAX_SCAN_DEPTH = 4

class ScanCancelledError(Exception):
    """Wird ausgelöst, wenn ein Scan abgebrochen wurde."""


@dataclass(slots=True)
class MountInfo:
    mount_point: Path
    filesystem: str
    source: str


@dataclass(slots=True)
class ScanResult:
    root_path: Path
    is_network: bool
    mods: list[ModInfo]
    duration_seconds: float


class ModScanner:
    """
    Scannt einen Mods-Ordner.

    Der Scanner funktioniert mit lokalen Verzeichnissen und mit
    unter Linux eingehängten Netzlaufwerken.
    """

    def __init__(
        self,
        calculate_network_sizes: bool = False,
    ) -> None:
        self.calculate_network_sizes = calculate_network_sizes

    def scan(
        self,
        root_path: Path | str,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> ScanResult:
        started_at = time.monotonic()

        root_text = str(root_path)

        if "://" in root_text:
            raise ValueError(
                "Netzwerkadressen wie smb:// werden nicht direkt "
                "unterstützt. Binde das Netzlaufwerk zuerst unter "
                "/mnt, /media oder über GVFS ein."
            )

        root = Path(root_path).expanduser()

        if not root.exists():
            raise FileNotFoundError(
                f"Der Mods-Ordner existiert nicht: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Der Mods-Pfad ist kein Verzeichnis: {root}"
            )

        mount_table = read_mount_table()
        root_is_network = is_network_path(
            root,
            mount_table,
        )

        mod_directories = self._find_mod_directories(
            root=root,
            cancel_callback=cancel_callback,
        )

        total_mods = len(mod_directories)
        found_mods: list[ModInfo] = []

        if progress_callback:
            progress_callback(
                0,
                total_mods,
                "Scan wird vorbereitet",
            )

        for index, mod_directory in enumerate(
            mod_directories,
            start=1,
        ):
            self._check_cancelled(cancel_callback)

            mod_info = self._scan_mod_directory(
                library_root=root,
                mod_directory=mod_directory,
                mount_table=mount_table,
                cancel_callback=cancel_callback,
            )

            found_mods.append(mod_info)

            if progress_callback:
                progress_callback(
                    index,
                    total_mods,
                    mod_info.name,
                )

        duration = time.monotonic() - started_at

        return ScanResult(
            root_path=root,
            is_network=root_is_network,
            mods=found_mods,
            duration_seconds=duration,
        )

    def _find_mod_directories(
        self,
        root: Path,
        cancel_callback: CancelCallback | None,
    ) -> list[Path]:
        """
        Findet direkte und verschachtelte Mods.

        Unterstützte Beispiele:

        Bibliothek/Mod
        Bibliothek/Charakter/Mod
        Bibliothek/Charakter/Character Skin/Mod
        """

        found_mods: list[Path] = []

        def scan_directory(
            directory: Path,
            depth: int,
        ) -> None:
            self._check_cancelled(
                cancel_callback
            )

            if depth > MAX_SCAN_DEPTH:
                return

            try:
                entries = list(
                 os.scandir(directory)
            )
            except (
                OSError,
                PermissionError,
            ):
                return

            directories: list[Path] = []
            has_direct_mod_marker = False

            for entry in entries:
                self._check_cancelled(
                    cancel_callback
                )

                if entry.name.startswith("."):
                    continue

                try:
                    if entry.is_file(
                        follow_symlinks=False
                    ):
                        lower_name = entry.name.casefold()

                        if (
                            lower_name.endswith(".ini")
                            or lower_name in MOD_MARKER_FILES
                        ):
                            has_direct_mod_marker = True

                    elif entry.is_dir(
                        follow_symlinks=True
                    ):
                        if (
                            entry.name
                            not in IGNORED_DIRECTORIES
                        ):
                            directories.append(
                                Path(entry.path)
                            )

                except OSError:
                    continue

            # Ein Ordner mit einer direkten INI- oder Metadaten-Datei
            # wird als eigentlicher Mod behandelt.
            if depth >= 1 and has_direct_mod_marker:
                found_mods.append(directory)
                return

            # Bei der Struktur Charakter / Typ / Mod ist die dritte
            # Ebene der Mod-Ordner. Dort suchen wir zusätzlich in
            # Unterordnern nach INI-Dateien.
            if (
                depth >= 3
                and self._contains_mod_marker(
                    directory,
                    cancel_callback,
                )
            ):
                found_mods.append(directory)
                return

            directories.sort(
                key=lambda path: path.name.casefold()
            )

            for child_directory in directories:
                scan_directory(
                    child_directory,
                    depth + 1,
                )

        try:
            root_directories = []

            with os.scandir(root) as entries:
                for entry in entries:
                    self._check_cancelled(
                        cancel_callback
                    )

                    if entry.name.startswith("."):
                        continue

                    try:
                        if entry.is_dir(
                            follow_symlinks=True
                        ):
                            root_directories.append(
                                Path(entry.path)
                            )
                    except OSError:
                        continue

        except PermissionError as error:
            raise PermissionError(
                f"Keine Leseberechtigung für: {root}"
            ) from error

        root_directories.sort(
            key=lambda path: path.name.casefold()
        )

        for directory in root_directories:
            scan_directory(
                directory,
                depth=1,
            )

        found_mods.sort(
            key=lambda path: str(path).casefold()
        )

        return found_mods    
    def _contains_mod_marker(
        self,
        directory: Path,
        cancel_callback: CancelCallback | None,
    ) -> bool:
        """
        Prüft einen Mod-Ordner und höchstens zwei Unterebenen
        auf INI- oder Metadaten-Dateien.
        """

        directory_depth = len(
            directory.parts
        )

        try:
            for current_directory, directory_names, file_names in os.walk(
                directory,
                followlinks=False,
            ):
                self._check_cancelled(
                    cancel_callback
                )

                current_path = Path(
                    current_directory
                )

                current_depth = (
                    len(current_path.parts)
                    - directory_depth
                )

                if current_depth >= 2:
                    directory_names[:] = []

                directory_names[:] = [
                    name
                    for name in directory_names
                    if (
                        name not in IGNORED_DIRECTORIES
                        and not name.startswith(".")
                    )
                ]

                for file_name in file_names:
                    lower_name = file_name.casefold()

                    if (
                        lower_name.endswith(".ini")
                        or lower_name in MOD_MARKER_FILES
                    ):
                        return True

        except OSError:
            return False

        return False
    
    def _scan_mod_directory(
        self,
        library_root: Path,
        mod_directory: Path,
        mount_table: list[MountInfo],
        cancel_callback: CancelCallback | None,
    ) -> ModInfo:
        file_count = 0
        ini_file_count = 0
        total_size = 0

        preview_path: Path | None = None
        errors: list[str] = []

        network_path = is_network_path(
            mod_directory,
            mount_table,
        )

        characters = detect_characters(
            mod_directory
        )
        calculate_size = (
            not network_path
            or self.calculate_network_sizes
        )
        
        structure = detect_mod_structure(
            library_root=library_root,
            mod_directory=mod_directory,
        )
        
        detected_characters = list(
            detect_characters(
                mod_directory
            )
        )

        if(
            structure.character
            and structure.character.casefold()
            not in {
                character.casefold()
                for character in detected_characters
            }
        ):
            detected_characters.insert(
                0,
                structure.character,
            )
        characters = tuple(
            detected_characters
        )
        try:
            modified_at = (
                mod_directory.stat().st_mtime
            )
        except OSError as error:
            modified_at = None
            errors.append(str(error))

        def handle_walk_error(
            error: OSError,
        ) -> None:
            errors.append(str(error))

        try:
            for (
                current_directory,
                directory_names,
                file_names,
            ) in os.walk(
                mod_directory,
                followlinks=False,
                onerror=handle_walk_error,
            ):
                self._check_cancelled(
                    cancel_callback
                )

                directory_names[:] = [
                    name
                    for name in directory_names
                    if name not in IGNORED_DIRECTORIES
                ]

                current_path = Path(
                    current_directory
                )

                for file_name in file_names:
                    self._check_cancelled(
                        cancel_callback
                    )

                    file_count += 1

                    file_path = (
                        current_path / file_name
                    )

                    lower_name = file_name.casefold()

                    if lower_name.endswith(".ini"):
                        ini_file_count += 1

                    if (
                        preview_path is None
                        and lower_name
                        in PREVIEW_FILENAMES
                    ):
                        preview_path = file_path

                    if calculate_size:
                        try:
                            total_size += (
                                file_path.stat().st_size
                            )
                        except OSError as error:
                            if len(errors) < 5:
                                errors.append(
                                    str(error)
                                )

        except OSError as error:
            errors.append(str(error))

        error_message: str | None = None

        if errors:
            unique_errors = list(
                dict.fromkeys(errors)
            )

            error_message = "; ".join(
                unique_errors[:3]
            )

        return ModInfo(
            name=mod_directory.name,
            path=mod_directory,
            is_symlink=mod_directory.is_symlink(),
            is_network=network_path,
            file_count=file_count,
            ini_file_count=ini_file_count,
            total_size=(
                total_size
                if calculate_size
                else None
            ),
            modified_at=modified_at,
            preview_path=preview_path,
            error=error_message,
            characters=characters,
            mod_type=structure.mod_type,
            relative_path=structure.relative_path,
        )

    @staticmethod
    def _check_cancelled(
        cancel_callback: CancelCallback | None,
    ) -> None:
        if (
            cancel_callback is not None
            and cancel_callback()
        ):
            raise ScanCancelledError()


def read_mount_table() -> list[MountInfo]:
    """
    Liest die Linux-Mount-Tabelle.

    /proc/self/mountinfo enthält auch CIFS-, NFS- und
    GVFS-Einhängepunkte.
    """
    mountinfo_file = Path(
        "/proc/self/mountinfo"
    )

    if not mountinfo_file.exists():
        return []

    mounts: list[MountInfo] = []

    try:
        lines = mountinfo_file.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

    except OSError:
        return []

    for line in lines:
        try:
            left_side, right_side = line.split(
                " - ",
                maxsplit=1,
            )

            left_fields = left_side.split()
            right_fields = right_side.split()

            if (
                len(left_fields) < 5
                or len(right_fields) < 2
            ):
                continue

            mount_point = Path(
                decode_mount_field(
                    left_fields[4]
                )
            )

            filesystem = right_fields[0]
            source = decode_mount_field(
                right_fields[1]
            )

            mounts.append(
                MountInfo(
                    mount_point=mount_point,
                    filesystem=filesystem,
                    source=source,
                )
            )

        except (
            ValueError,
            IndexError,
        ):
            continue

    mounts.sort(
        key=lambda mount: len(
            str(mount.mount_point)
        ),
        reverse=True,
    )

    return mounts


def decode_mount_field(
    value: str,
) -> str:
    """Dekodiert Escape-Sequenzen aus mountinfo."""
    return (
        value
        .replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def is_network_path(
    path: Path | str,
    mount_table: list[MountInfo] | None = None,
) -> bool:
    """Prüft, ob ein Pfad auf einem Netzlaufwerk liegt."""
    candidate = Path(path).expanduser()

    try:
        candidate = candidate.resolve(
            strict=False
        )
    except OSError:
        candidate = candidate.absolute()

    candidate_text = str(candidate)

    if (
        "/gvfs/" in candidate_text
        and candidate_text.startswith(
            "/run/user/"
        )
    ):
        return True

    mounts = (
        mount_table
        if mount_table is not None
        else read_mount_table()
    )

    for mount in mounts:
        if not path_is_inside(
            candidate,
            mount.mount_point,
        ):
            continue

        filesystem = (
            mount.filesystem.casefold()
        )

        source = mount.source.casefold()

        if filesystem in NETWORK_FILESYSTEMS:
            return True

        if source.startswith("//"):
            return True

        if (
            ":" in source
            and filesystem.startswith("nfs")
        ):
            return True

        return False

    return False


def path_is_inside(
    path: Path,
    parent: Path,
) -> bool:
    """Prüft, ob path innerhalb von parent liegt."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False