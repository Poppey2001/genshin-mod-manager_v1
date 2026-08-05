from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys
import unicodedata

from pathlib import Path
from typing import Final


IS_WINDOWS: Final = os.name == "nt"
IS_LINUX: Final = sys.platform.startswith("linux")
IS_MACOS: Final = sys.platform == "darwin"


WINDOWS_RESERVED_NAMES: Final = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


NETWORK_FILESYSTEM_TYPES: Final = {
    "9p",
    "afs",
    "ceph",
    "cifs",
    "davfs",
    "davfs2",
    "fuse.curlftpfs",
    "fuse.davfs",
    "fuse.gvfsd-fuse",
    "fuse.rclone",
    "fuse.sshfs",
    "fuseblk",
    "glusterfs",
    "nfs",
    "nfs4",
    "smb3",
    "sshfs",
}


class PlatformSupportError(Exception):
    """Fehler bei einer betriebssystemspezifischen Aktion."""


def absolute_path(
    path: Path | str,
) -> Path:
    """
    Erzeugt einen absoluten Pfad, ohne zu verlangen,
    dass der Pfad bereits existiert.
    """
    candidate = Path(path).expanduser()

    try:
        return candidate.resolve(
            strict=False
        )
    except OSError:
        return Path(
            os.path.abspath(
                os.fspath(candidate)
            )
        )


def normalized_path_key(
    path: Path | str,
) -> str:
    """
    Normalisiert einen Pfad für sichere Vergleiche.

    Windows behandelt Groß- und Kleinschreibung dabei
    als identisch.
    """
    value = os.path.abspath(
        os.path.expanduser(
            os.fspath(path)
        )
    )

    value = os.path.normpath(value)

    if IS_WINDOWS:
        value = os.path.normcase(value)

    return value


def paths_equal(
    first: Path | str,
    second: Path | str,
) -> bool:
    return (
        normalized_path_key(first)
        == normalized_path_key(second)
    )


def path_is_inside(
    path: Path | str,
    parent: Path | str,
    *,
    include_equal: bool = True,
) -> bool:
    """
    Prüft plattformübergreifend, ob ein Pfad innerhalb
    eines anderen Pfades liegt.
    """
    path_key = normalized_path_key(path)
    parent_key = normalized_path_key(parent)

    if path_key == parent_key:
        return include_equal

    try:
        common_path = os.path.commonpath(
            [
                path_key,
                parent_key,
            ]
        )
    except ValueError:
        # Unter Windows beispielsweise unterschiedliche Laufwerke.
        return False

    return common_path == parent_key


def paths_overlap(
    first: Path | str,
    second: Path | str,
) -> bool:
    """
    Erkennt, ob Pfade identisch sind oder einer im anderen liegt.
    """
    return (
        path_is_inside(first, second)
        or path_is_inside(second, first)
    )


def sanitize_path_segment(
    value: str,
    *,
    fallback: str = "Imported Mod",
    maximum_length: int = 180,
) -> str:
    """
    Erzeugt einen Linux- und Windows-kompatiblen Ordnernamen.

    Die Windows-Regeln werden auf allen Plattformen angewendet,
    damit eine Linux-Bibliothek später auch unter Windows
    verwendet werden kann.
    """
    cleaned = unicodedata.normalize(
        "NFKC",
        value,
    )

    cleaned = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        cleaned,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    cleaned = cleaned.strip(
        " ."
    )

    if not cleaned:
        cleaned = fallback

    # Auch CON.txt oder AUX.ini sind unter Windows reserviert.
    first_name_part = cleaned.split(
        ".",
        maxsplit=1,
    )[0].upper()

    if first_name_part in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    cleaned = cleaned[
        :maximum_length
    ].rstrip(
        " ."
    )

    if not cleaned:
        return fallback

    return cleaned


def is_network_path(
    path: Path | str,
) -> bool:
    """
    Erkennt UNC-Pfade, gemappte Windows-Netzlaufwerke
    und typische Linux-Netz-Dateisysteme.
    """
    if IS_WINDOWS:
        return _is_windows_network_path(path)

    if IS_LINUX:
        filesystem_type = _linux_filesystem_type(
            path
        )

        if filesystem_type is None:
            return False

        return (
            filesystem_type.casefold()
            in NETWORK_FILESYSTEM_TYPES
        )

    return False


def _is_windows_network_path(
    path: Path | str,
) -> bool:
    path_text = os.fspath(path)

    normalized = path_text.replace(
        "/",
        "\\",
    )

    # Normaler UNC-Pfad:
    # \\server\freigabe
    if normalized.startswith("\\\\"):
        return True

    # Erweiterter UNC-Pfad:
    # \\?\UNC\server\freigabe
    if normalized.casefold().startswith(
        "\\\\?\\unc\\"
    ):
        return True

    drive, _tail = os.path.splitdrive(
        normalized
    )

    if not drive:
        return False

    drive_root = f"{drive}\\"

    try:
        kernel32 = ctypes.WinDLL(
            "kernel32",
            use_last_error=True,
        )

        get_drive_type = (
            kernel32.GetDriveTypeW
        )

        get_drive_type.argtypes = [
            ctypes.c_wchar_p
        ]

        get_drive_type.restype = (
            ctypes.c_uint
        )

        drive_type = get_drive_type(
            drive_root
        )

    except (AttributeError, OSError):
        return False

    # GetDriveTypeW:
    # 4 = DRIVE_REMOTE
    return drive_type == 4


