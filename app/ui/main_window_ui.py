from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QResizeEvent,
)

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.games.registry import (
    all_games,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.services.icon_manager import (
    resolve_game_icon_path,
    resolve_navigation_icon_path,
)

from app.version import (
    APP_VERSION_DISPLAY,
)


# ============================================================
# Icon fallbacks
# ============================================================

TOP_NAV_FALLBACK_ICONS = {
    "library": QStyle.StandardPixmap.SP_DirHomeIcon,
    "gamebanana": QStyle.StandardPixmap.SP_DriveNetIcon,
    "profiles": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "conflicts": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "icons": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
}


# ============================================================
# Helpers
# ============================================================

def stable_game_id(
    game,
) -> str:
    value = getattr(
        game,
        "game_id",
        None,
    )

    if value:
        return str(
            value
        )

    value = getattr(
        game,
        "id",
        None,
    )

    if hasattr(
        value,
        "value",
    ):
        return str(
            value.value
        )

    return str(
        value
    )


def game_importer_name(
    game,
) -> str:
    value = getattr(
        game,
        "importer_name",
        None,
    )

    if value:
        return str(
            value
        )

    return str(
        getattr(
            game,
            "importer",
            "",
        )
    )


def load_game_icon(
    game_id: str,
) -> QIcon:
    icon_path = resolve_game_icon_path(
        game_id
    )

    if icon_path is None:
        return QIcon()

    return QIcon(
        str(icon_path)
    )


def load_top_navigation_icon(
    icon_id: str,
    widget: QWidget,
) -> QIcon:
    icon_path = resolve_navigation_icon_path(
        icon_id
    )

    if icon_path is not None:
        icon = QIcon(
            str(icon_path)
        )
        if not icon.isNull():
            return icon

    fallback = TOP_NAV_FALLBACK_ICONS.get(
        icon_id
    )

    if fallback is not None:
        return widget.style().standardIcon(
            fallback
        )

    return QIcon()


# ============================================================
# Animated Stack
# ============================================================

class AnimatedStackedWidget(
    QStackedWidget
):
    """
    Sehr kurze, dezente Seiten-Transition.

    Die Page selbst wird nicht verändert. Stattdessen wird ein
    Snapshot der alten Seite kurz als Overlay ausgeblendet und
    minimal verschoben.

    Dadurch bleiben Library/GameBanana/Profiles/Conflicts komplett
    unabhängig von der Animation.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self._duration_ms = 165
        self._slide_distance = 16

        self._animation_group: (
            QParallelAnimationGroup
            | None
        ) = None

        self._overlay: (
            QLabel
            | None
        ) = None

        self._pending_index: (
            int
            | None
        ) = None

    def setCurrentWidget(
        self,
        widget: QWidget,
    ) -> None:
        index = self.indexOf(
            widget
        )

        if index >= 0:
            self.setCurrentIndex(
                index
            )

    def setCurrentIndex(
        self,
        index: int,
    ) -> None:
        index = int(
            index
        )

        if (
            index < 0
            or index >= self.count()
        ):
            return

        current_index = (
            super().currentIndex()
        )

        if index == current_index:
            return

        if self._animation_group is not None:
            self._pending_index = index
            return

        if (
            current_index < 0
            or not self.isVisible()
            or self.width() <= 1
            or self.height() <= 1
        ):
            super().setCurrentIndex(
                index
            )
            return

        old_widget = self.widget(
            current_index
        )

        if old_widget is None:
            super().setCurrentIndex(
                index
            )
            return

        snapshot = old_widget.grab()

        super().setCurrentIndex(
            index
        )

        if snapshot.isNull():
            return

        overlay = QLabel(
            self
        )

        overlay.setObjectName(
            "pageTransitionOverlay"
        )

        overlay.setPixmap(
            snapshot
        )

        overlay.setScaledContents(
            True
        )

        overlay.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        start_rect = QRect(
            0,
            0,
            self.width(),
            self.height(),
        )

        direction = (
            -1
            if index > current_index
            else 1
        )

        end_rect = QRect(
            direction
            * self._slide_distance,
            0,
            self.width(),
            self.height(),
        )

        overlay.setGeometry(
            start_rect
        )

        opacity = QGraphicsOpacityEffect(
            overlay
        )

        opacity.setOpacity(
            1.0
        )

        overlay.setGraphicsEffect(
            opacity
        )

        geometry_animation = QPropertyAnimation(
            overlay,
            b"geometry",
            self,
        )

        geometry_animation.setDuration(
            self._duration_ms
        )

        geometry_animation.setStartValue(
            start_rect
        )

        geometry_animation.setEndValue(
            end_rect
        )

        geometry_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        opacity_animation = QPropertyAnimation(
            opacity,
            b"opacity",
            self,
        )

        opacity_animation.setDuration(
            self._duration_ms
        )

        opacity_animation.setStartValue(
            1.0
        )

        opacity_animation.setEndValue(
            0.0
        )

        opacity_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        group = QParallelAnimationGroup(
            self
        )

        group.addAnimation(
            geometry_animation
        )

        group.addAnimation(
            opacity_animation
        )

        group.finished.connect(
            self._finish_transition
        )

        self._overlay = overlay
        self._animation_group = group

        overlay.show()
        overlay.raise_()

        group.start()

    def _finish_transition(
        self,
    ) -> None:
        overlay = self._overlay
        group = self._animation_group

        self._overlay = None
        self._animation_group = None

        if overlay is not None:
            overlay.hide()
            overlay.setGraphicsEffect(
                None
            )
            overlay.deleteLater()

        if group is not None:
            group.deleteLater()

        pending = self._pending_index
        self._pending_index = None

        if (
            pending is not None
            and pending
            != super().currentIndex()
        ):
            self.setCurrentIndex(
                pending
            )

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

        if self._overlay is not None:
            geometry = (
                self._overlay.geometry()
            )

            self._overlay.setGeometry(
                geometry.x(),
                geometry.y(),
                self.width(),
                self.height(),
            )


# ============================================================
# Game Button - ICON ONLY
# ============================================================

class GameSidebarButton(
    QToolButton
):
    """
    Ein Game-Button zeigt absichtlich nur das echte Game-Icon.

    Name + Importer erscheinen als Tooltip.
    """

    def __init__(
        self,
        *,
        game,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.game = game
        self.game_id = stable_game_id(
            game
        )

        self.setObjectName(
            "gameSidebarButton"
        )

        self.setCheckable(
            True
        )

        self.setAutoExclusive(
            False
        )

        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )

        self.setIconSize(
            QSize(
                48,
                48,
            )
        )

        self.setIcon(
            load_game_icon(
                self.game_id
            )
        )

        self.setFixedSize(
            66,
            66,
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.refresh_tooltip()

    def refresh_tooltip(
        self,
    ) -> None:
        importer = game_importer_name(
            self.game
        )

        if importer:
            text = (
                f"{self.game.name}\n"
                f"{importer}"
            )
        else:
            text = str(
                self.game.name
            )

        self.setToolTip(
            text
        )

    def refresh_icon(
        self,
    ) -> None:
        self.setIcon(
            load_game_icon(
                self.game_id
            )
        )



# ============================================================
# Navigation Button + Conflict Badge
# ============================================================

class TopNavigationButton(
    QPushButton
):
    """
    Hauptnavigation mit Icon + Text.
    """

    def __init__(
        self,
        *,
        page_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.page_id = page_id

        self.setObjectName(
            "topNavigationButton"
        )

        self.setCheckable(
            True
        )

        self.setAutoExclusive(
            False
        )

        self.setMinimumHeight(
            42
        )

        self.setIconSize(
            QSize(
                18,
                18,
            )
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.badge = QLabel(
            self
        )

        self.badge.setObjectName(
            "navigationBadge"
        )

        self.badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.badge.setFixedSize(
            24,
            18,
        )

        self.badge.hide()

    def set_badge_count(
        self,
        count: int,
    ) -> None:
        count = max(
            0,
            int(count),
        )

        if count <= 0:
            self.badge.hide()
            return

        self.badge.setText(
            "99+"
            if count > 99
            else str(count)
        )

        self.badge.show()
        self._position_badge()

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._position_badge()

    def _position_badge(
        self,
    ) -> None:
        self.badge.move(
            self.width()
            - self.badge.width()
            - 4,
            2,
        )


# ============================================================
# Main Window UI
# ============================================================

class MainWindowUI(
    QWidget
):
    """
    Moderne Hauptfenster-Shell.

    Design:
    - links nur Game-Icons
    - oben Icon + Text Navigation
    - Settings ebenfalls mit Icon
    - aktuelle Game-Info separat
    - Conflict Badge bleibt erhalten
    - dezente Page-Transition

    MainWindow-kompatible Public API bleibt unverändert.
    """

    game_selected = Signal(
        str
    )

    page_selected = Signal(
        str
    )

    settings_requested = Signal()

    PAGE_LIBRARY = "library"
    PAGE_GAMEBANANA = "gamebanana"
    PAGE_PROFILES = "profiles"
    PAGE_CONFLICTS = "conflicts"
    PAGE_ICONS = "icons"

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "mainWindowUi"
        )

        self.config = config

        self.game_buttons: dict[
            str,
            GameSidebarButton,
        ] = {}

        self.navigation_buttons: dict[
            str,
            TopNavigationButton,
        ] = {}

        self.game_button_group = QButtonGroup(
            self
        )

        self.game_button_group.setExclusive(
            True
        )

        self.navigation_button_group = QButtonGroup(
            self
        )

        self.navigation_button_group.setExclusive(
            True
        )

        self.page_stack = AnimatedStackedWidget(
            self
        )

        self.game_name_label = QLabel()
        self.importer_label = QLabel()
        self.sidebar_title = QLabel()
        self.games_title = QLabel()
        self.version_label = QLabel()

        self.settings_button = QPushButton()

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self.set_active_game(
            self.config.selected_game
        )

        self.set_active_page(
            self.PAGE_LIBRARY
        )

    # ========================================================
    # Root
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        root_layout = QHBoxLayout(
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

        root_layout.addWidget(
            self._create_game_sidebar()
        )

        root_layout.addWidget(
            self._create_workspace(),
            stretch=1,
        )

        self._apply_stylesheet()

    # ========================================================
    # Icon-only Game Sidebar
    # ========================================================

    def _create_game_sidebar(
        self,
    ) -> QWidget:
        sidebar = QFrame(
            self
        )

        sidebar.setObjectName(
            "gameSidebar"
        )

        sidebar.setFixedWidth(
            92
        )

        layout = QVBoxLayout(
            sidebar
        )

        layout.setContentsMargins(
            12,
            15,
            12,
            14,
        )

        layout.setSpacing(
            9
        )

        self.sidebar_title.setObjectName(
            "sidebarAppTitle"
        )

        self.sidebar_title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.sidebar_title
        )

        layout.addSpacing(
            8
        )

        self.games_title.setObjectName(
            "sidebarSectionTitle"
        )

        self.games_title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.games_title
        )

        layout.addSpacing(
            2
        )

        for game in all_games():
            game_id = stable_game_id(
                game
            )

            button = GameSidebarButton(
                game=game,
                parent=sidebar,
            )

            button.clicked.connect(
                lambda _checked=False, value=game_id: (
                    self.game_selected.emit(
                        value
                    )
                )
            )

            self.game_button_group.addButton(
                button
            )

            self.game_buttons[
                game_id
            ] = button

            layout.addWidget(
                button,
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )

        layout.addStretch(
            1
        )

        self.version_label.setObjectName(
            "sidebarVersion"
        )

        self.version_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.version_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.version_label
        )

        return sidebar

    # ========================================================
    # Workspace
    # ========================================================

    def _create_workspace(
        self,
    ) -> QWidget:
        workspace = QWidget(
            self
        )

        workspace.setObjectName(
            "mainWorkspace"
        )

        layout = QVBoxLayout(
            workspace
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

        layout.addWidget(
            self._create_top_bar()
        )

        layout.addWidget(
            self.page_stack,
            stretch=1,
        )

        return workspace

    # ========================================================
    # Top Bar
    # ========================================================

    def _create_top_bar(
        self,
    ) -> QWidget:
        top_bar = QFrame(
            self
        )

        top_bar.setObjectName(
            "topBar"
        )

        layout = QHBoxLayout(
            top_bar
        )

        layout.setContentsMargins(
            22,
            10,
            16,
            10,
        )

        layout.setSpacing(
            12
        )

        # ----------------------------------------------------
        # Current Game
        # ----------------------------------------------------

        game_info = QFrame(
            top_bar
        )

        game_info.setObjectName(
            "currentGameCard"
        )

        game_info.setMinimumWidth(
            190
        )

        game_info.setMaximumWidth(
            290
        )

        game_info_layout = QVBoxLayout(
            game_info
        )

        game_info_layout.setContentsMargins(
            12,
            7,
            12,
            7,
        )

        game_info_layout.setSpacing(
            1
        )

        self.game_name_label.setObjectName(
            "currentGameName"
        )

        self.importer_label.setObjectName(
            "currentImporter"
        )

        game_info_layout.addWidget(
            self.game_name_label
        )

        game_info_layout.addWidget(
            self.importer_label
        )

        layout.addWidget(
            game_info
        )

        # ----------------------------------------------------
        # Navigation - ICON + TEXT
        # ----------------------------------------------------

        navigation_frame = QFrame(
            top_bar
        )

        navigation_frame.setObjectName(
            "topNavigationFrame"
        )

        navigation_layout = QHBoxLayout(
            navigation_frame
        )

        navigation_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        navigation_layout.setSpacing(
            3
        )

        for page_id in (
            self.PAGE_LIBRARY,
            self.PAGE_GAMEBANANA,
            self.PAGE_PROFILES,
            self.PAGE_CONFLICTS,
            self.PAGE_ICONS,
        ):
            button = TopNavigationButton(
                page_id=page_id,
                parent=navigation_frame,
            )

            button.setIcon(
                load_top_navigation_icon(
                    page_id,
                    button,
                )
            )

            button.clicked.connect(
                lambda _checked=False, value=page_id: (
                    self.page_selected.emit(
                        value
                    )
                )
            )

            self.navigation_button_group.addButton(
                button
            )

            self.navigation_buttons[
                page_id
            ] = button

            navigation_layout.addWidget(
                button
            )

        layout.addWidget(
            navigation_frame
        )

        layout.addStretch(
            1
        )

        # ----------------------------------------------------
        # Settings - ICON + TEXT
        # ----------------------------------------------------

        self.settings_button.setObjectName(
            "settingsTopButton"
        )

        self.settings_button.setMinimumHeight(
            42
        )

        self.settings_button.setIconSize(
            QSize(
                18,
                18,
            )
        )

        self.settings_button.setIcon(
            load_top_navigation_icon(
                "settings",
                self.settings_button,
            )
        )

        self.settings_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.settings_button.clicked.connect(
            self.settings_requested
        )

        layout.addWidget(
            self.settings_button
        )

        return top_bar

    # ========================================================
    # Current Game
    # ========================================================

    def set_active_game(
        self,
        game_id: str,
    ) -> None:
        button = self.game_buttons.get(
            game_id
        )

        if button is None:
            return

        button.setChecked(
            True
        )

        game = button.game

        self.game_name_label.setText(
            str(
                game.name
            )
        )

        self.importer_label.setText(
            game_importer_name(
                game
            )
        )

    # ========================================================
    # Current Page
    # ========================================================

    def set_active_page(
        self,
        page_id: str,
    ) -> None:
        button = self.navigation_buttons.get(
            page_id
        )

        if button is not None:
            button.setChecked(
                True
            )

    # ========================================================
    # Conflict Badge
    # ========================================================

    def set_conflict_count(
        self,
        count: int,
    ) -> None:
        button = self.navigation_buttons.get(
            self.PAGE_CONFLICTS
        )

        if button is not None:
            button.set_badge_count(
                count
            )

    # ========================================================
    # Runtime icon refresh
    # ========================================================

    def refresh_icons(
        self,
    ) -> None:
        for button in self.game_buttons.values():
            button.refresh_icon()

        for page_id, button in self.navigation_buttons.items():
            button.setIcon(
                load_top_navigation_icon(
                    page_id,
                    button,
                )
            )

        self.settings_button.setIcon(
            load_top_navigation_icon(
                "settings",
                self.settings_button,
            )
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.sidebar_title.setText(
            "XXMI"
        )

        self.games_title.setText(
            tr(
                "ui.games.title"
            ).upper()
        )

        self.version_label.setText(
            APP_VERSION_DISPLAY
        )

        labels = {
            self.PAGE_LIBRARY: tr(
                "navigation.library"
            ),
            self.PAGE_GAMEBANANA: tr(
                "navigation.gamebanana"
            ),
            self.PAGE_PROFILES: tr(
                "navigation.profiles"
            ),
            self.PAGE_CONFLICTS: tr(
                "navigation.conflicts"
            ),
            self.PAGE_ICONS: tr(
                "navigation.icons"
            ),
        }

        for page_id, text in labels.items():
            button = self.navigation_buttons.get(
                page_id
            )

            if button is not None:
                button.setText(
                    text
                )

        self.settings_button.setText(
            tr(
                "navigation.settings"
            )
        )

        self.settings_button.setToolTip(
            tr(
                "navigation.settings"
            )
        )

        for button in self.game_buttons.values():
            button.refresh_tooltip()

    # ========================================================
    # Styles
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QWidget#mainWindowUi,
            QWidget#mainWorkspace {
                background-color: #101319;
                color: #e7e9ef;
            }

            /* ================================================
               GAME SIDEBAR
               ================================================ */

            QFrame#gameSidebar {
                background-color: #151920;
                border-right: 1px solid #292f39;
            }

            QLabel#sidebarAppTitle {
                color: #f5f6f8;
                font-size: 18px;
                font-weight: 900;
                letter-spacing: 1px;
            }

            QLabel#sidebarSectionTitle {
                color: #656f7d;
                font-size: 8px;
                font-weight: 800;
            }

            QLabel#sidebarVersion {
                color: #59616d;
                font-size: 8px;
                padding-top: 6px;
            }

            QToolButton#gameSidebarButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 13px;
                padding: 7px;
            }

            QToolButton#gameSidebarButton:hover {
                background-color: #20262e;
                border-color: #303843;
            }

            QToolButton#gameSidebarButton:checked {
                background-color: #292440;
                border: 1px solid #7864e8;
            }

            QToolButton#gameSidebarButton:pressed {
                background-color: #332d4c;
            }

            /* ================================================
               TOP BAR
               ================================================ */

            QFrame#topBar {
                background-color: #151920;
                border-bottom: 1px solid #292f39;
                min-height: 70px;
                max-height: 70px;
            }

            QFrame#currentGameCard {
                background-color: #1a1f27;
                border: 1px solid #2c333e;
                border-radius: 9px;
            }

            QLabel#currentGameName {
                background-color: transparent;
                color: #f4f5f7;
                font-size: 13px;
                font-weight: 850;
            }

            QLabel#currentImporter {
                background-color: transparent;
                color: #7f8997;
                font-size: 9px;
            }

            /* ================================================
               ICON + TEXT NAVIGATION
               ================================================ */

            QFrame#topNavigationFrame {
                background-color: #11151a;
                border: 1px solid #292f39;
                border-radius: 10px;
            }

            QPushButton#topNavigationButton {
                min-width: 0px;
                min-height: 40px;
                padding-left: 10px;
                padding-right: 11px;

                background-color: transparent;
                color: #87919f;

                border: 1px solid transparent;
                border-radius: 7px;

                font-size: 10px;
                font-weight: 750;
            }

            QPushButton#topNavigationButton:hover {
                background-color: #20262e;
                color: #e8ebef;
            }

            QPushButton#topNavigationButton:checked {
                background-color: #292440;
                color: #ffffff;
                border: 1px solid #574a96;
                font-weight: 850;
            }

            QLabel#navigationBadge {
                background-color: #e24d61;
                color: #ffffff;
                border: none;
                border-radius: 9px;
                font-size: 9px;
                font-weight: 900;
                padding: 0px;
            }

            /* ================================================
               SETTINGS - ICON + TEXT
               ================================================ */

            QPushButton#settingsTopButton {
                min-width: 0px;
                min-height: 40px;
                padding-left: 10px;
                padding-right: 11px;

                background-color: #1b2027;
                color: #a7afbb;

                border: 1px solid #303742;
                border-radius: 8px;

                font-size: 10px;
                font-weight: 750;
            }

            QPushButton#settingsTopButton:hover {
                background-color: #252c35;
                color: #ffffff;
                border-color: #444d5a;
            }

            QPushButton#settingsTopButton:pressed {
                background-color: #2c3440;
            }

            /* ================================================
               WORKSPACE
               ================================================ */

            QStackedWidget {
                background-color: #101319;
                border: none;
            }

            QLabel#pageTransitionOverlay {
                background-color: #101319;
                border: none;
            }

            QToolTip {
                background-color: #20262e;
                color: #f0f2f5;
                border: 1px solid #3a424e;
                padding: 7px;
            }
            """
        )


# ============================================================
# Placeholder Page - compatibility helper
# ============================================================

def create_placeholder_page(
    *,
    title: str,
    description: str,
    parent: QWidget | None = None,
) -> QWidget:
    page = QWidget(
        parent
    )

    layout = QVBoxLayout(
        page
    )

    layout.setContentsMargins(
        32,
        28,
        32,
        28,
    )

    layout.setSpacing(
        10
    )

    title_label = QLabel(
        title
    )

    title_label.setObjectName(
        "pageTitle"
    )

    description_label = QLabel(
        description
    )

    description_label.setWordWrap(
        True
    )

    description_label.setObjectName(
        "pageDescription"
    )

    layout.addWidget(
        title_label
    )

    layout.addWidget(
        description_label
    )

    layout.addStretch(
        1
    )

    return page


__all__ = [
    "AnimatedStackedWidget",
    "GameSidebarButton",
    "MainWindowUI",
    "TopNavigationButton",
    "create_placeholder_page",
]
