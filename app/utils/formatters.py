from __future__ import annotations

from datetime import datetime


def format_file_size(
    size: int | None,
) -> str:
    """Formatiert eine Dateigröße als lesbaren Text."""
    if size is None:
        return "Nicht berechnet"

    units = (
        "B",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
    )

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"

            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"


def format_timestamp(
    timestamp: float | None,
) -> str:
    """Formatiert einen Unix-Zeitstempel für die Oberfläche."""
    if timestamp is None:
        return "Unbekannt"

    return datetime.fromtimestamp(
        timestamp
    ).strftime(
        "%d.%m.%Y %H:%M"
    )