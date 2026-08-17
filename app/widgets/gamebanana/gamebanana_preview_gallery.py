from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import (
    QSize,
    QThreadPool,
    QTimer,
    Qt,
    QUrl,
)

from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QPixmap,
)

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.workers.gamebanana_preview_image_worker import (
    GameBananaPreviewImageWorker,
)


class StablePixmapLabel(
    QLabel
):
    """
    QLabel für skalierte Pixmaps ohne SizeHint-Rückkopplung.

    Ein normales QLabel verwendet die Pixmap-Größe als sizeHint().
    In Layouts kann das zu folgendem Kreislauf führen:

        größere Pixmap
        -> größerer sizeHint
        -> größeres Label/Dialog
        -> erneutes Scaling
        -> noch größerer sizeHint

    Dieses Label entkoppelt die Layout-Größe vollständig von der
    aktuell dargestellten Pixmap.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setScaledContents(
            False
        )

        self.setMinimumSize(
            1,
            1,
        )

        # QSizePolicy.Ignored sagt dem Layout explizit:
        # sizeHint() der Pixmap nicht zur Größenberechnung benutzen.
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

    def sizeHint(
        self,
    ) -> QSize:
        return QSize(
            1,
            1,
        )

    def minimumSizeHint(
        self,
    ) -> QSize:
        return QSize(
            1,
            1,
        )


class PreviewLightboxDialog(
    QDialog
):
    def __init__(
        self,
        *,
        pixmap: QPixmap,
        image_index: int,
        image_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self._source_pixmap = QPixmap(
            pixmap
        )

        self._rendering = False

        self.image_index = int(
            image_index
        )

        self.image_count = int(
            image_count
        )

        self.setObjectName(
            "gameBananaPreviewLightbox"
        )

        self.setModal(
            True
        )

        self.resize(
            1100,
            760,
        )

        # Der Dialog darf vom Benutzer größer/kleiner gezogen werden,
        # aber niemals durch die Pixmap selbst wachsen.
        self.setMinimumSize(
            720,
            520,
        )

        self.image_label = StablePixmapLabel(
            self
        )

        self.image_label.setObjectName(
            "gameBananaLightboxImage"
        )

        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        self.counter_label = QLabel(
            self
        )

        self.counter_label.setObjectName(
            "gameBananaLightboxCounter"
        )

        self.close_button = QPushButton(
            self
        )

        self.close_button.setObjectName(
            "gameBananaSecondaryButton"
        )

        self.close_button.clicked.connect(
            self.accept
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        layout.setSpacing(
            10
        )

        layout.addWidget(
            self.image_label,
            stretch=1,
        )

        footer = QHBoxLayout()
        footer.setSpacing(
            8
        )

        footer.addWidget(
            self.counter_label
        )

        footer.addStretch(
            1
        )

        footer.addWidget(
            self.close_button
        )

        layout.addLayout(
            footer
        )

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self._render_pixmap()

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._render_pixmap()

    def _render_pixmap(
        self,
    ) -> None:
        if self._rendering:
            return

        if self._source_pixmap.isNull():
            self.image_label.clear()
            return

        available = self.image_label.contentsRect().size()

        if (
            available.width() <= 1
            or available.height() <= 1
        ):
            return

        self._rendering = True

        try:
            scaled = self._source_pixmap.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.image_label.setPixmap(
                scaled
            )

        finally:
            self._rendering = False

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.setWindowTitle(
            tr(
                "gamebanana.preview.lightbox_title"
            )
        )

        self.counter_label.setText(
            tr(
                "gamebanana.preview.counter",
                current=(
                    self.image_index
                    + 1
                ),
                total=self.image_count,
            )
        )

        self.close_button.setText(
            tr(
                "common.close"
            )
        )


class GameBananaPreviewGallery(
    QFrame
):
    """
    Asynchrone Preview-Gallery.

    - beliebig viele Preview-URLs
    - Hauptbild
    - horizontale Thumbnail-Leiste
    - Vor / Zurück
    - Bildzähler
    - Vollbild-/Lightbox-Ansicht
    - Bild im Browser öffnen
    - separater ThreadPool (max. 4 Downloads)
    - Memory-Cache für bereits geladene Bilder
    """

    CACHE_MAX_ITEMS = 48
    CACHE_MAX_BYTES = (
        80
        * 1024
        * 1024
    )

    _byte_cache: OrderedDict[
        str,
        bytes,
    ] = OrderedDict()

    _cache_size_bytes = 0

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "gameBananaPreviewGallery"
        )

        self._urls: tuple[
            str,
            ...,
        ] = ()

        self._current_index = 0
        self._generation = 0
        self._compact_mode = False

        self._pixmaps: dict[
            str,
            QPixmap,
        ] = {}

        self._failed_urls: set[
            str
        ] = set()

        self._thumbnail_buttons: list[
            QToolButton
        ] = []

        self._thread_pool = QThreadPool(
            self
        )

        self._thread_pool.setMaxThreadCount(
            4
        )

        self.title_label = QLabel(
            self
        )

        self.title_label.setObjectName(
            "gameBananaPreviewTitle"
        )

        self.counter_label = QLabel(
            self
        )

        self.counter_label.setObjectName(
            "gameBananaPreviewCounter"
        )

        self.main_image_label = StablePixmapLabel(
            self
        )

        self.main_image_label.setObjectName(
            "gameBananaPreviewMainImage"
        )

        self.main_image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # WICHTIG:
        # Die Preview-Fläche hat eine stabile Höhe.
        #
        # Ohne feste Höhe übernimmt QLabel den sizeHint des
        # geladenen Pixmaps. In einem QScrollArea führt das zu
        # einer Layout-Rückkopplung:
        #
        # Pixmap -> größerer sizeHint -> größeres Widget ->
        # neues Scaling -> noch größerer sizeHint ...
        #
        # Dadurch wurden die Bilder immer größer und der
        # Detail-Scrollbereich sprang nach oben.
        self.main_image_label.setMinimumHeight(
            340
        )

        self.main_image_label.setMaximumHeight(
            340
        )

        self.main_image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.previous_button = QPushButton(
            self
        )

        self.previous_button.setObjectName(
            "gameBananaSecondaryButton"
        )

        self.previous_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.next_button = QPushButton(
            self
        )

        self.next_button.setObjectName(
            "gameBananaSecondaryButton"
        )

        self.next_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.fullscreen_button = QPushButton(
            self
        )

        self.fullscreen_button.setObjectName(
            "gameBananaSecondaryButton"
        )

        self.fullscreen_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.open_button = QPushButton(
            self
        )

        self.open_button.setObjectName(
            "gameBananaSecondaryButton"
        )

        self.open_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.thumbnail_scroll = QScrollArea(
            self
        )

        self.thumbnail_scroll.setObjectName(
            "gameBananaPreviewThumbnailScroll"
        )

        self.thumbnail_scroll.setWidgetResizable(
            True
        )

        self.thumbnail_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.thumbnail_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.thumbnail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.thumbnail_container = QWidget()

        self.thumbnail_container.setObjectName(
            "gameBananaPreviewThumbnailContainer"
        )

        self.thumbnail_layout = QHBoxLayout(
            self.thumbnail_container
        )

        self.thumbnail_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.thumbnail_layout.setSpacing(
            7
        )

        self.thumbnail_layout.addStretch(
            1
        )

        self.thumbnail_scroll.setWidget(
            self.thumbnail_container
        )

        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self.clear()

    # ========================================================
    # UI
    # ========================================================

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
            8
        )

        heading = QHBoxLayout()
        heading.setSpacing(
            8
        )

        heading.addWidget(
            self.title_label,
            stretch=1,
        )

        heading.addWidget(
            self.counter_label
        )

        layout.addLayout(
            heading
        )

        layout.addWidget(
            self.main_image_label
        )

        navigation = QHBoxLayout()
        navigation.setSpacing(
            8
        )

        self.previous_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.next_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        navigation.addWidget(
            self.previous_button,
            stretch=1,
        )

        navigation.addWidget(
            self.next_button,
            stretch=1,
        )

        layout.addLayout(
            navigation
        )

        self.thumbnail_scroll.setMinimumHeight(
            82
        )

        self.thumbnail_scroll.setMaximumHeight(
            96
        )

        layout.addWidget(
            self.thumbnail_scroll
        )

        actions = QHBoxLayout()
        actions.setSpacing(
            8
        )

        self.fullscreen_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.open_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        actions.addWidget(
            self.fullscreen_button,
            stretch=1,
        )

        actions.addWidget(
            self.open_button,
            stretch=1,
        )

        layout.addLayout(
            actions
        )

    def _connect_signals(
        self,
    ) -> None:
        self.previous_button.clicked.connect(
            self.show_previous
        )

        self.next_button.clicked.connect(
            self.show_next
        )

        self.fullscreen_button.clicked.connect(
            self.open_lightbox
        )

        self.open_button.clicked.connect(
            self.open_current_image
        )

    def set_compact_mode(
        self,
        enabled: bool,
    ) -> None:
        enabled = bool(enabled)

        if enabled == self._compact_mode:
            return

        self._compact_mode = enabled

        image_height = (
            260
            if enabled
            else 340
        )

        self.main_image_label.setMinimumHeight(
            image_height
        )
        self.main_image_label.setMaximumHeight(
            image_height
        )

        if enabled:
            self.thumbnail_scroll.setMinimumHeight(72)
            self.thumbnail_scroll.setMaximumHeight(84)
        else:
            self.thumbnail_scroll.setMinimumHeight(82)
            self.thumbnail_scroll.setMaximumHeight(96)

        self.main_image_label.updateGeometry()
        self.thumbnail_scroll.updateGeometry()

        # GameBananaPreviewGallery besitzt absichtlich keine
        # parameterlose _render_pixmap()-Methode. Diese gehört
        # ausschließlich zum PreviewLightboxDialog.
        #
        # Die Gallery rendert immer das aktuell ausgewählte Bild
        # über _current_pixmap() -> _render_main_pixmap(...).
        pixmap = self._current_pixmap()

        if pixmap is not None:
            self._render_main_pixmap(
                pixmap
            )

    # ========================================================
    # Public API
    # ========================================================

    def set_preview_urls(
        self,
        urls,
    ) -> None:
        normalized: list[str] = []
        seen: set[str] = set()

        for value in urls or ():
            if not value:
                continue

            url = str(
                value
            ).strip()

            if (
                not url
                or url in seen
            ):
                continue

            seen.add(
                url
            )

            normalized.append(
                url
            )

        self._generation += 1
        self._thread_pool.clear()

        self._urls = tuple(
            normalized
        )

        self._current_index = 0
        self._pixmaps.clear()
        self._failed_urls.clear()

        self._rebuild_thumbnails()

        if not self._urls:
            self._show_empty_state()
            self._sync_controls()
            return

        self.main_image_label.setPixmap(
            QPixmap()
        )

        self.main_image_label.setText(
            tr(
                "gamebanana.preview.loading"
            )
        )

        self._load_all_images()
        self._sync_controls()
        self._refresh_current_image()

    def clear(
        self,
    ) -> None:
        self.set_preview_urls(
            ()
        )

    def shutdown(
        self,
    ) -> None:
        self._generation += 1
        self._thread_pool.clear()

    @property
    def image_count(
        self,
    ) -> int:
        return len(
            self._urls
        )

    # ========================================================
    # Navigation
    # ========================================================

    def show_previous(
        self,
        _checked: bool = False,
    ) -> None:
        if not self._urls:
            return

        self.set_current_index(
            max(
                0,
                self._current_index
                - 1,
            )
        )

    def show_next(
        self,
        _checked: bool = False,
    ) -> None:
        if not self._urls:
            return

        self.set_current_index(
            min(
                len(self._urls)
                - 1,
                self._current_index
                + 1,
            )
        )

    def set_current_index(
        self,
        index: int,
    ) -> None:
        if not self._urls:
            return

        index = max(
            0,
            min(
                len(self._urls)
                - 1,
                int(index),
            ),
        )

        scroll_area = (
            self._find_parent_scroll_area()
        )

        scroll_value = (
            scroll_area
            .verticalScrollBar()
            .value()
            if scroll_area is not None
            else None
        )

        if (
            index
            == self._current_index
        ):
            self._refresh_current_image()
            self._restore_parent_scroll(
                scroll_area,
                scroll_value,
            )
            return

        self._current_index = index
        self._sync_controls()
        self._refresh_thumbnail_selection()
        self._refresh_current_image()

        self._restore_parent_scroll(
            scroll_area,
            scroll_value,
        )

    # ========================================================
    # Browser / lightbox
    # ========================================================

    def open_current_image(
        self,
        _checked: bool = False,
    ) -> None:
        url = self._current_url()

        if not url:
            return

        QDesktopServices.openUrl(
            QUrl(
                url
            )
        )

    def open_lightbox(
        self,
        _checked: bool = False,
    ) -> None:
        pixmap = self._current_pixmap()

        if (
            pixmap is None
            or pixmap.isNull()
        ):
            return

        dialog = PreviewLightboxDialog(
            pixmap=pixmap,
            image_index=(
                self._current_index
            ),
            image_count=len(
                self._urls
            ),
            parent=self,
        )

        dialog.exec()

    # ========================================================
    # Images
    # ========================================================

    def _load_all_images(
        self,
    ) -> None:
        generation = (
            self._generation
        )

        for url in self._urls:
            cached = self._cache_get(
                url
            )

            if cached is not None:
                self._consume_image_bytes(
                    url=url,
                    data=cached,
                    generation=generation,
                )

                continue

            worker = (
                GameBananaPreviewImageWorker(
                    url=url,
                    generation=generation,
                )
            )

            worker.signals.loaded.connect(
                self._on_image_loaded
            )

            worker.signals.failed.connect(
                self._on_image_failed
            )

            self._thread_pool.start(
                worker
            )

    def _on_image_loaded(
        self,
        url: str,
        data,
        generation: int,
    ) -> None:
        self._consume_image_bytes(
            url=url,
            data=data,
            generation=generation,
        )

    def _consume_image_bytes(
        self,
        *,
        url: str,
        data,
        generation: int,
    ) -> None:
        if (
            generation
            != self._generation
            or url
            not in self._urls
        ):
            return

        try:
            raw = bytes(
                data
            )
        except (
            TypeError,
            ValueError,
        ):
            self._on_image_failed(
                url,
                "invalid_bytes",
                generation,
            )

            return

        pixmap = QPixmap()

        if not pixmap.loadFromData(
            raw
        ):
            self._on_image_failed(
                url,
                "invalid_image",
                generation,
            )

            return

        self._cache_put(
            url,
            raw,
        )

        self._pixmaps[
            url
        ] = pixmap

        self._failed_urls.discard(
            url
        )

        self._update_thumbnail(
            url
        )

        if (
            url
            == self._current_url()
        ):
            scroll_area = (
                self._find_parent_scroll_area()
            )

            scroll_value = (
                scroll_area
                .verticalScrollBar()
                .value()
                if scroll_area is not None
                else None
            )

            self._render_main_pixmap(
                pixmap
            )

            self._restore_parent_scroll(
                scroll_area,
                scroll_value,
            )

        self._sync_controls()

    def _on_image_failed(
        self,
        url: str,
        _message: str,
        generation: int,
    ) -> None:
        if (
            generation
            != self._generation
            or url
            not in self._urls
        ):
            return

        self._failed_urls.add(
            url
        )

        index = self._urls.index(
            url
        )

        if (
            0
            <= index
            < len(
                self._thumbnail_buttons
            )
        ):
            button = (
                self._thumbnail_buttons[
                    index
                ]
            )

            button.setText(
                "!"
            )

            button.setToolTip(
                tr(
                    "gamebanana.preview.load_failed"
                )
            )

        if (
            url
            == self._current_url()
        ):
            self.main_image_label.setPixmap(
                QPixmap()
            )

            self.main_image_label.setText(
                tr(
                    "gamebanana.preview.load_failed"
                )
            )

        self._sync_controls()

    def _refresh_current_image(
        self,
    ) -> None:
        if not self._urls:
            self._show_empty_state()
            return

        url = self._current_url()

        if not url:
            self._show_empty_state()
            return

        pixmap = self._pixmaps.get(
            url
        )

        if pixmap is not None:
            self._render_main_pixmap(
                pixmap
            )

        elif (
            url
            in self._failed_urls
        ):
            self.main_image_label.setPixmap(
                QPixmap()
            )

            self.main_image_label.setText(
                tr(
                    "gamebanana.preview.load_failed"
                )
            )

        else:
            self.main_image_label.setPixmap(
                QPixmap()
            )

            self.main_image_label.setText(
                tr(
                    "gamebanana.preview.loading"
                )
            )

        self._sync_controls()
        self._refresh_thumbnail_selection()

    def _render_main_pixmap(
        self,
        pixmap: QPixmap,
    ) -> None:
        if pixmap.isNull():
            return

        available = self.main_image_label.size()

        if (
            available.width() <= 1
            or available.height() <= 1
        ):
            return

        scaled = pixmap.scaled(
            available,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.main_image_label.setText(
            ""
        )

        self.main_image_label.setPixmap(
            scaled
        )

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        pixmap = self._current_pixmap()

        if pixmap is not None:
            self._render_main_pixmap(
                pixmap
            )

    # ========================================================
    # Thumbnails
    # ========================================================

    def _rebuild_thumbnails(
        self,
    ) -> None:
        for button in self._thumbnail_buttons:
            self.thumbnail_layout.removeWidget(
                button
            )

            button.deleteLater()

        self._thumbnail_buttons.clear()

        for (
            index,
            _url,
        ) in enumerate(
            self._urls
        ):
            button = QToolButton(
                self.thumbnail_container
            )

            button.setObjectName(
                "gameBananaPreviewThumbnail"
            )

            button.setCheckable(
                True
            )

            # Ein Thumbnail-Klick soll nicht den äußeren
            # Details-QScrollArea wegen Fokus automatisch bewegen.
            button.setFocusPolicy(
                Qt.FocusPolicy.NoFocus
            )

            button.setFixedSize(
                104,
                68,
            )

            button.setIconSize(
                QSize(
                    94,
                    58,
                )
            )

            button.setText(
                str(
                    index
                    + 1
                )
            )

            button.clicked.connect(
                lambda _checked=False, value=index: (
                    self.set_current_index(
                        value
                    )
                )
            )

            self._thumbnail_buttons.append(
                button
            )

            self.thumbnail_layout.insertWidget(
                self.thumbnail_layout.count()
                - 1,
                button,
            )

        self._refresh_thumbnail_selection()

    def _update_thumbnail(
        self,
        url: str,
    ) -> None:
        if url not in self._urls:
            return

        index = self._urls.index(
            url
        )

        if (
            index < 0
            or index
            >= len(
                self._thumbnail_buttons
            )
        ):
            return

        pixmap = self._pixmaps.get(
            url
        )

        if (
            pixmap is None
            or pixmap.isNull()
        ):
            return

        thumb = pixmap.scaled(
            94,
            58,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        button = (
            self._thumbnail_buttons[
                index
            ]
        )

        button.setText(
            ""
        )

        button.setIcon(
            QIcon(
                thumb
            )
        )

        button.setToolTip(
            tr(
                "gamebanana.preview.thumbnail_tooltip",
                current=index + 1,
                total=len(
                    self._urls
                ),
            )
        )

    def _refresh_thumbnail_selection(
        self,
    ) -> None:
        for (
            index,
            button,
        ) in enumerate(
            self._thumbnail_buttons
        ):
            selected = (
                index
                == self._current_index
            )

            button.setChecked(
                selected
            )

            button.setProperty(
                "selected",
                selected,
            )

            button.style().unpolish(
                button
            )

            button.style().polish(
                button
            )

    # ========================================================
    # State
    # ========================================================

    def _sync_controls(
        self,
    ) -> None:
        count = len(
            self._urls
        )

        has_images = (
            count > 0
        )

        self.previous_button.setEnabled(
            has_images
            and self._current_index
            > 0
        )

        self.next_button.setEnabled(
            has_images
            and self._current_index
            < count - 1
        )

        pixmap = self._current_pixmap()

        has_loaded_current = (
            pixmap is not None
            and not pixmap.isNull()
        )

        self.fullscreen_button.setEnabled(
            has_loaded_current
        )

        self.open_button.setEnabled(
            has_images
        )

        self.thumbnail_scroll.setVisible(
            count > 1
        )

        if has_images:
            self.counter_label.setText(
                tr(
                    "gamebanana.preview.counter",
                    current=(
                        self._current_index
                        + 1
                    ),
                    total=count,
                )
            )

        else:
            self.counter_label.clear()

    def _show_empty_state(
        self,
    ) -> None:
        self.main_image_label.setPixmap(
            QPixmap()
        )

        self.main_image_label.setText(
            tr(
                "gamebanana.preview.empty"
            )
        )

    def _current_url(
        self,
    ) -> str | None:
        if not self._urls:
            return None

        if not (
            0
            <= self._current_index
            < len(
                self._urls
            )
        ):
            return None

        return self._urls[
            self._current_index
        ]

    def _current_pixmap(
        self,
    ) -> QPixmap | None:
        url = self._current_url()

        if not url:
            return None

        return self._pixmaps.get(
            url
        )

    # ========================================================
    # Parent scroll stability
    # ========================================================

    def _find_parent_scroll_area(
        self,
    ) -> QScrollArea | None:
        parent = self.parentWidget()

        while parent is not None:
            if isinstance(
                parent,
                QScrollArea,
            ):
                return parent

            parent = (
                parent.parentWidget()
            )

        return None

    @staticmethod
    def _restore_parent_scroll(
        scroll_area: QScrollArea | None,
        value: int | None,
    ) -> None:
        if (
            scroll_area is None
            or value is None
        ):
            return

        # Zweimal wiederherstellen:
        # - sofort
        # - nach dem nächsten Layout-Pass
        #
        # Damit gewinnt die gespeicherte Position auch gegen
        # ein verzögertes QScrollArea-Relayout.
        bar = (
            scroll_area
            .verticalScrollBar()
        )

        bar.setValue(
            value
        )

        QTimer.singleShot(
            0,
            lambda: (
                scroll_area
                .verticalScrollBar()
                .setValue(
                    value
                )
            ),
        )

    # ========================================================
    # Cache
    # ========================================================

    @classmethod
    def _cache_get(
        cls,
        url: str,
    ) -> bytes | None:
        data = cls._byte_cache.get(
            url
        )

        if data is None:
            return None

        cls._byte_cache.move_to_end(
            url
        )

        return data

    @classmethod
    def _cache_put(
        cls,
        url: str,
        data: bytes,
    ) -> None:
        existing = cls._byte_cache.pop(
            url,
            None,
        )

        if existing is not None:
            cls._cache_size_bytes -= len(
                existing
            )

        cls._byte_cache[
            url
        ] = data

        cls._cache_size_bytes += len(
            data
        )

        while (
            len(
                cls._byte_cache
            )
            > cls.CACHE_MAX_ITEMS
            or cls._cache_size_bytes
            > cls.CACHE_MAX_BYTES
        ):
            (
                _old_url,
                old_data,
            ) = cls._byte_cache.popitem(
                last=False
            )

            cls._cache_size_bytes -= len(
                old_data
            )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "gamebanana.preview.title"
            )
        )

        self.previous_button.setText(
            tr(
                "gamebanana.preview.previous"
            )
        )

        self.next_button.setText(
            tr(
                "gamebanana.preview.next"
            )
        )

        self.fullscreen_button.setText(
            tr(
                "gamebanana.preview.fullscreen"
            )
        )

        self.open_button.setText(
            tr(
                "gamebanana.preview.open"
            )
        )

        for (
            index,
            button,
        ) in enumerate(
            self._thumbnail_buttons
        ):
            button.setToolTip(
                tr(
                    "gamebanana.preview.thumbnail_tooltip",
                    current=index + 1,
                    total=len(
                        self._urls
                    ),
                )
            )

        if not self._urls:
            self._show_empty_state()
        else:
            self._refresh_current_image()

        self._sync_controls()


__all__ = [
    "GameBananaPreviewGallery",
]
