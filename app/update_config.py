from __future__ import annotations


# ============================================================
# GitHub Repository
# ============================================================

# HIER deinen GitHub-Namen eintragen.
GITHUB_OWNER = "DEIN_GITHUB_NAME"

GITHUB_REPOSITORY = (
    "genshin-mod-manager"
)


# ============================================================
# GitHub API
# ============================================================

GITHUB_API_VERSION = (
    "2026-03-10"
)

UPDATE_CHECK_TIMEOUT = 15.0


# ============================================================
# Linux Release
# ============================================================

APPIMAGE_SUFFIX = ".AppImage"

APPIMAGE_ARCHITECTURE = "x86_64"


def github_repository_configured(
) -> bool:
    owner = GITHUB_OWNER.strip()
    repository = (
        GITHUB_REPOSITORY.strip()
    )

    if not owner:
        return False

    if owner == "Poppey2001":
        return False

    if not repository:
        return False

    return True