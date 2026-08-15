from __future__ import annotations

from PySide6.QtCore import (
    Signal,
)

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.services.update_service import (
    UpdateInfo,
)


class UpdateDialog(
    QDialog
):
    install_requested = Signal()

    def __init__(
        self,
        *,
        update: UpdateInfo,
        install_supported: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.update = update

        self.install_supported = (
            install_supported
        )

        self._busy = False

        self.title_label = QLabel(
            self
        )

        self.version_label = QLabel(
            self
        )

        self.source_label = QLabel(
            self
        )

        self.status_label = QLabel(
            self
        )

        self.progress_bar = (
            QProgressBar(
                self
            )
        )

        self.later_button = (
            QPushButton(
                self
            )
        )

        self.install_button = (
            QPushButton(
                self
            )
        )

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        self.setMinimumWidth(
            500
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        layout.setSpacing(
            14
        )

        self.title_label.setObjectName(
            "updateTitle"
        )

        self.version_label.setWordWrap(
            True
        )

        self.source_label.setWordWrap(
            True
        )

        self.status_label.setWordWrap(
            True
        )

        self.progress_bar.setVisible(
            False
        )

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(
            0
        )

        buttons = QHBoxLayout()

        buttons.addStretch(
            1
        )

        buttons.addWidget(
            self.later_button
        )

        buttons.addWidget(
            self.install_button
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.version_label
        )

        layout.addWidget(
            self.source_label
        )

        layout.addWidget(
            self.progress_bar
        )

        layout.addWidget(
            self.status_label
        )

        layout.addLayout(
            buttons
        )

        self.later_button.clicked.connect(
            self.reject
        )

        self.install_button.clicked.connect(
            self.install_requested.emit
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.setWindowTitle(
            tr(
                "updates.dialog.window_title"
            )
        )

        self.title_label.setText(
            tr(
                "updates.dialog.available"
            )
        )

        self.version_label.setText(
            tr(
                "updates.dialog.version",
                current=(
                    self.update
                    .current_version
                ),
                new=(
                    self.update
                    .version_display
                ),
            )
        )

        self.source_label.setText(
            tr(
                "updates.dialog.source",
                tag=(
                    self.update.tag
                ),
            )
        )

        self.later_button.setText(
            tr(
                "updates.dialog.later"
            )
        )

        self.install_button.setText(
            tr(
                "updates.dialog.install"
            )
        )

        if (
            not self.install_supported
            and not self._busy
        ):
            self.status_label.setText(
                tr(
                    "updates.dialog.install_unavailable"
                )
            )

        elif not self._busy:
            self.status_label.clear()

        self.install_button.setEnabled(
            self.install_supported
            and not self._busy
        )

    # ========================================================
    # Download
    # ========================================================

    def start_download(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            0,
        )

        self.install_button.setEnabled(
            False
        )

        self.later_button.setEnabled(
            False
        )

        self.status_label.setText(
            tr(
                "updates.status.downloading"
            )
        )

    def update_progress(
        self,
        current: int,
        total: int,
        name: str,
    ) -> None:
        if total > 0:
            percent = min(
                100,
                max(
                    0,
                    int(
                        (
                            current
                            * 100
                        )
                        / total
                    ),
                ),
            )

            self.progress_bar.setRange(
                0,
                100,
            )

            self.progress_bar.setValue(
                percent
            )

        else:
            self.progress_bar.setRange(
                0,
                0,
            )

        self.status_label.setText(
            tr(
                "updates.status.download_progress",
                current=(
                    self._format_bytes(
                        current
                    )
                ),
                total=(
                    self._format_bytes(
                        total
                    )
                    if total > 0
                    else "?"
                ),
                file=name,
            )
        )

    def show_installing(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            0,
        )

        self.status_label.setText(
            tr(
                "updates.status.installing"
            )
        )

    def show_error(
        self,
        message: str,
    ) -> None:
        self._busy = False

        self.progress_bar.setVisible(
            False
        )

        self.status_label.setText(
            tr(
                "updates.status.failed",
                error=message,
            )
        )

        self.later_button.setEnabled(
            True
        )

        self.install_button.setEnabled(
            self.install_supported
        )

    # ========================================================
    # Close
    # ========================================================

    def reject(
        self,
    ) -> None:
        if self._busy:
            return

        super().reject()

    # ========================================================
    # Bytes
    # ========================================================

    @staticmethod
    def _format_bytes(
        value: int,
    ) -> str:
        size = float(
            max(
                0,
                int(
                    value
                ),
            )
        )

        units = (
            "B",
            "KB",
            "MB",
            "GB",
        )

        for unit in units:
            if (
                size < 1024.0
                or unit
                == units[
                    -1
                ]
            ):
                if unit == "B":
                    return (
                        f"{int(size)} {unit}"
                    )

                return (
                    f"{size:.1f} {unit}"
                )

            size /= 1024.0

        return (
            f"{size:.1f} GB"
        )


__all__ = [
    "UpdateDialog",
]