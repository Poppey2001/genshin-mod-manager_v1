from __future__ import annotations

import json
import logging

from typing import Any

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    urlencode,
    urljoin,
)

from urllib.request import (
    Request,
    urlopen,
)

from app.gamebanana.models import (
    GameBananaBrowseResult,
    GameBananaFile,
    GameBananaMod,
    GameBananaModSummary,
)

from app.gamebanana.url_parser import (
    parse_mod_reference,
)

from app.games import (
    GameDefinition,
)


logger = logging.getLogger(
    __name__
)


GAMEBANANA_API_ROOT = (
    "https://api.gamebanana.com"
)

GAMEBANANA_SITE_ROOT = (
    "https://gamebanana.com"
)


# ============================================================
# Browser-Konfiguration
# ============================================================

RECENT_SEARCH_PAGES = 5

EXPECTED_PAGE_SIZE = 20


# ============================================================
# Gewünschte Felder
#
# Die tatsächlich erlaubten Felder werden dynamisch über
# Core/Item/Data/AllowedFields abgefragt.
# ============================================================

PREFERRED_MOD_FIELDS = (
    "name",
    "Owner().name",
    "Game().name",
    "Category().name",
    "Files().aFiles()",

    "Preview().sStructuredDataFullsizeUrl()",
    "Preview().sSubFeedImageUrl()",

    "screenshots",

    "Url().sProfileUrl()",
    "description",
    "downloads",
    "likes",
    "views",
    "date",
    "udate",
)


PREFERRED_SUMMARY_FIELDS = (
    "name",
    "Owner().name",
    "Game().name",
    "Category().name",

    # Hochauflösende Preview bevorzugen
    "Preview().sStructuredDataFullsizeUrl()",

    # Nur als Fallback
    "Preview().sSubFeedImageUrl()",

    "Url().sProfileUrl()",
    "downloads",
    "likes",
    "views",
    "date",
    "udate",
)


# ============================================================
# Exceptions
# ============================================================

class GameBananaClientError(
    RuntimeError
):
    """Allgemeiner GameBanana-API-Fehler."""


class GameBananaNotFoundError(
    GameBananaClientError
):
    """Die angeforderte Mod wurde nicht gefunden."""


class GameBananaGameMismatchError(
    GameBananaClientError
):
    """Die Mod gehört zu einem anderen Spiel."""


# ============================================================
# Client
# ============================================================

