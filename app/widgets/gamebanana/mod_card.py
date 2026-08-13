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
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gamebanana.models import (
    GameBananaModSummary,
)

from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)


class GameBananaModCard(
    QFrame
):
    clicked = Signal(
        object
    )

    def __init__(
        self,
        *,
        mod: GameBananaModSummary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.mod = mod

        self.setObjectName(
            "gameBananaModCard"
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setMinimumWidth(
            245
        )

        self.setMaximumWidth(
            380
        )

        self.preview = (
            GameBananaPreviewImage(
                parent=self,
                minimum_height=155,
            )
        )

        self.preview.setFixedHeight(
            165
        )

        self.name_label = QLabel(
            mod.name
        )

        self.author_label = QLabel()

        self.category_label = QLabel()

        self.stats_label = QLabel()

        self._build_ui()

        self._set_values()

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            12,
        )

        layout.setSpacing(
            6
        )

        self.name_label.setObjectName(
            "gameBananaCardTitle"
        )

        self.name_label.setWordWrap(
            True
        )

        self.author_label.setObjectName(
            "gameBananaCardAuthor"
        )

        self.category_label.setObjectName(
            "gameBananaCardCategory"
        )

        self.stats_label.setObjectName(
            "gameBananaCardStats"
        )

        layout.addWidget(
            self.preview
        )

        layout.addWidget(
            self.name_label
        )

        layout.addWidget(
            self.author_label
        )

        layout.addWidget(
            self.category_label
        )

        layout.addWidget(
            self.stats_label
        )

        layout.addStretch(
            1
        )

        self.setStyleSheet(
            """
            QFrame#gameBananaModCard {
                background: #191e27;
                border: 1px solid #2b323e;
                border-radius: 11px;
            }

            QFrame#gameBananaModCard:hover {
                background: #202631;
                border-color: #6d5ee8;
            }

            QLabel#gameBananaCardTitle {
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
            }

            QLabel#gameBananaCardAuthor {
                color: #a3aab7;
                font-size: 12px;
            }

            QLabel#gameBananaCardCategory {
                color: #8172e8;
                font-size: 11px;
                font-weight: 600;
            }

            QLabel#gameBananaCardStats {
                color: #7e8796;
                font-size: 11px;
            }
            """
        )

    def _set_values(
        self,
    ) -> None:
        self.preview.set_preview_url(
            self.mod.preview_url
        )

        self.author_label.setText(
            (
                f"von {self.mod.author}"
                if self.mod.author
                else "Unbekannter Autor"
            )
        )

        self.category_label.setText(
            self.mod.category
            or "Mod"
        )

        self.stats_label.setText(
            (
                f"↓ {self._format_number(self.mod.downloads)}"
                f"    ♥ {self._format_number(self.mod.likes)}"
                f"    👁 {self._format_number(self.mod.views)}"
            )
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
                self.mod
            )

        super().mousePressEvent(
            event
        )

    @staticmethod
    def _format_number(
        value: int | None,
    ) -> str:
        if value is None:
            return "-"

        if value >= 1_000_000:
            return (
                f"{value / 1_000_000:.1f}M"
            )

        if value >= 1_000:
            return (
                f"{value / 1_000:.1f}K"
            )

        return str(
            value
        )


__all__ = [
    "GameBananaModCard",
]