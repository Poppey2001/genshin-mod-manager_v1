from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QResizeEvent,
)

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gamebanana.models import (
    GameBananaModSummary,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.widgets.gamebanana.mod_card import (
    GameBananaModCard,
)


CARD_TARGET_WIDTH = 340


class GameBananaModGrid(
    QWidget
):
    mod_clicked = Signal(
        object
    )

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self._items: tuple[
            GameBananaModSummary,
            ...,
        ] = ()

        self._cards: list[
            GameBananaModCard
        ] = []

        self._column_count = 0

        self.empty_label = QLabel(
            self
        )

        self.scroll_area = (
            QScrollArea()
        )

        self.content_widget = (
            QWidget()
        )

        self.grid_layout = (
            QGridLayout(
                self.content_widget
            )
        )

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _build_ui(
        self,
    ) -> None:
        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(
            0
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setObjectName(
            "gameBananaEmptyLabel"
        )

        self.grid_layout.setContentsMargins(
            6,
            6,
            12,
            18,
        )

        self.grid_layout.setHorizontalSpacing(
            14
        )

        self.grid_layout.setVerticalSpacing(
            14
        )

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_area.setWidget(
            self.content_widget
        )

        root_layout.addWidget(
            self.empty_label,
            stretch=1,
        )

        root_layout.addWidget(
            self.scroll_area,
            stretch=1,
        )

        self.empty_label.hide()

        self.setStyleSheet(
            """
            QLabel#gameBananaEmptyLabel {
                color: #777f8d;
                font-size: 14px;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            """
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.empty_label.setText(
            tr(
                "gamebanana.grid.empty"
            )
        )

    # ========================================================
    # Mods
    # ========================================================

    def set_mods(
        self,
        mods: tuple[
            GameBananaModSummary,
            ...,
        ]
        | list[
            GameBananaModSummary
        ],
    ) -> None:
        self._clear_cards()

        self._items = tuple(
            mods
        )

        if not self._items:
            self.scroll_area.hide()

            self.empty_label.show()

            return

        self.empty_label.hide()

        self.scroll_area.show()

        for mod in self._items:
            card = (
                GameBananaModCard(
                    mod=mod,
                    parent=self.content_widget,
                )
            )

            card.clicked.connect(
                self.mod_clicked
            )

            self._cards.append(
                card
            )

        self._rebuild_grid(
            force=True
        )

    def clear(
        self,
    ) -> None:
        self.set_mods(
            ()
        )

    # ========================================================
    # Responsive Grid
    # ========================================================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._rebuild_grid()

    def _rebuild_grid(
        self,
        *,
        force: bool = False,
    ) -> None:
        if not self._cards:
            return

        available_width = max(
            1,
            self.scroll_area.viewport().width()
            - 12,
        )

        columns = max(
            1,
            available_width
            // CARD_TARGET_WIDTH,
        )

        if (
            not force
            and columns
            == self._column_count
        ):
            return

        self._column_count = (
            columns
        )

        for card in self._cards:
            self.grid_layout.removeWidget(
                card
            )

        for (
            index,
            card,
        ) in enumerate(
            self._cards
        ):
            row = (
                index
                // columns
            )

            column = (
                index
                % columns
            )

            self.grid_layout.addWidget(
                card,
                row,
                column,
            )

        for column in range(
            columns
        ):
            self.grid_layout.setColumnStretch(
                column,
                1,
            )

    # ========================================================
    # Clear
    # ========================================================

    def _clear_cards(
        self,
    ) -> None:
        for card in self._cards:
            self.grid_layout.removeWidget(
                card
            )

            card.deleteLater()

        self._cards.clear()

        self._items = ()

        self._column_count = 0


__all__ = [
    "GameBananaModGrid",
]