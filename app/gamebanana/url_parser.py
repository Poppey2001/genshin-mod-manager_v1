from __future__ import annotations

from dataclasses import dataclass

from urllib.parse import (
    urlparse,
)


class GameBananaUrlError(
    ValueError
):
    """Ungültige GameBanana-Mod-Referenz."""


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaModReference:
    mod_id: int

    original_value: str


def parse_mod_reference(
    value: str | int,
) -> GameBananaModReference:
    """
    Unterstützt:

    527716

    https://gamebanana.com/mods/527716

    https://www.gamebanana.com/mods/527716
    """

    if isinstance(
        value,
        int,
    ):
        if value <= 0:
            raise GameBananaUrlError(
                "Die GameBanana-Mod-ID muss größer als 0 sein."
            )

        return GameBananaModReference(
            mod_id=value,
            original_value=str(
                value
            ),
        )

    if not isinstance(
        value,
        str,
    ):
        raise GameBananaUrlError(
            "Die GameBanana-Referenz muss ein String oder Integer sein."
        )

    original_value = (
        value.strip()
    )

    if not original_value:
        raise GameBananaUrlError(
            "Es wurde keine GameBanana-URL oder Mod-ID angegeben."
        )

    # --------------------------------------------------
    # Reine Mod-ID
    # --------------------------------------------------

    if original_value.isdigit():
        mod_id = int(
            original_value
        )

        if mod_id <= 0:
            raise GameBananaUrlError(
                "Die GameBanana-Mod-ID muss größer als 0 sein."
            )

        return GameBananaModReference(
            mod_id=mod_id,
            original_value=(
                original_value
            ),
        )

    # --------------------------------------------------
    # URL
    # --------------------------------------------------

    parsed = urlparse(
        original_value
    )

    if parsed.scheme.casefold() not in {
        "http",
        "https",
    }:
        raise GameBananaUrlError(
            "Es wird eine HTTP- oder HTTPS-GameBanana-URL erwartet."
        )

    hostname = (
        parsed.hostname
        or ""
    ).casefold()

    if not (
        hostname == "gamebanana.com"
        or hostname.endswith(
            ".gamebanana.com"
        )
    ):
        raise GameBananaUrlError(
            "Die URL gehört nicht zu GameBanana."
        )

    path_parts = [
        part
        for part in (
            parsed.path
            .strip("/")
            .split("/")
        )
        if part
    ]

    if len(path_parts) < 2:
        raise GameBananaUrlError(
            "Die GameBanana-Mod-ID konnte aus der URL nicht gelesen werden."
        )

    if (
        path_parts[0].casefold()
        != "mods"
    ):
        raise GameBananaUrlError(
            "Die URL verweist nicht auf eine GameBanana-Mod-Submission."
        )

    raw_mod_id = (
        path_parts[1]
    )

    if not raw_mod_id.isdigit():
        raise GameBananaUrlError(
            "Die GameBanana-Mod-ID ist ungültig."
        )

    mod_id = int(
        raw_mod_id
    )

    if mod_id <= 0:
        raise GameBananaUrlError(
            "Die GameBanana-Mod-ID muss größer als 0 sein."
        )

    return GameBananaModReference(
        mod_id=mod_id,
        original_value=(
            original_value
        ),
    )