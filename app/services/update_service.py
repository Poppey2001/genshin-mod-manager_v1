from __future__ import annotations

import ast
import hashlib
import json
import shutil
import stat
import zipfile

from collections.abc import (
    Callable,
)

from dataclasses import (
    dataclass,
)

from enum import (
    Enum,
)

from pathlib import (
    Path,
    PurePosixPath,
)

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.request import (
    Request,
    urlopen,
)

from packaging.version import (
    InvalidVersion,
    Version,
)

from app.update_config import (
    MAX_UPDATE_FILE_COUNT,
    MAX_UPDATE_UNCOMPRESSED_SIZE,
    REMOTE_VERSION_PATH,
    UPDATE_BRANCH,
    UPDATE_CHECK_TIMEOUT,
    UPDATE_DOWNLOAD_TIMEOUT,
    build_raw_file_url,
    build_source_archive_url,
)

from app.version import (
    APP_VERSION,
)


# ============================================================
# Callback Types
# ============================================================

ProgressCallback = Callable[
    [
        int,
        int,
        str,
    ],
    None,
]

CancelCallback = Callable[
    [],
    bool,
]


# ============================================================
# Exceptions
# ============================================================

class UpdateServiceError(
    RuntimeError
):
    pass


class UpdateCancelledError(
    UpdateServiceError
):
    pass


# ============================================================
# Channel
# ============================================================

class UpdateChannel(
    str,
    Enum,
):
    STABLE = "stable"

    PRERELEASE = "prerelease"


# ============================================================
# Update Info
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class UpdateInfo:
    current_version: Version

    version: Version

    version_display: str

    tag: str

    archive_url: str

    @property
    def prerelease(
        self,
    ) -> bool:
        return (
            self.version
            .is_prerelease
        )

    @property
    def tag_name(
        self,
    ) -> str:
        return self.tag

    @property
    def release_name(
        self,
    ) -> str:
        return self.version_display

    @property
    def release_notes(
        self,
    ) -> str:
        return ""

    @property
    def release_url(
        self,
    ) -> str:
        return ""

    @property
    def published_at(
        self,
    ) -> None:
        return None


# ============================================================
# Staged Update
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class StagedUpdate:
    info: UpdateInfo

    cache_root: Path

    archive_path: Path

    extract_root: Path

    payload_root: Path

    manifest_path: Path


# ============================================================
# Update Service
# ============================================================

