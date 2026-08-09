from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from app.i18n import tr

class LibraryOperationStatusWidget(QWidget):
    """
    Zeigt Status und Fortschritt der
    Bibliotheks-Operationen an.

    LibraryPage muss dadurch keinen
    QProgressBar und kein Status-Label
    mehr direkt verwalten.
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.progress_bar = QProgressBar(
            self
        )

        self.progress_bar.setVisible(
            False
        )

        self.progress_bar.setTextVisible(
            True
        )

        self.status_label = QLabel(
            self
        )

        self.status_label.setObjectName(
            "libraryStatus"
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            6
        )

        layout.addWidget(
            self.progress_bar
        )

        layout.addWidget(
            self.status_label
        )

    def set_status(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            message
        )

    def start_import(
        self,
        source_count: int,
    ) -> None:
        self._start_determinate(
            maximum=max(
                source_count,
                1,
            ),
            text=tr(
                "library.progress.import_preparing"
            ),
        )

    def update_import_progress(
        self,
        *,
        current: int,
        total: int,
        source_name: str,
    ) -> None:
        self._update_determinate(
            current=current,
            total=total,
            text=(
                f"{current}/{total} – "
                f"{source_name}"
            ),
        )

    def start_scan(
        self,
    ) -> None:
        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            0,
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            tr(
                "library.progress.scan_preparing"
            )
        )

    def update_scan_progress(
        self,
        *,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.progress_bar.setVisible(
            True
        )

        if total > 0:
            self.progress_bar.setRange(
                0,
                total,
            )

            self.progress_bar.setValue(
                current
            )

            self.progress_bar.setFormat(
                (
                    f"{current}/{total} – "
                    f"{mod_name}"
                )
            )

        else:
            self.progress_bar.setRange(
                0,
                0,
            )

            self.progress_bar.setFormat(
                tr(
                    "library.progress."
                    "scan_indeterminate",
                    name=mod_name,
                )
            )

        self.set_status(
            tr(
                "library.progress."
                "scan_processing",
                name=mod_name,
            )
        )

    def start_bulk(
        self,
        item_count: int,
    ) -> None:
        self._start_determinate(
            maximum=max(
                item_count,
                1,
            ),
            text=tr(
                "library.progress.bulk_preparing"
            ),
        )

    def update_bulk_progress(
        self,
        *,
        current: int,
        total: int,
        mod_name: str,
    ) -> None:
        self.set_status(
            tr(
                "library.progress."
                "bulk_processing",
                name=mod_name,
            )
        )
        self.set_status(
            tr(
                "library.progress.bulk_processing",
                name=mod_name,
            )
        )

    def finish_operation(
        self,
    ) -> None:
        self.progress_bar.setVisible(
            False
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            ""
        )

    def _start_determinate(
        self,
        *,
        maximum: int,
        text: str,
    ) -> None:
        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            max(
                maximum,
                1,
            ),
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            text
        )

    def _update_determinate(
        self,
        *,
        current: int,
        total: int,
        text: str,
    ) -> None:
        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            max(
                total,
                1,
            ),
        )

        self.progress_bar.setValue(
            current
        )

        self.progress_bar.setFormat(
            text
        )