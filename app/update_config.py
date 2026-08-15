from __future__ import annotations


# ============================================================
# GitHub
# ============================================================

GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)

GITHUB_API_VERSION = (
    "2026-03-10"
)


# ============================================================
# Netzwerk
# ============================================================

UPDATE_CHECK_TIMEOUT = 15.0

UPDATE_DOWNLOAD_TIMEOUT = 60.0


# ============================================================
# Windows Update
# ============================================================

WINDOWS_UPDATE_SUFFIX = ".zip"

WINDOWS_UPDATE_KEYWORDS = (
    "windows",
    "win64",
    "x86_64",
    "amd64",
)


# ============================================================
# Dateien, die bei einem Script-Update ersetzt werden
# ============================================================

WINDOWS_REPLACE_ITEMS = (
    "main.py",
    "app",
    "assets",
)


# ============================================================
# Repository Config
# ============================================================

_INVALID_OWNERS = {
    "",
    "dein_github_name",
    "your_github_name",
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