from __future__ import annotations

from urllib.parse import (
    quote,
)


# ============================================================
# GitHub Repository
# ============================================================

# Hier deinen echten GitHub-Benutzernamen /
# deine Organisation eintragen.
GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)


# ============================================================
# Update Branch
#
# Von hier wird nur app/version.py gelesen.
# ============================================================

UPDATE_BRANCH = "main"

REMOTE_VERSION_PATH = (
    "app/version.py"
)


# ============================================================
# Netzwerk
# ============================================================

UPDATE_CHECK_TIMEOUT = 15.0

UPDATE_DOWNLOAD_TIMEOUT = 120.0


# ============================================================
# ZIP Sicherheit
# ============================================================

MAX_UPDATE_FILE_COUNT = 30_000

MAX_UPDATE_UNCOMPRESSED_SIZE = (
    2
    * 1024
    * 1024
    * 1024
)


# ============================================================
# Dateien / Ordner, die der Updater ersetzt
# ============================================================

UPDATE_REPLACE_ITEMS = (
    "main.py",
    "app",
    "assets",
)


# ============================================================
# Repository konfiguriert?
# ============================================================

_INVALID_OWNERS = {
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
        in _INVALID_OWNERS
    ):
        return False

    return bool(
        repository
    )


# ============================================================
# URLs
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


def build_source_archive_url(
    *,
    tag: str,
) -> str:
    owner = quote(
        GITHUB_OWNER.strip(),
        safe="",
    )

    repository = quote(
        GITHUB_REPOSITORY.strip(),
        safe="",
    )

    encoded_tag = quote(
        tag.strip(),
        safe="",
    )

    return (
        "https://github.com/"
        f"{owner}/"
        f"{repository}/"
        "archive/refs/tags/"
        f"{encoded_tag}.zip"
    )


__all__ = [
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "MAX_UPDATE_FILE_COUNT",
    "MAX_UPDATE_UNCOMPRESSED_SIZE",
    "REMOTE_VERSION_PATH",
    "UPDATE_BRANCH",
    "UPDATE_CHECK_TIMEOUT",
    "UPDATE_DOWNLOAD_TIMEOUT",
    "UPDATE_REPLACE_ITEMS",
    "build_raw_file_url",
    "build_source_archive_url",
    "github_repository_configured",
]