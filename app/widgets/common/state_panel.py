from __future__ import annotations

from enum import Enum
from typing import Callable

from PySide6.QtCore import (
    QSize,
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QIcon,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# State Kind
# ============================================================

class StateKind(
    str,
    Enum,
):
    EMPTY = "empty"
    LOADING = "loading"
    ERROR = "error"
    SUCCESS = "success"
    INFO = "info"


# ============================================================
# Loading Dots
# ============================================================

class LoadingDots(
    QLabel
):
    """
    Kleine Qt-only Loading-Animation.

    Keine GIF-Datei und kein externer Asset notwendig.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "stateLoadingDots"
        )

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setFixedHeight(
            26
        )

        self._frame = 0

        self._timer = QTimer(
            self
        )

        self._timer.setInterval(
            330
        )

        self._timer.timeout.connect(
            self._advance
        )

        self._advance()

    def start(
        self,
    ) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(
        self,
    ) -> None:
        self._timer.stop()

    def showEvent(
        self,
        event,
    ) -> None:
        super().showEvent(
            event
        )

        self.start()

    def hideEvent(
        self,
        event,
    ) -> None:
        self.stop()

        super().hideEvent(
            event
        )

    def _advance(
        self,
    ) -> None:
        frames = (
            "•  ·  ·",
            "·  •  ·",
            "·  ·  •",
        )

        self.setText(
            frames[
                self._frame
                % len(frames)
            ]
        )

        self._frame += 1


# ============================================================
# State Panel
# ============================================================

class StatePanel(
    QWidget
):
    """
    Gemeinsame Darstellung für:

    - Empty
    - Loading
    - Error
    - Success
    - Info

    Die Texte werden bewusst von der jeweiligen Page geliefert.
    Dadurch bleibt dieses Widget vollständig kompatibel mit dem
    bestehenden i18n/tr()-System.
    """

    primary_requested = Signal()
    secondary_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "statePanel"
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._kind = StateKind.INFO
        self._icon = QIcon()
        self._fallback_symbol = "i"

        self._build_ui()
        self._apply_stylesheet()

        self.configure(
            kind=StateKind.INFO,
            title="",
            description="",
        )

    # ========================================================
    # Build
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        root_layout.setSpacing(
            0
        )

        root_layout.addStretch(
            1
        )

        self.card = QFrame(
            self
        )

        self.card.setObjectName(
            "stateCard"
        )

        self.card.setMaximumWidth(
            560
        )

        self.card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        card_layout = QVBoxLayout(
            self.card
        )

        card_layout.setContentsMargins(
            34,
            32,
            34,
            30,
        )

        card_layout.setSpacing(
            0
        )

        # ----------------------------------------------------
        # Icon container
        # ----------------------------------------------------

        self.icon_frame = QFrame(
            self.card
        )

        self.icon_frame.setObjectName(
            "stateIconFrame"
        )

        self.icon_frame.setFixedSize(
            62,
            62,
        )

        icon_layout = QVBoxLayout(
            self.icon_frame
        )

        icon_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.icon_label = QLabel(
            self.icon_frame
        )

        self.icon_label.setObjectName(
            "stateIcon"
        )

        self.icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.icon_label.setFixedSize(
            60,
            60,
        )

        icon_layout.addWidget(
            self.icon_label
        )

        card_layout.addWidget(
            self.icon_frame,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        card_layout.addSpacing(
            18
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        self.title_label = QLabel(
            self.card
        )

        self.title_label.setObjectName(
            "stateTitle"
        )

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label.setWordWrap(
            True
        )

        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        card_layout.addWidget(
            self.title_label
        )

        card_layout.addSpacing(
            8
        )

        # ----------------------------------------------------
        # Description
        # ----------------------------------------------------

        self.description_label = QLabel(
            self.card
        )

        self.description_label.setObjectName(
            "stateDescription"
        )

        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label.setWordWrap(
            True
        )

        self.description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.description_label.setMaximumWidth(
            440
        )

        card_layout.addWidget(
            self.description_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        # ----------------------------------------------------
        # Loading animation
        # ----------------------------------------------------

        self.loading_dots = LoadingDots(
            self.card
        )

        card_layout.addSpacing(
            14
        )

        card_layout.addWidget(
            self.loading_dots
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        self.actions_frame = QWidget(
            self.card
        )

        self.actions_frame.setObjectName(
            "stateActions"
        )

        actions_layout = QHBoxLayout(
            self.actions_frame
        )

        actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        actions_layout.setSpacing(
            10
        )

        actions_layout.addStretch(
            1
        )

        self.secondary_button = QPushButton(
            self.actions_frame
        )

        self.secondary_button.setObjectName(
            "stateSecondaryButton"
        )

        self.secondary_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.secondary_button.clicked.connect(
            self.secondary_requested
        )

        actions_layout.addWidget(
            self.secondary_button
        )

        self.primary_button = QPushButton(
            self.actions_frame
        )

        self.primary_button.setObjectName(
            "statePrimaryButton"
        )

        self.primary_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.primary_button.clicked.connect(
            self.primary_requested
        )

        actions_layout.addWidget(
            self.primary_button
        )

        actions_layout.addStretch(
            1
        )

        card_layout.addSpacing(
            20
        )

        card_layout.addWidget(
            self.actions_frame
        )

        root_layout.addWidget(
            self.card,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root_layout.addStretch(
            1
        )

    # ========================================================
    # Public API
    # ========================================================

    @property
    def kind(
        self,
    ) -> StateKind:
        return self._kind

    def configure(
        self,
        *,
        kind: StateKind,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
        primary_text: str = "",
        secondary_text: str = "",
    ) -> None:
        self._kind = StateKind(
            kind
        )

        self.card.setProperty(
            "stateKind",
            self._kind.value,
        )

        self.icon_frame.setProperty(
            "stateKind",
            self._kind.value,
        )

        self.title_label.setText(
            str(title)
        )

        self.description_label.setText(
            str(description)
        )

        self.description_label.setVisible(
            bool(
                str(description).strip()
            )
        )

        self._icon = (
            QIcon(icon)
            if icon is not None
            else QIcon()
        )

        self._fallback_symbol = {
            StateKind.EMPTY: "—",
            StateKind.LOADING: "…",
            StateKind.ERROR: "!",
            StateKind.SUCCESS: "✓",
            StateKind.INFO: "i",
        }[
            self._kind
        ]

        self._render_icon()

        is_loading = (
            self._kind
            == StateKind.LOADING
        )

        self.loading_dots.setVisible(
            is_loading
        )

        if is_loading:
            self.loading_dots.start()
        else:
            self.loading_dots.stop()

        self.primary_button.setText(
            str(primary_text)
        )

        self.primary_button.setVisible(
            bool(
                str(primary_text).strip()
            )
        )

        self.secondary_button.setText(
            str(secondary_text)
        )

        self.secondary_button.setVisible(
            bool(
                str(secondary_text).strip()
            )
        )

        self.actions_frame.setVisible(
            self.primary_button.isVisible()
            or self.secondary_button.isVisible()
        )

        # Qt aktualisiert Property-Selektoren nicht automatisch.
        for widget in (
            self.card,
            self.icon_frame,
        ):
            style = widget.style()
            style.unpolish(
                widget
            )
            style.polish(
                widget
            )
            widget.update()

        self.title_label.updateGeometry()
        self.description_label.updateGeometry()
        self.card.updateGeometry()

        QTimer.singleShot(
            0,
            self._refresh_card_geometry,
        )

    def _refresh_card_geometry(
        self,
    ) -> None:
        self.title_label.updateGeometry()
        self.description_label.updateGeometry()

        layout = self.card.layout()

        if layout is not None:
            layout.invalidate()
            layout.activate()

        self.card.updateGeometry()

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        available = max(
            1,
            self.width() - 48,
        )

        if available <= 320:
            target_width = max(
                220,
                available,
            )
        else:
            target_width = min(
                560,
                max(
                    340,
                    int(
                        available * 0.82
                    ),
                ),
            )

        if self.card.width() != target_width:
            self.card.setFixedWidth(
                target_width
            )

        self._refresh_card_geometry()

    def show_empty(
        self,
        *,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
        primary_text: str = "",
        secondary_text: str = "",
    ) -> None:
        self.configure(
            kind=StateKind.EMPTY,
            title=title,
            description=description,
            icon=icon,
            primary_text=primary_text,
            secondary_text=secondary_text,
        )

    def show_loading(
        self,
        *,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
    ) -> None:
        self.configure(
            kind=StateKind.LOADING,
            title=title,
            description=description,
            icon=icon,
        )

    def show_error(
        self,
        *,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
        primary_text: str = "",
        secondary_text: str = "",
    ) -> None:
        self.configure(
            kind=StateKind.ERROR,
            title=title,
            description=description,
            icon=icon,
            primary_text=primary_text,
            secondary_text=secondary_text,
        )

    def show_success(
        self,
        *,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
        primary_text: str = "",
    ) -> None:
        self.configure(
            kind=StateKind.SUCCESS,
            title=title,
            description=description,
            icon=icon,
            primary_text=primary_text,
        )

    def show_info(
        self,
        *,
        title: str,
        description: str = "",
        icon: QIcon | None = None,
        primary_text: str = "",
        secondary_text: str = "",
    ) -> None:
        self.configure(
            kind=StateKind.INFO,
            title=title,
            description=description,
            icon=icon,
            primary_text=primary_text,
            secondary_text=secondary_text,
        )

    # ========================================================
    # Icon
    # ========================================================

    def _render_icon(
        self,
    ) -> None:
        if not self._icon.isNull():
            pixmap = self._icon.pixmap(
                QSize(
                    30,
                    30,
                )
            )

            self.icon_label.setText(
                ""
            )

            self.icon_label.setPixmap(
                pixmap
            )

            return

        self.icon_label.setPixmap(
            QIcon().pixmap(
                QSize(
                    1,
                    1,
                )
            )
        )

        self.icon_label.setText(
            self._fallback_symbol
        )

    # ========================================================
    # Styling
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        self.setStyleSheet(
            STATE_PANEL_QSS
        )


# ============================================================
# Content + State Stack
# ============================================================

class ContentStateStack(
    QWidget
):
    """
    Wrapper für eine bestehende Page-/Content-Fläche.

    Index 0: eigentlicher Inhalt
    Index 1: gemeinsamer StatePanel

    Eine Page muss damit nicht selbst mehrere Empty/Error/Loading
    Widgets verwalten.
    """

    primary_requested = Signal()
    secondary_requested = Signal()

    def __init__(
        self,
        *,
        content: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "contentStateStack"
        )

        self.content = content

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
            0
        )

        self.stack = QStackedWidget(
            self
        )

        self.stack.setObjectName(
            "contentStateInternalStack"
        )

        self.state_panel = StatePanel(
            self.stack
        )

        self.stack.addWidget(
            self.content
        )

        self.stack.addWidget(
            self.state_panel
        )

        layout.addWidget(
            self.stack
        )

        self.state_panel.primary_requested.connect(
            self.primary_requested
        )

        self.state_panel.secondary_requested.connect(
            self.secondary_requested
        )

        self.show_content()

    @property
    def is_showing_content(
        self,
    ) -> bool:
        return (
            self.stack.currentWidget()
            is self.content
        )

    def show_content(
        self,
    ) -> None:
        self.state_panel.loading_dots.stop()

        self.stack.setCurrentWidget(
            self.content
        )

    def show_empty(
        self,
        **kwargs,
    ) -> None:
        self.state_panel.show_empty(
            **kwargs
        )

        self.stack.setCurrentWidget(
            self.state_panel
        )

    def show_loading(
        self,
        **kwargs,
    ) -> None:
        self.state_panel.show_loading(
            **kwargs
        )

        self.stack.setCurrentWidget(
            self.state_panel
        )

    def show_error(
        self,
        **kwargs,
    ) -> None:
        self.state_panel.show_error(
            **kwargs
        )

        self.stack.setCurrentWidget(
            self.state_panel
        )

    def show_success(
        self,
        **kwargs,
    ) -> None:
        self.state_panel.show_success(
            **kwargs
        )

        self.stack.setCurrentWidget(
            self.state_panel
        )

    def show_info(
        self,
        **kwargs,
    ) -> None:
        self.state_panel.show_info(
            **kwargs
        )

        self.stack.setCurrentWidget(
            self.state_panel
        )


# ============================================================
# Optional helper
# ============================================================

def connect_state_action(
    signal,
    callback: Callable[[], None] | None,
) -> None:
    """
    Kleine Convenience-Funktion für optionale Retry-/Action-Callbacks.
    """

    if callback is not None:
        signal.connect(
            callback
        )


# ============================================================
# QSS
# ============================================================

STATE_PANEL_QSS = r"""
QWidget#statePanel {
    background: transparent;
}

