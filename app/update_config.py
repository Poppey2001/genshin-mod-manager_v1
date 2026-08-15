from __future__ import annotations

import os


# ============================================================
# GitHub Repository
# ============================================================

GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)


# ============================================================
# GitHub API
# ============================================================

GITHUB_API_VERSION = (
    "2026-03-10"
)

UPDATE_CHECK_TIMEOUT = 15.0

UPDATE_DOWNLOAD_TIMEOUT = 30.0


# ============================================================
# Optionaler GitHub Token
#
# Für öffentliche Repositories nicht notwendig.
#
# Kann z.B. gesetzt werden mit:
#
# export GITHUB_TOKEN="..."
# ============================================================

GITHUB_TOKEN_ENV = (
    "GITHUB_TOKEN"
)


def github_token() -> str | None:
    value = (
        os.environ
        .get(
            GITHUB_TOKEN_ENV,
            "",
        )
        .strip()
    )

    return (
        value
        if value
        else None
    )


# ============================================================
# Linux Release
# ============================================================

APPIMAGE_SUFFIX = (
    ".AppImage"
)

APPIMAGE_ARCHITECTURE = (
    "x86_64"
)

APPIMAGE_ARCHITECTURE_ALIASES = (
    "x86_64",
    "amd64",
)


# ============================================================
# Repository prüfen
# ============================================================

_INVALID_OWNER_VALUES = {
    "",
    "dein_github_name",
    "your_github_name",
    "github_owner",
    "owner",
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


__all__ = [
    "APPIMAGE_ARCHITECTURE",
    "APPIMAGE_ARCHITECTURE_ALIASES",
    "APPIMAGE_SUFFIX",
    "GITHUB_API_VERSION",
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "UPDATE_CHECK_TIMEOUT",
    "UPDATE_DOWNLOAD_TIMEOUT",
    "github_repository_configured",
    "github_token",
]