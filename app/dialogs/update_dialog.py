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

        self.title_label = QLabel()

        self.version_label = QLabel()

        self.files_label = QLabel()

        self.status_label = QLabel()

        self.progress_bar = (
            QProgressBar()
        )

        self.later_button = (
            QPushButton()
        )

        self.install_button = (
            QPushButton()
        )

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

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

        self.title_label.setWordWrap(
            True
        )

        self.version_label.setWordWrap(
            True
        )

        self.files_label.setWordWrap(
            True
        )

        self.status_label.setWordWrap(
            True
        )

        self.progress_bar.hide()

        self.progress_bar.setRange(
            0,
            max(
                1,
                self.update.file_count,
            ),
        )

        actions = QHBoxLayout()

        actions.addStretch(
            1
        )

        actions.addWidget(
            self.later_button
        )

        actions.addWidget(
            self.install_button
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.version_label
        )

        layout.addWidget(
            self.files_label
        )

        layout.addWidget(
            self.progress_bar
        )

        layout.addWidget(
            self.status_label
        )

        layout.addLayout(
            actions
        )

        self.later_button.clicked.connect(
            self.reject
        )

        self.install_button.clicked.connect(
            self.install_requested.emit
        )

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

        self.files_label.setText(
            tr(
                "updates.dialog.script_count",
                count=(
                    self.update
                    .file_count
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
                    "updates.dialog.script_install_unavailable"
                )
            )

        self.install_button.setEnabled(
            self.install_supported
            and not self._busy
        )

    def start_download(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.show()

        self.progress_bar.setRange(
            0,
            max(
                1,
                self.update.file_count,
            ),
        )

        self.progress_bar.setValue(
            0
        )

        self.status_label.setText(
            tr(
                "updates.status.downloading_scripts"
            )
        )

        self.install_button.setEnabled(
            False
        )

        self.later_button.setEnabled(
            False
        )

    def update_progress(
        self,
        current: int,
        total: int,
        path: str,
    ) -> None:
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

        self.status_label.setText(
            tr(
                "updates.status.downloading_file",
                current=current,
                total=total,
                path=path,
            )
        )

    def show_installing(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.setRange(
            0,
            0,
        )

        self.progress_bar.show()

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

        self.progress_bar.hide()

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

    def reject(
        self,
    ) -> None:
        if self._busy:
            return

        super().reject()


__all__ = [
    "UpdateDialog",
]