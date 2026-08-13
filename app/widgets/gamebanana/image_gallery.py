from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QMouseEvent,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)


class GameBananaImageThumbnail(
    QFrame
):
    clicked = Signal(
        str
    )

    def __init__(
        self,
        *,
        url: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.url = url

        self.setObjectName(
            "gameBananaThumbnail"
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setFixedSize(
            128,
            84,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            3,
            3,
            3,
            3,
        )

        self.image = (
            GameBananaPreviewImage(
                parent=self,
                minimum_height=70,
            )
        )

        self.image.set_preview_url(
            url
        )

        layout.addWidget(
            self.image
        )

    def set_selected(
        self,
        selected: bool,
    ) -> None:
        self.setProperty(
            "selected",
            selected,
        )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.clicked.emit(
                self.url
            )

        super().mousePressEvent(
            event
        )


class GameBananaImageGallery(
    QWidget
):
    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.urls: tuple[
            str,
            ...,
        ] = ()

        self.current_index = 0

        self.main_image = (
            GameBananaPreviewImage(
                parent=self,
                minimum_height=300,
            )
        )

        self.main_image.setMinimumHeight(
            320
        )

        self.main_image.setMaximumHeight(
            520
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

        self.thumbnail_scroll = (
            QScrollArea()
        )

        self.thumbnail_container = (
            QWidget()
        )

        self.thumbnail_layout = (
            QHBoxLayout(
                self.thumbnail_container
            )
        )

        self.thumbnails: list[
            GameBananaImageThumbnail
        ] = []

        self._build_ui()

        self.clear()

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

        layout.addWidget(
            self.main_image
        )

        navigation = QHBoxLayout()

        self.previous_button.setFixedWidth(
            48
        )

        self.next_button.setFixedWidth(
            48
        )

        navigation.addWidget(
            self.previous_button
        )

        navigation.addStretch(
            1
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

        self.thumbnail_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.thumbnail_layout.setSpacing(
            8
        )

        self.thumbnail_layout.addStretch(
            1
        )

        self.thumbnail_scroll.setWidgetResizable(
            True
        )

        self.thumbnail_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.thumbnail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.thumbnail_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.thumbnail_scroll.setFixedHeight(
            112
        )

        self.thumbnail_scroll.setWidget(
            self.thumbnail_container
        )

        layout.addWidget(
            self.thumbnail_scroll
        )

        self.previous_button.clicked.connect(
            self.previous
        )

        self.next_button.clicked.connect(
            self.next
        )

        self.setStyleSheet(
            """
            QFrame#gameBananaThumbnail {
                background: #151a22;
                border: 1px solid #303744;
                border-radius: 7px;
            }

            QFrame#gameBananaThumbnail:hover {
                border-color: #6f61da;
            }

            QFrame#gameBananaThumbnail[selected="true"] {
                border: 2px solid #806bff;
                background: #25213a;
            }

            QLabel {
                color: #8f97a6;
            }
            """
        )

    # ========================================================
    # URLs
    # ========================================================

    def set_urls(
        self,
        urls,
    ) -> None:
        unique_urls: list[str] = []

        seen: set[str] = set()

        for value in urls:
            if not isinstance(
                value,
                str,
            ):
                continue

            url = value.strip()

            if (
                not url
                or url in seen
            ):
                continue

            seen.add(
                url
            )

            unique_urls.append(
                url
            )

        self.urls = tuple(
            unique_urls
        )

        self._rebuild_thumbnails()

        if not self.urls:
            self.current_index = 0

            self.main_image.set_preview_url(
                None
            )

            self.counter_label.setText(
                "Keine Bilder"
            )

            self.previous_button.setEnabled(
                False
            )

            self.next_button.setEnabled(
                False
            )

            self.thumbnail_scroll.hide()

            return

        self.thumbnail_scroll.setVisible(
            len(
                self.urls
            )
            > 1
        )

        self.select_index(
            0
        )

    def clear(
        self,
    ) -> None:
        self.set_urls(
            ()
        )

    # ========================================================
    # Navigation
    # ========================================================

    def select_index(
        self,
        index: int,
    ) -> None:
        if not self.urls:
            return

        index = max(
            0,
            min(
                index,
                len(
                    self.urls
                )
                - 1,
            ),
        )

        self.current_index = (
            index
        )

        self.main_image.set_preview_url(
            self.urls[
                index
            ]
        )

        self.counter_label.setText(
            (
                f"{index + 1} / "
                f"{len(self.urls)}"
            )
        )

        self.previous_button.setEnabled(
            index > 0
        )

        self.next_button.setEnabled(
            index
            < len(
                self.urls
            )
            - 1
        )

        for (
            thumbnail_index,
            thumbnail,
        ) in enumerate(
            self.thumbnails
        ):
            thumbnail.set_selected(
                thumbnail_index
                == index
            )

    def previous(
        self,
    ) -> None:
        self.select_index(
            self.current_index - 1
        )

    def next(
        self,
    ) -> None:
        self.select_index(
            self.current_index + 1
        )

    def _select_url(
        self,
        url: str,
    ) -> None:
        try:
            index = (
                self.urls.index(
                    url
                )
            )

        except ValueError:
            return

        self.select_index(
            index
        )

    # ========================================================
    # Thumbnails
    # ========================================================

    def _rebuild_thumbnails(
        self,
    ) -> None:
        for thumbnail in (
            self.thumbnails
        ):
            self.thumbnail_layout.removeWidget(
                thumbnail
            )

            thumbnail.deleteLater()

        self.thumbnails.clear()

        # Stretch entfernen.
        while (
            self.thumbnail_layout.count()
        ):
            item = (
                self.thumbnail_layout
                .takeAt(
                    0
                )
            )

            widget = item.widget()

            if (
                widget is not None
                and widget
                not in self.thumbnails
            ):
                # Bereits deleteLater oder
                # kein Thumbnail.
                pass

        for url in self.urls:
            thumbnail = (
                GameBananaImageThumbnail(
                    url=url,
                    parent=(
                        self.thumbnail_container
                    ),
                )
            )

            thumbnail.clicked.connect(
                self._select_url
            )

            self.thumbnails.append(
                thumbnail
            )

            self.thumbnail_layout.addWidget(
                thumbnail
            )

        self.thumbnail_layout.addStretch(
            1
        )


__all__ = [
    "GameBananaImageGallery",
]