class UpdateService:
    def __init__(
        self,
        *,
        current_version: str | None = None,
        channel: UpdateChannel = (
            UpdateChannel.PRERELEASE
        ),
    ) -> None:
        version_text = (
            current_version
            if current_version is not None
            else APP_VERSION
        )

        try:
            self.current_version = (
                Version(
                    version_text
                )
            )

        except InvalidVersion as error:
            raise UpdateServiceError(
                (
                    "Die lokale APP_VERSION "
                    "ist ungültig:\n"
                    f"{version_text}"
                )
            ) from error

        self.channel = channel

    # ========================================================
    # Update prüfen
    # ========================================================

    def check_for_update(
        self,
        *,
        allow_prerelease: (
            bool
            | None
        ) = None,
    ) -> UpdateInfo | None:
        if allow_prerelease is None:
            allow_prerelease = (
                self.channel
                == UpdateChannel.PRERELEASE
            )

        # ----------------------------------------------------
        # Nur die Remote version.py laden.
        # Keine GitHub REST API.
        # ----------------------------------------------------

        version_url = (
            build_raw_file_url(
                ref=UPDATE_BRANCH,
                path=(
                    REMOTE_VERSION_PATH
                ),
            )
        )

        data = (
            self._download_bytes(
                version_url,
                timeout=(
                    UPDATE_CHECK_TIMEOUT
                ),
            )
        )

        (
            remote_version,
            version_display,
        ) = (
            self._parse_version_file(
                data
            )
        )

        # ----------------------------------------------------
        # Bereits aktuell
        # ----------------------------------------------------

        if (
            remote_version
            <= self.current_version
        ):
            return None

        # ----------------------------------------------------
        # Stable Channel
        # ----------------------------------------------------

        if (
            not allow_prerelease
            and remote_version
            .is_prerelease
        ):
            return None

        # ----------------------------------------------------
        # Der Git-Tag wird automatisch aus APP_VERSION
        # gebildet.
        #
        # 0.4.5a2
        # ↓
        # v0.4.5a2
        # ----------------------------------------------------

        tag = (
            "v"
            + str(
                remote_version
            )
        )

        archive_url = (
            build_source_archive_url(
                tag=tag
            )
        )

        return UpdateInfo(
            current_version=(
                self.current_version
            ),
            version=(
                remote_version
            ),
            version_display=(
                version_display
            ),
            tag=tag,
            archive_url=(
                archive_url
            ),
        )

    # ========================================================
    # Update herunterladen + entpacken
    # ========================================================

    def download_update(
        self,
        *,
        info: UpdateInfo,
        cache_root: Path,
        progress_callback: (
            ProgressCallback
            | None
        ) = None,
        cancel_callback: (
            CancelCallback
            | None
        ) = None,
    ) -> StagedUpdate:
        cache_root = (
            Path(
                cache_root
            )
            .expanduser()
            .absolute()
        )

        archive_path = (
            cache_root
            / "source.zip"
        )

        extract_root = (
            cache_root
            / "extracted"
        )

        manifest_path = (
            cache_root
            / "manifest.json"
        )

        # ----------------------------------------------------
        # Alten Cache entfernen
        # ----------------------------------------------------

        if cache_root.exists():
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

        cache_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            # ================================================
            # Source ZIP herunterladen
            # ================================================

            self._download_to_file(
                url=(
                    info.archive_url
                ),
                destination=(
                    archive_path
                ),
                progress_callback=(
                    progress_callback
                ),
                cancel_callback=(
                    cancel_callback
                ),
            )

            self._check_cancelled(
                cancel_callback
            )

            # ================================================
            # ZIP prüfen
            # ================================================

            if not zipfile.is_zipfile(
                archive_path
            ):
                raise UpdateServiceError(
                    (
                        "GitHub hat kein gültiges "
                        "ZIP-Archiv geliefert."
                    )
                )

            archive_sha256 = (
                self._sha256_file(
                    archive_path
                )
            )

            # ================================================
            # Sicher entpacken
            # ================================================

            extract_root.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._extract_archive_securely(
                archive_path=(
                    archive_path
                ),
                destination=(
                    extract_root
                ),
                cancel_callback=(
                    cancel_callback
                ),
            )

            self._check_cancelled(
                cancel_callback
            )

            # ================================================
            # GitHub Root-Ordner finden
            # ================================================

            payload_root = (
                self._find_payload_root(
                    extract_root
                )
            )

            # ================================================
            # Entpackte Version prüfen
            #
            # So stellen wir sicher, dass das ZIP wirklich
            # zur zuvor gefundenen Version gehört.
            # ================================================

            extracted_version_path = (
                payload_root
                / REMOTE_VERSION_PATH
            )

            if not (
                extracted_version_path
                .is_file()
            ):
                raise UpdateServiceError(
                    (
                        "Das Update enthält keine "
                        f"{REMOTE_VERSION_PATH}."
                    )
                )

            (
                archive_version,
                archive_display,
            ) = (
                self._parse_version_file(
                    extracted_version_path
                    .read_bytes()
                )
            )

            if (
                archive_version
                != info.version
            ):
                raise UpdateServiceError(
                    (
                        "Die Version des ZIP-Archivs "
                        "stimmt nicht mit der zuvor "
                        "gefundenen Version überein."
                        "\n\n"
                        f"Erwartet: {info.version}"
                        "\n"
                        f"ZIP: {archive_version}"
                    )
                )

            # ================================================
            # Hauptstruktur prüfen
            # ================================================

            if not (
                payload_root
                / "main.py"
            ).is_file():
                raise UpdateServiceError(
                    (
                        "Das Update enthält "
                        "keine main.py."
                    )
                )

            if not (
                payload_root
                / "app"
            ).is_dir():
                raise UpdateServiceError(
                    (
                        "Das Update enthält "
                        "keinen app/-Ordner."
                    )
                )

            # ================================================
            # Manifest
            # ================================================

            manifest = {
                "schema_version": 1,

                "version": str(
                    archive_version
                ),

                "version_display": (
                    archive_display
                ),

                "tag": (
                    info.tag
                ),

                "archive_sha256": (
                    archive_sha256
                ),

                "archive_path": (
                    str(
                        archive_path
                    )
                ),

                "payload_root": (
                    str(
                        payload_root
                    )
                ),
            }

            manifest_path.write_text(
                json.dumps(
                    manifest,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            return StagedUpdate(
                info=info,
                cache_root=(
                    cache_root
                ),
                archive_path=(
                    archive_path
                ),
                extract_root=(
                    extract_root
                ),
                payload_root=(
                    payload_root
                ),
                manifest_path=(
                    manifest_path
                ),
            )

        except Exception:
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            raise

    # ========================================================
    # Remote Version Parser
    # ========================================================

    @staticmethod
    def _parse_version_file(
        data: bytes,
    ) -> tuple[
        Version,
        str,
    ]:
        try:
            source = (
                data.decode(
                    "utf-8"
                )
            )

        except UnicodeDecodeError as error:
            raise UpdateServiceError(
                (
                    "Die entfernte version.py "
                    "ist nicht UTF-8."
                )
            ) from error

        try:
            tree = ast.parse(
                source
            )

        except SyntaxError as error:
            raise UpdateServiceError(
                (
                    "Die entfernte version.py "
                    "enthält ungültigen "
                    "Python-Code."
                )
            ) from error

        values: dict[
            str,
            str,
        ] = {}

        for node in tree.body:
            name: (
                str
                | None
            ) = None

            value_node = None

            # -----------------------------------------------
            # APP_VERSION = "..."
            # -----------------------------------------------

            if isinstance(
                node,
                ast.Assign,
            ):
                if len(
                    node.targets
                ) != 1:
                    continue

                target = (
                    node.targets[
                        0
                    ]
                )

                if isinstance(
                    target,
                    ast.Name,
                ):
                    name = target.id

                    value_node = (
                        node.value
                    )

            # -----------------------------------------------
            # APP_VERSION: str = "..."
            # -----------------------------------------------

            elif isinstance(
                node,
                ast.AnnAssign,
            ):
                if isinstance(
                    node.target,
                    ast.Name,
                ):
                    name = (
                        node.target.id
                    )

                    value_node = (
                        node.value
                    )

            if (
                name
                not in {
                    "APP_VERSION",
                    "APP_VERSION_DISPLAY",
                }
                or value_node is None
            ):
                continue

            try:
                value = (
                    ast.literal_eval(
                        value_node
                    )
                )

            except (
                ValueError,
                TypeError,
            ):
                continue

            if isinstance(
                value,
                str,
            ):
                values[
                    name
                ] = (
                    value.strip()
                )

        version_text = (
            values.get(
                "APP_VERSION",
                "",
            )
        )

        if not version_text:
            raise UpdateServiceError(
                (
                    "APP_VERSION wurde in "
                    "der entfernten version.py "
                    "nicht gefunden."
                )
            )

        try:
            version = (
                Version(
                    version_text
                )
            )

        except InvalidVersion as error:
            raise UpdateServiceError(
                (
                    "Ungültige Remote-Version: "
                    f"{version_text}"
                )
            ) from error

        display = (
            values.get(
                "APP_VERSION_DISPLAY"
            )
            or str(
                version
            )
        )

        return (
            version,
            display,
        )

    # ========================================================
    # Kleine Datei herunterladen
    # ========================================================

    @staticmethod
    def _download_bytes(
        url: str,
        *,
        timeout: float,
    ) -> bytes:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "XXMI-Mod-Manager-Updater"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                return response.read()

        except HTTPError as error:
            raise UpdateServiceError(
                (
                    "GitHub HTTP "
                    f"{error.code}."
                )
            ) from error

        except URLError as error:
            raise UpdateServiceError(
                (
                    "GitHub konnte nicht "
                    "erreicht werden."
                    "\n\n"
                    f"{error}"
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                (
                    "Zeitüberschreitung bei "
                    "der Update-Prüfung."
                )
            ) from error

    # ========================================================
    # ZIP Download
    # ========================================================

    @staticmethod
    def _download_to_file(
        *,
        url: str,
        destination: Path,
        progress_callback: (
            ProgressCallback
            | None
        ),
        cancel_callback: (
            CancelCallback
            | None
        ),
    ) -> None:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "XXMI-Mod-Manager-Updater"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=(
                    UPDATE_DOWNLOAD_TIMEOUT
                ),
            ) as response:
                content_length = (
                    response.headers.get(
                        "Content-Length"
                    )
                )

                try:
                    total = int(
                        content_length
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    total = 0

                received = 0

                with destination.open(
                    "wb"
                ) as output:
                    while True:
                        if (
                            cancel_callback
                            is not None
                            and cancel_callback()
                        ):
                            raise UpdateCancelledError(
                                (
                                    "Update-Download "
                                    "abgebrochen."
                                )
                            )

                        chunk = response.read(
                            1024
                            * 1024
                        )

                        if not chunk:
                            break

                        output.write(
                            chunk
                        )

                        received += len(
                            chunk
                        )

                        if (
                            progress_callback
                            is not None
                        ):
                            progress_callback(
                                received,
                                total,
                                "source.zip",
                            )

        except UpdateCancelledError:
            raise

        except HTTPError as error:
            if error.code == 404:
                raise UpdateServiceError(
                    (
                        "Das GitHub Source-ZIP "
                        "wurde nicht gefunden."
                        "\n\n"
                        "Prüfe, ob der passende "
                        "Git-Tag existiert."
                    )
                ) from error

            raise UpdateServiceError(
                (
                    "GitHub Download HTTP "
                    f"{error.code}."
                )
            ) from error

        except URLError as error:
            raise UpdateServiceError(
                (
                    "Das Update-ZIP konnte "
                    "nicht heruntergeladen werden."
                    "\n\n"
                    f"{error}"
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                (
                    "Zeitüberschreitung beim "
                    "Update-Download."
                )
            ) from error

    # ========================================================
    # Sicher entpacken
    # ========================================================

    @classmethod
    def _extract_archive_securely(
        cls,
        *,
        archive_path: Path,
        destination: Path,
        cancel_callback: (
            CancelCallback
            | None
        ),
    ) -> None:
        destination_resolved = (
            destination.resolve()
        )

        with zipfile.ZipFile(
            archive_path,
            "r",
        ) as archive:
            entries = (
                archive.infolist()
            )

            if (
                len(
                    entries
                )
                > MAX_UPDATE_FILE_COUNT
            ):
                raise UpdateServiceError(
                    (
                        "Das Update-ZIP enthält "
                        "zu viele Dateien."
                    )
                )

            total_uncompressed = sum(
                max(
                    0,
                    entry.file_size,
                )
                for entry
                in entries
            )

            if (
                total_uncompressed
                > MAX_UPDATE_UNCOMPRESSED_SIZE
            ):
                raise UpdateServiceError(
                    (
                        "Das entpackte Update "
                        "wäre zu groß."
                    )
                )

            # ================================================
            # Zuerst ALLE Pfade prüfen
            # ================================================

            for entry in entries:
                cls._check_cancelled(
                    cancel_callback
                )

                normalized = (
                    entry.filename
                    .replace(
                        "\\",
                        "/",
                    )
                )

                path = PurePosixPath(
                    normalized
                )

                if path.is_absolute():
                    raise UpdateServiceError(
                        (
                            "Unsicherer absoluter "
                            "Pfad im Update-ZIP."
                        )
                    )

                if (
                    ".."
                    in path.parts
                ):
                    raise UpdateServiceError(
                        (
                            "Unsicherer relativer "
                            "Pfad im Update-ZIP."
                        )
                    )

                if (
                    path.parts
                    and ":"
                    in path.parts[
                        0
                    ]
                ):
                    raise UpdateServiceError(
                        (
                            "Unsicherer Windows-Pfad "
                            "im Update-ZIP."
                        )
                    )

                # --------------------------------------------
                # Symlinks ablehnen
                # --------------------------------------------

                unix_mode = (
                    entry.external_attr
                    >> 16
                )

                if stat.S_ISLNK(
                    unix_mode
                ):
                    raise UpdateServiceError(
                        (
                            "Symlinks sind im "
                            "Update-ZIP nicht erlaubt."
                        )
                    )

                target = (
                    destination.joinpath(
                        *path.parts
                    )
                )

                try:
                    (
                        target.resolve(
                            strict=False
                        )
                        .relative_to(
                            destination_resolved
                        )
                    )

                except ValueError as error:
                    raise UpdateServiceError(
                        (
                            "Eine Update-Datei "
                            "würde den Cache "
                            "verlassen."
                        )
                    ) from error

            # ================================================
            # Erst jetzt entpacken
            # ================================================

            for entry in entries:
                cls._check_cancelled(
                    cancel_callback
                )

                archive.extract(
                    entry,
                    destination,
                )

    # ========================================================
    # Payload Root
    # ========================================================

    @staticmethod
    def _find_payload_root(
        extract_root: Path,
    ) -> Path:
        directories = [
            path
            for path
            in extract_root.iterdir()
            if path.is_dir()
        ]

        files = [
            path
            for path
            in extract_root.iterdir()
            if path.is_file()
        ]

        if (
            files
            or len(
                directories
            )
            != 1
        ):
            raise UpdateServiceError(
                (
                    "Das GitHub Source-ZIP "
                    "besitzt eine unerwartete "
                    "Verzeichnisstruktur."
                )
            )

        return directories[
            0
        ]

    # ========================================================
    # SHA-256
    # ========================================================

    @staticmethod
    def _sha256_file(
        path: Path,
    ) -> str:
        hasher = (
            hashlib.sha256()
        )

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

                hasher.update(
                    chunk
                )

        return (
            hasher.hexdigest()
        )

    # ========================================================
    # Cancel
    # ========================================================

    @staticmethod
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
            raise UpdateCancelledError(
                (
                    "Update-Download "
                    "abgebrochen."
                )
            )


__all__ = [
    "StagedUpdate",
    "UpdateCancelledError",
    "UpdateChannel",
    "UpdateInfo",
    "UpdateService",
    "UpdateServiceError",
]