from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models.mod import ModInfo


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
        """Findet alle direkten Mod-Unterordner."""
        mod_directories: list[Path] = []

        try:
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
                            mod_directories.append(
                                Path(entry.path)
                            )

                    except OSError:
                        # Beispielsweise ein kaputter Symlink.
                        continue

        except PermissionError as error:
            raise PermissionError(
                f"Keine Leseberechtigung für: {root}"
            ) from error

        mod_directories.sort(
            key=lambda path: path.name.casefold()
        )

        return mod_directories

    def _scan_mod_directory(
        self,
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

        calculate_size = (
            not network_path
            or self.calculate_network_sizes
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