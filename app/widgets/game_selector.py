from __future__ import annotations

from PySide6.QtCore import (
    QSignalBlocker,
    Signal,
)

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.games import (
    all_games,
    find_game,
)

from app.i18n import (
    tr,
    translation_manager,
)


class GameSelectorWidget(QFrame):
    game_change_requested = Signal(str)

    def __init__(
        self,
        *,
        selected_game: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "gameSelector"
        )

        self.title_label = QLabel(
            self
        )

        self.game_combobox = QComboBox(
            self
        )

        self.importer_label = QLabel(
            self
        )

        self.game_combobox.setObjectName(
            "gameSelectorCombo"
        )

        self.importer_label.setObjectName(
            "gameImporterLabel"
        )

        self._build_ui()
        self._populate_games()

        self.set_current_game(
            selected_game
        )

        self.game_combobox.currentIndexChanged.connect(
            self._on_game_changed
        )

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

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
            10,
        )

        layout.setSpacing(
            6
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.game_combobox
        )

        layout.addWidget(
            self.importer_label
        )

    def _populate_games(
        self,
    ) -> None:
        self.game_combobox.clear()

        for game in all_games():
            self.game_combobox.addItem(
                game.name,
                userData=(
                    game.id.value
                ),
            )

    def set_current_game(
        self,
        game_id: str,
    ) -> None:
        game = find_game(
            game_id
        )

        if game is None:
            return

        blocker = QSignalBlocker(
            self.game_combobox
        )

        index = (
            self.game_combobox.findData(
                game.id.value
            )
        )

        if index >= 0:
            self.game_combobox.setCurrentIndex(
                index
            )

        del blocker

        self._update_importer_label()

    def _on_game_changed(
        self,
        _index: int,
    ) -> None:
        game_id = (
            self.game_combobox
            .currentData()
        )

        if not isinstance(
            game_id,
            str,
        ):
            return

        self._update_importer_label()

        self.game_change_requested.emit(
            game_id
        )

    def _update_importer_label(
        self,
    ) -> None:
        game_id = (
            self.game_combobox
            .currentData()
        )

        if not isinstance(
            game_id,
            str,
        ):
            self.importer_label.clear()
            return

        game = find_game(
            game_id
        )

        if game is None:
            self.importer_label.clear()
            return

        self.importer_label.setText(
            tr(
                "game.selector.importer",
                importer=game.importer,
            )
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "game.selector.title"
            )
        )

        self._update_importer_label()