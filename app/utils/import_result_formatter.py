from __future__ import annotations

from app.services.mod_importer import (
    ImportBatchResult,
    ImportStatus,
)
from app.i18n import tr

def _format_mod_count(
    count: int,
) -> str:
    key = (
        "common.mod_count.one"
        if count == 1
        else "common.mod_count.other"
    )

    return tr(
        key,
        count=count,
    )

def format_import_result(
    result: ImportBatchResult,
    *,
    max_items: int = 12,
) -> str:
    summary_lines: list[str] = []

    for item in result.items[:max_items]:
        if (
            item.status
            == ImportStatus.IMPORTED
        ):
            destination_name = (
                item.destination.name
                if item.destination is not None
                else tr("common.unknown")
            )

            summary_lines.append(
                f"✓ {item.source.name} "
                f"→ {destination_name}"
            )

        elif (
            item.status
            == ImportStatus.SKIPPED
        ):
            summary_lines.append(
                f"– {item.source.name}: "
                f"{item.message}"
            )

        else:
            summary_lines.append(
                f"✗ {item.source.name}: "
                f"{item.message}"
            )

    remaining_count = (
        len(result.items)
        - max_items
    )

    if remaining_count > 0:
        summary_lines.append(
            tr(
                "library.result.remaining",
                count=remaining_count,
            )
        )

    lines = [
        tr(
            "library.import_result.imported",
            count=result.imported_count,
        ),
        tr(
            "library.import_result.skipped",
            count=result.skipped_count,
        ),
        tr(
            "library.import_result.failed",
            count=result.failed_count,
        ),
        tr(
            "library.import_result.duration",
            seconds=result.duration_seconds,
        ),
    ]

    if summary_lines:
        lines.extend(
            (
                "",
                *summary_lines,
            )
        )

    return "\n".join(
        lines
    )

def format_import_status(
    result: ImportBatchResult,
) -> str:
    imported = _format_mod_count(
        result.imported_count
    )

    if result.failed_count:
        return tr(
            "library.import_result."
            "status_failed",
            imported=imported,
            failed=result.failed_count,
        )

    if result.skipped_count:
        return tr(
            "library.import_result."
            "status_skipped",
            imported=imported,
            skipped=result.skipped_count,
        )

    return tr(
        "library.import_result."
        "status_success",
        imported=imported,
    )