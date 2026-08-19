from __future__ import annotations

from PySide6.QtCore import (
    QUrl,
    Signal,
)

from PySide6.QtGui import (
    QDesktopServices,
    QFontDatabase,
    QGuiApplication,
)

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
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
        self._error_message = ""

        self.setObjectName(
            "updateDialog"
        )

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

        self.error_frame = QFrame(
            self
        )

        self.error_frame.setObjectName(
            "updateErrorFrame"
        )

        self.error_title_label = QLabel(
            self.error_frame
        )

        self.error_title_label.setObjectName(
            "updateErrorTitle"
        )

        self.error_details = QPlainTextEdit(
            self.error_frame
        )

        self.error_details.setObjectName(
            "updateErrorDetails"
        )

        self.error_details.setReadOnly(
            True
        )

        self.error_details.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )

        fixed_font = (
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        )

        self.error_details.setFont(
            fixed_font
        )

        self.copy_error_button = QPushButton(
            self.error_frame
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

        self.install_button.setObjectName(
            "primaryButton"
        )

        self._build_ui()
        self._apply_style()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _build_ui(
        self,
    ) -> None:
        self.resize(
            720,
            560,
        )

        self.setMinimumSize(
            620,
            470,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            22,
            20,
            22,
            18,
        )

        layout.setSpacing(
            12
        )

        self.title_label.setObjectName(
            "updateTitle"
        )

        self.title_label.setWordWrap(
            True
        )

        self.version_label.setObjectName(
            "updateVersion"
        )

        self.version_label.setWordWrap(
            True
        )

        self.notes_label.setObjectName(
            "updateSectionTitle"
        )

        self.notes_view.setObjectName(
            "updateNotes"
        )

        self.notes_view.setOpenExternalLinks(
            False
        )

        self.notes_view.setPlainText(
            self.update.release_notes.strip()
        )

        self.status_label.setObjectName(
            "updateStatus"
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

        error_layout = QVBoxLayout(
            self.error_frame
        )

        error_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        error_layout.setSpacing(
            8
        )

        error_layout.addWidget(
            self.error_title_label
        )

        self.error_details.setMinimumHeight(
            115
        )

        self.error_details.setMaximumHeight(
            190
        )

        error_layout.addWidget(
            self.error_details
        )

        error_buttons = QHBoxLayout()

        error_buttons.addStretch(
            1
        )

        error_buttons.addWidget(
            self.copy_error_button
        )

        error_layout.addLayout(
            error_buttons
        )

        self.error_frame.hide()

        self.copy_error_button.clicked.connect(
            self._copy_error
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

        button_layout.setSpacing(
            9
        )

        button_layout.addWidget(
            self.release_button
        )

        button_layout.addStretch(
            1
        )

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

        layout.addWidget(
            self.error_frame
        )

        layout.addLayout(
            button_layout
        )

    def _apply_style(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QDialog#updateDialog {
                background-color: #111419;
                color: #e8ebf0;
            }

            QDialog#updateDialog QLabel {
                background: transparent;
                color: #dfe4eb;
            }

            QDialog#updateDialog QLabel#updateTitle {
                color: #f7f8fa;
                font-size: 20px;
                font-weight: 800;
            }

            QDialog#updateDialog QLabel#updateVersion {
                color: #d5dae2;
                font-size: 13px;
            }

            QDialog#updateDialog QLabel#updateSectionTitle,
            QDialog#updateDialog QLabel#updateErrorTitle {
                color: #eef1f5;
                font-weight: 700;
            }

            QDialog#updateDialog QLabel#updateStatus {
                color: #b7c0cc;
            }

            QDialog#updateDialog QTextBrowser#updateNotes,
            QDialog#updateDialog QPlainTextEdit#updateErrorDetails {
                background-color: #171b22;
                color: #e6e9ee;
                border: 1px solid #2e3540;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #6657c9;
                selection-color: #ffffff;
            }

            QDialog#updateDialog QFrame#updateErrorFrame {
                background-color: #1b1719;
                border: 1px solid #673a42;
                border-radius: 9px;
            }

            QDialog#updateDialog QProgressBar {
                min-height: 16px;
                background-color: #1b2028;
                color: #f1f3f6;
                border: 1px solid #323a46;
                border-radius: 7px;
                text-align: center;
            }

            QDialog#updateDialog QProgressBar::chunk {
                background-color: #6758d1;
                border-radius: 6px;
            }

            QDialog#updateDialog QPushButton {
                min-height: 34px;
                padding: 0 13px;
                background-color: #282e38;
                color: #edf0f4;
                border: 1px solid #3a424f;
                border-radius: 7px;
                font-weight: 600;
            }

            QDialog#updateDialog QPushButton:hover {
                background-color: #343b47;
                border-color: #505a69;
            }

            QDialog#updateDialog QPushButton:disabled {
                background-color: #1a1f26;
                color: #69717d;
                border-color: #292f38;
            }

            QDialog#updateDialog QPushButton#primaryButton {
                background-color: #6758d1;
                color: #ffffff;
                border-color: #7a6de0;
            }

            QDialog#updateDialog QPushButton#primaryButton:hover {
                background-color: #7566dd;
                border-color: #8a7de7;
            }

            QToolTip {
                background-color: #20242c;
                color: #f1f3f6;
                border: 1px solid #3a404b;
                padding: 5px 7px;
            }
            """
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

        self.error_title_label.setText(
            tr(
                "updates.dialog.error_details"
            )
        )

        self.copy_error_button.setText(
            tr(
                "updates.dialog.copy_error"
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
            and not self._error_message
        ):
            if not (
                self.update.release_ready
            ):
                self.status_label.setText(
                    tr(
                        "updates.dialog.release_not_ready",
                        version=self.update.version,
                    )
                )

            else:
                self.status_label.setText(
                    tr(
                        "updates.dialog.install_unavailable"
                    )
                )

        self.install_button.setEnabled(
            self.install_supported
            and not self._busy
        )

    def _hide_error(
        self,
    ) -> None:
        self._error_message = ""

        self.error_details.clear()

        self.error_frame.hide()

    def start_download(
        self,
    ) -> None:
        self._busy = True
        self._hide_error()

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

    def start_local_build(
        self,
    ) -> None:
        self._busy = True
        self._hide_error()

        self.progress_bar.setVisible(
            True
        )

        self.progress_bar.setRange(
            0,
            0,
        )

        self.status_label.setText(
            tr(
                "updates.status.local_build.preparing"
            )
        )

        self.install_button.setEnabled(
            False
        )

        self.later_button.setEnabled(
            False
        )

    def update_local_build_stage(
        self,
        stage: str,
    ) -> None:
        key_by_stage = {
            "download_source": (
                "updates.status.local_build.download_source"
            ),
            "extract_source": (
                "updates.status.local_build.extract_source"
            ),
            "build_windows": (
                "updates.status.local_build.build_windows"
            ),
            "build_complete": (
                "updates.status.local_build.complete"
            ),
        }

        key = key_by_stage.get(
            stage
        )

        if key is None:
            return

        self.status_label.setText(
            tr(
                key
            )
        )

        self.progress_bar.setRange(
            0,
            0,
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

        self._error_message = str(
            message
        ).strip()

        self.status_label.setText(
            tr(
                "updates.status.failed_short"
            )
        )

        self.error_details.setPlainText(
            self._error_message
        )

        self.error_frame.setVisible(
            bool(
                self._error_message
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
        self._hide_error()

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

    def _copy_error(
        self,
    ) -> None:
        if not self._error_message:
            return

        clipboard = (
            QGuiApplication.clipboard()
        )

        clipboard.setText(
            self._error_message
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
