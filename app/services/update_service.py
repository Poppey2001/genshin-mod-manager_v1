from __future__ import annotations

import ast
import hashlib
import json
import logging
import shutil

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

from typing import (
    Any,
)

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    quote,
    urlencode,
)

from urllib.request import (
    Request,
    urlopen,
)

from packaging.version import (
    InvalidVersion,
    Version,
)

from app import update_config

from app.version import (
    APP_VERSION,
)


logger = logging.getLogger(
    __name__
)


# ============================================================
# GitHub
# ============================================================

GITHUB_API_ROOT = (
    "https://api.github.com"
)


# ============================================================
# Config
#
# Die getattr-Fallbacks sorgen dafür, dass der neue Service
# auch dann bereits importierbar ist, wenn update_config.py
# noch nicht vollständig auf die neue Version umgestellt wurde.
# ============================================================

GITHUB_OWNER = getattr(
    update_config,
    "GITHUB_OWNER",
    "",
)

GITHUB_REPOSITORY = getattr(
    update_config,
    "GITHUB_REPOSITORY",
    "",
)

GITHUB_API_VERSION = getattr(
    update_config,
    "GITHUB_API_VERSION",
    "2026-03-10",
)

UPDATE_BRANCH = getattr(
    update_config,
    "UPDATE_BRANCH",
    "main",
)

REMOTE_VERSION_FILE = getattr(
    update_config,
    "REMOTE_VERSION_FILE",
    "app/version.py",
)

UPDATE_CHECK_TIMEOUT = float(
    getattr(
        update_config,
        "UPDATE_CHECK_TIMEOUT",
        15.0,
    )
)

UPDATE_DOWNLOAD_TIMEOUT = float(
    getattr(
        update_config,
        "UPDATE_DOWNLOAD_TIMEOUT",
        30.0,
    )
)


# ============================================================
# Callbacks
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
    """
    Allgemeiner Fehler des Update-Systems.
    """


# ============================================================
# Update Channel
#
# Behalten wir unter demselben Namen, damit dein bestehender
# Worker während des Umbaus nicht sofort an Imports scheitert.
# ============================================================

class UpdateChannel(
    str,
    Enum,
):
    STABLE = "stable"
    PRERELEASE = "prerelease"


# ============================================================
# Legacy ReleaseAsset
#
# Temporär vorhanden, damit alte Imports aus update_worker.py
# während des Umbaus nicht sofort kaputtgehen.
#
# Der neue Script-Updater verwendet ReleaseAsset NICHT.
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class ReleaseAsset:
    name: str

    download_url: str

    size: int

    content_type: (
        str
        | None
    ) = None

    digest: (
        str
        | None
    ) = None

    @property
    def sha256(
        self,
    ) -> str | None:
        digest = (
            self.digest
            or ""
        ).strip()

        algorithm, separator, value = (
            digest.partition(
                ":"
            )
        )

        if (
            separator != ":"
            or algorithm.casefold()
            != "sha256"
            or not value
        ):
            return None

        return (
            value
            .strip()
            .casefold()
        )


# ============================================================
# Remote Update File
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class RemoteUpdateFile:
    """
    Eine aktualisierbare Datei aus dem GitHub Tree.
    """

    path: str

    git_sha: str

    size: int


# ============================================================
# Update Info
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class UpdateInfo:
    """
    Beschreibung eines gefundenen Script-Updates.
    """

    current_version: Version

    version: Version

    version_display: str

    branch: str

    commit_sha: str

    tree_sha: str

    commit_url: str

    files: tuple[
        RemoteUpdateFile,
        ...,
    ]

    # ========================================================
    # Neue API
    # ========================================================

    @property
    def file_count(
        self,
    ) -> int:
        return len(
            self.files
        )

    # ========================================================
    # Legacy-Kompatibilität für den alten UpdateDialog /
    # Controller während des Umbaus.
    # ========================================================

    @property
    def tag_name(
        self,
    ) -> str:
        return (
            str(
                self.version
            )
        )

    @property
    def release_name(
        self,
    ) -> str:
        return (
            self.version_display
        )

    @property
    def release_notes(
        self,
    ) -> str:
        return ""

    @property
    def release_url(
        self,
    ) -> str:
        return (
            self.commit_url
        )

    @property
    def published_at(
        self,
    ) -> None:
        return None

    @property
    def prerelease(
        self,
    ) -> bool:
        return (
            self.version
            .is_prerelease
        )

    @property
    def assets(
        self,
    ) -> tuple[
        ReleaseAsset,
        ...,
    ]:
        return ()

    def find_appimage_asset(
        self,
    ) -> None:
        """
        Legacy-Kompatibilität.

        Das neue System verwendet keine AppImages oder
        Release-Assets mehr.
        """

        return None


