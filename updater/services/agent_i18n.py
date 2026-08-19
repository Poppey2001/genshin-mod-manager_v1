from __future__ import annotations

import json
import locale
import os
import sys
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES = ("de", "en")
_DEFAULT_LANGUAGE = "en"
_CURRENT_LANGUAGE = ""
_TRANSLATIONS: dict[str, dict[str, Any]] = {}


def system_language() -> str:
    for value in (
        os.environ.get("LANGUAGE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ):
        normalized = normalize_language(value)
        if normalized:
            return normalized

    try:
        value = locale.getlocale()[0] or ""
    except Exception:
        value = ""

    return normalize_language(value) or _DEFAULT_LANGUAGE


def normalize_language(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return ""
    prefix = text.split("_", 1)[0]
    return prefix if prefix in SUPPORTED_LANGUAGES else ""


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        return Path(str(frozen_root))
    return Path(__file__).resolve().parents[2]


def _locale_path(language: str) -> Path:
    return _resource_root() / "app" / "i18n" / "locales" / f"{language}.json"


def _load(language: str) -> dict[str, Any]:
    if language in _TRANSLATIONS:
        return _TRANSLATIONS[language]

    path = _locale_path(language)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    if not isinstance(data, dict):
        data = {}

    _TRANSLATIONS[language] = data
    return data


def set_language(language: object) -> str:
    global _CURRENT_LANGUAGE
    normalized = normalize_language(language) or system_language()
    _CURRENT_LANGUAGE = normalized
    return normalized


def current_language() -> str:
    if not _CURRENT_LANGUAGE:
        return set_language(system_language())
    return _CURRENT_LANGUAGE


def tr(key: str, **kwargs: object) -> str:
    language = current_language()
    primary = _load(language)
    fallback = _load(_DEFAULT_LANGUAGE)

    value = primary.get(key, fallback.get(key, key))
    template = str(value)

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


__all__ = [
    "SUPPORTED_LANGUAGES",
    "current_language",
    "normalize_language",
    "set_language",
    "system_language",
    "tr",
]
