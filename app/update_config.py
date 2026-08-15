from __future__ import annotations

from urllib.parse import quote


# ============================================================
# GitHub Repository
# ============================================================

GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)


# ============================================================
# Update Branch
# ============================================================

UPDATE_BRANCH = "main"


# ============================================================
# Remote Version
# ============================================================

REMOTE_VERSION_PATH = (
    "app/version.py"
)

# Kompatibilität mit älteren Zwischenständen
REMOTE_VERSION_FILE = (
    REMOTE_VERSION_PATH
)


# ============================================================
# Netzwerk
# ============================================================

UPDATE_CHECK_TIMEOUT = 15.0

UPDATE_DOWNLOAD_TIMEOUT = 120.0


# ============================================================
# ZIP-Sicherheitslimits
# ============================================================

MAX_UPDATE_FILE_COUNT = 30_000

MAX_UPDATE_UNCOMPRESSED_SIZE = (
    2
    * 1024
    * 1024
    * 1024
)


# ============================================================
# Inhalte, die installiert werden
# ============================================================

UPDATE_REPLACE_ITEMS = (
    "main.py",
    "app",
    "assets",
)


# ============================================================
# Repository prüfen
# ============================================================

_INVALID_OWNER_VALUES = {
    "",
    "dein_github_name",
    "your_github_name",
    "github_owner",
}


def github_repository_configured(
) -> bool:
    owner = (
        GITHUB_OWNER
        .strip()
    )

    repository = (
        GITHUB_REPOSITORY
        .strip()
    )

    if (
        owner.casefold()
        in _INVALID_OWNER_VALUES
    ):
        return False

    if not repository:
        return False

    return True


# ============================================================
# RAW-Datei URL
# ============================================================

def build_raw_file_url(
    *,
    ref: str,
    path: str,
) -> str:
    owner = quote(
        GITHUB_OWNER.strip(),
        safe="",
    )

    repository = quote(
        GITHUB_REPOSITORY.strip(),
        safe="",
    )

    encoded_ref = quote(
        ref.strip(),
        safe="",
    )

    encoded_path = "/".join(
        quote(
            part,
            safe="",
        )
        for part
        in path
        .replace(
            "\\",
            "/",
        )
        .split(
            "/"
        )
        if part
    )

    return (
        "https://raw.githubusercontent.com/"
        f"{owner}/"
        f"{repository}/"
        f"{encoded_ref}/"
        f"{encoded_path}"
    )


# ============================================================
# Remote version.py
# ============================================================

def remote_version_url(
) -> str:
    return build_raw_file_url(
        ref=UPDATE_BRANCH,
        path=REMOTE_VERSION_PATH,
    )


# ============================================================
# Source ZIP des Branches
#
# WICHTIG:
# Wir benutzen KEIN Release und KEIN Tag.
#
# main.zip wird direkt von GitHub erzeugt.
# ============================================================

def source_zip_url(
) -> str:
    owner = quote(
        GITHUB_OWNER.strip(),
        safe="",
    )

    repository = quote(
        GITHUB_REPOSITORY.strip(),
        safe="",
    )

    branch = quote(
        UPDATE_BRANCH.strip(),
        safe="",
    )

    return (
        "https://github.com/"
        f"{owner}/"
        f"{repository}/"
        "archive/refs/heads/"
        f"{branch}.zip"
    )


# ============================================================
# Kompatibilität mit älteren Service-Versionen
# ============================================================

def build_source_archive_url(
    *,
    tag: str | None = None,
    branch: str | None = None,
) -> str:
    """
    Kompatibilitätsfunktion.

    Unser neues System benutzt bewusst den Branch.
    Ein übergebener Tag wird ignoriert, damit wir nicht
    wieder vom Git-Tag abhängig werden.
    """

    selected_branch = (
        branch
        or UPDATE_BRANCH
    )

    owner = quote(
        GITHUB_OWNER.strip(),
        safe="",
    )

    repository = quote(
        GITHUB_REPOSITORY.strip(),
        safe="",
    )

    encoded_branch = quote(
        selected_branch.strip(),
        safe="",
    )

    return (
        "https://github.com/"
        f"{owner}/"
        f"{repository}/"
        "archive/refs/heads/"
        f"{encoded_branch}.zip"
    )


__all__ = [
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "MAX_UPDATE_FILE_COUNT",
    "MAX_UPDATE_UNCOMPRESSED_SIZE",
    "REMOTE_VERSION_FILE",
    "REMOTE_VERSION_PATH",
    "UPDATE_BRANCH",
    "UPDATE_CHECK_TIMEOUT",
    "UPDATE_DOWNLOAD_TIMEOUT",
    "UPDATE_REPLACE_ITEMS",
    "build_raw_file_url",
    "build_source_archive_url",
    "github_repository_configured",
    "remote_version_url",
    "source_zip_url",
]