class GameBananaClient:
    def __init__(
        self,
        *,
        timeout: float = 20.0,
    ) -> None:
        self.timeout = timeout

        self._allowed_mod_fields: (
            set[str]
            | None
        ) = None

    # ========================================================
    # Einzelne Mod laden
    # ========================================================

    def fetch_mod(
        self,
        reference: str | int,
        *,
        expected_game: (
            GameDefinition
            | None
        ) = None,
    ) -> GameBananaMod:
        parsed_reference = (
            parse_mod_reference(
                reference
            )
        )

        fields = (
            self._supported_fields(
                PREFERRED_MOD_FIELDS
            )
        )

        if "name" not in fields:
            raise GameBananaClientError(
                (
                    "GameBanana stellt das benötigte "
                    "Mod-Namensfeld nicht bereit."
                )
            )

        if (
            "Files().aFiles()"
            not in fields
        ):
            raise GameBananaClientError(
                (
                    "GameBanana stellt keine "
                    "Dateiliste für Mods bereit."
                )
            )

        parameters = {
            "itemtype": "Mod",
            "itemid": (
                parsed_reference.mod_id
            ),
            "fields": ",".join(
                fields
            ),
            "return_keys": "1",
            "format": "json_min",
        }

        data = (
            self._request_json(
                (
                    f"{GAMEBANANA_API_ROOT}"
                    "/Core/Item/Data?"
                    f"{urlencode(parameters)}"
                )
            )
        )

        field_data = (
            self._normalize_item_response(
                data=data,
                fields=fields,
            )
        )

        mod = self._build_mod(
            mod_id=(
                parsed_reference.mod_id
            ),
            data=field_data,
        )

        if expected_game is not None:
            self._validate_game(
                mod=mod,
                expected_game=(
                    expected_game
                ),
            )

        return mod

    # ========================================================
    # Neueste Mods
    # ========================================================

    def browse_latest(
        self,
        *,
        game: GameDefinition,
        page: int = 1,
    ) -> GameBananaBrowseResult:
        page = max(
            1,
            int(
                page
            ),
        )

        mod_ids = (
            self._fetch_latest_ids(
                game=game,
                page=page,
            )
        )

        summaries = (
            self._fetch_summaries(
                mod_ids
            )
        )

        return (
            GameBananaBrowseResult(
                items=tuple(
                    summaries
                ),
                page=page,
                query=None,
                has_previous=(
                    page > 1
                ),
                has_next=(
                    len(
                        mod_ids
                    )
                    >= EXPECTED_PAGE_SIZE
                ),
                pages_scanned=1,
            )
        )

    # ========================================================
    # Recent Search
    # ========================================================

    def search_recent_mods(
        self,
        *,
        game: GameDefinition,
        query: str,
        max_pages: int = (
            RECENT_SEARCH_PAGES
        ),
    ) -> GameBananaBrowseResult:
        query = (
            query.strip()
        )

        normalized_query = (
            query.casefold()
        )

        if len(
            normalized_query
        ) < 2:
            raise GameBananaClientError(
                (
                    "Der Suchbegriff muss mindestens "
                    "zwei Zeichen enthalten."
                )
            )

        max_pages = max(
            1,
            min(
                int(
                    max_pages
                ),
                RECENT_SEARCH_PAGES,
            ),
        )

        matches: list[
            GameBananaModSummary
        ] = []

        seen_ids: set[
            int
        ] = set()

        pages_scanned = 0

        for page in range(
            1,
            max_pages + 1,
        ):
            mod_ids = (
                self._fetch_latest_ids(
                    game=game,
                    page=page,
                )
            )

            if not mod_ids:
                break

            pages_scanned += 1

            summaries = (
                self._fetch_summaries(
                    mod_ids
                )
            )

            for summary in summaries:
                haystack = " ".join(
                    (
                        summary.name,
                        summary.author
                        or "",
                        summary.category
                        or "",
                    )
                ).casefold()

                if (
                    normalized_query
                    not in haystack
                ):
                    continue

                if (
                    summary.id
                    in seen_ids
                ):
                    continue

                seen_ids.add(
                    summary.id
                )

                matches.append(
                    summary
                )

            if (
                len(
                    mod_ids
                )
                < EXPECTED_PAGE_SIZE
            ):
                break

        return (
            GameBananaBrowseResult(
                items=tuple(
                    matches
                ),
                page=1,
                query=query,
                has_previous=False,
                has_next=False,
                pages_scanned=(
                    pages_scanned
                ),
            )
        )

    # ========================================================
    # Core/List/New
    # ========================================================

    def _fetch_latest_ids(
        self,
        *,
        game: GameDefinition,
        page: int,
    ) -> list[int]:
        parameters = {
            "page": max(
                1,
                int(
                    page
                ),
            ),
            "itemtype": "Mod",
            "gameid": (
                self._gamebanana_id(
                    game
                )
            ),
            "include_updated": "1",
            "format": "json_min",
        }

        data = (
            self._request_json(
                (
                    f"{GAMEBANANA_API_ROOT}"
                    "/Core/List/New?"
                    f"{urlencode(parameters)}"
                )
            )
        )

        if not isinstance(
            data,
            list,
        ):
            raise GameBananaClientError(
                (
                    "GameBanana hat keine gültige "
                    "Modliste zurückgegeben."
                )
            )

        mod_ids: list[int] = []

        for item in data:
            # ----------------------------------------------
            # Dokumentiertes Format:
            #
            # ["Mod", 12345]
            # ----------------------------------------------

            if (
                isinstance(
                    item,
                    list,
                )
                and len(
                    item
                ) >= 2
            ):
                item_type = (
                    item[0]
                )

                item_id = (
                    self._safe_int(
                        item[1]
                    )
                )

                if (
                    isinstance(
                        item_type,
                        str,
                    )
                    and item_type.casefold()
                    == "mod"
                    and item_id
                    is not None
                ):
                    mod_ids.append(
                        item_id
                    )

                continue

            # ----------------------------------------------
            # Defensiver Fallback
            # ----------------------------------------------

            if isinstance(
                item,
                dict,
            ):
                item_type = (
                    self._first_string(
                        item,
                        (
                            "itemtype",
                            "type",
                            "_sItemType",
                        ),
                    )
                )

                item_id = (
                    self._first_int(
                        item,
                        (
                            "itemid",
                            "id",
                            "_idRow",
                        ),
                    )
                )

                if (
                    item_id
                    is not None
                    and (
                        item_type
                        is None
                        or item_type.casefold()
                        == "mod"
                    )
                ):
                    mod_ids.append(
                        item_id
                    )

        # Reihenfolge behalten,
        # doppelte IDs entfernen.
        return list(
            dict.fromkeys(
                mod_ids
            )
        )

    # ========================================================
    # Summary-Daten laden
    # ========================================================

    def _fetch_summaries(
        self,
        mod_ids: list[int],
    ) -> list[
        GameBananaModSummary
    ]:
        if not mod_ids:
            return []

        fields = (
            self._supported_fields(
                PREFERRED_SUMMARY_FIELDS
            )
        )

        if "name" not in fields:
            raise GameBananaClientError(
                (
                    "GameBanana stellt das benötigte "
                    "Mod-Namensfeld nicht bereit."
                )
            )

        summaries: list[
            GameBananaModSummary
        ] = []

        # --------------------------------------------------
        # Kleine Batches halten die Request-URL kurz.
        # --------------------------------------------------

        for start in range(
            0,
            len(
                mod_ids
            ),
            20,
        ):
            batch_ids = (
                mod_ids[
                    start:
                    start + 20
                ]
            )

            try:
                batch = (
                    self._fetch_summary_batch(
                        mod_ids=batch_ids,
                        fields=fields,
                    )
                )

                summaries.extend(
                    batch
                )

                continue

            except GameBananaClientError:
                logger.exception(
                    (
                        "GameBanana-Multicall "
                        "fehlgeschlagen; verwende "
                        "Einzelabfragen."
                    )
                )

            # ------------------------------------------------
            # Multicall-Fallback
            # ------------------------------------------------

            for mod_id in batch_ids:
                try:
                    summary = (
                        self._fetch_single_summary(
                            mod_id=mod_id,
                            fields=fields,
                        )
                    )

                except GameBananaClientError:
                    logger.exception(
                        (
                            "Summary für GameBanana-Mod "
                            "%s konnte nicht geladen werden."
                        ),
                        mod_id,
                    )

                    continue

                summaries.append(
                    summary
                )

        return summaries

    # ========================================================
    # Core/Item/Data Multicall
    # ========================================================

    def _fetch_summary_batch(
        self,
        *,
        mod_ids: list[int],
        fields: tuple[str, ...],
    ) -> list[
        GameBananaModSummary
    ]:
        parameters: list[
            tuple[
                str,
                str | int,
            ]
        ] = []

        field_string = ",".join(
            fields
        )

        for (
            index,
            mod_id,
        ) in enumerate(
            mod_ids
        ):
            parameters.extend(
                (
                    (
                        f"itemtype[{index}]",
                        "Mod",
                    ),
                    (
                        f"itemid[{index}]",
                        mod_id,
                    ),
                    (
                        f"fields[{index}]",
                        field_string,
                    ),
                )
            )

        data = (
            self._request_json(
                (
                    f"{GAMEBANANA_API_ROOT}"
                    "/Core/Item/Data?"
                    f"{urlencode(parameters)}"
                )
            )
        )

        if not isinstance(
            data,
            list,
        ):
            raise GameBananaClientError(
                (
                    "GameBanana hat keine gültige "
                    "Multicall-Antwort geliefert."
                )
            )

        summaries: list[
            GameBananaModSummary
        ] = []

        for (
            mod_id,
            item_data,
        ) in zip(
            mod_ids,
            data,
            strict=False,
        ):
            if (
                isinstance(
                    item_data,
                    dict,
                )
                and "error"
                in item_data
            ):
                continue

            normalized = (
                self._normalize_item_response(
                    data=item_data,
                    fields=fields,
                )
            )

            try:
                summary = (
                    self._build_summary(
                        mod_id=mod_id,
                        data=normalized,
                    )
                )

            except GameBananaClientError:
                continue

            summaries.append(
                summary
            )

        return summaries

    # ========================================================
    # Einzelnes Summary als Fallback
    # ========================================================

    def _fetch_single_summary(
        self,
        *,
        mod_id: int,
        fields: tuple[str, ...],
    ) -> GameBananaModSummary:
        parameters = {
            "itemtype": "Mod",
            "itemid": mod_id,
            "fields": ",".join(
                fields
            ),
            "return_keys": "1",
            "format": "json_min",
        }

        data = (
            self._request_json(
                (
                    f"{GAMEBANANA_API_ROOT}"
                    "/Core/Item/Data?"
                    f"{urlencode(parameters)}"
                )
            )
        )

        normalized = (
            self._normalize_item_response(
                data=data,
                fields=fields,
            )
        )

        return (
            self._build_summary(
                mod_id=mod_id,
                data=normalized,
            )
        )

    # ========================================================
    # Allowed Fields
    # ========================================================

    def _supported_fields(
        self,
        preferred_fields: tuple[
            str,
            ...,
        ],
    ) -> tuple[
        str,
        ...,
    ]:
        allowed_fields = (
            self._get_allowed_mod_fields()
        )

        return tuple(
            field_name
            for field_name
            in preferred_fields
            if field_name
            in allowed_fields
        )

    def _get_allowed_mod_fields(
        self,
    ) -> set[str]:
        if (
            self._allowed_mod_fields
            is not None
        ):
            return (
                self._allowed_mod_fields
            )

        parameters = {
            "itemtype": "Mod",
            "format": "json_min",
        }

        data = (
            self._request_json(
                (
                    f"{GAMEBANANA_API_ROOT}"
                    "/Core/Item/Data/AllowedFields?"
                    f"{urlencode(parameters)}"
                )
            )
        )

        if not isinstance(
            data,
            list,
        ):
            raise GameBananaClientError(
                (
                    "GameBanana hat keine gültige "
                    "Feldliste zurückgegeben."
                )
            )

        self._allowed_mod_fields = {
            value
            for value
            in data
            if isinstance(
                value,
                str,
            )
        }

        return (
            self._allowed_mod_fields
        )

    # ========================================================
    # HTTP
    # ========================================================

    def _request_json(
        self,
        url: str,
    ) -> Any:
        request = Request(
            url,
            headers={
                "Accept": (
                    "application/json"
                ),
                "User-Agent": (
                    "XXMI-Mod-Manager/0.4"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_data = (
                    response.read()
                )

                charset = (
                    response.headers
                    .get_content_charset()
                    or "utf-8"
                )

        except HTTPError as error:
            if error.code == 404:
                raise (
                    GameBananaNotFoundError(
                        (
                            "Die GameBanana-Mod "
                            "wurde nicht gefunden."
                        )
                    )
                ) from error

            raise GameBananaClientError(
                (
                    "GameBanana-API-Fehler "
                    f"HTTP {error.code}."
                )
            ) from error

        except URLError as error:
            raise GameBananaClientError(
                (
                    "GameBanana konnte nicht "
                    "erreicht werden."
                    "\n\n"
                    f"{error}"
                )
            ) from error

        except TimeoutError as error:
            raise GameBananaClientError(
                (
                    "Die GameBanana-Anfrage "
                    "hat zu lange gedauert."
                )
            ) from error

        try:
            return json.loads(
                raw_data.decode(
                    charset
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise GameBananaClientError(
                (
                    "GameBanana hat keine gültige "
                    "JSON-Antwort geliefert."
                )
            ) from error

    # ========================================================
    # Item Response normalisieren
    # ========================================================

    @staticmethod
    def _normalize_item_response(
        *,
        data: Any,
        fields: tuple[
            str,
            ...,
        ],
    ) -> dict[
        str,
        Any,
    ]:
        if isinstance(
            data,
            dict,
        ):
            return data

        if isinstance(
            data,
            list,
        ):
            return {
                field_name: value
                for (
                    field_name,
                    value,
                )
                in zip(
                    fields,
                    data,
                    strict=False,
                )
            }

        raise GameBananaClientError(
            (
                "GameBanana hat ein unerwartetes "
                "Datenformat geliefert."
            )
        )

    # ========================================================
    # Summary bauen
    # ========================================================

    def _build_summary(
        self,
        *,
        mod_id: int,
        data: dict[
            str,
            Any,
        ],
    ) -> GameBananaModSummary:
        name = (
            self._optional_string(
                data.get(
                    "name"
                )
            )
        )

        if not name:
            raise GameBananaClientError(
                (
                    "Die GameBanana-Mod besitzt "
                    "keinen gültigen Namen."
                )
            )

        return (
            GameBananaModSummary(
                id=mod_id,
                name=name,
                author=(
                    self._optional_string(
                        data.get(
                            "Owner().name"
                        )
                    )
                ),
                game_name=(
                    self._optional_string(
                        data.get(
                            "Game().name"
                        )
                    )
                ),
                category=(
                    self._optional_string(
                        data.get(
                            "Category().name"
                        )
                    )
                ),
                profile_url=(
                    self._normalize_url(
                        self._optional_string(
                            data.get(
                                "Url().sProfileUrl()"
                            )
                        )
                    )
                ),
                preview_url=(
                    self._normalize_url(
                        self._optional_string(
                            data.get(
                                "Preview().sStructuredDataFullsizeUrl()"
                            )
                        )
                        or self._optional_string(
                            data.get(
                                "Preview().sSubFeedImageUrl()"
                            )
                        )
                    )
                ),
                downloads=(
                    self._safe_int(
                        data.get(
                            "downloads"
                        )
                    )
                ),
                likes=(
                    self._safe_int(
                        data.get(
                            "likes"
                        )
                    )
                ),
                views=(
                    self._safe_int(
                        data.get(
                            "views"
                        )
                    )
                ),
                date_added=(
                    self._safe_int(
                        data.get(
                            "date"
                        )
                    )
                ),
                date_updated=(
                    self._safe_int(
                        data.get(
                            "udate"
                        )
                    )
                ),
            )
        )

    # ========================================================
    # Vollständige Mod bauen
    # ========================================================

    def _build_mod(
        self,
        *,
        mod_id: int,
        data: dict[
            str,
            Any,
        ],
    ) -> GameBananaMod:
        summary = (
            self._build_summary(
                mod_id=mod_id,
                data=data,
            )
        )

        files = (
            self._parse_files(
                data.get(
                    "Files().aFiles()"
                )
            )
        )
        image_urls = (
            self._parse_image_urls(
                data
            )
        )
        return (
            GameBananaMod(
                id=summary.id,
                name=summary.name,
                author=(
                    summary.author
                ),
                game_name=(
                    summary.game_name
                ),
                profile_url=(
                    summary.profile_url
                ),
                preview_url=(
                    summary.preview_url
                ),
                description=(
                    self._optional_string(
                        data.get(
                            "description"
                        )
                    )
                ),
                files=tuple(
                    files
                ),
                image_urls=(
                    image_urls
                ),
                category=(
                    summary.category
                ),
                downloads=(
                    summary.downloads
                ),
                likes=(
                    summary.likes
                ),
                views=(
                    summary.views
                ),
                date_added=(
                    summary.date_added
                ),
                date_updated=(
                    summary.date_updated
                ),
            )
        )

    # ========================================================
    # Dateien
    # ========================================================
    # ========================================================
    # Bilder
    # ========================================================

    def _parse_image_urls(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> tuple[
        str,
        ...,
    ]:
        urls: list[str] = []

        # ----------------------------------------------------
        # Hochauflösende Hauptpreview zuerst
        # ----------------------------------------------------

        for field_name in (
            (
                "Preview()."
                "sStructuredDataFullsizeUrl()"
            ),
            (
                "Preview()."
                "sSubFeedImageUrl()"
            ),
        ):
            value = (
                self._optional_string(
                    data.get(
                        field_name
                    )
                )
            )

            if value:
                normalized = (
                    self._normalize_url(
                        value
                    )
                )

                if normalized:
                    urls.append(
                        normalized
                    )

        # ----------------------------------------------------
        # Screenshots
        # ----------------------------------------------------

        screenshots = (
            data.get(
                "screenshots"
            )
        )

        self._collect_image_urls(
            screenshots,
            urls,
        )

        # ----------------------------------------------------
        # Reihenfolge behalten,
        # Duplikate entfernen.
        # ----------------------------------------------------

        result: list[str] = []

        seen: set[str] = set()

        for url in urls:
            if url in seen:
                continue

            seen.add(
                url
            )

            result.append(
                url
            )

        return tuple(
            result
        )

    def _collect_image_urls(
        self,
        value: Any,
        output: list[str],
    ) -> None:
        if value is None:
            return

        # ----------------------------------------------------
        # Direkte URL
        # ----------------------------------------------------

        if isinstance(
            value,
            str,
        ):
            candidate = (
                value.strip()
            )

            if candidate.startswith(
                (
                    "http://",
                    "https://",
                    "//",
                )
            ):
                normalized = (
                    self._normalize_url(
                        candidate
                    )
                )

                if normalized:
                    output.append(
                        normalized
                    )

            return

        # ----------------------------------------------------
        # Liste
        # ----------------------------------------------------

        if isinstance(
            value,
            list,
        ):
            for item in value:
                self._collect_image_urls(
                    item,
                    output,
                )

            return

        # ----------------------------------------------------
        # Dictionary
        # ----------------------------------------------------

        if not isinstance(
            value,
            dict,
        ):
            return

        # Manche GameBanana-Strukturen liefern
        # Base-URL + Dateinamen separat.
        base_url = (
            self._first_string(
                value,
                (
                    "_sBaseUrl",
                    "base_url",
                    "baseUrl",
                ),
            )
        )

        filename = (
            self._first_string(
                value,
                (
                    "_sFile",
                    "filename",
                    "file",
                ),
            )
        )

        if (
            base_url
            and filename
        ):
            combined = (
                base_url.rstrip(
                    "/"
                )
                + "/"
                + filename.lstrip(
                    "/"
                )
            )

            normalized = (
                self._normalize_url(
                    combined
                )
            )

            if normalized:
                output.append(
                    normalized
                )

        # Typische direkte URL-Felder
        for key in (
            "_sFullSizeUrl",
            "_sImageUrl",
            "_sUrl",
            "fullsize",
            "full",
            "image",
            "image_url",
            "url",
            "src",
        ):
            raw_url = (
                value.get(
                    key
                )
            )

            if not isinstance(
                raw_url,
                str,
            ):
                continue

            raw_url = (
                raw_url.strip()
            )

            if not raw_url:
                continue

            if not raw_url.startswith(
                (
                    "http://",
                    "https://",
                    "//",
                )
            ):
                continue

            normalized = (
                self._normalize_url(
                    raw_url
                )
            )

            if normalized:
                output.append(
                    normalized
                )

        # ----------------------------------------------------
        # Unbekannte verschachtelte Strukturen
        # defensiv ebenfalls durchsuchen.
        # ----------------------------------------------------

        for child in value.values():
            if isinstance(
                child,
                (
                    list,
                    dict,
                ),
            ):
                self._collect_image_urls(
                    child,
                    output,
                )
    def _parse_files(
        self,
        raw_files: Any,
    ) -> list[
        GameBananaFile
    ]:
        records: list[
            tuple[
                int | None,
                dict[
                    str,
                    Any,
                ],
            ]
        ] = []

        if isinstance(
            raw_files,
            list,
        ):
            for record in raw_files:
                if isinstance(
                    record,
                    dict,
                ):
                    records.append(
                        (
                            None,
                            record,
                        )
                    )

        elif isinstance(
            raw_files,
            dict,
        ):
            for (
                outer_key,
                record,
            ) in raw_files.items():
                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                records.append(
                    (
                        self._safe_int(
                            outer_key
                        ),
                        record,
                    )
                )

        parsed_files: list[
            GameBananaFile
        ] = []

        for (
            fallback_id,
            record,
        ) in records:
            file_id = (
                self._first_int(
                    record,
                    (
                        "_idRow",
                        "id",
                        "fileid",
                        "_id",
                    ),
                )
                or fallback_id
            )

            name = (
                self._first_string(
                    record,
                    (
                        "_sFile",
                        "filename",
                        "file",
                        "name",
                        "_sName",
                    ),
                )
            )

            download_url = (
                self._find_download_url(
                    record
                )
            )

            if not download_url:
                logger.warning(
                    (
                        "GameBanana-Datei %s "
                        "besitzt keine Download-URL."
                    ),
                    file_id,
                )

                continue

            if not name:
                name = (
                    "gamebanana-file-"
                    f"{file_id or len(parsed_files) + 1}"
                )

            parsed_files.append(
                GameBananaFile(
                    id=file_id,
                    name=name,
                    download_url=(
                        download_url
                    ),
                    size=(
                        self._first_int(
                            record,
                            (
                                "_nFilesize",
                                "_nFileSize",
                                "filesize",
                                "size",
                            ),
                        )
                    ),
                    description=(
                        self._first_string(
                            record,
                            (
                                "_sDescription",
                                "description",
                            ),
                        )
                    ),
                    date_added=(
                        self._first_int(
                            record,
                            (
                                "_tsDateAdded",
                                "date_added",
                                "date",
                            ),
                        )
                    ),
                    raw=dict(
                        record
                    ),
                )
            )

        return parsed_files

    def _find_download_url(
        self,
        record: dict[
            str,
            Any,
        ],
    ) -> str | None:
        preferred_keys = (
            "_sDownloadUrl",
            "download_url",
            "downloadUrl",
            "_sFileUrl",
            "_sUrl",
            "url",
        )

        for key in preferred_keys:
            value = (
                record.get(
                    key
                )
            )

            if not isinstance(
                value,
                str,
            ):
                continue

            normalized = (
                self._normalize_url(
                    value
                )
            )

            if normalized:
                return normalized

        # --------------------------------------------------
        # Fallback bei leicht geänderten API-Feldnamen
        # --------------------------------------------------

        for (
            key,
            value,
        ) in record.items():
            if not isinstance(
                value,
                str,
            ):
                continue

            normalized_key = (
                str(
                    key
                )
                .casefold()
            )

            if (
                "url"
                not in normalized_key
            ):
                continue

            if not (
                "download"
                in normalized_key
                or "file"
                in normalized_key
            ):
                continue

            normalized = (
                self._normalize_url(
                    value
                )
            )

            if normalized:
                return normalized

        return None

    # ========================================================
    # Spiel validieren
    # ========================================================

    def _validate_game(
        self,
        *,
        mod: GameBananaMod,
        expected_game: GameDefinition,
    ) -> None:
        if not mod.game_name:
            logger.warning(
                (
                    "GameBanana hat keinen "
                    "Spielnamen für Mod %s geliefert."
                ),
                mod.id,
            )

            return

        expected = (
            self._normalize_game_name(
                expected_game.name
            )
        )

        actual = (
            self._normalize_game_name(
                mod.game_name
            )
        )

        if actual == expected:
            return

        raise (
            GameBananaGameMismatchError(
                (
                    f"Die Mod „{mod.name}“ gehört "
                    f"zu „{mod.game_name}“, nicht zu "
                    f"„{expected_game.name}“."
                )
            )
        )

    @staticmethod
    def _normalize_game_name(
        value: str,
    ) -> str:
        return "".join(
            character
            for character
            in value.casefold()
            if character.isalnum()
        )

    # ========================================================
    # GameBanana Game ID
    # ========================================================

    @staticmethod
    def _gamebanana_id(
        game: GameDefinition,
    ) -> int:
        # Neue Property
        value = getattr(
            game,
            "gamebanana_id",
            None,
        )

        if callable(
            value
        ):
            value = value()

        # Dataclass-Feld
        if value is None:
            value = getattr(
                game,
                "gamebanana_game_id",
                None,
            )

        try:
            game_id = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:
            raise GameBananaClientError(
                (
                    f"Für „{game.name}“ ist keine "
                    "gültige GameBanana-Spiel-ID "
                    "konfiguriert."
                )
            ) from error

        if game_id <= 0:
            raise GameBananaClientError(
                (
                    f"Für „{game.name}“ ist keine "
                    "gültige GameBanana-Spiel-ID "
                    "konfiguriert."
                )
            )

        return game_id

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if not isinstance(
            value,
            str,
        ):
            return None

        value = (
            value.strip()
        )

        return (
            value
            or None
        )

    @classmethod
    def _first_string(
        cls,
        record: dict[
            str,
            Any,
        ],
        keys: tuple[
            str,
            ...,
        ],
    ) -> str | None:
        for key in keys:
            value = (
                cls._optional_string(
                    record.get(
                        key
                    )
                )
            )

            if value:
                return value

        return None

    @classmethod
    def _first_int(
        cls,
        record: dict[
            str,
            Any,
        ],
        keys: tuple[
            str,
            ...,
        ],
    ) -> int | None:
        for key in keys:
            value = (
                cls._safe_int(
                    record.get(
                        key
                    )
                )
            )

            if value is not None:
                return value

        return None

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int | None:
        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            int,
        ):
            return value

        if isinstance(
            value,
            float,
        ):
            return int(
                value
            )

        if isinstance(
            value,
            str,
        ):
            try:
                return int(
                    float(
                        value.strip()
                    )
                )

            except ValueError:
                return None

        return None

    @staticmethod
    def _normalize_url(
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        return urljoin(
            GAMEBANANA_SITE_ROOT,
            value,
        )


__all__ = [
    "GameBananaClient",
    "GameBananaClientError",
    "GameBananaNotFoundError",
    "GameBananaGameMismatchError",
    "RECENT_SEARCH_PAGES",
]