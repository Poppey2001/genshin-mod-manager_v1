from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QThreadPool,
)

from PySide6.QtGui import (
    QPixmap,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)

from app.workers.library_preview_worker import (
    LibraryPreviewWorker,
)
from app.i18n import (
    tr,
)

class ModPreviewGallery(
    QFrame
):
    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "libraryPreviewGallery"
        )

        self._request_token = 0

        self._local_images: tuple[
            Path,
            ...,
        ] = ()

        self._remote_images: tuple[
            str,
            ...,
        ] = ()

        self._current_index = 0

        self._workers: set[
            LibraryPreviewWorker
        ] = set()

        self.image_stack = (
            QStackedWidget()
        )

        self.local_image = QLabel()

        self.remote_image = (
            GameBananaPreviewImage(
                minimum_height=180
            )
        )

        self.empty_label = QLabel(
            tr(
                "library.preview.none"
            )
        )

        self.previous_button = (
            QPushButton(
                "‹"
            )
        )

        self.next_button = (
            QPushButton(
                "›"
            )
        )

        self.counter_label = QLabel()

        self.source_label = QLabel()

        self._build_ui()

        self.clear_preview()

    def _build_ui(
        self,
    ) -> None:
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

        self.local_image.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.local_image.setMinimumHeight(
            190
        )

        self.remote_image.setMinimumHeight(
            190
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setMinimumHeight(
            190
        )

        self.image_stack.addWidget(
            self.empty_label
        )

        self.image_stack.addWidget(
            self.local_image
        )

        self.image_stack.addWidget(
            self.remote_image
        )

        layout.addWidget(
            self.image_stack
        )

        navigation = QHBoxLayout()

        self.previous_button.setFixedWidth(
            42
        )

        self.next_button.setFixedWidth(
            42
        )

        navigation.addWidget(
            self.previous_button
        )

        navigation.addStretch(
            1
        )

        navigation.addWidget(
            self.source_label
        )

        navigation.addWidget(
            self.counter_label
        )

        navigation.addStretch(
            1
        )

        navigation.addWidget(
            self.next_button
        )

        layout.addLayout(
            navigation
        )

        self.previous_button.clicked.connect(
            self.previous
        )

        self.next_button.clicked.connect(
            self.next
        )

        self.setStyleSheet(
            """
            QFrame#libraryPreviewGallery {
                background: #11151b;
                border: 1px solid #2b313d;
                border-radius: 9px;
            }

            QFrame#libraryPreviewGallery QLabel {
                color: #8f98a8;
            }
            """
        )

    # ========================================================
    # Mod laden
    # ========================================================

    def load_mod(
        self,
        mod_path,
    ) -> None:
        self._request_token += 1

        token = (
            self._request_token
        )

        self.clear_preview(
            invalidate=False
        )

        self.empty_label.setText(
            tr(
                "library.preview.loading"
            )
        )

        worker = (
            LibraryPreviewWorker(
                mod_path=mod_path
            )
        )

        self._workers.add(
            worker
        )

        worker.signals.finished.connect(
            lambda path, result, w=worker, t=token: (
                self._on_loaded(
                    path,
                    result,
                    w,
                    t,
                )
            )
        )

        worker.signals.failed.connect(
            lambda path, message, w=worker, t=token: (
                self._on_failed(
                    path,
                    message,
                    w,
                    t,
                )
            )
        )

        QThreadPool.globalInstance().start(
            worker
        )

    def _on_loaded(
        self,
        _path,
        result,
        worker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            token
            != self._request_token
        ):
            return

        self._local_images = (
            result.local_images
        )

        self._remote_images = (
            result.remote_images
        )

        self._current_index = 0

        self._show_current()

    def _on_failed(
        self,
        _path,
        _message: str,
        worker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            token
            != self._request_token
        ):
            return

        self.clear_preview(
            invalidate=False
        )

        self.empty_label.setText(
            tr(
                "library.preview.unavailable"
            )
        )

    # ========================================================
    # Images
    # ========================================================

    def _all_count(
        self,
    ) -> int:
        return (
            len(
                self._local_images
            )
            + len(
                self._remote_images
            )
        )

    def _show_current(
        self,
    ) -> None:
        total = (
            self._all_count()
        )

        if total <= 0:
            self.image_stack.setCurrentWidget(
                self.empty_label
            )

            self.empty_label.setText(
                "Keine Vorschau"
            )

            self.counter_label.clear()

            self.source_label.clear()

            self.previous_button.setEnabled(
                False
            )

            self.next_button.setEnabled(
                False
            )

            return

        self._current_index = max(
            0,
            min(
                self._current_index,
                total - 1,
            ),
        )

        local_count = len(
            self._local_images
        )

        if (
            self._current_index
            < local_count
        ):
            path = (
                self._local_images[
                    self._current_index
                ]
            )

            pixmap = QPixmap(
                str(
                    path
                )
            )

            if pixmap.isNull():
                self.local_image.setText(
                    tr(
                        "library.preview.image_load_failed"
                    )
                )

                self.local_image.setPixmap(
                    QPixmap()
                )

            else:
                self.local_image.setText(
                    ""
                )

                self.local_image.setPixmap(
                    pixmap.scaled(
                        380,
                        240,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            self.image_stack.setCurrentWidget(
                self.local_image
            )

            
            self.source_label.setText(
                tr(
                    "library.preview.local"
                )
            )
            

        else:
            remote_index = (
                self._current_index
                - local_count
            )

            url = (
                self._remote_images[
                    remote_index
                ]
            )

            self.remote_image.set_preview_url(
                url
            )

            self.image_stack.setCurrentWidget(
                self.remote_image
            )

            self.source_label.setText(
                    tr(
                        "library.preview.gamebanana"
                    )
            )

        self.counter_label.setText(
            (
                f"{self._current_index + 1}"
                f" / {total}"
            )
        )

        self.previous_button.setEnabled(
            self._current_index > 0
        )

        self.next_button.setEnabled(
            self._current_index
            < total - 1
        )

    def previous(
        self,
    ) -> None:
        self._current_index -= 1

        self._show_current()

    def next(
        self,
    ) -> None:
        self._current_index += 1

        self._show_current()

    def clear_preview(
        self,
        *,
        invalidate: bool = True,
    ) -> None:
        if invalidate:
            self._request_token += 1

        self._local_images = ()

        self._remote_images = ()

        self._current_index = 0

        self.local_image.clear()

        self.remote_image.set_preview_url(
            None
        )

        self.image_stack.setCurrentWidget(
            self.empty_label
        )

        self.empty_label.setText(
            "Keine Vorschau"
        )

        self.counter_label.clear()

        self.source_label.clear()

        self.previous_button.setEnabled(
            False
        )

        self.next_button.setEnabled(
            False
        )


__all__ = [
    "ModPreviewGallery",
]