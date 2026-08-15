from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zlib

from collections.abc import (
    Callable,
)

from dataclasses import (
    dataclass,
)

from pathlib import Path

from app.platform_support import (
    resource_path,
)


GENSHIN_GAME_ID = (
    "genshin-impact"
)

ORFIX_FILENAME = (
    "orfixapplier_ver_4_2_e863a.exe"
)

RELEASE57_FILENAME = (
    "57ReleaseVersion.exe"
)


ProgressCallback = Callable[
    [
        int,
        int,
        str,
    ],
    None,
]


# ============================================================
# Exceptions
# ============================================================

class ModDuplicateError(
    RuntimeError
):
    pass


class NormalizerUnavailableError(
    ModDuplicateError
):
    pass


class NormalizerExecutionError(
    ModDuplicateError
):
    pass


class DuplicateDeleteError(
    ModDuplicateError
):
    pass


# ============================================================
# Models
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class ModFingerprint:
    crc32: str

    sha256: str

    file_count: int

    total_size: int


@dataclass(
    frozen=True,
    slots=True,
)
class DuplicateCheckResult:
    source: Path

    source_fingerprint: ModFingerprint

    duplicate_path: Path | None

    duplicate_fingerprint: (
        ModFingerprint
        | None
    )

    compared_count: int

    normalized: bool

    @property
    def is_duplicate(
        self,
    ) -> bool:
        duplicate = (
            self.duplicate_fingerprint
        )

        if (
            self.duplicate_path
            is None
            or duplicate is None
        ):
            return False

        # CRC32 ist der schnelle Vorfilter.
        if (
            self.source_fingerprint.crc32
            != duplicate.crc32
        ):
            return False

        # SHA-256 entscheidet endgültig.
        return (
            self.source_fingerprint.sha256
            == duplicate.sha256
        )


@dataclass(
    frozen=True,
    slots=True,
)
class _TreeStamp:
    file_count: int

    total_size: int

    newest_mtime_ns: int


# ============================================================
# Service
# ============================================================

