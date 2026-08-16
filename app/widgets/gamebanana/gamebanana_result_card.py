from __future__ import annotations

from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gamebanana import (
    GameBananaMod,
)

from app.i18n import (
    tr,
    translation_manager,
)


class GameBananaResultCard(
    QFrame
):
    open_requested = Signal(
        int
    )

    def __init__(
        self,
        *,
        mod: GameBananaMod,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.mod = mod

        self.setObjectName(
            "gameBananaResultCard"
        )

        self.name_label = QLabel(
            mod.name,
            self,
        )

        self.name_label.setObjectName(
            "gameBananaResultTitle"
        )

        self.name_label.setWordWrap(
            True
        )

        self.id_label = QLabel(
            self
        )

        self.id_label.setObjectName(
            "gameBananaResultId"
        )

        self.id_label.setWordWrap(
            True
        )

        self.author_label = QLabel(
            self
        )

        self.author_label.setObjectName(
            "gameBananaResultMeta"
        )

        self.author_label.setWordWrap(
            True
        )

        self.game_label = QLabel(
            self
        )

        self.game_label.setObjectName(
            "gameBananaResultMeta"
        )

        self.game_label.setWordWrap(
            True
        )

        self.open_button = QPushButton(
            self
        )

        self.open_button.setObjectName(
            "gameBananaResultOpenButton"
        )

        self.open_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        layout.setSpacing(
            6
        )

        layout.addWidget(
            self.name_label
        )

        layout.addWidget(
            self.id_label
        )

        layout.addWidget(
            self.author_label
        )

        layout.addWidget(
            self.game_label
        )

        layout.addSpacing(
            3
        )

        layout.addWidget(
            self.open_button
        )

        self.open_button.clicked.connect(
            self._emit_open
        )

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _emit_open(
        self,
        _checked: bool = False,
    ) -> None:
        self.open_requested.emit(
            int(
                self.mod.id
            )
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        unknown = tr(
            "gamebanana.value.unknown"
        )

        self.id_label.setText(
            tr(
                "gamebanana.result.id",
                id=self.mod.id,
            )
        )

        self.author_label.setText(
            tr(
                "gamebanana.result.author",
                author=(
                    self.mod.author
                    or unknown
                ),
            )
        )

        self.game_label.setText(
            tr(
                "gamebanana.result.game",
                game=(
                    self.mod.game_name
                    or unknown
                ),
            )
        )

        self.open_button.setText(
            tr(
                "gamebanana.result.open"
            )
        )


__all__ = [
    "GameBananaResultCard",
]