QFrame#stateCard {
    background: #171b22;
    border: 1px solid #2b323d;
    border-radius: 14px;
}

QFrame#stateIconFrame {
    background: #202631;
    border: 1px solid #303845;
    border-radius: 31px;
}

QLabel#stateIcon {
    background: transparent;
    border: none;
    color: #9ba5b3;
    font-size: 27px;
    font-weight: 800;
}

QLabel#stateTitle {
    background: transparent;
    color: #f3f4f6;
    font-size: 18px;
    font-weight: 800;
    padding-top: 2px;
    padding-bottom: 2px;
}

QLabel#stateDescription {
    background: transparent;
    color: #8d96a4;
    font-size: 12px;
    padding-top: 2px;
    padding-bottom: 2px;
}

QLabel#stateLoadingDots {
    background: transparent;
    color: #8d7cff;
    font-size: 18px;
    font-weight: 900;
}

QPushButton#statePrimaryButton {
    min-height: 36px;
    padding-left: 16px;
    padding-right: 16px;

    background: #735ee8;
    color: #ffffff;

    border: 1px solid #8674ef;
    border-radius: 8px;

    font-size: 11px;
    font-weight: 800;
}

QPushButton#statePrimaryButton:hover {
    background: #806cf0;
    border-color: #9a8af4;
}

