from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
    translation_manager,
)


class LibraryStatsWidget(QWidget):
    """
    Zeigt die Statistik-Karten der Mod-Bibliothek an.

    Dieses Widget stellt nur die Werte dar.
    Die Berechnung der Werte bleibt außerhalb des Widgets.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.total_value = QLabel(
            "0",
            self,
        )

        self.active_value = QLabel(
            "0",
            self,
        )

        self.conflict_value = QLabel(
            "0",
            self,
        )

        self.character_value = QLabel(
            "0",
            self,
        )

        self.total_title_label: QLabel
        self.total_subtitle_label: QLabel

        self.active_title_label: QLabel
        self.active_subtitle_label: QLabel

        self.conflict_title_label: QLabel
        self.conflict_subtitle_label: QLabel

        self.character_title_label: QLabel
        self.character_subtitle_label: QLabel

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _build_ui(
        self,
    ) -> None:
        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            12
        )

        (
            total_card,
            self.total_title_label,
            self.total_subtitle_label,
        ) = self._create_stat_card(
            value_label=self.total_value,
            object_name="totalStatCard",
        )

        (
            active_card,
            self.active_title_label,
            self.active_subtitle_label,
        ) = self._create_stat_card(
            value_label=self.active_value,
            object_name="activeStatCard",
        )

        (
            conflict_card,
            self.conflict_title_label,
            self.conflict_subtitle_label,
        ) = self._create_stat_card(
            value_label=self.conflict_value,
            object_name="conflictStatCard",
        )

        (
            character_card,
            self.character_title_label,
            self.character_subtitle_label,
        ) = self._create_stat_card(
            value_label=self.character_value,
            object_name="characterStatCard",
        )

        layout.addWidget(
            total_card
        )

        layout.addWidget(
            active_card
        )

        layout.addWidget(
            conflict_card
        )

        layout.addWidget(
            character_card
        )

    def _create_stat_card(
        self,
        *,
        value_label: QLabel,
        object_name: str,
    ) -> tuple[
        QFrame,
        QLabel,
        QLabel,
    ]:
        card = QFrame(
            self
        )

        card.setObjectName(
            object_name
        )

        card.setProperty(
            "statCard",
            True,
        )

        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        card.setMinimumHeight(
            94
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            16,
            13,
            16,
            13,
        )

        card_layout.setSpacing(
            2
        )

        title_label = QLabel(
            card
        )

        title_label.setObjectName(
            "statTitle"
        )

        value_label.setParent(
            card
        )

        value_label.setObjectName(
            "statValue"
        )

        subtitle_label = QLabel(
            card
        )

        subtitle_label.setObjectName(
            "statSubtitle"
        )

        card_layout.addWidget(
            title_label
        )

        card_layout.addWidget(
            value_label
        )

        card_layout.addWidget(
            subtitle_label
        )

        return (
            card,
            title_label,
            subtitle_label,
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.total_title_label.setText(
            tr(
                "library.stats."
                "total.title"
            )
        )

        self.total_subtitle_label.setText(
            tr(
                "library.stats."
                "total.subtitle"
            )
        )

        self.active_title_label.setText(
            tr(
                "library.stats."
                "active.title"
            )
        )

        self.active_subtitle_label.setText(
            tr(
                "library.stats."
                "active.subtitle"
            )
        )

        self.conflict_title_label.setText(
            tr(
                "library.stats."
                "conflicts.title"
            )
        )

        self.conflict_subtitle_label.setText(
            tr(
                "library.stats."
                "conflicts.subtitle"
            )
        )

        self.character_title_label.setText(
            tr(
                "library.stats."
                "characters.title"
            )
        )

        self.character_subtitle_label.setText(
            tr(
                "library.stats."
                "characters.subtitle"
            )
        )

    def set_values(
        self,
        *,
        total: int,
        active: int,
        conflicts: int,
        characters: int,
    ) -> None:
        self.total_value.setText(
            str(total)
        )

        self.active_value.setText(
            str(active)
        )

        self.conflict_value.setText(
            str(conflicts)
        )

        self.character_value.setText(
            str(characters)
        )

    def reset(
        self,
    ) -> None:
        self.set_values(
            total=0,
            active=0,
            conflicts=0,
            characters=0,
        )