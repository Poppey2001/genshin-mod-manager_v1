from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QSize,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QIcon,
    QResizeEvent,
)

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
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

from app.platform_support import (
    resource_path,
)

from app.version import (
    APP_VERSION_DISPLAY,
)


# ============================================================
# Game Icon Mapping
# ============================================================

GAME_ICON_FILES = {
    "genshin-impact": (
        "genshin-impact.png"
    ),
    "honkai-star-rail": (
        "honkai-star-rail.png"
    ),
    "zenless-zone-zero": (
        "zenless-zone-zero.png"
    ),
    "wuthering-waves": (
        "wuthering-waves.png"
    ),
    "honkai-impact-3rd": (
        "honkai-impact-3rd.png"
    ),
    "arknights-endfield": (
        "arknights-endfield.png"
    ),
}


# ============================================================
# Hilfsfunktionen
# ============================================================

def stable_game_id(
    game,
) -> str:
    """
    Liefert unabhängig von Enum/Property
    die stabile Game-ID.
    """

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
    widget: QWidget,
) -> QIcon:
    filename = GAME_ICON_FILES.get(
        game_id
    )

    if filename:
        icon_path = resource_path(
            "assets",
            "icons",
            "games",
            filename,
        )

        if Path(
            icon_path
        ).is_file():
            return QIcon(
                str(
                    icon_path
                )
            )

    return (
        widget.style()
        .standardIcon(
            QStyle.StandardPixmap.SP_FileIcon
        )
    )


# ============================================================
# Game Button
# ============================================================

class GameSidebarButton(
    QToolButton
):
    """
    Button für ein einzelnes XXMI-Spiel.
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

        self.game_id = (
            stable_game_id(
                game
            )
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
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

        self.setIconSize(
            QSize(
                46,
                46,
            )
        )

        self.setIcon(
            load_game_icon(
                self.game_id,
                self,
            )
        )

        self.setText(
            (
                f"{game.name}\n"
                f"{game_importer_name(game)}"
            )
        )

        self.setMinimumHeight(
            66
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )


# ============================================================
# Navigation Button + Badge
# ============================================================

class TopNavigationButton(
    QToolButton
):
    """
    Button der oberen Navigation.

    Der Konflikt-Button kann zusätzlich
    einen Zahlen-Badge anzeigen.
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

        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )

        self.setIconSize(
            QSize(
                24,
                24,
            )
        )

        self.setMinimumSize(
            92,
            68,
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
            20,
        )

        self.badge.hide()

    def set_badge_count(
        self,
        count: int,
    ) -> None:
        count = max(
            0,
            int(
                count
            ),
        )

        if count <= 0:
            self.badge.hide()

            return

        self.badge.setText(
            (
                "99+"
                if count > 99
                else str(count)
            )
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
            self.width() - 27,
            3,
        )


# ============================================================
# Main Window UI
# ============================================================

