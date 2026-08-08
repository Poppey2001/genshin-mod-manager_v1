from __future__ import annotations

from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
    BulkItemStatus,
)


def format_bulk_result(
    result: BulkBatchResult,
    *,
    max_items: int = 15,
) -> str:
    """
    Erstellt den ausführlichen Ergebnistext
    einer Sammelaktion.
    """

    action_text = {
        BulkAction.ENABLE: "Aktivieren",
        BulkAction.DISABLE: "Deaktivieren",
        BulkAction.ADOPT: "Übernehmen",
    }[result.action]

    detail_lines: list[str] = []

    for item in result.items[:max_items]:
        if item.status == BulkItemStatus.SUCCESS:
            symbol = "✓"

        elif item.status == BulkItemStatus.SKIPPED:
            symbol = "–"

        elif item.status == BulkItemStatus.CONFLICT:
            symbol = "!"

        else:
            symbol = "✗"

        detail_lines.append(
            f"{symbol} "
            f"{item.mod_name}: "
            f"{item.message}"
        )

    remaining_count = (
        len(result.items)
        - max_items
    )

    if remaining_count > 0:
        detail_lines.append(
            f"… und {remaining_count} weitere"
        )

    details = "\n".join(
        detail_lines
    )

    cancelled_text = ""

    if result.cancelled:
        cancelled_text = (
            "\n\n"
            "Die Sammelaktion wurde "
            "vorzeitig abgebrochen."
        )

    message = (
        f"Aktion: {action_text}\n\n"
        f"Erfolgreich: "
        f"{result.success_count}\n"
        f"Übersprungen: "
        f"{result.skipped_count}\n"
        f"Konflikte: "
        f"{result.conflict_count}\n"
        f"Fehlgeschlagen: "
        f"{result.failed_count}\n"
        f"Dauer: "
        f"{result.duration_seconds:.1f} "
        f"Sekunden"
        f"{cancelled_text}"
    )

    if details:
        message += (
            "\n\n"
            f"{details}"
        )

    return message


def format_bulk_status(
    result: BulkBatchResult,
) -> str:
    """
    Kurzer Status für die LibraryPage.
    """

    if result.cancelled:
        return (
            "Die Sammelaktion wurde "
            "abgebrochen."
        )

    return (
        "Sammelaktion abgeschlossen: "
        f"{result.success_count} "
        "erfolgreich."
    )


def bulk_result_requires_warning(
    result: BulkBatchResult,
) -> bool:
    """
    Bestimmt, ob das Ergebnis als
    Warnung dargestellt werden sollte.
    """

    return (
        result.failed_count > 0
        or result.conflict_count > 0
        or result.cancelled
    )