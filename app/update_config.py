from __future__ import annotations


# ============================================================
# GitHub Repository
# ============================================================

GITHUB_OWNER = "Poppey2001"

GITHUB_REPOSITORY = (
    "genshin-mod-manager_v1"
)


# ============================================================
# Shared version backend
# ============================================================

# app/version.py is the single source of truth for BOTH
# Linux and Windows.
GITHUB_VERSION_REF = "main"

GITHUB_VERSION_FILE = (
    "app/version.py"
)


# ============================================================
# GitHub API
# ============================================================

GITHUB_API_VERSION = (
    "2026-03-10"
)

UPDATE_CHECK_TIMEOUT = 20.0


# ============================================================
# Linux Release / AppImage
# ============================================================

APPIMAGE_SUFFIX = ".AppImage"

APPIMAGE_ARCHITECTURE = "x86_64"


# ============================================================
# Windows Release / Installer
# ============================================================

WINDOWS_INSTALLER_SUFFIX = ".exe"

WINDOWS_INSTALLER_NAME_TOKENS = (
    "setup",
    "installer",
)

WINDOWS_INSTALLER_ARCHITECTURE = (
    "x86_64"
)


def github_repository_configured(
) -> bool:
    owner = GITHUB_OWNER.strip()
    repository = (
        GITHUB_REPOSITORY.strip()
    )

    if not owner:
        return False

    if not repository:
        return False

    placeholders = {
        "dein_github_name",
        "your_github_name",
        "owner",
        "repository",
        "repo",
    }

    if owner.casefold() in placeholders:
        return False

    if repository.casefold() in placeholders:
        return False

    return True


__all__ = [
    "APPIMAGE_ARCHITECTURE",
    "APPIMAGE_SUFFIX",
    "GITHUB_API_VERSION",
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "GITHUB_VERSION_FILE",
    "GITHUB_VERSION_REF",
    "UPDATE_CHECK_TIMEOUT",
    "WINDOWS_INSTALLER_ARCHITECTURE",
    "WINDOWS_INSTALLER_NAME_TOKENS",
    "WINDOWS_INSTALLER_SUFFIX",
    "github_repository_configured",
]