class MainWindowUI(
    QWidget
):
    """
    Reine Hauptfenster-Oberfläche.

    Keine Game-, Import-, Download- oder
    Mod-Logik gehört hier hinein.
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

    def __init__(
        self,
        *,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
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

        self.game_button_group = (
            QButtonGroup(
                self
            )
        )

        self.game_button_group.setExclusive(
            True
        )

        self.navigation_button_group = (
            QButtonGroup(
                self
            )
        )

        self.navigation_button_group.setExclusive(
            True
        )

        self.page_stack = (
            QStackedWidget(
                self
            )
        )

        self.game_name_label = QLabel()

        self.importer_label = QLabel()

        self.sidebar_title = QLabel()

        self.sidebar_subtitle = QLabel()

        self.games_title = QLabel()

        self.version_label = QLabel()

        self.settings_button = (
            QToolButton()
        )

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
    # Main layout
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        root_layout = (
            QHBoxLayout(
                self
            )
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
    # Game Sidebar
    # ========================================================

    def _create_game_sidebar(
        self,
    ) -> QWidget:
        sidebar = QFrame()

        sidebar.setObjectName(
            "gameSidebar"
        )

        sidebar.setFixedWidth(
            270
        )

        layout = (
            QVBoxLayout(
                sidebar
            )
        )

        layout.setContentsMargins(
            16,
            20,
            16,
            18,
        )

        layout.setSpacing(
            10
        )

        # ----------------------------------------------------
        # App title
        # ----------------------------------------------------

        self.sidebar_title.setObjectName(
            "sidebarAppTitle"
        )

        self.sidebar_subtitle.setObjectName(
            "sidebarAppSubtitle"
        )

        layout.addWidget(
            self.sidebar_title
        )

        layout.addWidget(
            self.sidebar_subtitle
        )

        layout.addSpacing(
            12
        )

        # ----------------------------------------------------
        # Games
        # ----------------------------------------------------

        self.games_title.setObjectName(
            "sidebarSectionTitle"
        )

        layout.addWidget(
            self.games_title
        )

        for game in all_games():
            game_id = (
                stable_game_id(
                    game
                )
            )

            button = (
                GameSidebarButton(
                    game=game,
                    parent=sidebar,
                )
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
                button
            )

        layout.addStretch(
            1
        )

        self.version_label.setObjectName(
            "sidebarVersion"
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
        workspace = QWidget()

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
    # Top bar
    # ========================================================

    def _create_top_bar(
        self,
    ) -> QWidget:
        top_bar = QFrame()

        top_bar.setObjectName(
            "topBar"
        )

        layout = QHBoxLayout(
            top_bar
        )

        layout.setContentsMargins(
            22,
            8,
            16,
            8,
        )

        layout.setSpacing(
            4
        )

        # ----------------------------------------------------
        # Current game
        # ----------------------------------------------------

        game_info_layout = (
            QVBoxLayout()
        )

        game_info_layout.setSpacing(
            0
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

        layout.addLayout(
            game_info_layout
        )

        layout.addSpacing(
            30
        )

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------

        navigation_definitions = (
            (
                self.PAGE_LIBRARY,
                QStyle.StandardPixmap.SP_DirHomeIcon,
            ),
            (
                self.PAGE_GAMEBANANA,
                QStyle.StandardPixmap.SP_DriveNetIcon,
            ),
            (
                self.PAGE_PROFILES,
                QStyle.StandardPixmap.SP_FileDialogInfoView,
            ),
            (
                self.PAGE_CONFLICTS,
                QStyle.StandardPixmap.SP_MessageBoxWarning,
            ),
        )

        for (
            page_id,
            standard_icon,
        ) in navigation_definitions:
            button = (
                TopNavigationButton(
                    page_id=page_id,
                    parent=top_bar,
                )
            )

            button.setIcon(
                self.style()
                .standardIcon(
                    standard_icon
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

            layout.addWidget(
                button
            )

        layout.addStretch(
            1
        )

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        self.settings_button.setObjectName(
            "settingsTopButton"
        )

        self.settings_button.setIcon(
            self.style()
            .standardIcon(
                QStyle.StandardPixmap.SP_FileDialogDetailedView
            )
        )

        self.settings_button.setIconSize(
            QSize(
                26,
                26,
            )
        )

        self.settings_button.setFixedSize(
            48,
            48,
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
        button = (
            self.game_buttons.get(
                game_id
            )
        )

        if button is not None:
            button.setChecked(
                True
            )

            game = button.game

            self.game_name_label.setText(
                game.name
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
        button = (
            self.navigation_buttons.get(
                page_id
            )
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
        button = (
            self.navigation_buttons.get(
                self.PAGE_CONFLICTS
            )
        )

        if button is not None:
            button.set_badge_count(
                count
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

        self.sidebar_subtitle.setText(
            "Mod Manager"
        )

        self.games_title.setText(
            tr(
                "ui.games.title"
            )
        )

        self.version_label.setText(
            APP_VERSION_DISPLAY
        )

        labels = {
            self.PAGE_LIBRARY: (
                tr(
                    "navigation.library"
                )
            ),
            self.PAGE_GAMEBANANA: (
                tr(
                    "navigation.gamebanana"
                )
            ),
            self.PAGE_PROFILES: (
                tr(
                    "navigation.profiles"
                )
            ),
            self.PAGE_CONFLICTS: (
                tr(
                    "navigation.conflicts"
                )
            ),
        }

        for (
            page_id,
            text,
        ) in labels.items():
            button = (
                self.navigation_buttons.get(
                    page_id
                )
            )

            if button is not None:
                button.setText(
                    text
                )

        self.settings_button.setToolTip(
            tr(
                "navigation.settings"
            )
        )

    # ========================================================
    # Styles
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        self.setStyleSheet(
            """
            QWidget#mainWorkspace {
                background: #12151b;
            }

            QFrame#gameSidebar {
                background: #191d25;
                border-right: 1px solid #2b303b;
            }

            QLabel#sidebarAppTitle {
                color: #ffffff;
                font-size: 25px;
                font-weight: 800;
            }

            QLabel#sidebarAppSubtitle {
                color: #89909f;
                font-size: 13px;
            }

            QLabel#sidebarSectionTitle {
                color: #737b8b;
                font-size: 11px;
                font-weight: 700;
                padding-left: 5px;
            }

            QLabel#sidebarVersion {
                color: #626a78;
                font-size: 11px;
            }

            QToolButton#gameSidebarButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 10px;
                color: #c9ced8;
                padding: 8px 10px;
                text-align: left;
            }

            QToolButton#gameSidebarButton:hover {
                background: #222833;
                border-color: #303744;
            }

            QToolButton#gameSidebarButton:checked {
                background: #29243f;
                border: 1px solid #7967e8;
                color: #ffffff;
                font-weight: 600;
            }

            QFrame#topBar {
                background: #191d25;
                border-bottom: 1px solid #2b303b;
                min-height: 82px;
                max-height: 82px;
            }

            QLabel#currentGameName {
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }

            QLabel#currentImporter {
                color: #8d95a5;
                font-size: 12px;
            }

            QToolButton#topNavigationButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #949cab;
                padding: 5px 10px;
            }

            QToolButton#topNavigationButton:hover {
                background: #232933;
                color: #ffffff;
            }

            QToolButton#topNavigationButton:checked {
                background: #2a2542;
                color: #ffffff;
                border-bottom: 2px solid #806bff;
            }

            QLabel#navigationBadge {
                background: #e74b5e;
                color: #ffffff;
                border-radius: 9px;
                font-size: 10px;
                font-weight: 800;
                padding: 0px;
            }

            QToolButton#settingsTopButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 9px;
            }

            QToolButton#settingsTopButton:hover {
                background: #252b36;
                border-color: #353c49;
            }

            QStackedWidget {
                background: #12151b;
                border: none;
            }
            """
        )


# ============================================================
# Placeholder Page
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