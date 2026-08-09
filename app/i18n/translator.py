from __future__ import annotations

import json

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QObject,
    Signal,
)


class TranslationManager(QObject):
    language_changed = Signal(str)

    def __init__(
        self,
        *,
        default_language: str = "de",
        fallback_language: str = "de",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._locales_directory = (
            Path(__file__).resolve().parent
            / "locales"
        )

        self._fallback_language = (
            fallback_language
        )

        self._language = (
            default_language
        )

        self._translations: dict[
            str,
            dict[str, str],
        ] = {}

        self._load_language(
            self._fallback_language
        )

        if (
            self._language
            != self._fallback_language
        ):
            self._load_language(
                self._language
            )

    @property
    def language(
        self,
    ) -> str:
        return self._language

    def set_language(
        self,
        language: str,
    ) -> bool:
        language = (
            language.strip().lower()
        )

        if not language:
            return False

        if language == self._language:
            return True

        if not self._load_language(
            language
        ):
            return False

        self._language = language

        self.language_changed.emit(
            language
        )

        return True

    def translate(
        self,
        key: str,
        **values: Any,
    ) -> str:
        text = self._translation_for(
            language=self._language,
            key=key,
        )

        if text is None:
            text = self._translation_for(
                language=(
                    self._fallback_language
                ),
                key=key,
            )

        if text is None:
            return f"[{key}]"

        if not values:
            return text

        try:
            return text.format(
                **values
            )

        except (
            KeyError,
            ValueError,
            IndexError,
        ):
            return text

    def available_languages(
        self,
    ) -> tuple[str, ...]:
        if not self._locales_directory.exists():
            return ()

        languages = sorted(
            path.stem
            for path
            in self._locales_directory.glob(
                "*.json"
            )
            if path.is_file()
        )

        return tuple(
            languages
        )

    def _translation_for(
        self,
        *,
        language: str,
        key: str,
    ) -> str | None:
        translations = (
            self._translations.get(
                language
            )
        )

        if translations is None:
            if not self._load_language(
                language
            ):
                return None

            translations = (
                self._translations.get(
                    language
                )
            )

        if translations is None:
            return None

        return translations.get(
            key
        )

    def _load_language(
        self,
        language: str,
    ) -> bool:
        if language in self._translations:
            return True

        path = (
            self._locales_directory
            / f"{language}.json"
        )

        if not path.is_file():
            return False

        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return False

        if not isinstance(
            data,
            dict,
        ):
            return False

        translations: dict[
            str,
            str,
        ] = {}

        for key, value in data.items():
            if not isinstance(
                key,
                str,
            ):
                continue

            if not isinstance(
                value,
                str,
            ):
                continue

            translations[key] = value

        self._translations[
            language
        ] = translations

        return True


translation_manager = (
    TranslationManager()
)


def tr(
    key: str,
    **values: Any,
) -> str:
    return (
        translation_manager.translate(
            key,
            **values,
        )
    )


def set_language(
    language: str,
) -> bool:
    return (
        translation_manager.set_language(
            language
        )
    )