from __future__ import annotations

import json
import logging
import re

from typing import Any

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    urlencode,
    urljoin,
    urlsplit,
)

from urllib.request import (
    Request,
    urlopen,
)

from app.gamebanana.models import (
    GameBananaFile,
    GameBananaMod,
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

GAMEBANANA_SCREENSHOT_ROOT = (
    "https://images.gamebanana.com/img/ss/mods"
)


PREFERRED_MOD_FIELDS = (
    "name",
    "Owner().name",
    "Game().name",
    "Files().aFiles()",
    "Preview().sStructuredDataFullsizeUrl()",
    "Preview().sSubFeedImageUrl()",
    "screenshots",
    "Url().sProfileUrl()",
    "description",
)


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
    # Öffentliche API
    # ========================================================

    def fetch_mod(
        self,
        reference: str | int,
        *,
        expected_game: (
            GameDefinition
            | None
        ) = None,
        include_screenshots: bool = True,
    ) -> GameBananaMod:
        parsed_reference = (
            parse_mod_reference(
                reference
            )
        )

        fields = (
            self._supported_mod_fields(
                include_screenshots=(
                    include_screenshots
                )
            )
        )

        if "name" not in fields:
            raise GameBananaClientError(
                "GameBanana stellt das benötigte Mod-Namensfeld nicht bereit."
            )

        if (
            "Files().aFiles()"
            not in fields
        ):
            raise GameBananaClientError(
                "GameBanana stellt keine Dateiliste für Mods bereit."
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

        data = self._request_json(
            (
                f"{GAMEBANANA_API_ROOT}"
                "/Core/Item/Data?"
                f"{urlencode(parameters)}"
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
    # Allowed fields
    # ========================================================

    def _supported_mod_fields(
        self,
        *,
        include_screenshots: bool = True,
    ) -> tuple[str, ...]:
        allowed_fields = (
            self._get_allowed_mod_fields()
        )

        return tuple(
            field_name
            for field_name
            in PREFERRED_MOD_FIELDS
            if (
                field_name
                in allowed_fields
                and (
                    include_screenshots
                    or field_name
                    != "screenshots"
                )
            )
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

        data = self._request_json(
            (
                f"{GAMEBANANA_API_ROOT}"
                "/Core/Item/Data/AllowedFields?"
                f"{urlencode(parameters)}"
            )
        )

        if not isinstance(
            data,
            list,
        ):
            raise GameBananaClientError(
                "GameBanana hat keine gültige Feldliste zurückgegeben."
            )

        allowed_fields = {
            value
            for value in data
            if isinstance(
                value,
                str,
            )
        }

        self._allowed_mod_fields = (
            allowed_fields
        )

        return allowed_fields

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
                        "Die GameBanana-Mod wurde nicht gefunden."
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
                    "erreicht werden.\n\n"
                    f"{error}"
                )
            ) from error

        except TimeoutError as error:
            raise GameBananaClientError(
                "Die GameBanana-Anfrage hat zu lange gedauert."
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
                "GameBanana hat keine gültige JSON-Antwort geliefert."
            ) from error

    # ========================================================
    # API Response
    # ========================================================

    @staticmethod
    def _normalize_item_response(
        *,
        data: Any,
        fields: tuple[str, ...],
    ) -> dict[
        str,
        Any,
    ]:
        if isinstance(
            data,
            dict,
        ):
            return data

        # Fallback für APIs, die trotz return_keys
        # eine positionsbasierte Liste liefern.
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
            "GameBanana hat ein unerwartetes Datenformat geliefert."
        )

    def _build_mod(
        self,
        *,
        mod_id: int,
        data: dict[
            str,
            Any,
        ],
    ) -> GameBananaMod:
        name = self._optional_string(
            data.get(
                "name"
            )
        )

        if not name:
            raise GameBananaClientError(
                "Die GameBanana-Mod besitzt keinen gültigen Namen."
            )

        files = self._parse_files(
            data.get(
                "Files().aFiles()"
            )
        )

        preview_urls = (
            self._parse_preview_urls(
                fullsize_preview=(
                    data.get(
                        "Preview().sStructuredDataFullsizeUrl()"
                    )
                ),
                screenshots=(
                    data.get(
                        "screenshots"
                    )
                ),
                fallback_preview=(
                    data.get(
                        "Preview().sSubFeedImageUrl()"
                    )
                ),
            )
        )

        return GameBananaMod(
            id=mod_id,
            name=name,
            author=self._optional_string(
                data.get(
                    "Owner().name"
                )
            ),
            game_name=self._optional_string(
                data.get(
                    "Game().name"
                )
            ),
            profile_url=self._normalize_url(
                self._optional_string(
                    data.get(
                        "Url().sProfileUrl()"
                    )
                )
            ),
            preview_url=(
                preview_urls[0]
                if preview_urls
                else self._normalize_url(
                    self._optional_string(
                        data.get(
                            "Preview().sSubFeedImageUrl()"
                        )
                    )
                )
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
            preview_urls=(
                preview_urls
            ),
        )

    # ========================================================
    # Previews / Screenshots
    # ========================================================

    def _parse_preview_urls(
        self,
        *,
        fullsize_preview: Any,
        screenshots: Any,
        fallback_preview: Any,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Sammelt alle Bild-URLs, die GameBanana für die Submission
        liefert.

        Reihenfolge:
        1. Structured Fullsize Preview
        2. alle Einträge aus `screenshots`
        3. SubFeed Preview als Fallback

        `screenshots` hat sich historisch in mehreren Strukturen
        gezeigt. Deshalb wird die Struktur defensiv rekursiv
        ausgewertet.
        """

        result: list[str] = []
        seen: set[str] = set()

        def add(
            value: Any,
        ) -> None:
            if not isinstance(
                value,
                str,
            ):
                return

            normalized = (
                self._normalize_media_url(
                    value
                )
            )

            if (
                not normalized
                or normalized in seen
            ):
                return

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        add(
            fullsize_preview
        )

        self._collect_screenshot_urls(
            screenshots,
            add=add,
            key_hint="screenshots",
        )

        add(
            fallback_preview
        )

        return tuple(
            result
        )

    def _collect_screenshot_urls(
        self,
        value: Any,
        *,
        add,
        key_hint: str = "",
    ) -> None:
        """
        Liest GameBananas Screenshot-Feld defensiv aus.

        Wichtig:
        Core/Item/Data kann `screenshots` als bereits geparste
        Liste/Dictionary ODER als serialisierten String liefern.
        Bei manchen Mods sieht dieser String beispielsweise so aus:

            {"_sFile":"a.jpg",...},{"_sFile":"b.jpg",...}

        also mehrere JSON-Objekte ohne äußere eckige Klammern.
        Dieser String ist KEINE URL und darf niemals direkt an
        urllib.Request übergeben werden.
        """

        if value is None:
            return

        if isinstance(value, str):
            text = value.strip()

            if not text:
                return

            # 1) Echte absolute Bild-URL.
            if self._looks_like_media_url(text):
                add(text)
                return

            # 2) Serialisierte Screenshot-Struktur dekodieren.
            decoded = self._decode_screenshot_payload(text)

            if decoded is not None:
                self._collect_screenshot_urls(
                    decoded,
                    add=add,
                    key_hint="screenshots",
                )
                return

            # 3) Nur echte Fullsize-Dateinamen akzeptieren.
            #    _sFile100/_sFile220/_sFile530 sind lediglich
            #    Größenvarianten desselben Screenshots und werden
            #    absichtlich NICHT als eigene Gallery-Bilder geladen.
            normalized_hint = str(key_hint).casefold()

            if normalized_hint in {
                "_sfile",
                "file",
                "filename",
            }:
                built = self._build_screenshot_url(
                    filename=text,
                    base_url=None,
                )

                if built:
                    add(built)

            return

        if isinstance(value, dict):
            base = self._first_string(
                value,
                (
                    "_sBaseUrl",
                    "base_url",
                    "baseUrl",
                ),
            )

            filename = self._first_string(
                value,
                (
                    "_sFile",
                    "filename",
                    "file",
                ),
            )

            if filename:
                built = self._build_screenshot_url(
                    filename=filename,
                    base_url=base,
                )

                if built:
                    add(built)

            # Nested API variants such as _aImages are supported,
            # but scalar thumbnail fields are not promoted to
            # independent screenshots.
            for key, nested in value.items():
                if key in {
                    "_sBaseUrl",
                    "base_url",
                    "baseUrl",
                    "_sFile",
                    "filename",
                    "file",
                    "_sFile100",
                    "_sFile220",
                    "_sFile530",
                }:
                    continue

                if isinstance(
                    nested,
                    (
                        dict,
                        list,
                        tuple,
                        set,
                    ),
                ):
                    self._collect_screenshot_urls(
                        nested,
                        add=add,
                        key_hint=str(key),
                    )
                    continue

                if isinstance(nested, str):
                    # Unterstützt echte URL-Felder oder erneut
                    # serialisierte Nested-Strukturen.
                    nested_hint = str(key).casefold()
                    if (
                        "url" in nested_hint
                        or "image" in nested_hint
                        or "preview" in nested_hint
                        or "screen" in nested_hint
                    ):
                        self._collect_screenshot_urls(
                            nested,
                            add=add,
                            key_hint=str(key),
                        )

            return

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            for nested in value:
                self._collect_screenshot_urls(
                    nested,
                    add=add,
                    key_hint=key_hint,
                )

    @staticmethod
    def _decode_screenshot_payload(
        text: str,
    ) -> Any | None:
        """
        Dekodiert sowohl normales JSON als auch GameBananas
        komma-separierte Objektfolge ohne äußere [].
        """

        stripped = str(text).strip()

        if not stripped:
            return None

        candidates = [
            stripped,
        ]

        if (
            stripped.startswith("{")
            and stripped.endswith("}")
            and "},{" in stripped.replace(" ", "")
        ):
            candidates.append(
                "[" + stripped + "]"
            )

        for candidate in candidates:
            try:
                decoded = json.loads(candidate)
            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue

            if isinstance(
                decoded,
                (
                    dict,
                    list,
                    tuple,
                ),
            ):
                return decoded

        return None

    def _build_screenshot_url(
        self,
        *,
        filename: str,
        base_url: str | None,
    ) -> str | None:
        filename = str(filename).strip()

        if not filename:
            return None

        # Falls das API-Feld bereits eine echte URL enthält.
        if self._looks_like_media_url(filename):
            return self._normalize_media_url(filename)

        # Nur einfache Mediendateinamen akzeptieren. Dadurch kann
        # ein JSON-Blob oder anderer Fremdtext nicht versehentlich
        # zum Hostnamen werden.
        if (
            "/" in filename
            or "\\" in filename
            or "{" in filename
            or "}" in filename
            or "[" in filename
            or "]" in filename
            or '"' in filename
            or "'" in filename
        ):
            return None

        if not self._looks_like_image_filename(filename):
            return None

        base = (
            self._normalize_media_url(base_url)
            if base_url
            else GAMEBANANA_SCREENSHOT_ROOT
        )

        if not base:
            base = GAMEBANANA_SCREENSHOT_ROOT

        return (
            base.rstrip("/")
            + "/"
            + filename.lstrip("/")
        )

    @staticmethod
    def _looks_like_image_filename(
        value: str,
    ) -> bool:
        text = str(value).strip().casefold()

        return any(
            text.endswith(extension)
            for extension in (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".gif",
            )
        )

    @staticmethod
    def _looks_like_media_url(
        value: str,
    ) -> bool:
        text = str(value).strip()

        if not text:
            return False

        if not text.startswith(
            (
                "http://",
                "https://",
                "//",
            )
        ):
            return False

        lowered = text.casefold()

        return any(
            token in lowered
            for token in (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".gif",
                "/img/",
                "/image/",
                "/images/",
            )
        )

    @staticmethod
    def _normalize_media_url(
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        value = str(value).strip()

        if not value:
            return None

        # Struktur-/JSON-Text ist niemals eine URL.
        if value[0] in "{[\"'":
            return None

        if any(
            character in value
            for character in (
                "\n",
                "\r",
                "\t",
            )
        ):
            return None

        if value.startswith("//"):
            candidate = "https:" + value

        elif value.startswith(
            (
                "http://",
                "https://",
            )
        ):
            candidate = value

        elif value.startswith("/"):
            candidate = urljoin(
                GAMEBANANA_SITE_ROOT,
                value,
            )

        else:
            # Ein Host ohne Schema ist nur gültig, wenn sein
            # erster Teil wirklich wie ein Hostname aussieht.
            first_segment = value.split("/", 1)[0]

            if not re.fullmatch(
                r"[A-Za-z0-9.-]+(?::[0-9]+)?",
                first_segment,
            ):
                return None

            if "." not in first_segment:
                return None

            candidate = "https://" + value

        try:
            parsed = urlsplit(candidate)
        except ValueError:
            return None

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return None

        if not parsed.netloc:
            return None

        try:
            _ = parsed.hostname
        except ValueError:
            return None

        if not parsed.hostname:
            return None

        return candidate

    # ========================================================
    # Dateien
    # ========================================================

    def _parse_files(
        self,
        raw_files: Any,
    ) -> list[
        GameBananaFile
    ]:
        records: list[
            tuple[
                int | None,
                dict[str, Any],
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
            # Manche API-Antworten verwenden
            # die File-ID als Dictionary-Key.
            for (
                outer_key,
                record,
            ) in raw_files.items():
                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                fallback_id = (
                    self._safe_int(
                        outer_key
                    )
                )

                records.append(
                    (
                        fallback_id,
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

            name = self._first_string(
                record,
                (
                    "_sFile",
                    "filename",
                    "file",
                    "name",
                    "_sName",
                ),
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
                    "gamebanana-file"
                    f"-{file_id or len(parsed_files) + 1}"
                )

            parsed_files.append(
                GameBananaFile(
                    id=file_id,
                    name=name,
                    download_url=(
                        download_url
                    ),
                    size=self._first_int(
                        record,
                        (
                            "_nFilesize",
                            "_nFileSize",
                            "filesize",
                            "size",
                        ),
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

            if isinstance(
                value,
                str,
            ):
                normalized = (
                    self._normalize_url(
                        value
                    )
                )

                if normalized:
                    return normalized

        # Fallback bei leicht geänderten
        # GameBanana-Feldnamen.
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
                str(key)
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
    # Spielprüfung
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
    # Hilfsfunktionen
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

        value = value.strip()

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
            value = cls._safe_int(
                record.get(
                    key
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
            str,
        ):
            try:
                return int(
                    value.strip()
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