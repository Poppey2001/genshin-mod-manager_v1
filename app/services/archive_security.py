from __future__ import annotations

import re
import stat
import tarfile
import zipfile

from dataclasses import (
    dataclass,
    field,
)

from enum import StrEnum

from pathlib import (
    Path,
    PurePosixPath,
)

import py7zr
import rarfile


# ============================================================
# Limits
# ============================================================

MAX_ARCHIVE_ENTRIES = 100_000

MAX_TOTAL_UNCOMPRESSED = (
    32
    * 1024
    * 1024
    * 1024
)

MAX_SINGLE_FILE_SIZE = (
    8
    * 1024
    * 1024
    * 1024
)

MAX_PATH_LENGTH = 1024

MAX_COMPONENT_LENGTH = 255

MAX_COMPRESSION_RATIO = 1000.0

MIN_RATIO_CHECK_SIZE = (
    64
    * 1024
    * 1024
)

MAX_REPORTED_WARNING_FILES = 25


# ============================================================
# Dateitypen
# ============================================================

EXECUTABLE_WARNING_SUFFIXES = {
    ".exe",
    ".com",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".scr",
    ".msi",
    ".msp",
    ".reg",
    ".lnk",
    ".jar",
    ".sh",
    ".desktop",
    ".py",
}


# DLL/ASI/SO sind bei Modding nicht automatisch schädlich.
# Deshalb nur WARNEN, niemals allein deshalb blockieren.
BINARY_REVIEW_SUFFIXES = {
    ".dll",
    ".asi",
    ".so",
    ".dylib",
}


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *{
        f"COM{index}"
        for index in range(
            1,
            10,
        )
    },
    *{
        f"LPT{index}"
        for index in range(
            1,
            10,
        )
    },
}


SUPPORTED_ARCHIVE_SUFFIXES = (
    ".zip",
    ".7z",
    ".rar",

    ".tar",
    ".tar.gz",
    ".tgz",

    ".tar.bz2",
    ".tbz2",

    ".tar.xz",
    ".txz",
)


# ============================================================
# Modelle
# ============================================================

class ArchiveKind(
    StrEnum
):
    ZIP = "zip"
    SEVEN_ZIP = "7z"
    RAR = "rar"
    TAR = "tar"


class ArchiveIssueSeverity(
    StrEnum
):
    WARNING = "warning"
    BLOCK = "block"


@dataclass(
    frozen=True,
    slots=True,
)
class ArchiveIssue:
    severity: ArchiveIssueSeverity

    code: str

    message: str

    member: str | None = None


@dataclass(
    slots=True,
)
class ArchiveSecurityReport:
    source: Path

    kind: ArchiveKind

    entry_count: int = 0

    total_uncompressed: int = 0

    issues: list[
        ArchiveIssue
    ] = field(
        default_factory=list
    )

    warning_files: list[
        str
    ] = field(
        default_factory=list
    )

    @property
    def blocked(
        self,
    ) -> bool:
        return any(
            issue.severity
            == ArchiveIssueSeverity.BLOCK
            for issue in self.issues
        )

    @property
    def warnings(
        self,
    ) -> tuple[
        ArchiveIssue,
        ...,
    ]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity
            == ArchiveIssueSeverity.WARNING
        )

    @property
    def blocking_issues(
        self,
    ) -> tuple[
        ArchiveIssue,
        ...,
    ]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity
            == ArchiveIssueSeverity.BLOCK
        )


class ArchiveSecurityError(
    RuntimeError
):
    """Archiv konnte nicht sicher untersucht werden."""


# ============================================================
# Erkennung
# ============================================================

def is_supported_archive(
    path: Path | str,
) -> bool:
    path = Path(
        path
    )

    filename = (
        path.name
        .casefold()
    )

    return any(
        filename.endswith(
            suffix
        )
        for suffix
        in SUPPORTED_ARCHIVE_SUFFIXES
    )


def detect_archive_kind(
    path: Path | str,
) -> ArchiveKind:
    path = Path(
        path
    )

    filename = (
        path.name
        .casefold()
    )

    if filename.endswith(
        ".zip"
    ):
        return ArchiveKind.ZIP

    if filename.endswith(
        ".7z"
    ):
        return ArchiveKind.SEVEN_ZIP

    if filename.endswith(
        ".rar"
    ):
        return ArchiveKind.RAR

    if any(
        filename.endswith(
            suffix
        )
        for suffix in (
            ".tar",
            ".tar.gz",
            ".tgz",
            ".tar.bz2",
            ".tbz2",
            ".tar.xz",
            ".txz",
        )
    ):
        return ArchiveKind.TAR

    raise ArchiveSecurityError(
        (
            "Nicht unterstütztes "
            f"Archivformat: {path.name}"
        )
    )


