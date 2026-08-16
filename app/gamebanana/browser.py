from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.gamebanana.client import GAMEBANANA_API_ROOT, GameBananaClient
from app.gamebanana.models import GameBananaBrowseResult, GameBananaMod


GAMEBANANA_GAME_IDS: dict[str, int] = {
    "genshin-impact": 8552,
    "honkai-star-rail": 18366,
    "zenless-zone-zero": 19567,
    "wuthering-waves": 20357,
    "honkai-impact-3rd": 10349,
    "arknights-endfield": 24320,
}


class GameBananaBrowserError(RuntimeError):
    """Fehler beim Laden der GameBanana-Modliste."""


class GameBananaBrowserService:
    """Lädt neue Mods und durchsucht die neuesten GameBanana-Seiten."""

    SEARCH_PAGE_COUNT = 3

    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def browse(
        self,
        *,
        game_id: str,
        page: int = 1,
        query: str = "",
        cancel_callback: Callable[[], bool] | None = None,
    ) -> GameBananaBrowseResult:
        game_id = str(game_id).strip()
        numeric_game_id = GAMEBANANA_GAME_IDS.get(game_id)
        if numeric_game_id is None:
            raise GameBananaBrowserError(
                "Für das ausgewählte Spiel ist noch keine GameBanana-Game-ID "
                f"hinterlegt: {game_id}"
            )

        normalized_query = str(query).strip().casefold()
        if normalized_query:
            return self._search_recent(
                game_id=game_id,
                numeric_game_id=numeric_game_id,
                query=normalized_query,
                cancel_callback=cancel_callback,
            )

        return self._load_page(
            game_id=game_id,
            numeric_game_id=numeric_game_id,
            page=max(1, int(page)),
            cancel_callback=cancel_callback,
        )

    def _load_page(
        self,
        *,
        game_id: str,
        numeric_game_id: int,
        page: int,
        cancel_callback: Callable[[], bool] | None,
    ) -> GameBananaBrowseResult:
        self._check_cancelled(cancel_callback)
        ids = self._fetch_new_ids(game_id=numeric_game_id, page=page)
        mods = self._fetch_mods(ids, cancel_callback=cancel_callback)
        return GameBananaBrowseResult(
            game_id=game_id,
            page=page,
            query="",
            mods=tuple(mods),
            has_previous=page > 1,
            has_next=bool(ids),
        )

    def _search_recent(
        self,
        *,
        game_id: str,
        numeric_game_id: int,
        query: str,
        cancel_callback: Callable[[], bool] | None,
    ) -> GameBananaBrowseResult:
        all_ids: list[int] = []
        seen: set[int] = set()

        for page in range(1, self.SEARCH_PAGE_COUNT + 1):
            self._check_cancelled(cancel_callback)
            page_ids = self._fetch_new_ids(game_id=numeric_game_id, page=page)
            if not page_ids:
                break
            for mod_id in page_ids:
                if mod_id in seen:
                    continue
                seen.add(mod_id)
                all_ids.append(mod_id)

        mods = self._fetch_mods(all_ids, cancel_callback=cancel_callback)
        matches = [
            mod
            for mod in mods
            if query in " ".join((mod.name or "", mod.author or "")).casefold()
        ]

        return GameBananaBrowseResult(
            game_id=game_id,
            page=1,
            query=query,
            mods=tuple(matches),
            has_previous=False,
            has_next=False,
        )

    def _fetch_new_ids(self, *, game_id: int, page: int) -> list[int]:
        parameters = {
            "page": max(1, int(page)),
            "itemtype": "Mod",
            "gameid": int(game_id),
            "format": "json_min",
        }
        url = f"{GAMEBANANA_API_ROOT}/Core/List/New?{urlencode(parameters)}"
        return self._extract_mod_ids(self._request_json(url))

    def _fetch_mods(
        self,
        ids: list[int],
        *,
        cancel_callback: Callable[[], bool] | None,
    ) -> list[GameBananaMod]:
        if not ids:
            return []

        client = GameBananaClient(timeout=self.timeout)
        mods: list[GameBananaMod] = []
        for mod_id in ids:
            self._check_cancelled(cancel_callback)
            try:
                mod = client.fetch_mod(mod_id, include_screenshots=False)
            except Exception:
                # Ein einzelner gelöschter/versteckter Eintrag soll die
                # komplette Browser-Seite nicht unbrauchbar machen.
                continue
            mods.append(mod)
        return mods

    def _request_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "XXMI-Mod-Manager/0.4",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_data = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
        except HTTPError as error:
            raise GameBananaBrowserError(
                f"GameBanana-API-Fehler HTTP {error.code}."
            ) from error
        except URLError as error:
            raise GameBananaBrowserError(
                f"GameBanana konnte nicht erreicht werden.\n\n{error}"
            ) from error
        except TimeoutError as error:
            raise GameBananaBrowserError(
                "Die GameBanana-Anfrage hat zu lange gedauert."
            ) from error

        try:
            return json.loads(raw_data.decode(charset))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GameBananaBrowserError(
                "GameBanana hat keine gültige JSON-Antwort geliefert."
            ) from error

    @classmethod
    def _extract_mod_ids(cls, data: Any) -> list[int]:
        if not isinstance(data, list):
            raise GameBananaBrowserError(
                "GameBanana hat eine unerwartete Modlisten-Antwort geliefert."
            )

        result: list[int] = []
        seen: set[int] = set()
        for entry in data:
            mod_id = cls._mod_id_from_entry(entry)
            if mod_id is None or mod_id <= 0 or mod_id in seen:
                continue
            seen.add(mod_id)
            result.append(mod_id)
        return result

    @staticmethod
    def _mod_id_from_entry(entry: Any) -> int | None:
        if isinstance(entry, bool):
            return None
        if isinstance(entry, int):
            return entry
        if isinstance(entry, str):
            try:
                return int(entry)
            except ValueError:
                return None
        if isinstance(entry, dict):
            for key in ("id", "_idRow", "itemid", "item_id"):
                value = entry.get(key)
                try:
                    if value is not None:
                        return int(value)
                except (TypeError, ValueError):
                    continue
            return None
        if isinstance(entry, (list, tuple)):
            for value in reversed(entry):
                if isinstance(value, bool):
                    continue
                try:
                    parsed = int(value)
                except (TypeError, ValueError):
                    continue
                if parsed > 0:
                    return parsed
        return None

    @staticmethod
    def _check_cancelled(
        cancel_callback: Callable[[], bool] | None,
    ) -> None:
        if cancel_callback is not None and cancel_callback():
            raise GameBananaBrowserError("GameBanana-Browser wurde abgebrochen.")


__all__ = [
    "GAMEBANANA_GAME_IDS",
    "GameBananaBrowseResult",
    "GameBananaBrowserError",
    "GameBananaBrowserService",
]
