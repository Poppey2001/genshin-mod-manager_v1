from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.config import DATA_DIR
from app.i18n import tr
from app.platform_support import resource_path


CUSTOM_ICON_ROOT = DATA_DIR / "custom-icons"
MAX_ICON_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_ICON_SUFFIXES = (
    ".png",
    ".svg",
    ".ico",
    ".jpg",
    ".jpeg",
    ".webp",
)

GAME_ICON_FILES = {
    "genshin-impact": "genshin-impact.png",
    "honkai-star-rail": "honkai-star-rail.png",
    "zenless-zone-zero": "zenless-zone-zero.png",
    "wuthering-waves": "wuthering-waves.png",
    "honkai-impact-3rd": "honkai-impact-3rd.png",
    "arknights-endfield": "arknights-endfield.png",
}

NAVIGATION_ICON_FILES = {
    "library": "library.svg",
    "gamebanana": "gamebanana.svg",
    "profiles": "profiles.svg",
    "conflicts": "conflicts.svg",
    "icons": "icons.svg",
    "settings": "settings.svg",
}

_CATEGORY_NAMES = {
    "games",
    "navigation",
    "application",
}

_SAFE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,80}$")


class IconManagerError(RuntimeError):
    pass


def ensure_custom_icon_directory() -> Path:
    CUSTOM_ICON_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )
    return CUSTOM_ICON_ROOT


def _safe_slot_directory(
    category: str,
) -> Path:
    normalized = str(category).strip().casefold()
    if normalized not in _CATEGORY_NAMES:
        raise IconManagerError(
            tr("icons.error.unsupported_category")
        )

    root = ensure_custom_icon_directory().resolve()
    directory = (root / normalized).resolve()

    try:
        directory.relative_to(root)
    except ValueError as error:
        raise IconManagerError(
            tr("icons.error.unsafe_path")
        ) from error

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    return directory


def _validate_key(
    key: str,
) -> str:
    normalized = str(key).strip().casefold()
    if not _SAFE_KEY_RE.fullmatch(normalized):
        raise IconManagerError(
            tr("icons.error.invalid_key")
        )
    return normalized


def _custom_icon_candidates(
    category: str,
    key: str,
) -> tuple[Path, ...]:
    directory = _safe_slot_directory(category)
    normalized_key = _validate_key(key)

    return tuple(
        directory / f"{normalized_key}{suffix}"
        for suffix in SUPPORTED_ICON_SUFFIXES
    )


def custom_icon_path(
    category: str,
    key: str,
) -> Path | None:
    for candidate in _custom_icon_candidates(
        category,
        key,
    ):
        if candidate.is_file():
            return candidate

    return None


def _custom_icon_source_candidates(
    category: str,
    key: str,
) -> tuple[Path, ...]:
    directory = _safe_slot_directory(category)
    normalized_key = _validate_key(key)

    return tuple(
        directory / f"{normalized_key}.source{suffix}"
        for suffix in SUPPORTED_ICON_SUFFIXES
    )


def custom_icon_source_path(
    category: str,
    key: str,
) -> Path | None:
    for candidate in _custom_icon_source_candidates(
        category,
        key,
    ):
        if candidate.is_file():
            return candidate

    return None


def store_custom_icon_source(
    category: str,
    key: str,
    source_file: Path | str,
) -> Path:
    source = Path(source_file).expanduser()

    if not source.is_file():
        raise IconManagerError(
            tr("icons.error.file_missing")
        )

    suffix = source.suffix.casefold()
    if suffix not in SUPPORTED_ICON_SUFFIXES:
        raise IconManagerError(
            tr("icons.error.unsupported_type")
        )

    try:
        source_size = source.stat().st_size
    except OSError as error:
        raise IconManagerError(
            tr("icons.error.unreadable")
        ) from error

    if source_size <= 0:
        raise IconManagerError(
            tr("icons.error.empty")
        )

    if source_size > MAX_ICON_FILE_SIZE:
        raise IconManagerError(
            tr("icons.error.too_large")
        )

    candidates = _custom_icon_source_candidates(
        category,
        key,
    )
    destination = next(
        path
        for path in candidates
        if path.suffix.casefold() == suffix
    )

    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except OSError as error:
            raise IconManagerError(
                tr("icons.error.previous_remove")
            ) from error

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

        raise IconManagerError(
            tr("icons.error.save_failed")
        ) from error

    return destination


def install_custom_icon(
    category: str,
    key: str,
    source_file: Path | str,
) -> Path:
    source = Path(source_file).expanduser()

    if not source.is_file():
        raise IconManagerError(
            tr("icons.error.file_missing")
        )

    suffix = source.suffix.casefold()
    if suffix not in SUPPORTED_ICON_SUFFIXES:
        raise IconManagerError(
            tr("icons.error.unsupported_type")
        )

    try:
        source_size = source.stat().st_size
    except OSError as error:
        raise IconManagerError(
            tr("icons.error.unreadable")
        ) from error

    if source_size <= 0:
        raise IconManagerError(
            tr("icons.error.empty")
        )

    if source_size > MAX_ICON_FILE_SIZE:
        raise IconManagerError(
            tr("icons.error.too_large")
        )

    candidates = _custom_icon_candidates(
        category,
        key,
    )
    destination = next(
        path
        for path in candidates
        if path.suffix.casefold() == suffix
    )

    for candidate in candidates:
        try:
            candidate.unlink(
                missing_ok=True
            )
        except OSError as error:
            raise IconManagerError(
                tr("icons.error.previous_remove")
            ) from error

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    try:
        shutil.copy2(
            source,
            temporary,
        )
        temporary.replace(
            destination
        )
    except OSError as error:
        try:
            temporary.unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise IconManagerError(
            tr("icons.error.save_failed")
        ) from error

    return destination



