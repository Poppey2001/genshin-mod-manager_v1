from __future__ import annotations

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from app.i18n import (
    tr,
)

from app.services.archive_security import (
    ArchiveSecurityReport,
)


def review_archive_security(
    *,
    reports: list[
        ArchiveSecurityReport
    ],
    parent: QWidget | None = None,
) -> bool:
    """
    Zeigt das Ergebnis der Archivprüfung.

    Rückgabe:
        True:
            Import darf weiterlaufen.

        False:
            Import wird abgebrochen.
    """

    blocked_lines: list[str] = []
    warning_lines: list[str] = []

    # ========================================================
    # Reports zusammenfassen
    # ========================================================

    for report in reports:
        for issue in (
            report.blocking_issues
        ):
            line = (
                f"• {report.source.name}: "
                f"{issue.message}"
            )

            if issue.member:
                line += (
                    "\n    "
                    f"{issue.member}"
                )

            blocked_lines.append(
                line
            )

        for issue in (
            report.warnings
        ):
            line = (
                f"• {report.source.name}"
            )

            if issue.member:
                line += (
                    f": {issue.member}"
                )

            else:
                line += (
                    f": {issue.message}"
                )

            warning_lines.append(
                line
            )

    # ========================================================
    # BLOCK
    # ========================================================

    if blocked_lines:
        visible_lines = (
            blocked_lines[:20]
        )

        message = (
            tr(
                "archive.security.blocked.message"
            )
            + "\n\n"
            + "\n\n".join(
                visible_lines
            )
        )

        remaining = (
            len(blocked_lines)
            - len(visible_lines)
        )

        if remaining > 0:
            message += tr(
                "archive.security.more",
                count=remaining,
            )

        QMessageBox.critical(
            parent,
            tr(
                "archive.security.blocked.title"
            ),
            message,
        )

        return False

    # ========================================================
    # Keine Warnungen
    # ========================================================

    if not warning_lines:
        return True

    # ========================================================
    # WARNUNG
    # ========================================================

    visible_lines = (
        warning_lines[:25]
    )

    message = (
        tr(
            "archive.security.warning.message"
        )
        + "\n\n"
        + "\n".join(
            visible_lines
        )
    )

    remaining = (
        len(warning_lines)
        - len(visible_lines)
    )

    if remaining > 0:
        message += tr(
            "archive.security.more",
            count=remaining,
        )

    answer = QMessageBox.warning(
        parent,
        tr(
            "archive.security.warning.title"
        ),
        message,
        (
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        ),
        QMessageBox.StandardButton.No,
    )

    return (
        answer
        == QMessageBox.StandardButton.Yes
    )