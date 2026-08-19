from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
    translation_manager,
)
from app.models.profile import (
    ModProfile,
)


class ProfileCard(
    QFrame
):
    activate_requested = Signal(
        object
    )
    save_current_requested = Signal(
        object
    )
    rename_requested = Signal(
        object
    )
    delete_requested = Signal(
        object
    )

    def __init__(
        self,
        *,
        profile: ModProfile,
        active: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.profile = profile
        self._active = active
        self._busy = False

        self.setObjectName(
            "profileCard"
        )
        self.setProperty(
            "active",
            active,
        )

        # Kompakte Karten statt mit dem Grid mitzuwachsen.
        self.setFixedWidth(
            340
        )
        self.setMinimumHeight(
            184
        )
        self.setMaximumHeight(
            214
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Maximum,
        )

        self.name_label = QLabel(
            self
        )
        self.name_label.setObjectName(
            "profileCardName"
        )

        self.active_badge = QLabel(
            self
        )
        self.active_badge.setObjectName(
            "profileActiveBadge"
        )
        self.active_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.stats_label = QLabel(
            self
        )
        self.stats_label.setObjectName(
            "profileCardStats"
        )

        self.updated_label = QLabel(
            self
        )
        self.updated_label.setObjectName(
            "profileCardUpdated"
        )

        self.activate_button = QPushButton(
            self
        )
        self.activate_button.setObjectName(
            "profileActivateButton"
        )

        self.save_button = QPushButton(
            self
        )
        self.save_button.setObjectName(
            "profileSecondaryButton"
        )

        self.rename_button = QPushButton(
            self
        )
        self.rename_button.setObjectName(
            "profileSecondaryButton"
        )

        self.delete_button = QPushButton(
            self
        )
        self.delete_button.setObjectName(
            "profileDeleteButton"
        )

        self._build_ui()
        self._connect_signals()

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
            16,
            14,
            16,
            14,
        )
        layout.setSpacing(
            10
        )

        top = QHBoxLayout()
        top.setSpacing(
            10
        )
        top.addWidget(
            self.name_label,
            stretch=1,
        )
        top.addWidget(
            self.active_badge,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        layout.addLayout(
            top
        )
        layout.addWidget(
            self.stats_label
        )
        layout.addWidget(
            self.updated_label
        )
        layout.addSpacing(
            4
        )

        primary = QHBoxLayout()
        primary.setSpacing(
            7
        )
        primary.addWidget(
            self.activate_button
        )
        primary.addWidget(
            self.save_button
        )
        primary.addStretch(
            1
        )

        secondary = QHBoxLayout()
        secondary.setSpacing(
            7
        )
        secondary.addWidget(
            self.rename_button
        )
        secondary.addWidget(
            self.delete_button
        )
        secondary.addStretch(
            1
        )

        layout.addLayout(
            primary
        )
        layout.addLayout(
            secondary
        )

    def _connect_signals(
        self,
    ) -> None:
        self.activate_button.clicked.connect(
            lambda _checked=False: self.activate_requested.emit(
                self.profile
            )
        )
        self.save_button.clicked.connect(
            lambda _checked=False: self.save_current_requested.emit(
                self.profile
            )
        )
        self.rename_button.clicked.connect(
            lambda _checked=False: self.rename_requested.emit(
                self.profile
            )
        )
        self.delete_button.clicked.connect(
            lambda _checked=False: self.delete_requested.emit(
                self.profile
            )
        )

    def set_active(
        self,
        active: bool,
    ) -> None:
        self._active = active
        self.setProperty(
            "active",
            active,
        )

        self.style().unpolish(
            self
        )
        self.style().polish(
            self
        )

        self.retranslate_ui()

    def set_busy(
        self,
        busy: bool,
    ) -> None:
        self._busy = busy

        for button in (
            self.activate_button,
            self.save_button,
            self.rename_button,
            self.delete_button,
        ):
            button.setEnabled(
                not busy
            )

        self.retranslate_ui()

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.name_label.setText(
            self.profile.name
        )

        self.active_badge.setText(
            tr(
                "profiles.card.active"
            )
        )
        self.active_badge.setVisible(
            self._active
        )

        self.stats_label.setText(
            tr(
                "profiles.card.stats",
                total=self.profile.total_count,
                enabled=self.profile.enabled_count,
            )
        )

        self.updated_label.setText(
            tr(
                "profiles.card.updated",
                value=self._format_updated_at(
                    self.profile.updated_at
                ),
            )
        )

        self.activate_button.setText(
            tr(
                "profiles.action.activate"
            )
        )
        self.save_button.setText(
            tr(
                "profiles.action.save_current"
            )
        )
        self.rename_button.setText(
            tr(
                "profiles.action.rename"
            )
        )
        self.delete_button.setText(
            tr(
                "profiles.action.delete"
            )
        )

        self.activate_button.setEnabled(
            not self._busy
            and not self._active
        )

    @staticmethod
    def _format_updated_at(
        value: str,
    ) -> str:
        try:
            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
            return parsed.astimezone().strftime(
                "%Y-%m-%d %H:%M"
            )
        except ValueError:
            return value


__all__ = [
    "ProfileCard",
]