def install_custom_icon_data(
    category: str,
    key: str,
    data: bytes,
    *,
    suffix: str = ".png",
) -> Path:
    normalized_suffix = str(suffix).strip().casefold()
    if normalized_suffix not in SUPPORTED_ICON_SUFFIXES:
        raise IconManagerError(
            tr("icons.error.unsupported_type")
        )

    payload = bytes(data)
    if not payload:
        raise IconManagerError(
            tr("icons.error.empty")
        )

    if len(payload) > MAX_ICON_FILE_SIZE:
        raise IconManagerError(
            tr("icons.error.too_large")
        )

    candidates = _custom_icon_candidates(
        category,
        key,
    )
    destination = next(
        path
        for path in candidates
        if path.suffix.casefold() == normalized_suffix
    )

    for candidate in candidates:
        try:
            candidate.unlink(
                missing_ok=True
            )
        except OSError as error:
            raise IconManagerError(
                tr("icons.error.previous_remove")
            ) from error

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    try:
        temporary.write_bytes(payload)
        temporary.replace(destination)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

        raise IconManagerError(
            tr("icons.error.save_failed")
        ) from error

    return destination

def reset_custom_icon(
    category: str,
    key: str,
) -> bool:
    removed = False

    candidates = (
        *_custom_icon_candidates(
            category,
            key,
        ),
        *_custom_icon_source_candidates(
            category,
            key,
        ),
    )

    for candidate in candidates:
        if not candidate.exists():
            continue

        try:
            candidate.unlink()
        except OSError as error:
            raise IconManagerError(
                tr("icons.error.remove_failed")
            ) from error

        removed = True

    return removed


def reset_all_custom_icons() -> None:
    root = ensure_custom_icon_directory()

    try:
        shutil.rmtree(
            root,
            ignore_errors=False,
        )
    except FileNotFoundError:
        pass
    except OSError as error:
        raise IconManagerError(
            tr("icons.error.reset_failed")
        ) from error

    root.mkdir(
        parents=True,
        exist_ok=True,
    )


def default_game_icon_path(
    game_id: str,
) -> Path | None:
    filename = GAME_ICON_FILES.get(
        str(game_id).strip().casefold()
    )

    if not filename:
        return None

    candidate = Path(
        resource_path(
            "assets",
            "icons",
            "games",
            filename,
        )
    )

    return candidate if candidate.is_file() else None


def default_navigation_icon_path(
    icon_id: str,
) -> Path | None:
    filename = NAVIGATION_ICON_FILES.get(
        str(icon_id).strip().casefold()
    )

    if not filename:
        return None

    candidate = Path(
        resource_path(
            "assets",
            "icons",
            "navigation",
            filename,
        )
    )

    return candidate if candidate.is_file() else None


def default_application_icon_path() -> Path | None:
    candidate = Path(
        resource_path(
            "assets",
            "icons",
            "app.png",
        )
    )

    return candidate if candidate.is_file() else None


def resolve_game_icon_path(
    game_id: str,
) -> Path | None:
    return (
        custom_icon_path(
            "games",
            game_id,
        )
        or default_game_icon_path(
            game_id
        )
    )


def resolve_navigation_icon_path(
    icon_id: str,
) -> Path | None:
    return (
        custom_icon_path(
            "navigation",
            icon_id,
        )
        or default_navigation_icon_path(
            icon_id
        )
    )


def resolve_application_icon_path() -> Path | None:
    return (
        custom_icon_path(
            "application",
            "app",
        )
        or default_application_icon_path()
    )


def is_custom_icon(
    category: str,
    key: str,
) -> bool:
    return custom_icon_path(
        category,
        key,
    ) is not None


__all__ = [
    "CUSTOM_ICON_ROOT",
    "GAME_ICON_FILES",
    "IconManagerError",
    "NAVIGATION_ICON_FILES",
    "SUPPORTED_ICON_SUFFIXES",
    "custom_icon_path",
    "custom_icon_source_path",
    "default_application_icon_path",
    "default_game_icon_path",
    "default_navigation_icon_path",
    "ensure_custom_icon_directory",
    "install_custom_icon",
    "install_custom_icon_data",
    "is_custom_icon",
    "reset_all_custom_icons",
    "reset_custom_icon",
    "resolve_application_icon_path",
    "resolve_game_icon_path",
    "resolve_navigation_icon_path",
    "store_custom_icon_source",
]