# ============================================================
# Öffentliche Prüfung
# ============================================================

def inspect_archive(
    path: Path | str,
) -> ArchiveSecurityReport:
    source = (
        Path(path)
        .expanduser()
        .absolute()
    )

    if not source.is_file():
        raise ArchiveSecurityError(
            (
                "Archiv wurde nicht "
                f"gefunden:\n{source}"
            )
        )

    kind = detect_archive_kind(
        source
    )

    report = (
        ArchiveSecurityReport(
            source=source,
            kind=kind,
        )
    )

    seen_paths: set[str] = set()

    try:
        if kind == ArchiveKind.ZIP:
            _inspect_zip(
                source=source,
                report=report,
                seen_paths=seen_paths,
            )

        elif (
            kind
            == ArchiveKind.SEVEN_ZIP
        ):
            _inspect_7z(
                source=source,
                report=report,
                seen_paths=seen_paths,
            )

        elif kind == ArchiveKind.RAR:
            _inspect_rar(
                source=source,
                report=report,
                seen_paths=seen_paths,
            )

        elif kind == ArchiveKind.TAR:
            _inspect_tar(
                source=source,
                report=report,
                seen_paths=seen_paths,
            )

    except ArchiveSecurityError:
        raise

    except Exception as error:
        raise ArchiveSecurityError(
            (
                f"Archiv „{source.name}“ "
                "konnte nicht untersucht werden.\n\n"
                f"{type(error).__name__}: "
                f"{error}"
            )
        ) from error

    _finalize_report(
        report
    )

    return report


# ============================================================
# ZIP
# ============================================================

def _inspect_zip(
    *,
    source: Path,
    report: ArchiveSecurityReport,
    seen_paths: set[str],
) -> None:
    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:
        for info in (
            archive.infolist()
        ):
            unix_mode = (
                info.external_attr
                >> 16
            )

            file_type = (
                stat.S_IFMT(
                    unix_mode
                )
            )

            is_symlink = (
                file_type
                == stat.S_IFLNK
            )

            is_special = (
                file_type
                not in {
                    0,
                    stat.S_IFREG,
                    stat.S_IFDIR,
                    stat.S_IFLNK,
                }
            )

            encrypted = bool(
                info.flag_bits
                & 0x1
            )

            _inspect_member(
                report=report,
                seen_paths=seen_paths,
                name=info.filename,
                uncompressed_size=(
                    info.file_size
                ),
                compressed_size=(
                    info.compress_size
                ),
                is_directory=(
                    info.is_dir()
                ),
                is_symlink=(
                    is_symlink
                ),
                is_special=(
                    is_special
                ),
                encrypted=encrypted,
            )


# ============================================================
# TAR
# ============================================================

def _inspect_tar(
    *,
    source: Path,
    report: ArchiveSecurityReport,
    seen_paths: set[str],
) -> None:
    with tarfile.open(
        source,
        "r:*",
    ) as archive:
        for member in (
            archive.getmembers()
        ):
            is_link = (
                member.issym()
                or member.islnk()
            )

            is_special = not (
                member.isfile()
                or member.isdir()
                or is_link
            )

            _inspect_member(
                report=report,
                seen_paths=seen_paths,
                name=member.name,
                uncompressed_size=(
                    member.size
                    if member.isfile()
                    else 0
                ),
                compressed_size=None,
                is_directory=(
                    member.isdir()
                ),
                is_symlink=(
                    is_link
                ),
                is_special=(
                    is_special
                ),
                encrypted=False,
            )


# ============================================================
# 7-Zip
# ============================================================

def _inspect_7z(
    *,
    source: Path,
    report: ArchiveSecurityReport,
    seen_paths: set[str],
) -> None:
    with py7zr.SevenZipFile(
        source,
        mode="r",
        max_extract_size=(
            MAX_TOTAL_UNCOMPRESSED
        ),
    ) as archive:
        if archive.needs_password():
            _add_block(
                report,
                code="encrypted_archive",
                message=(
                    "Passwortgeschützte Archive "
                    "werden derzeit nicht importiert."
                ),
            )

        for info in archive.list():
            is_special = not (
                info.is_file
                or info.is_directory
                or info.is_symlink
            )

            _inspect_member(
                report=report,
                seen_paths=seen_paths,
                name=info.filename,
                uncompressed_size=(
                    info.uncompressed
                    or 0
                ),
                compressed_size=(
                    info.compressed
                ),
                is_directory=(
                    info.is_directory
                ),
                is_symlink=(
                    info.is_symlink
                ),
                is_special=(
                    is_special
                ),
                encrypted=False,
            )


# ============================================================
# RAR
# ============================================================