QPushButton#statePrimaryButton:pressed {
    background: #6754d1;
}

QPushButton#stateSecondaryButton {
    min-height: 36px;
    padding-left: 16px;
    padding-right: 16px;

    background: #202631;
    color: #c8ced7;

    border: 1px solid #343d49;
    border-radius: 8px;

    font-size: 11px;
    font-weight: 750;
}

QPushButton#stateSecondaryButton:hover {
    background: #29313c;
    color: #ffffff;
    border-color: #46515f;
}

/* ---------------------------------------------------------
   Empty
   --------------------------------------------------------- */

QFrame#stateIconFrame[stateKind="empty"] {
    background: #20252c;
    border-color: #343b45;
}

QFrame#stateIconFrame[stateKind="empty"] QLabel#stateIcon {
    color: #8c96a3;
}

/* ---------------------------------------------------------
   Loading
   --------------------------------------------------------- */

QFrame#stateIconFrame[stateKind="loading"] {
    background: #25213a;
    border-color: #514493;
}

QFrame#stateIconFrame[stateKind="loading"] QLabel#stateIcon {
    color: #9b89ff;
}

/* ---------------------------------------------------------
   Error
   --------------------------------------------------------- */

QFrame#stateCard[stateKind="error"] {
    border-color: #51313a;
}

QFrame#stateIconFrame[stateKind="error"] {
    background: #382128;
    border-color: #71404d;
}

QFrame#stateIconFrame[stateKind="error"] QLabel#stateIcon {
    color: #f07182;
}

/* ---------------------------------------------------------
   Success
   --------------------------------------------------------- */

QFrame#stateCard[stateKind="success"] {
    border-color: #28493d;
}

QFrame#stateIconFrame[stateKind="success"] {
    background: #1c352d;
    border-color: #396a58;
}

QFrame#stateIconFrame[stateKind="success"] QLabel#stateIcon {
    color: #69d2aa;
}

/* ---------------------------------------------------------
   Info
   --------------------------------------------------------- */

QFrame#stateIconFrame[stateKind="info"] {
    background: #202a3b;
    border-color: #3d5373;
}

QFrame#stateIconFrame[stateKind="info"] QLabel#stateIcon {
    color: #7ca9e8;
}

QStackedWidget#contentStateInternalStack {
    background: transparent;
    border: none;
}
"""


__all__ = [
    "ContentStateStack",
    "LoadingDots",
    "StateKind",
    "StatePanel",
    "connect_state_action",
]