class ModDuplicateService:
    """
    Vergleicht Mods nach einer normalisierten Arbeitskopie.

    Genshin:
        1. temporäre Kopie
        2. ORFix
        3. 57ReleaseVersion
        4. CRC32
        5. SHA-256

    Andere Spiele:
        1. temporäre Kopie
        2. CRC32
        3. SHA-256

    Die Originaldateien werden dabei niemals verändert.
    """

    def __init__(
        self,
        *,
        tool_timeout_seconds: int = 600,
    ) -> None:
        self.tool_timeout_seconds = (
            max(
                30,
                int(
                    tool_timeout_seconds
                ),
            )
        )

        self._cache: dict[
            tuple[
                str,
                str,
                _TreeStamp,
            ],
            ModFingerprint,
        ] = {}

        self._cache_lock = (
            threading.Lock()
        )

    # ========================================================
    # Public
    # ========================================================

    def find_duplicate(
        self,
        *,
        source: Path,
        library_paths: tuple[
            Path,
            ...,
        ],
        game_id: str,
        progress_callback: (
            ProgressCallback
            | None
        ) = None,
    ) -> DuplicateCheckResult:
        source = (
            self._normalize_source_path(
                source
            )
        )

        candidates = tuple(
            self._normalize_source_path(
                path
            )
            for path
            in library_paths
            if Path(
                path
            ).exists()
        )

        total = len(
            candidates
        )

        if progress_callback:
            progress_callback(
                0,
                total,
                source.name,
            )

        source_fingerprint = (
            self.fingerprint_mod(
                source=source,
                game_id=game_id,
            )
        )

        compared = 0

        for (
            index,
            candidate,
        ) in enumerate(
            candidates,
            start=1,
        ):
            # -----------------------------------------------
            # Gleicher tatsächlicher Ordner?
            # -----------------------------------------------

            try:
                if (
                    candidate.resolve()
                    == source.resolve()
                ):
                    continue

            except OSError:
                pass

            if progress_callback:
                progress_callback(
                    index,
                    total,
                    candidate.name,
                )

            compared += 1

            candidate_fingerprint = (
                self.fingerprint_mod(
                    source=candidate,
                    game_id=game_id,
                )
            )

            # ===============================================
            # CRC32: schneller Vorfilter
            # ===============================================

            if (
                source_fingerprint.crc32
                != candidate_fingerprint.crc32
            ):
                continue

            # ===============================================
            # SHA-256: endgültiger Vergleich
            # ===============================================

            if (
                source_fingerprint.sha256
                != candidate_fingerprint.sha256
            ):
                continue

            return DuplicateCheckResult(
                source=source,
                source_fingerprint=(
                    source_fingerprint
                ),
                duplicate_path=(
                    candidate
                ),
                duplicate_fingerprint=(
                    candidate_fingerprint
                ),
                compared_count=(
                    compared
                ),
                normalized=(
                    game_id
                    == GENSHIN_GAME_ID
                ),
            )

        return DuplicateCheckResult(
            source=source,
            source_fingerprint=(
                source_fingerprint
            ),
            duplicate_path=None,
            duplicate_fingerprint=None,
            compared_count=compared,
            normalized=(
                game_id
                == GENSHIN_GAME_ID
            ),
        )

    # ========================================================
    # Fingerprint
    # ========================================================

    def fingerprint_mod(
        self,
        *,
        source: Path,
        game_id: str,
    ) -> ModFingerprint:
        source = (
            self._normalize_source_path(
                source
            )
        )

        stamp = (
            self._tree_stamp(
                source
            )
        )

        cache_key = (
            str(
                source
            ),
            game_id,
            stamp,
        )

        with self._cache_lock:
            cached = (
                self._cache.get(
                    cache_key
                )
            )

        if cached is not None:
            return cached

        with tempfile.TemporaryDirectory(
            prefix=(
                "xxmimm-fingerprint-"
            )
        ) as temp_directory:
            temp_root = Path(
                temp_directory
            )

            # -----------------------------------------------
            # 57ReleaseVersion prüft, ob es innerhalb
            # eines "Mods"-Pfades ausgeführt wird.
            # -----------------------------------------------

            mods_root = (
                temp_root
                / "Mods"
            )

            work_root = (
                mods_root
                / "ModUnderTest"
            )

            mods_root.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copytree(
                source,
                work_root,
                symlinks=False,
            )

            # ===============================================
            # Genshin-Normalisierung
            # ===============================================

            if (
                game_id
                == GENSHIN_GAME_ID
            ):
                self._run_genshin_normalizers(
                    work_root
                )

            fingerprint = (
                self._hash_tree(
                    work_root
                )
            )

        with self._cache_lock:
            self._cache[
                cache_key
            ] = fingerprint

        return fingerprint

    # ========================================================
    # ORFix + 57ReleaseVersion
    # ========================================================

    def _run_genshin_normalizers(
        self,
        work_root: Path,
    ) -> None:
        orfix = (
            self._tool_path(
                ORFIX_FILENAME
            )
        )

        release57 = (
            self._tool_path(
                RELEASE57_FILENAME
            )
        )

        # ===============================================
        # 1. ORFix
        # ===============================================

        self._run_windows_tool(
            executable=orfix,
            arguments=(
                "--nonverbose",
                "--ignoredisabled",
            ),
            cwd=work_root,
            display_name="ORFix",
            stdin_text=(
                "\n"
                "\n"
                "\n"
                "\n"
            ),
        )

        # ===============================================
        # 2. 57ReleaseVersion
        #
        # --nolog:
        #   keine interaktive Log-Abfrage
        #
        # -df:
        #   disabled Dateien auslassen
        # ===============================================

        self._run_windows_tool(
            executable=release57,
            arguments=(
                "--nolog",
                "-df",
            ),
            cwd=work_root,
            display_name=(
                "57ReleaseVersion"
            ),
            stdin_text=(
                "\n"
                "\n"
                "\n"
                "\n"
            ),
        )

    # ========================================================
    # Tool Runner
    # ========================================================

    def _run_windows_tool(
        self,
        *,
        executable: Path,
        arguments: tuple[
            str,
            ...,
        ],
        cwd: Path,
        display_name: str,
        stdin_text: str | None = None,
    ) -> None:
        """
        Startet ein Windows-Normalisierungstool.

        Windows:
            EXE direkt

        Linux:
            EXE über Wine

        stdin_text kann für Tools verwendet werden,
        die trotz CLI-Modus auf "Press Enter" warten.
        """

        # ====================================================
        # EXE vorhanden?
        # ====================================================

        if not executable.is_file():
            raise (
                NormalizerUnavailableError(
                    (
                        f"{display_name} wurde "
                        "nicht gefunden:\n"
                        f"{executable}"
                    )
                )
            )

        # ====================================================
        # Command
        # ====================================================

        command = (
            self._build_tool_command(
                executable
            )
        )

        command.extend(
            arguments
        )

        # ====================================================
        # Environment
        # ====================================================

        env = os.environ.copy()

        if not (
            sys.platform.startswith(
                "win"
            )
        ):
            # Wine selbst soll möglichst ruhig bleiben.
            env.setdefault(
                "WINEDEBUG",
                "-all",
            )

            # Verhindert einige unnötige Grafikinitialisierungen.
            env.setdefault(
                "WINEDLLOVERRIDES",
                (
                    "winemenubuilder.exe=d;"
                )
            )

        # ====================================================
        # Windows Flags
        # ====================================================

        creation_flags = 0

        if (
            sys.platform.startswith(
                "win"
            )
        ):
            creation_flags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )

        # ====================================================
        # Run
        # ====================================================

        try:
            completed = subprocess.run(
                command,
                cwd=str(
                    cwd
                ),

                # --------------------------------------------
                # WICHTIG:
                #
                # Kein DEVNULL mehr.
                #
                # ORFix benutzt Python input() für
                # "Press Enter".
                # --------------------------------------------

                input=(
                    stdin_text
                    if stdin_text is not None
                    else ""
                ),

                stdout=(
                    subprocess.PIPE
                ),

                stderr=(
                    subprocess.STDOUT
                ),

                text=True,

                encoding="utf-8",

                errors="replace",

                timeout=(
                    self.tool_timeout_seconds
                ),

                check=False,

                env=env,

                creationflags=(
                    creation_flags
                ),
            )

        except subprocess.TimeoutExpired as error:
            raise (
                NormalizerExecutionError(
                    (
                        f"{display_name} hat "
                        "das Zeitlimit überschritten."
                    )
                )
            ) from error

        except OSError as error:
            raise (
                NormalizerExecutionError(
                    (
                        f"{display_name} konnte "
                        "nicht gestartet werden.\n\n"
                        f"{error}"
                    )
                )
            ) from error

        # ====================================================
        # Output
        # ====================================================

        output = (
            completed.stdout
            or ""
        )

        # ----------------------------------------------------
        # Wine-Grafikwarnungen aus der sichtbaren
        # Fehlermeldung entfernen.
        # ----------------------------------------------------

        output = (
            self._clean_tool_output(
                output
            )
        )

        # ====================================================
        # Success
        # ====================================================

        if (
            completed.returncode
            == 0
        ):
            return

        # ====================================================
        # Error
        # ====================================================

        if len(
            output
        ) > 4000:
            output = output[
                -4000:
            ]

        raise (
            NormalizerExecutionError(
                (
                    f"{display_name} wurde mit "
                    f"Exit-Code "
                    f"{completed.returncode} beendet."
                    "\n\n"
                    f"{output}"
                )
            )
        )
        
    @staticmethod
    def _clean_tool_output(
        output: str,
    ) -> str:
        """
        Entfernt bekannte Wine/Mesa-Warnungen aus der
        sichtbaren Programmausgabe.

        Die Ausgabe des eigentlichen Fixers bleibt erhalten.
        """

        ignored_fragments = (
            "libegl warning:",
            "pci id for fd ",
            "egl: failed to create dri2 screen",
        )

        cleaned_lines: list[
            str
        ] = []

        for line in (
            output.splitlines()
        ):
            stripped = (
                line.strip()
            )

            lowered = (
                stripped.casefold()
            )

            if any(
                fragment
                in lowered
                for fragment
                in ignored_fragments
            ):
                continue

            cleaned_lines.append(
                line
            )

        return (
            "\n".join(
                cleaned_lines
            )
            .strip()
        )     
    
    def _build_tool_command(
        self,
        executable: Path,
    ) -> list[
        str
    ]:
        if (
            sys.platform.startswith(
                "win"
            )
        ):
            return [
                str(
                    executable
                )
            ]

        wine = (
            shutil.which(
                "wine"
            )
            or shutil.which(
                "wine64"
            )
        )

        if wine is None:
            raise (
                NormalizerUnavailableError(
                    (
                        "Für ORFix und "
                        "57ReleaseVersion wird "
                        "unter Linux Wine benötigt."
                    )
                )
            )

        return [
            wine,
            str(
                executable
            ),
        ]

    # ========================================================
    # Hash
    # ========================================================

    def _hash_tree(
        self,
        root: Path,
    ) -> ModFingerprint:
        crc_value = 0

        sha_value = (
            hashlib.sha256()
        )

        file_count = 0

        total_size = 0

        preview_paths = (
            self._metadata_preview_paths(
                root
            )
        )

        paths = [
            path
            for path
            in root.rglob(
                "*"
            )
            if path.is_file()
        ]

        paths.sort(
            key=lambda path: (
                path.relative_to(
                    root
                )
                .as_posix()
                .casefold()
            )
        )

        for path in paths:
            relative = (
                path.relative_to(
                    root
                )
                .as_posix()
            )

            if self._ignore_hash_file(
                relative_path=relative,
                preview_paths=(
                    preview_paths
                ),
            ):
                continue

            try:
                size = (
                    path.stat()
                    .st_size
                )

            except OSError as error:
                raise ModDuplicateError(
                    (
                        "Eine Mod-Datei konnte "
                        "nicht gelesen werden:\n"
                        f"{path}\n\n"
                        f"{error}"
                    )
                ) from error

            # -----------------------------------------------
            # Der relative Pfad gehört zum Fingerprint.
            #
            # Zwei Mods mit unterschiedlichen internen
            # Dateinamen gelten damit nicht automatisch
            # als identisch.
            # -----------------------------------------------

            header = (
                relative.encode(
                    "utf-8",
                    errors="surrogatepass",
                )
                + b"\0"
                + int(
                    size
                ).to_bytes(
                    8,
                    byteorder="little",
                    signed=False,
                )
            )

            crc_value = zlib.crc32(
                header,
                crc_value,
            )

            sha_value.update(
                header
            )

            try:
                with path.open(
                    "rb"
                ) as handle:
                    while True:
                        chunk = handle.read(
                            1024
                            * 1024
                        )

                        if not chunk:
                            break

                        crc_value = (
                            zlib.crc32(
                                chunk,
                                crc_value,
                            )
                        )

                        sha_value.update(
                            chunk
                        )

            except OSError as error:
                raise ModDuplicateError(
                    (
                        "Eine Mod-Datei konnte "
                        "nicht gehasht werden:\n"
                        f"{path}\n\n"
                        f"{error}"
                    )
                ) from error

            file_count += 1

            total_size += size

        return ModFingerprint(
            crc32=(
                f"{crc_value & 0xFFFFFFFF:08X}"
            ),
            sha256=(
                sha_value.hexdigest()
            ),
            file_count=file_count,
            total_size=total_size,
        )

    # ========================================================
    # Dateien ignorieren
    # ========================================================

    @staticmethod
    def _ignore_hash_file(
        *,
        relative_path: str,
        preview_paths: set[
            str
        ],
    ) -> bool:
        normalized = (
            relative_path
            .replace(
                "\\",
                "/",
            )
        )

        name = (
            Path(
                normalized
            )
            .name
        )

        lower_name = (
            name.casefold()
        )

        # -----------------------------------------------
        # Manager-Metadaten
        # -----------------------------------------------

        if lower_name in {
            ".gmm-managed.json",
            ".xxmimm-managed.json",
            ".xxmimm-mod.json",
            ".xxmimm-source.json",
            ".ds_store",
            "thumbs.db",
        }:
            return True

        # -----------------------------------------------
        # Vom Manager bekannte Preview-Datei
        # -----------------------------------------------

        if (
            normalized.casefold()
            in preview_paths
        ):
            return True

        # -----------------------------------------------
        # ORFix / ReleaseVersion Backups
        # -----------------------------------------------

        if (
            lower_name.startswith(
                "backup_orfix_applier_"
            )
        ):
            return True

        if (
            lower_name.startswith(
                "original_"
            )
        ):
            return True

        if (
            lower_name
            == "processing_log.txt"
        ):
            return True

        return False

    # ========================================================
    # Preview-Metadata
    # ========================================================

    @staticmethod
    def _metadata_preview_paths(
        root: Path,
    ) -> set[
        str
    ]:
        metadata_path = (
            root
            / ".xxmimm-mod.json"
        )

        if not metadata_path.is_file():
            return set()

        try:
            data = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return set()

        if not isinstance(
            data,
            dict,
        ):
            return set()

        value = data.get(
            "preview_file"
        )

        if not isinstance(
            value,
            str,
        ):
            return set()

        normalized = (
            value.replace(
                "\\",
                "/",
            )
            .lstrip(
                "/"
            )
            .casefold()
        )

        return {
            normalized
        }

    # ========================================================
    # Cache Stamp
    # ========================================================

    @staticmethod
    def _tree_stamp(
        root: Path,
    ) -> _TreeStamp:
        count = 0

        size = 0

        newest = 0

        for path in root.rglob(
            "*"
        ):
            if not path.is_file():
                continue

            try:
                stat = (
                    path.stat()
                )

            except OSError:
                continue

            count += 1

            size += (
                stat.st_size
            )

            newest = max(
                newest,
                stat.st_mtime_ns,
            )

        return _TreeStamp(
            file_count=count,
            total_size=size,
            newest_mtime_ns=newest,
        )

    # ========================================================
    # Löschen
    # ========================================================

    def delete_confirmed_duplicate(
        self,
        *,
        result: DuplicateCheckResult,
        active_root: Path,
    ) -> None:
        if not (
            result.is_duplicate
        ):
            raise DuplicateDeleteError(
                (
                    "Der Mod wurde nicht als "
                    "SHA-256-Duplikat bestätigt."
                )
            )

        source = (
            result.source
            .expanduser()
            .absolute()
        )

        active_root = (
            Path(
                active_root
            )
            .expanduser()
            .absolute()
        )

        try:
            source.relative_to(
                active_root
            )

        except ValueError as error:
            raise DuplicateDeleteError(
                (
                    "Aus Sicherheitsgründen dürfen "
                    "nur Mods innerhalb des aktiven "
                    "XXMI-Mod-Ordners gelöscht werden."
                )
            ) from error

        if source == active_root:
            raise DuplicateDeleteError(
                (
                    "Der Active-Mods-Hauptordner "
                    "darf nicht gelöscht werden."
                )
            )

        if source.is_symlink():
            source.unlink()

            return

        if source.is_dir():
            shutil.rmtree(
                source
            )

            return

        if source.exists():
            source.unlink()

            return

        raise DuplicateDeleteError(
            (
                "Der zu löschende Mod "
                "existiert nicht mehr."
            )
        )

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _normalize_source_path(
        source: Path,
    ) -> Path:
        path = (
            Path(
                source
            )
            .expanduser()
            .absolute()
        )

        if path.is_symlink():
            try:
                path = path.resolve()

            except OSError:
                pass

        if not path.is_dir():
            raise ModDuplicateError(
                (
                    "Für den Duplikatvergleich "
                    "wird ein Mod-Ordner benötigt:"
                    "\n"
                    f"{path}"
                )
            )

        return path

    @staticmethod
    def _tool_path(
        filename: str,
    ) -> Path:
        return Path(
            resource_path(
                "assets",
                "tools",
                "genshin",
                filename,
            )
        )


__all__ = [
    "DuplicateCheckResult",
    "DuplicateDeleteError",
    "ModDuplicateError",
    "ModDuplicateService",
    "ModFingerprint",
    "NormalizerExecutionError",
    "NormalizerUnavailableError",
]