def _inspect_rar(
    *,
    source: Path,
    report: ArchiveSecurityReport,
    seen_paths: set[str],
) -> None:
    with rarfile.RarFile(
        source,
        mode="r",
        errors="strict",
    ) as archive:
        if archive.needs_password():
            _add_block(
                report,
                code="encrypted_archive",
                message=(
                    "Passwortgeschützte Archive "
                    "werden derzeit nicht importiert."
                ),
            )

        for info in archive.infolist():
            redirected = (
                getattr(
                    info,
                    "file_redir",
                    None,
                )
                is not None
            )

            is_symlink = (
                info.is_symlink()
                or redirected
            )

            is_special = not (
                info.is_file()
                or info.is_dir()
                or is_symlink
            )

            _inspect_member(
                report=report,
                seen_paths=seen_paths,
                name=info.filename,
                uncompressed_size=(
                    info.file_size
                    or 0
                ),
                compressed_size=(
                    info.compress_size
                    or 0
                ),
                is_directory=(
                    info.is_dir()
                ),
                is_symlink=(
                    is_symlink
                ),
                is_special=(
                    is_special
                ),
                encrypted=(
                    info.needs_password()
                ),
            )


# ============================================================
# Gemeinsame Member-Prüfung
# ============================================================

def _inspect_member(
    *,
    report: ArchiveSecurityReport,
    seen_paths: set[str],
    name: str,
    uncompressed_size: int,
    compressed_size: int | None,
    is_directory: bool,
    is_symlink: bool,
    is_special: bool,
    encrypted: bool,
) -> None:
    report.entry_count += 1

    if (
        report.entry_count
        > MAX_ARCHIVE_ENTRIES
    ):
        _add_block(
            report,
            code="too_many_entries",
            message=(
                "Das Archiv enthält zu viele Dateien."
            ),
        )

        return

    try:
        relative_path = (
            safe_member_relative_path(
                name
            )
        )

    except ArchiveSecurityError as error:
        _add_block(
            report,
            code="unsafe_path",
            message=str(
                error
            ),
            member=name,
        )

        return

    normalized_key = (
        relative_path
        .as_posix()
        .casefold()
    )

    if (
        normalized_key
        in seen_paths
    ):
        _add_block(
            report,
            code="duplicate_path",
            message=(
                "Mehrere Archiveinträge würden "
                "auf denselben Zielpfad geschrieben."
            ),
            member=name,
        )

    else:
        seen_paths.add(
            normalized_key
        )

    if is_symlink:
        _add_block(
            report,
            code="link",
            message=(
                "Symbolische Links, Hardlinks "
                "und Junctions werden aus "
                "Sicherheitsgründen nicht importiert."
            ),
            member=name,
        )

    if is_special:
        _add_block(
            report,
            code="special_file",
            message=(
                "Das Archiv enthält einen "
                "nicht unterstützten speziellen "
                "Dateityp."
            ),
            member=name,
        )

    if encrypted:
        _add_block(
            report,
            code="encrypted_member",
            message=(
                "Passwortgeschützte Dateien "
                "werden derzeit nicht importiert."
            ),
            member=name,
        )

    if is_directory:
        return

    size = max(
        0,
        int(
            uncompressed_size
            or 0
        ),
    )

    report.total_uncompressed += (
        size
    )

    if (
        size
        > MAX_SINGLE_FILE_SIZE
    ):
        _add_block(
            report,
            code="single_file_too_large",
            message=(
                "Eine einzelne Datei überschreitet "
                "das erlaubte Größenlimit."
            ),
            member=name,
        )

    if (
        report.total_uncompressed
        > MAX_TOTAL_UNCOMPRESSED
    ):
        _add_block(
            report,
            code="archive_too_large",
            message=(
                "Die entpackte Gesamtgröße "
                "überschreitet das Sicherheitslimit."
            ),
        )

    compressed = int(
        compressed_size
        or 0
    )

    if (
        size
        >= MIN_RATIO_CHECK_SIZE
        and compressed > 0
    ):
        ratio = (
            size
            / compressed
        )

        if (
            ratio
            > MAX_COMPRESSION_RATIO
        ):
            _add_block(
                report,
                code="compression_ratio",
                message=(
                    "Die Kompressionsrate ist "
                    "ungewöhnlich hoch und könnte "
                    "auf eine Archiv-Bombe hinweisen."
                ),
                member=name,
            )

    _check_warning_extension(
        report=report,
        path=relative_path,
    )


# ============================================================
# Pfadsicherheit
# ============================================================

