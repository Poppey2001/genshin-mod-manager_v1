from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translation_manager


class _ResponsiveCenteredCardHost(QWidget):
    """Gemeinsame responsive Basis für Library Empty-State-Cards."""

    CARD_MAX_WIDTH = 560
    CARD_MIN_WIDTH = 280

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.card: QFrame | None = None

    def _sync_card_width(self) -> None:
        card = self.card

        if card is None:
            return

        available = max(
            1,
            self.width() - 48,
        )

        if available <= self.CARD_MIN_WIDTH:
            width = max(
                220,
                available,
            )
        else:
            width = min(
                self.CARD_MAX_WIDTH,
                available,
            )

        if card.width() != width:
            card.setFixedWidth(width)

        card.updateGeometry()

        layout = card.layout()

        if layout is not None:
            layout.invalidate()
            layout.activate()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_card_width()


class LibraryEmptyState(_ResponsiveCenteredCardHost):
    import_archives_requested = Signal()
    import_directory_requested = Signal()

    CARD_MAX_WIDTH = 560

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("libraryEmptyState")

        self.card = QFrame(self)
        self.card.setObjectName("libraryEmptyCard")
        self.card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.icon_label = QLabel("+", self.card)
        self.title_label = QLabel(self.card)
        self.description_label = QLabel(self.card)

        self.import_button = QPushButton(self.card)
        self.directory_button = QPushButton(self.card)

        self._build_ui()
        self._connect_signals()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)
        root.addStretch(1)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(38, 34, 38, 34)
        layout.setSpacing(0)

        self.icon_label.setObjectName("libraryEmptyIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(66, 66)

        layout.addWidget(
            self.icon_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addSpacing(18)

        self.title_label.setObjectName("libraryEmptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        layout.addWidget(self.title_label)

        layout.addSpacing(8)

        self.description_label.setObjectName(
            "libraryEmptyDescription"
        )
        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.description_label.setWordWrap(True)
        self.description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        layout.addWidget(self.description_label)
        layout.addSpacing(24)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addStretch(1)

        self.directory_button.setObjectName(
            "libraryEmptySecondaryButton"
        )
        self.directory_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.import_button.setObjectName(
            "libraryEmptyPrimaryButton"
        )
        self.import_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        actions.addWidget(self.directory_button)
        actions.addWidget(self.import_button)
        actions.addStretch(1)

        layout.addLayout(actions)

        root.addWidget(
            self.card,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        root.addStretch(1)

    def _connect_signals(self) -> None:
        self.import_button.clicked.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )
        self.directory_button.clicked.connect(
            lambda _checked=False:
            self.import_directory_requested.emit()
        )

    def set_actions_enabled(self, enabled: bool) -> None:
        self.import_button.setEnabled(bool(enabled))
        self.directory_button.setEnabled(bool(enabled))

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr("library.title")
        )
        self.description_label.setText(
            tr("library.description")
        )
        self.import_button.setText(
            "＋  " + tr("library.action.import")
        )
        self.directory_button.setText(
            tr("library.import.directory")
        )

        self.title_label.updateGeometry()
        self.description_label.updateGeometry()
        self._sync_card_width()

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(
            r"""
            QWidget#libraryEmptyState {
                background: transparent;
            }

            QFrame#libraryEmptyCard {
                background: #171b22;
                border: 1px solid #2d3440;
                border-radius: 14px;
            }

            QLabel#libraryEmptyIcon {
                background: #282340;
                color: #a394ff;
                border: 1px solid #51458b;
                border-radius: 33px;
                font-size: 32px;
                font-weight: 500;
            }

            QLabel#libraryEmptyTitle {
                background: transparent;
                color: #f4f5f7;
                font-size: 20px;
                font-weight: 800;
                padding-top: 2px;
                padding-bottom: 2px;
            }

            QLabel#libraryEmptyDescription {
                background: transparent;
                color: #8d96a4;
                font-size: 12px;
                padding-top: 2px;
                padding-bottom: 2px;
            }

            QPushButton#libraryEmptyPrimaryButton,
            QPushButton#libraryEmptySecondaryButton {
                min-height: 38px;
                padding-left: 16px;
                padding-right: 16px;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 800;
            }

            QPushButton#libraryEmptyPrimaryButton {
                background: #735ee8;
                color: #ffffff;
                border: 1px solid #8674ef;
            }

            QPushButton#libraryEmptyPrimaryButton:hover {
                background: #806cf0;
                border-color: #9a8af4;
            }

            QPushButton#libraryEmptySecondaryButton {
                background: #232933;
                color: #d4d9e1;
                border: 1px solid #363f4c;
            }

            QPushButton#libraryEmptySecondaryButton:hover {
                background: #2d3541;
                color: #ffffff;
                border-color: #4a5666;
            }

            QPushButton:disabled {
                background: #252a32;
                color: #656c78;
                border-color: #323842;
            }
            """
        )


class LibraryFilterEmptyState(_ResponsiveCenteredCardHost):
    reset_requested = Signal()

    CARD_MAX_WIDTH = 520

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("libraryFilterEmptyState")

        self._total_mods = 0

        self.card = QFrame(self)
        self.card.setObjectName("libraryFilterEmptyCard")
        self.card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.icon_label = QLabel("⌕", self.card)
        self.title_label = QLabel(self.card)
        self.reset_button = QPushButton(self.card)

        self._build_ui()
        self._connect_signals()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)
        root.addStretch(1)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(0)

        self.icon_label.setObjectName("libraryFilterEmptyIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(62, 62)

        layout.addWidget(
            self.icon_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        layout.addSpacing(18)

        self.title_label.setObjectName("libraryFilterEmptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        layout.addWidget(self.title_label)

        layout.addSpacing(22)

        self.reset_button.setObjectName(
            "libraryFilterEmptyResetButton"
        )
        self.reset_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.reset_button.setMinimumHeight(38)

        layout.addWidget(
            self.reset_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root.addWidget(
            self.card,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root.addStretch(1)

    def _connect_signals(self) -> None:
        self.reset_button.clicked.connect(
            lambda _checked=False:
            self.reset_requested.emit()
        )

    def set_total_mods(self, total: int) -> None:
        self._total_mods = max(
            0,
            int(total),
        )
        self.retranslate_ui()

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "library.status.filter_result",
                visible=0,
                total=self._total_mods,
            )
        )
        self.reset_button.setText(
            tr("library.filter.reset")
        )

        self.title_label.updateGeometry()
        self._sync_card_width()

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(
            r"""
            QWidget#libraryFilterEmptyState {
                background: transparent;
            }

            QFrame#libraryFilterEmptyCard {
                background: #171b22;
                border: 1px solid #2d3440;
                border-radius: 14px;
            }

            QLabel#libraryFilterEmptyIcon {
                background: #202631;
                color: #9ba5b3;
                border: 1px solid #37414e;
                border-radius: 31px;
                font-size: 27px;
                font-weight: 700;
            }

            QLabel#libraryFilterEmptyTitle {
                background: transparent;
                color: #f4f5f7;
                font-size: 19px;
                font-weight: 800;
                padding-top: 3px;
                padding-bottom: 3px;
            }

            QPushButton#libraryFilterEmptyResetButton {
                min-height: 38px;
                padding-left: 18px;
                padding-right: 18px;
                background: #292f39;
                color: #e3e7ec;
                border: 1px solid #3b4552;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 800;
            }

            QPushButton#libraryFilterEmptyResetButton:hover {
                background: #343d49;
                color: #ffffff;
                border-color: #505d6d;
            }
            """
        )


__all__ = [
    "LibraryEmptyState",
    "LibraryFilterEmptyState",
]
