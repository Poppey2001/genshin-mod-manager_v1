from __future__ import annotations

from app.workers.bulk_mod_worker import (
    BulkAction,
    BulkBatchResult,
    BulkItemStatus,
)
from app.i18n import tr

def format_bulk_result(
    result: BulkBatchResult,
    *,
    max_items: int = 15,
) -> str:
    action_key = {
        BulkAction.ENABLE:
            "library.bulk_result.action.enable",

        BulkAction.DISABLE:
            "library.bulk_result.action.disable",

        BulkAction.ADOPT:
            "library.bulk_result.action.adopt",
    }[result.action]

    action_text = tr(
        action_key
    )

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
            tr(
                "library.result.remaining",
                count=remaining_count,
            )
        )

    lines = [
        tr(
            "library.bulk_result.action",
            action=action_text,
        ),
        "",
        tr(
            "library.bulk_result.success",
            count=result.success_count,
        ),
        tr(
            "library.bulk_result.skipped",
            count=result.skipped_count,
        ),
        tr(
            "library.bulk_result.conflicts",
            count=result.conflict_count,
        ),
        tr(
            "library.bulk_result.failed",
            count=result.failed_count,
        ),
        tr(
            "library.bulk_result.duration",
            seconds=result.duration_seconds,
        ),
    ]

    if result.cancelled:
        lines.extend(
            (
                "",
                tr(
                    "library.bulk_result."
                    "cancelled_detail"
                ),
            )
        )

    if detail_lines:
        lines.extend(
            (
                "",
                *detail_lines,
            )
        )

    return "\n".join(
        lines
    )

def format_bulk_status(
    result: BulkBatchResult,
) -> str:
    if result.cancelled:
        return tr(
            "library.bulk_result."
            "status_cancelled"
        )

    return tr(
        "library.bulk_result."
        "status_completed",
        count=result.success_count,
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