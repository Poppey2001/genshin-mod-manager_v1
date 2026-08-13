from __future__ import annotations

from collections import (
    OrderedDict,
)

from PySide6.QtCore import (
    Qt,
    QThreadPool,
)

from PySide6.QtGui import (
    QPixmap,
    QResizeEvent,
)

from PySide6.QtWidgets import (
    QLabel,
    QWidget,
)

from app.workers.gamebanana_image_worker import (
    GameBananaImageWorker,
)


MAX_MEMORY_IMAGES = 96


class GameBananaPreviewImage(
    QLabel
):
    _memory_cache: (
        OrderedDict[
            str,
            QPixmap,
        ]
    ) = OrderedDict()

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        minimum_height: int = 150,
    ) -> None:
        super().__init__(
            parent
        )

        self._requested_url: (
            str
            | None
        ) = None

        self._pixmap_original: (
            QPixmap
            | None
        ) = None

        self._workers: set[
            GameBananaImageWorker
        ] = set()

        self.setObjectName(
            "gameBananaPreview"
        )

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setMinimumHeight(
            minimum_height
        )

        self._show_no_preview()

    # ========================================================
    # Public
    # ========================================================

    def set_preview_url(
        self,
        url: str | None,
    ) -> None:
        normalized = (
            url.strip()
            if isinstance(
                url,
                str,
            )
            else ""
        )

        self._requested_url = (
            normalized
            or None
        )

        self._pixmap_original = (
            None
        )

        self.clear()

        if not normalized:
            self._show_no_preview()

            return

        cached = (
            self._memory_cache.get(
                normalized
            )
        )

        if (
            cached is not None
            and not cached.isNull()
        ):
            self._memory_cache.move_to_end(
                normalized
            )

            self._pixmap_original = (
                cached
            )

            self._refresh_scaled_pixmap()

            return

        self.setText(
            "Vorschau wird geladen …"
        )

        worker = (
            GameBananaImageWorker(
                url=normalized
            )
        )

        self._workers.add(
            worker
        )

        worker.signals.finished.connect(
            lambda url, data, current_worker=worker: (
                self._on_loaded(
                    url,
                    data,
                    current_worker,
                )
            )
        )

        worker.signals.failed.connect(
            lambda url, message, current_worker=worker: (
                self._on_failed(
                    url,
                    message,
                    current_worker,
                )
            )
        )

        QThreadPool.globalInstance().start(
            worker
        )

    @classmethod
    def clear_memory_cache(
        cls,
    ) -> None:
        cls._memory_cache.clear()

    # ========================================================
    # Worker
    # ========================================================

    def _on_loaded(
        self,
        url: str,
        data: bytes,
        worker: GameBananaImageWorker,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            url
            != self._requested_url
        ):
            return

        pixmap = QPixmap()

        if not pixmap.loadFromData(
            data
        ):
            self._show_no_preview()

            return

        self._memory_cache[
            url
        ] = pixmap

        self._memory_cache.move_to_end(
            url
        )

        while (
            len(
                self._memory_cache
            )
            > MAX_MEMORY_IMAGES
        ):
            self._memory_cache.popitem(
                last=False
            )

        self._pixmap_original = (
            pixmap
        )

        self._refresh_scaled_pixmap()

    def _on_failed(
        self,
        url: str,
        _message: str,
        worker: GameBananaImageWorker,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            url
            != self._requested_url
        ):
            return

        self._show_no_preview()

    # ========================================================
    # Anzeige
    # ========================================================

    def _show_no_preview(
        self,
    ) -> None:
        self._pixmap_original = None

        self.clear()

        self.setText(
            "Keine Vorschau"
        )

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(
        self,
    ) -> None:
        pixmap = (
            self._pixmap_original
        )

        if (
            pixmap is None
            or pixmap.isNull()
        ):
            return

        target = (
            self.contentsRect()
            .size()
        )

        if (
            target.width() <= 0
            or target.height() <= 0
        ):
            return

        scaled = pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.setPixmap(
            scaled
        )


__all__ = [
    "GameBananaPreviewImage",
]