# ============================================================
# Staged Update
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class StagedUpdate:
    """
    Vollständig heruntergeladenes Update im Cache.
    """

    info: UpdateInfo

    cache_root: Path

    payload_root: Path

    manifest_path: Path


# ============================================================
# Update Service
# ============================================================

class UpdateService:
    """
    GitHub-basierter Python-Script-Updater.

    Ablauf:

        GitHub Branch
            ↓
        Commit SHA
            ↓
        Tree SHA
            ↓
        app/version.py aus genau diesem Commit
            ↓
        Versionsvergleich
            ↓
        Git Tree dieses Commits
            ↓
        Python-Dateien auswählen
            ↓
        Dateien einzeln in Cache laden
            ↓
        Git Blob SHA prüfen
            ↓
        zusätzlich SHA-256 erzeugen
            ↓
        manifest.json

    Der Service selbst verändert KEINE Dateien der laufenden
    Anwendung.

    Das eigentliche Austauschen übernimmt später der
    Windows-Update-Helper.
    """

    def __init__(
        self,
        *,
        owner: str | None = None,
        repository: str | None = None,
        current_version: str | None = None,
        channel: UpdateChannel = (
            UpdateChannel.PRERELEASE
        ),
        branch: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.owner = (
            owner
            if owner is not None
            else GITHUB_OWNER
        ).strip()

        self.repository = (
            repository
            if repository is not None
            else GITHUB_REPOSITORY
        ).strip()

        self.branch = (
            branch
            if branch is not None
            else UPDATE_BRANCH
        ).strip()

        self.channel = channel

        self.timeout = max(
            1.0,
            float(
                timeout
                if timeout is not None
                else UPDATE_CHECK_TIMEOUT
            ),
        )

        # ====================================================
        # Repository
        # ====================================================

        if not self.owner:
            raise ValueError(
                "GitHub owner fehlt."
            )

        if (
            self.owner.casefold()
            in {
                "dein_github_name",
                "your_github_name",
                "github_owner",
            }
        ):
            raise ValueError(
                (
                    "GITHUB_OWNER enthält noch "
                    "den Platzhalterwert."
                )
            )

        if not self.repository:
            raise ValueError(
                "GitHub repository fehlt."
            )

        if not self.branch:
            raise ValueError(
                "Update branch fehlt."
            )

        # ====================================================
        # Local Version
        # ====================================================

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
            raise ValueError(
                (
                    "Ungültige lokale "
                    f"Version: {version_text}"
                )
            ) from error

    # ========================================================
    # Public: Check
    # ========================================================

    def check_for_update(
        self,
        *,
        allow_prerelease: (
            bool
            | None
        ) = None,
    ) -> UpdateInfo | None:
        """
        Prüft den konfigurierten GitHub-Branch auf eine
        neuere APP_VERSION.

        Wichtig:

        Die Remote-version.py und alle später geladenen
        Dateien stammen aus demselben Commit.
        """

        # ----------------------------------------------------
        # Channel bestimmen
        # ----------------------------------------------------

        if allow_prerelease is None:
            allow_prerelease = (
                self.channel
                == UpdateChannel.PRERELEASE
            )

        # ----------------------------------------------------
        # Branch
        # ----------------------------------------------------

        branch_data = (
            self._fetch_branch()
        )

        (
            commit_sha,
            tree_sha,
        ) = (
            self._parse_branch_data(
                branch_data
            )
        )

        commit_url = (
            "https://github.com/"
            f"{self.owner}/"
            f"{self.repository}/"
            f"commit/{commit_sha}"
        )

        logger.debug(
            (
                "Update Commit: %s "
                "Tree: %s"
            ),
            commit_sha,
            tree_sha,
        )

        # ----------------------------------------------------
        # Remote version.py
        #
        # WICHTIG:
        # ref = commit_sha, NICHT branch.
        # ----------------------------------------------------

        version_source = (
            self._download_raw_file(
                REMOTE_VERSION_FILE,
                ref=(
                    commit_sha
                ),
            )
        )

        (
            remote_version,
            remote_display,
        ) = (
            self._parse_version_file(
                version_source
            )
        )

        logger.info(
            (
                "Update-Versionen: "
                "lokal=%s remote=%s"
            ),
            self.current_version,
            remote_version,
        )

        # ----------------------------------------------------
        # Nicht neuer
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
            logger.info(
                (
                    "Prerelease %s wird im "
                    "Stable-Kanal ignoriert."
                ),
                remote_version,
            )

            return None

        # ----------------------------------------------------
        # Tree
        # ----------------------------------------------------

        files = (
            self._fetch_update_tree(
                tree_sha=(
                    tree_sha
                )
            )
        )

        if not files:
            raise UpdateServiceError(
                (
                    "Der Update-Commit enthält "
                    "keine aktualisierbaren "
                    "Python-Dateien."
                )
            )

        # ----------------------------------------------------
        # version.py muss Teil des Updates sein.
        # ----------------------------------------------------

        if not any(
            file.path
            == REMOTE_VERSION_FILE
            for file
            in files
        ):
            raise UpdateServiceError(
                (
                    "Die Remote version.py "
                    "wurde nicht im "
                    "Update-Dateibaum gefunden."
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
                remote_display
            ),
            branch=(
                self.branch
            ),
            commit_sha=(
                commit_sha
            ),
            tree_sha=(
                tree_sha
            ),
            commit_url=(
                commit_url
            ),
            files=files,
        )

    # ========================================================
    # Public: Download
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
        """
        Lädt alle Update-Dateien in:

            cache_root/
                payload/
                    main.py
                    app/
                        ...

                manifest.json

        Es werden KEINE Dateien der eigentlichen Installation
        verändert.
        """

        cache_root = (
            Path(
                cache_root
            )
            .expanduser()
            .absolute()
        )

        payload_root = (
            cache_root
            / "payload"
        )

        # ----------------------------------------------------
        # Alten Cache dieses Updates entfernen.
        # ----------------------------------------------------

        if cache_root.exists():
            try:
                shutil.rmtree(
                    cache_root
                )

            except OSError as error:
                raise UpdateServiceError(
                    (
                        "Alter Update-Cache konnte "
                        "nicht gelöscht werden:\n"
                        f"{cache_root}"
                    )
                ) from error

        payload_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        total = len(
            info.files
        )

        manifest_files: list[
            dict[
                str,
                object,
            ]
        ] = []

        try:
            for (
                index,
                remote_file,
            ) in enumerate(
                info.files,
                start=1,
            ):
                self._check_cancelled(
                    cancel_callback
                )

                if (
                    progress_callback
                    is not None
                ):
                    progress_callback(
                        index - 1,
                        total,
                        remote_file.path,
                    )

                # ============================================
                # Download exakt aus dem geprüften Commit.
                # ============================================

                data = (
                    self._download_raw_file(
                        remote_file.path,
                        ref=(
                            info.commit_sha
                        ),
                    )
                )

                self._check_cancelled(
                    cancel_callback
                )

                # ============================================
                # Git Blob SHA verifizieren
                # ============================================

                actual_git_sha = (
                    self._git_blob_sha(
                        data
                    )
                )

                if (
                    actual_git_sha
                    != remote_file.git_sha
                ):
                    raise UpdateServiceError(
                        (
                            "Git-Integritätsprüfung "
                            "fehlgeschlagen:\n\n"
                            f"{remote_file.path}\n\n"
                            "Erwartet:\n"
                            f"{remote_file.git_sha}\n\n"
                            "Erhalten:\n"
                            f"{actual_git_sha}"
                        )
                    )

                # ============================================
                # Zusätzlich SHA-256 für unseren
                # lokalen Installations-Helper.
                # ============================================

                sha256 = (
                    hashlib.sha256(
                        data
                    )
                    .hexdigest()
                )

                # ============================================
                # Sicheres Cache-Ziel
                # ============================================

                destination = (
                    self._safe_cache_path(
                        payload_root,
                        remote_file.path,
                    )
                )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                try:
                    destination.write_bytes(
                        data
                    )

                except OSError as error:
                    raise UpdateServiceError(
                        (
                            "Update-Datei konnte "
                            "nicht in den Cache "
                            "geschrieben werden:\n"
                            f"{destination}"
                        )
                    ) from error

                # ============================================
                # Nach dem Schreiben nochmal SHA-256 prüfen.
                # ============================================

                try:
                    written_sha256 = (
                        self._sha256_file(
                            destination
                        )
                    )

                except OSError as error:
                    raise UpdateServiceError(
                        (
                            "Cache-Datei konnte "
                            "nicht überprüft werden:\n"
                            f"{destination}"
                        )
                    ) from error

                if (
                    written_sha256
                    != sha256
                ):
                    raise UpdateServiceError(
                        (
                            "SHA-256-Prüfung der "
                            "Cache-Datei ist "
                            "fehlgeschlagen:\n"
                            f"{remote_file.path}"
                        )
                    )

                manifest_files.append(
                    {
                        "path": (
                            remote_file.path
                        ),
                        "size": len(
                            data
                        ),
                        "git_sha": (
                            remote_file.git_sha
                        ),
                        "sha256": (
                            sha256
                        ),
                    }
                )

                if (
                    progress_callback
                    is not None
                ):
                    progress_callback(
                        index,
                        total,
                        remote_file.path,
                    )

            self._check_cancelled(
                cancel_callback
            )

            # ================================================
            # Manifest
            # ================================================

            manifest = {
                "schema_version": 1,

                "version": (
                    str(
                        info.version
                    )
                ),

                "version_display": (
                    info.version_display
                ),

                "branch": (
                    info.branch
                ),

                "commit_sha": (
                    info.commit_sha
                ),

                "tree_sha": (
                    info.tree_sha
                ),

                "file_count": len(
                    manifest_files
                ),

                "files": (
                    manifest_files
                ),
            }

            manifest_path = (
                cache_root
                / "manifest.json"
            )

            try:
                manifest_path.write_text(
                    json.dumps(
                        manifest,
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            except OSError as error:
                raise UpdateServiceError(
                    (
                        "Update-Manifest konnte "
                        "nicht gespeichert werden."
                    )
                ) from error

        except Exception:
            # ------------------------------------------------
            # Ein unvollständiges Update bleibt nicht liegen.
            # ------------------------------------------------

            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            raise

        return StagedUpdate(
            info=info,
            cache_root=(
                cache_root
            ),
            payload_root=(
                payload_root
            ),
            manifest_path=(
                manifest_path
            ),
        )

    # ========================================================
    # Public: Cache löschen
    # ========================================================

    @staticmethod
    def cleanup_staged_update(
        staged: StagedUpdate,
    ) -> None:
        shutil.rmtree(
            staged.cache_root,
            ignore_errors=True,
        )

    # ========================================================
    # GitHub Branch
    # ========================================================

    def _fetch_branch(
        self,
    ) -> dict[
        str,
        Any,
    ]:
        branch = quote(
            self.branch,
            safe="",
        )

        url = (
            f"{GITHUB_API_ROOT}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/branches/{branch}"
        )

        data = (
            self._request_json(
                url
            )
        )

        if not isinstance(
            data,
            dict,
        ):
            raise UpdateServiceError(
                (
                    "GitHub hat keine "
                    "gültigen Branch-Daten "
                    "geliefert."
                )
            )

        return data

    # ========================================================
    # Branch Data
    # ========================================================

    @staticmethod
    def _parse_branch_data(
        data: dict[
            str,
            Any,
        ],
    ) -> tuple[
        str,
        str,
    ]:
        commit = (
            data.get(
                "commit"
            )
        )

        if not isinstance(
            commit,
            dict,
        ):
            raise UpdateServiceError(
                (
                    "Der GitHub-Branch besitzt "
                    "keine Commit-Daten."
                )
            )

        commit_sha = (
            commit.get(
                "sha"
            )
        )

        if not isinstance(
            commit_sha,
            str,
        ):
            raise UpdateServiceError(
                (
                    "Der Branch besitzt "
                    "keine Commit-SHA."
                )
            )

        commit_sha = (
            commit_sha.strip()
        )

        if not commit_sha:
            raise UpdateServiceError(
                (
                    "Die Commit-SHA ist leer."
                )
            )

        commit_data = (
            commit.get(
                "commit"
            )
        )

        if not isinstance(
            commit_data,
            dict,
        ):
            raise UpdateServiceError(
                (
                    "GitHub hat keine "
                    "Commit-Metadaten geliefert."
                )
            )

        tree = (
            commit_data.get(
                "tree"
            )
        )

        if not isinstance(
            tree,
            dict,
        ):
            raise UpdateServiceError(
                (
                    "Der Commit besitzt "
                    "keine Git-Tree-Daten."
                )
            )

        tree_sha = (
            tree.get(
                "sha"
            )
        )

        if not isinstance(
            tree_sha,
            str,
        ):
            raise UpdateServiceError(
                (
                    "Der Commit besitzt "
                    "keine Tree-SHA."
                )
            )

        tree_sha = (
            tree_sha.strip()
        )

        if not tree_sha:
            raise UpdateServiceError(
                (
                    "Die Tree-SHA ist leer."
                )
            )

        return (
            commit_sha,
            tree_sha,
        )

    # ========================================================
    # Git Tree
    # ========================================================

    def _fetch_update_tree(
        self,
        *,
        tree_sha: str,
    ) -> tuple[
        RemoteUpdateFile,
        ...,
    ]:
        query = urlencode(
            {
                "recursive": "1",
            }
        )

        url = (
            f"{GITHUB_API_ROOT}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/git/trees/{tree_sha}"
            f"?{query}"
        )

        data = (
            self._request_json(
                url
            )
        )

        if not isinstance(
            data,
            dict,
        ):
            raise UpdateServiceError(
                (
                    "GitHub hat keinen "
                    "gültigen Git Tree geliefert."
                )
            )

        if bool(
            data.get(
                "truncated",
                False,
            )
        ):
            raise UpdateServiceError(
                (
                    "Der Git Tree wurde von "
                    "GitHub abgeschnitten. "
                    "Das Update wird aus "
                    "Sicherheitsgründen abgebrochen."
                )
            )

        raw_tree = (
            data.get(
                "tree"
            )
        )

        if not isinstance(
            raw_tree,
            list,
        ):
            raise UpdateServiceError(
                (
                    "Der Git Tree enthält "
                    "keine Dateiliste."
                )
            )

        files: list[
            RemoteUpdateFile
        ] = []

        for item in raw_tree:
            if not isinstance(
                item,
                dict,
            ):
                continue

            # ------------------------------------------------
            # Nur Dateien, keine Trees.
            # ------------------------------------------------

            if (
                item.get(
                    "type"
                )
                != "blob"
            ):
                continue

            path = (
                item.get(
                    "path"
                )
            )

            git_sha = (
                item.get(
                    "sha"
                )
            )

            size = (
                item.get(
                    "size",
                    0,
                )
            )

            if not isinstance(
                path,
                str,
            ):
                continue

            path = (
                path
                .replace(
                    "\\",
                    "/",
                )
                .lstrip(
                    "/"
                )
            )

            if not (
                self._is_update_file(
                    path
                )
            ):
                continue

            if not isinstance(
                git_sha,
                str,
            ):
                continue

            if not isinstance(
                size,
                int,
            ):
                size = 0

            files.append(
                RemoteUpdateFile(
                    path=path,
                    git_sha=(
                        git_sha
                    ),
                    size=max(
                        0,
                        size,
                    ),
                )
            )

        files.sort(
            key=lambda item: (
                item.path
                .casefold()
            )
        )

        return tuple(
            files
        )

    # ========================================================
    # Update-Dateifilter
    # ========================================================

    @staticmethod
    def _is_update_file(
        path: str,
    ) -> bool:
        """
        Falls update_config.py bereits die neue
        is_update_file()-Funktion enthält, benutzen wir sie.

        Sonst:

            main.py
            app/**/*.py
        """

        configured_filter = getattr(
            update_config,
            "is_update_file",
            None,
        )

        if callable(
            configured_filter
        ):
            return bool(
                configured_filter(
                    path
                )
            )

        normalized = (
            path
            .replace(
                "\\",
                "/",
            )
            .lstrip(
                "/"
            )
        )

        if (
            normalized
            == "main.py"
        ):
            return True

        return (
            normalized.startswith(
                "app/"
            )
            and normalized.endswith(
                ".py"
            )
        )

    # ========================================================
    # Remote version.py
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
                    "Remote version.py "
                    "ist nicht UTF-8."
                )
            ) from error

        try:
            module = (
                ast.parse(
                    source
                )
            )

        except SyntaxError as error:
            raise UpdateServiceError(
                (
                    "Remote version.py "
                    "enthält ungültigen "
                    "Python-Code."
                )
            ) from error

        values: dict[
            str,
            str,
        ] = {}

        for node in module.body:
            name: (
                str
                | None
            ) = None

            value_node: (
                ast.expr
                | None
            ) = None

            # ================================================
            # APP_VERSION = "..."
            # ================================================

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
                    name = (
                        target.id
                    )

                    value_node = (
                        node.value
                    )

            # ================================================
            # APP_VERSION: str = "..."
            # ================================================

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
                    "Remote version.py "
                    "enthält keine gültige "
                    "APP_VERSION."
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
    # Remote Datei
    # ========================================================

    def _download_raw_file(
        self,
        path: str,
        *,
        ref: str,
    ) -> bytes:
        """
        Lädt eine Datei aus genau dem angegebenen
        Commit-SHA.
        """

        normalized_path = (
            path
            .replace(
                "\\",
                "/",
            )
            .lstrip(
                "/"
            )
        )

        if not (
            normalized_path
        ):
            raise UpdateServiceError(
                (
                    "Leerer GitHub-Dateipfad."
                )
            )

        encoded_path = quote(
            normalized_path,
            safe="/",
        )

        query = urlencode(
            {
                "ref": ref,
            }
        )

        url = (
            f"{GITHUB_API_ROOT}"
            f"/repos/{self.owner}"
            f"/{self.repository}"
            f"/contents/{encoded_path}"
            f"?{query}"
        )

        request = Request(
            url,
            headers=(
                self._github_headers(
                    raw=True
                )
            ),
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=(
                    UPDATE_DOWNLOAD_TIMEOUT
                ),
            ) as response:
                return (
                    response.read()
                )

        except HTTPError as error:
            if error.code == 404:
                raise UpdateServiceError(
                    (
                        "Remote Update-Datei "
                        "wurde nicht gefunden:\n"
                        f"{normalized_path}"
                    )
                ) from error

            raise UpdateServiceError(
                (
                    "GitHub HTTP "
                    f"{error.code} beim "
                    "Download von:\n"
                    f"{normalized_path}"
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                (
                    "GitHub konnte beim "
                    "Dateidownload nicht "
                    "erreicht werden:\n"
                    f"{reason}"
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                (
                    "Zeitüberschreitung beim "
                    "Download von:\n"
                    f"{normalized_path}"
                )
            ) from error

    # ========================================================
    # JSON Request
    # ========================================================

    def _request_json(
        self,
        url: str,
    ) -> Any:
        request = Request(
            url,
            headers=(
                self._github_headers()
            ),
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=(
                    self.timeout
                ),
            ) as response:
                raw = (
                    response.read()
                )

        except HTTPError as error:
            if error.code == 404:
                raise UpdateServiceError(
                    (
                        "GitHub Repository, "
                        "Branch oder Objekt "
                        "wurde nicht gefunden."
                    )
                ) from error

            if error.code == 403:
                raise UpdateServiceError(
                    (
                        "GitHub hat die Anfrage "
                        "abgelehnt. Mögliches "
                        "API-Limit erreicht."
                    )
                ) from error

            raise UpdateServiceError(
                (
                    "GitHub API HTTP "
                    f"{error.code}."
                )
            ) from error

        except URLError as error:
            reason = getattr(
                error,
                "reason",
                error,
            )

            raise UpdateServiceError(
                (
                    "GitHub konnte nicht "
                    "erreicht werden:\n"
                    f"{reason}"
                )
            ) from error

        except TimeoutError as error:
            raise UpdateServiceError(
                (
                    "Zeitüberschreitung bei "
                    "der GitHub-Anfrage."
                )
            ) from error

        try:
            return (
                json.loads(
                    raw.decode(
                        "utf-8"
                    )
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateServiceError(
                (
                    "GitHub hat keine "
                    "gültige JSON-Antwort "
                    "geliefert."
                )
            ) from error

    # ========================================================
    # GitHub Headers
    # ========================================================

    @staticmethod
    def _github_headers(
        *,
        raw: bool = False,
    ) -> dict[
        str,
        str,
    ]:
        headers = {
            "Accept": (
                "application/vnd.github.raw+json"
                if raw
                else "application/vnd.github+json"
            ),

            "X-GitHub-Api-Version": (
                GITHUB_API_VERSION
            ),

            "User-Agent": (
                "XXMI-Mod-Manager-Updater"
            ),
        }

        token_function = getattr(
            update_config,
            "github_token",
            None,
        )

        token: (
            str
            | None
        ) = None

        if callable(
            token_function
        ):
            try:
                token = (
                    token_function()
                )

            except Exception:
                token = None

        if token:
            headers[
                "Authorization"
            ] = (
                f"Bearer {token}"
            )

        return headers

    # ========================================================
    # Git Blob Hash
    # ========================================================

    @staticmethod
    def _git_blob_sha(
        data: bytes,
    ) -> str:
        """
        Berechnet den klassischen Git Blob Object Hash:

            SHA1(
                b"blob <size>\\0"
                + data
            )

        Dieser Wert muss mit der SHA aus dem Git Tree
        übereinstimmen.
        """

        header = (
            f"blob {len(data)}\0"
            .encode(
                "ascii"
            )
        )

        try:
            hasher = hashlib.sha1(
                usedforsecurity=False
            )

        except TypeError:
            hasher = hashlib.sha1()

        hasher.update(
            header
        )

        hasher.update(
            data
        )

        return (
            hasher.hexdigest()
        )

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
    # Safe Cache Path
    # ========================================================

    @staticmethod
    def _safe_cache_path(
        root: Path,
        remote_path: str,
    ) -> Path:
        """
        Verhindert z.B.:

            ../../Windows/System32/...
        """

        normalized = (
            remote_path
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
                    "Absoluter Update-Pfad "
                    "ist nicht erlaubt:\n"
                    f"{remote_path}"
                )
            )

        if (
            ".."
            in path.parts
        ):
            raise UpdateServiceError(
                (
                    "Unsicherer Update-Pfad:\n"
                    f"{remote_path}"
                )
            )

        target = (
            root.joinpath(
                *path.parts
            )
        )

        root_resolved = (
            root.resolve()
        )

        target_resolved = (
            target.resolve(
                strict=False
            )
        )

        try:
            target_resolved.relative_to(
                root_resolved
            )

        except ValueError as error:
            raise UpdateServiceError(
                (
                    "Update-Datei würde den "
                    "Cache-Ordner verlassen:\n"
                    f"{remote_path}"
                )
            ) from error

        return target

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
            raise UpdateServiceError(
                "Update-Download abgebrochen."
            )


__all__ = [
    "ReleaseAsset",
    "RemoteUpdateFile",
    "StagedUpdate",
    "UpdateChannel",
    "UpdateInfo",
    "UpdateService",
    "UpdateServiceError",
]