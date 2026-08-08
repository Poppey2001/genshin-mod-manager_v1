from __future__ import annotations

from app.services.mod_importer import (
    ImportBatchResult,
    ImportStatus,
)


def format_import_result(
    result: ImportBatchResult,
    *,
    max_items: int = 12,
) -> str:
    """
    Erstellt den Text für die
    Import-Ergebnisanzeige.
    """
    summary_lines: list[str] = []

    for item in result.items[:max_items]:
        if (
            item.status
            == ImportStatus.IMPORTED
        ):
            destination_name = (
                item.destination.name
                if item.destination is not None
                else "Unbekannt"
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
            f"… und {remaining_count} weitere"
        )

    summary_text = "\n".join(
        summary_lines
    )

    header = (
        f"Importiert: "
        f"{result.imported_count}\n"
        f"Übersprungen: "
        f"{result.skipped_count}\n"
        f"Fehlgeschlagen: "
        f"{result.failed_count}\n"
        f"Dauer: "
        f"{result.duration_seconds:.1f} "
        "Sekunden"
    )

    if not summary_text:
        return header

    return (
        f"{header}\n\n"
        f"{summary_text}"
    )


def format_import_status(
    result: ImportBatchResult,
) -> str:
    """
    Kurzer Text für die Statusleiste
    der Bibliothek.
    """
    if result.failed_count:
        return (
            f"{result.imported_count} Mod(s) "
            "importiert, "
            f"{result.failed_count} "
            "fehlgeschlagen."
        )

    if result.skipped_count:
        return (
            f"{result.imported_count} Mod(s) "
            "importiert, "
            f"{result.skipped_count} "
            "übersprungen."
        )

    return (
        f"{result.imported_count} "
        "Mod(s) importiert."
    )