def _linux_filesystem_type(
    path: Path | str,
) -> str | None:
    mountinfo_path = Path(
        "/proc/self/mountinfo"
    )

    if not mountinfo_path.is_file():
        return None

    candidate = absolute_path(path)

    best_match_length = -1
    best_filesystem_type: str | None = None

    try:
        mountinfo_content = (
            mountinfo_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )
    except OSError:
        return None

    for line in mountinfo_content.splitlines():
        if " - " not in line:
            continue

        left_side, right_side = line.split(
            " - ",
            maxsplit=1,
        )

        left_fields = left_side.split()
        right_fields = right_side.split()

        if (
            len(left_fields) < 5
            or not right_fields
        ):
            continue

        mount_point_text = (
            _decode_mountinfo_path(
                left_fields[4]
            )
        )

        mount_point = Path(
            mount_point_text
        )

        if not path_is_inside(
            candidate,
            mount_point,
        ):
            continue

        mount_length = len(
            normalized_path_key(
                mount_point
            )
        )

        if mount_length <= best_match_length:
            continue

        best_match_length = mount_length
        best_filesystem_type = (
            right_fields[0]
        )

    return best_filesystem_type


def _decode_mountinfo_path(
    value: str,
) -> str:
    replacements = {
        r"\040": " ",
        r"\011": "\t",
        r"\012": "\n",
        r"\134": "\\",
    }

    for encoded, decoded in replacements.items():
        value = value.replace(
            encoded,
            decoded,
        )

    return value


def launcher_file_filter() -> str:
    if IS_WINDOWS:
        return (
            "Programme und Launcher "
            "(*.exe *.bat *.cmd *.com *.lnk);;"
            "Alle Dateien (*.*)"
        )

    if IS_MACOS:
        return (
            "Programme und Launcher "
            "(*.app *.command *.sh);;"
            "Alle Dateien (*)"
        )

    return (
        "Programme und Launcher "
        "(*.AppImage *.sh *.desktop);;"
        "Alle Dateien (*)"
    )


def launch_program(
    path: Path | str,
) -> None:
    """
    Startet einen Launcher mit dem nativen Mechanismus
    des Betriebssystems.
    """
    program_path = absolute_path(path)

    if not program_path.exists():
        raise PlatformSupportError(
            "Der Launcher wurde nicht gefunden.\n\n"
            f"Pfad: {program_path}"
        )

    try:
        if IS_WINDOWS:
            os.startfile(
                str(program_path)
            )
            return

        if IS_MACOS:
            subprocess.Popen(
                [
                    "open",
                    str(program_path),
                ],
                cwd=str(
                    program_path.parent
                ),
            )
            return

        if (
            program_path.is_file()
            and os.access(
                program_path,
                os.X_OK,
            )
            and (
                program_path.suffix.casefold()
                != ".desktop"
            )
        ):
            subprocess.Popen(
                [
                    str(program_path),
                ],
                cwd=str(
                    program_path.parent
                ),
            )
            return

        xdg_open = shutil.which(
            "xdg-open"
        )

        if xdg_open is None:
            raise PlatformSupportError(
                "xdg-open wurde nicht gefunden."
            )

        subprocess.Popen(
            [
                xdg_open,
                str(program_path),
            ],
            cwd=str(
                program_path.parent
            ),
        )

    except OSError as error:
        raise PlatformSupportError(
            "Der Launcher konnte nicht gestartet werden.\n\n"
            f"Pfad: {program_path}\n\n"
            f"{error}"
        ) from error


def reveal_in_file_manager(
    path: Path | str,
) -> None:
    """
    Öffnet einen Ordner beziehungsweise markiert eine Datei
    im nativen Dateimanager.
    """
    target = absolute_path(path)

    if not target.exists():
        raise PlatformSupportError(
            "Der Pfad wurde nicht gefunden.\n\n"
            f"Pfad: {target}"
        )

    try:
        if IS_WINDOWS:
            if target.is_file():
                subprocess.Popen(
                    [
                        "explorer.exe",
                        "/select,",
                        str(target),
                    ]
                )
            else:
                subprocess.Popen(
                    [
                        "explorer.exe",
                        str(target),
                    ]
                )

            return

        if IS_MACOS:
            if target.is_file():
                subprocess.Popen(
                    [
                        "open",
                        "-R",
                        str(target),
                    ]
                )
            else:
                subprocess.Popen(
                    [
                        "open",
                        str(target),
                    ]
                )

            return

        directory = (
            target
            if target.is_dir()
            else target.parent
        )

        xdg_open = shutil.which(
            "xdg-open"
        )

        if xdg_open is None:
            raise PlatformSupportError(
                "xdg-open wurde nicht gefunden."
            )

        subprocess.Popen(
            [
                xdg_open,
                str(directory),
            ]
        )

    except OSError as error:
        raise PlatformSupportError(
            "Der Dateimanager konnte nicht geöffnet werden.\n\n"
            f"{error}"
        ) from error


def resource_path(
    *parts: str,
) -> Path:
    """
    Liefert Ressourcenpfade sowohl im Quellprojekt
    als auch in einem PyInstaller-Build.
    """
    if getattr(
        sys,
        "frozen",
        False,
    ):
        bundle_root = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).parent,
            )
        )
    else:
        bundle_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

    return bundle_root.joinpath(
        *parts
    )


def configure_windows_app_id() -> None:
    """
    Setzt eine eigene Windows-Taskleisten-ID.
    """
    if not IS_WINDOWS:
        return

    try:
        shell32 = ctypes.WinDLL(
            "shell32",
            use_last_error=True,
        )

        shell32.SetCurrentProcessExplicitAppUserModelID(
            "CodeZer0Tw0.GenshinModManager"
        )

    except (AttributeError, OSError):
        pass