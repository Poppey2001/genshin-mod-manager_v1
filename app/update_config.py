from __future__ import annotations

import os


# ============================================================
# GitHub
# ============================================================

GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)

UPDATE_BRANCH = (
    "main"
)

GITHUB_API_VERSION = (
    "2026-03-10"
)


# ============================================================
# Netzwerk
# ============================================================

UPDATE_CHECK_TIMEOUT = 15.0

UPDATE_DOWNLOAD_TIMEOUT = 30.0


# ============================================================
# Remote Version
# ============================================================

REMOTE_VERSION_FILE = (
    "app/version.py"
)


# ============================================================
# Dateien, die aktualisiert werden
# ============================================================

UPDATE_EXACT_FILES = {
    "main.py",
}

UPDATE_PREFIXES = (
    "app/",
)

UPDATE_SUFFIXES = (
    ".py",
)


# ============================================================
# Optional GitHub Token
# ============================================================

GITHUB_TOKEN_ENV = (
    "GITHUB_TOKEN"
)


def github_token(
) -> str | None:
    value = (
        os.environ
        .get(
            GITHUB_TOKEN_ENV,
            "",
        )
        .strip()
    )

    if not value:
        return None

    return value


# ============================================================
# Repository Validierung
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
# Update Dateifilter
# ============================================================

def is_update_file(
    path: str,
) -> bool:
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

    if path in UPDATE_EXACT_FILES:
        return True

    if not path.endswith(
        UPDATE_SUFFIXES
    ):
        return False

    return any(
        path.startswith(
            prefix
        )
        for prefix
        in UPDATE_PREFIXES
    )


__all__ = [
    "GITHUB_API_VERSION",
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "REMOTE_VERSION_FILE",
    "UPDATE_BRANCH",
    "UPDATE_CHECK_TIMEOUT",
    "UPDATE_DOWNLOAD_TIMEOUT",
    "github_repository_configured",
    "github_token",
    "is_update_file",
]