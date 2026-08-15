from __future__ import annotations

from PySide6.QtCore import (
    QUrl,
    Signal,
)

from PySide6.QtGui import (
    QDesktopServices,
)

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
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


class UpdateDialog(QDialog):
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

        self.notes_label = QLabel(
            self
        )

        self.notes_view = QTextBrowser(
            self
        )

        self.status_label = QLabel(
            self
        )

        self.progress_bar = QProgressBar(
            self
        )

        self.release_button = QPushButton(
            self
        )

        self.later_button = QPushButton(
            self
        )

        self.install_button = QPushButton(
            self
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
            560
        )

        self.setMinimumHeight(
            420
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

        self.notes_label.setObjectName(
            "updateSectionTitle"
        )

        self.notes_view.setOpenExternalLinks(
            False
        )

        self.notes_view.setPlainText(
            self.update.release_notes.strip()
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

        self.status_label.setWordWrap(
            True
        )

        self.release_button.clicked.connect(
            self._open_release_page
        )

        self.later_button.clicked.connect(
            self.reject
        )

        self.install_button.clicked.connect(
            self.install_requested.emit
        )

        button_layout = QHBoxLayout()

        button_layout.addWidget(
            self.release_button
        )

        button_layout.addStretch()

        button_layout.addWidget(
            self.later_button
        )

        button_layout.addWidget(
            self.install_button
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.version_label
        )

        layout.addWidget(
            self.notes_label
        )

        layout.addWidget(
            self.notes_view,
            stretch=1,
        )

        layout.addWidget(
            self.progress_bar
        )

        layout.addWidget(
            self.status_label
        )

        layout.addLayout(
            button_layout
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
                    self.update.current_version
                ),
                new=(
                    self.update.version
                ),
            )
        )

        self.notes_label.setText(
            tr(
                "updates.dialog.release_notes"
            )
        )

        if not (
            self.update.release_notes
            .strip()
        ):
            self.notes_view.setPlainText(
                tr(
                    "updates.dialog.no_notes"
                )
            )

        self.release_button.setText(
            tr(
                "updates.dialog.open_release"
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

        self.install_button.setEnabled(
            self.install_supported
            and not self._busy
        )

    def start_download(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(
            0
        )

        self.status_label.setText(
            tr(
                "updates.status.downloading"
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
        received: int,
        total: int,
    ) -> None:
        if total <= 0:
            self.progress_bar.setRange(
                0,
                0,
            )

            return

        self.progress_bar.setRange(
            0,
            100,
        )

        percentage = int(
            received
            / total
            * 100
        )

        self.progress_bar.setValue(
            max(
                0,
                min(
                    percentage,
                    100,
                ),
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

    def show_installing(
        self,
    ) -> None:
        self._busy = True

        self.progress_bar.setRange(
            0,
            0,
        )

        self.progress_bar.setVisible(
            True
        )

        self.status_label.setText(
            tr(
                "updates.status.installing"
            )
        )

    def reject(
        self,
    ) -> None:
        if self._busy:
            return

        super().reject()

    def _open_release_page(
        self,
    ) -> None:
        if not self.update.release_url:
            return

        QDesktopServices.openUrl(
            QUrl(
                self.update.release_url
            )
        )