def safe_member_relative_path(
    name: str,
) -> Path:
    if not isinstance(
        name,
        str,
    ):
        raise ArchiveSecurityError(
            "Ungültiger Dateiname im Archiv."
        )

    if "\x00" in name:
        raise ArchiveSecurityError(
            "Archivpfad enthält ein Null-Zeichen."
        )

    normalized = (
        name
        .replace(
            "\\",
            "/",
        )
    )

    if len(
        normalized
    ) > MAX_PATH_LENGTH:
        raise ArchiveSecurityError(
            "Archivpfad ist zu lang."
        )

    if normalized.startswith(
        "/"
    ):
        raise ArchiveSecurityError(
            "Absoluter Archivpfad ist nicht erlaubt."
        )

    if re.match(
        r"^[A-Za-z]:",
        normalized,
    ):
        raise ArchiveSecurityError(
            "Windows-Laufwerkspfade sind nicht erlaubt."
        )

    pure_path = PurePosixPath(
        normalized
    )

    parts = [
        part
        for part in pure_path.parts
        if part not in {
            "",
            ".",
            "/",
        }
    ]

    if not parts:
        raise ArchiveSecurityError(
            "Archivpfad ist leer."
        )

    if ".." in parts:
        raise ArchiveSecurityError(
            "Archivpfad enthält '..'."
        )

    for component in parts:
        _validate_component(
            component
        )

    return Path(
        *parts
    )


def _validate_component(
    component: str,
) -> None:
    if len(
        component
    ) > MAX_COMPONENT_LENGTH:
        raise ArchiveSecurityError(
            "Ein Pfadbestandteil ist zu lang."
        )

    if any(
        ord(character) < 32
        for character in component
    ):
        raise ArchiveSecurityError(
            "Archivpfad enthält Steuerzeichen."
        )

    # Verhindert NTFS Alternate Data Streams.
    if ":" in component:
        raise ArchiveSecurityError(
            "Doppelpunkte in Archivpfaden sind nicht erlaubt."
        )

    if component.endswith(
        (
            " ",
            ".",
        )
    ):
        raise ArchiveSecurityError(
            (
                "Archivpfade mit abschließendem "
                "Punkt oder Leerzeichen sind "
                "nicht erlaubt."
            )
        )

    device_name = (
        component
        .split(
            ".",
            1,
        )[0]
        .upper()
    )

    if (
        device_name
        in WINDOWS_RESERVED_NAMES
    ):
        raise ArchiveSecurityError(
            (
                "Archivpfad verwendet einen "
                "reservierten Windows-Dateinamen."
            )
        )


# ============================================================
# Warnungen
# ============================================================

def _check_warning_extension(
    *,
    report: ArchiveSecurityReport,
    path: Path,
) -> None:
    suffix = (
        path.suffix
        .casefold()
    )

    if (
        suffix
        in EXECUTABLE_WARNING_SUFFIXES
    ):
        _add_warning_file(
            report,
            path,
            (
                "Das Archiv enthält eine "
                "ausführbare oder skriptbasierte Datei."
            ),
        )

        return

    if (
        suffix
        in BINARY_REVIEW_SUFFIXES
    ):
        _add_warning_file(
            report,
            path,
            (
                "Das Archiv enthält ein Binärmodul. "
                "Das kann bei XXMI-Mods legitim sein, "
                "sollte aber bewusst geprüft werden."
            ),
        )


def _add_warning_file(
    report: ArchiveSecurityReport,
    path: Path,
    message: str,
) -> None:
    if (
        len(
            report.warning_files
        )
        < MAX_REPORTED_WARNING_FILES
    ):
        report.warning_files.append(
            path.as_posix()
        )

    report.issues.append(
        ArchiveIssue(
            severity=(
                ArchiveIssueSeverity.WARNING
            ),
            code="review_file",
            message=message,
            member=(
                path.as_posix()
            ),
        )
    )


# ============================================================
# Abschlussprüfung
# ============================================================

def _finalize_report(
    report: ArchiveSecurityReport,
) -> None:
    try:
        archive_size = (
            report.source
            .stat()
            .st_size
        )

    except OSError:
        archive_size = 0

    if (
        archive_size > 0
        and report.total_uncompressed
        >= MIN_RATIO_CHECK_SIZE
    ):
        total_ratio = (
            report.total_uncompressed
            / archive_size
        )

        if (
            total_ratio
            > MAX_COMPRESSION_RATIO
        ):
            _add_block(
                report,
                code="total_compression_ratio",
                message=(
                    "Die Gesamt-Kompressionsrate "
                    "des Archivs ist ungewöhnlich hoch."
                ),
            )


def _add_block(
    report: ArchiveSecurityReport,
    *,
    code: str,
    message: str,
    member: str | None = None,
) -> None:
    report.issues.append(
        ArchiveIssue(
            severity=(
                ArchiveIssueSeverity.BLOCK
            ),
            code=code,
            message=message,
            member=member,
        )
    )