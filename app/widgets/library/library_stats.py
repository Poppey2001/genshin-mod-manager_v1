from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class LibraryStatsWidget(QWidget):
    """
    Zeigt die Statistik-Karten der Mod-Bibliothek an.

    Dieses Widget stellt nur die Werte dar.
    Die Berechnung der Werte bleibt in LibraryPage.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.total_value = QLabel("0")
        self.active_value = QLabel("0")
        self.conflict_value = QLabel("0")
        self.character_value = QLabel("0")

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(
            12
        )

        layout.addWidget(
            self._create_stat_card(
                title="Mods gesamt",
                value_label=self.total_value,
                object_name="totalStatCard",
                subtitle="Bibliothek",
            )
        )

        layout.addWidget(
            self._create_stat_card(
                title="Aktiviert",
                value_label=self.active_value,
                object_name="activeStatCard",
                subtitle="Im Spiel geladen",
            )
        )

        layout.addWidget(
            self._create_stat_card(
                title="Konflikte",
                value_label=self.conflict_value,
                object_name="conflictStatCard",
                subtitle="Benötigen Aufmerksamkeit",
            )
        )

        layout.addWidget(
            self._create_stat_card(
                title="Charaktere",
                value_label=self.character_value,
                object_name="characterStatCard",
                subtitle="Erkannte Zuordnungen",
            )
        )

    def _create_stat_card(
        self,
        *,
        title: str,
        value_label: QLabel,
        object_name: str,
        subtitle: str,
    ) -> QFrame:
        card = QFrame()
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

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            16,
            13,
            16,
            13,
        )
        layout.setSpacing(
            2
        )

        title_label = QLabel(
            title
        )
        title_label.setObjectName(
            "statTitle"
        )

        value_label.setObjectName(
            "statValue"
        )

        subtitle_label = QLabel(
            subtitle
        )
        subtitle_label.setObjectName(
            "statSubtitle"
        )

        layout.addWidget(
            title_label
        )
        layout.addWidget(
            value_label
        )
        layout.addWidget(
            subtitle_label
        )

        return card

    def set_values(
        self,
        *,
        total: int,
        active: int,
        conflicts: int,
        characters: int,
    ) -> None:
        """
        Aktualisiert alle angezeigten Statistikwerte.
        """
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

    def reset(self) -> None:
        """
        Setzt alle Statistikwerte auf null.
        """
        self.set_values(
            total=0,
            active=0,
            conflicts=0,
            characters=0,
        )