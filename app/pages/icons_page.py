from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app.games.registry import all_games
from app.i18n import (
    tr,
    translation_manager,
)
from app.dialogs.icon_editor_dialog import (
    IconEditorDialog,
)
from app.services.component_resources import (
    resolve_component_path,
)
from app.services.icon_manager import (
    IconManagerError,
    custom_icon_source_path,
    SUPPORTED_ICON_SUFFIXES,
    ensure_custom_icon_directory,
    install_custom_icon_data,
    is_custom_icon,
    reset_all_custom_icons,
    reset_custom_icon,
    store_custom_icon_source,
    resolve_application_icon_path,
    resolve_game_icon_path,
    resolve_navigation_icon_path,
)


PathProvider = Callable[[], Path | None]


NAVIGATION_SLOTS = (
    "library",
    "gamebanana",
    "profiles",
    "conflicts",
    "icons",
    "settings",
)

NAVIGATION_FALLBACKS = {
    "library": QStyle.StandardPixmap.SP_DirHomeIcon,
    "gamebanana": QStyle.StandardPixmap.SP_DriveNetIcon,
    "profiles": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "conflicts": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "icons": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
}


def _stable_game_id(
    game,
) -> str:
    value = getattr(
        game,
        "game_id",
        None,
    )

    if value:
        return str(value)

    value = getattr(
        game,
        "id",
        None,
    )

    if hasattr(
        value,
        "value",
    ):
        return str(value.value)

    return str(value)


class IconCard(
    QFrame
):
    changed = Signal()

    def __init__(
        self,
        *,
        category: str,
        key: str,
        title_provider: Callable[[], str],
        path_provider: PathProvider,
        fallback_icon_provider: Callable[[], QIcon] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.category = category
        self.key = key
        self.title_provider = title_provider
        self.path_provider = path_provider
        self.fallback_icon_provider = fallback_icon_provider

        self.setObjectName(
            "iconManagerCard"
        )
        self.setFixedWidth(
            250
        )
        self.setMinimumHeight(
            226
        )

        self.preview_label = QLabel(
            self
        )
        self.preview_label.setObjectName(
            "iconManagerPreview"
        )
        self.preview_label.setFixedSize(
            72,
            72,
        )
        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label = QLabel(
            self
        )
        self.title_label.setObjectName(
            "iconManagerCardTitle"
        )
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.title_label.setWordWrap(
            True
        )

        self.status_label = QLabel(
            self
        )
        self.status_label.setObjectName(
            "iconManagerCardStatus"
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.change_button = QPushButton(
            self
        )
        self.change_button.setObjectName(
            "iconManagerPrimaryButton"
        )

        self.adjust_button = QPushButton(
            self
        )
        self.adjust_button.setObjectName(
            "iconManagerSecondaryButton"
        )

        self.reset_button = QPushButton(
            self
        )
        self.reset_button.setObjectName(
            "iconManagerSecondaryButton"
        )

        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self.refresh()

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        layout.setSpacing(
            8
        )

        layout.addWidget(
            self.preview_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(
            self.title_label
        )
        layout.addWidget(
            self.status_label
        )
        layout.addStretch(
            1
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(
            7
        )
        buttons.addWidget(
            self.change_button,
            stretch=1,
        )
        buttons.addWidget(
            self.adjust_button,
            stretch=1,
        )

        layout.addLayout(
            buttons
        )
        layout.addWidget(
            self.reset_button
        )

    def _connect_signals(
        self,
    ) -> None:
        self.change_button.clicked.connect(
            self._choose_icon
        )
        self.adjust_button.clicked.connect(
            self._adjust_icon
        )
        self.reset_button.clicked.connect(
            self._reset_icon
        )

    def _choose_icon(
        self,
        _checked: bool = False,
    ) -> None:
        suffixes = " ".join(
            f"*{suffix}"
            for suffix in SUPPORTED_ICON_SUFFIXES
        )

        selected, _filter = QFileDialog.getOpenFileName(
            self,
            tr(
                "icons.dialog.select.title"
            ),
            "",
            tr(
                "icons.dialog.select.filter",
                patterns=suffixes,
            ),
        )

        if not selected:
            return

        self._edit_source_icon(
            Path(selected),
            remember_source=True,
        )

    def _adjust_icon(
        self,
        _checked: bool = False,
    ) -> None:
        if not is_custom_icon(
            self.category,
            self.key,
        ):
            return

        current = (
            custom_icon_source_path(
                self.category,
                self.key,
            )
            or self.path_provider()
        )
        if current is None:
            return

        self._edit_source_icon(
            current,
            remember_source=False,
        )

    def _edit_source_icon(
        self,
        source: Path,
        *,
        remember_source: bool,
    ) -> None:
        try:
            editor = IconEditorDialog(
                source_path=source,
                parent=self,
            )
        except (OSError, ValueError, RuntimeError):
            QMessageBox.warning(
                self,
                tr(
                    "icons.error.title"
                ),
                tr(
                    "icons.error.invalid_image"
                ),
            )
            return

        if editor.exec() != QDialog.DialogCode.Accepted:
            return

        png_data = editor.png_data()
        if not png_data:
            return

        try:
            if remember_source:
                store_custom_icon_source(
                    self.category,
                    self.key,
                    source,
                )

            install_custom_icon_data(
                self.category,
                self.key,
                png_data,
                suffix=".png",
            )
        except IconManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "icons.error.title"
                ),
                str(error),
            )
            return

        self.refresh()
        self.changed.emit()

    def _reset_icon(
        self,
        _checked: bool = False,
    ) -> None:
        try:
            changed = reset_custom_icon(
                self.category,
                self.key,
            )
        except IconManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "icons.error.title"
                ),
                str(error),
            )
            return

        self.refresh()

        if changed:
            self.changed.emit()

    def refresh(
        self,
    ) -> None:
        self.title_label.setText(
            self.title_provider()
        )

        path = self.path_provider()
        icon = QIcon(
            str(path)
        ) if path is not None else QIcon()

        if icon.isNull() and self.fallback_icon_provider is not None:
            icon = self.fallback_icon_provider()

        if icon.isNull():
            icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )

        pixmap = icon.pixmap(
            QSize(
                58,
                58,
            )
        )

        self.preview_label.setPixmap(
            pixmap
        )

        custom = is_custom_icon(
            self.category,
            self.key,
        )
        self.status_label.setText(
            tr(
                "icons.status.custom"
                if custom
                else "icons.status.default"
            )
        )
        self.status_label.setProperty(
            "custom",
            custom,
        )
        self.status_label.style().unpolish(
            self.status_label
        )
        self.status_label.style().polish(
            self.status_label
        )

        self.adjust_button.setEnabled(
            custom
        )
        self.reset_button.setEnabled(
            custom
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            self.title_provider()
        )
        self.change_button.setText(
            tr(
                "icons.action.change"
            )
        )
        self.adjust_button.setText(
            tr(
                "icons.action.adjust"
            )
        )
        self.reset_button.setText(
            tr(
                "icons.action.reset"
            )
        )
        self.refresh()


class IconsPage(
    QWidget
):
    icons_changed = Signal()

    CARD_WIDTH = 250
    CARD_GAP = 12

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "iconsPage"
        )

        self._cards: list[IconCard] = []
        self._current_columns = 0

        self.title_label = QLabel(
            self
        )
        self.description_label = QLabel(
            self
        )
        self.open_folder_button = QPushButton(
            self
        )
        self.reset_all_button = QPushButton(
            self
        )

        self.scroll_area = QScrollArea(
            self
        )
        self.scroll_content = QWidget()
        self.content_layout = QVBoxLayout(
            self.scroll_content
        )

        self._build_ui()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        QTimer.singleShot(
            0,
            self._reflow_all_sections,
        )

    def _build_ui(
        self,
    ) -> None:
        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            22,
            20,
            22,
            16,
        )
        root.setSpacing(
            14
        )

        header = QHBoxLayout()
        header.setSpacing(
            16
        )

        header_text = QVBoxLayout()
        header_text.setSpacing(
            3
        )

        self.title_label.setObjectName(
            "pageTitle"
        )
        self.description_label.setObjectName(
            "pageDescription"
        )
        self.description_label.setWordWrap(
            True
        )

        header_text.addWidget(
            self.title_label
        )
        header_text.addWidget(
            self.description_label
        )

        header.addLayout(
            header_text,
            stretch=1,
        )

        self.open_folder_button.setObjectName(
            "iconsHeaderSecondaryButton"
        )
        self.reset_all_button.setObjectName(
            "iconsHeaderDangerButton"
        )

        self.open_folder_button.clicked.connect(
            self._open_icon_folder
        )
        self.reset_all_button.clicked.connect(
            self._reset_all_icons
        )

        header.addWidget(
            self.open_folder_button,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        header.addWidget(
            self.reset_all_button,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        root.addLayout(
            header
        )

        self.scroll_area.setObjectName(
            "iconsScrollArea"
        )
        self.scroll_area.setWidgetResizable(
            True
        )
        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_content.setObjectName(
            "iconsScrollContent"
        )
        self.content_layout.setContentsMargins(
            0,
            0,
            4,
            0,
        )
        self.content_layout.setSpacing(
            18
        )

        self._game_section = self._create_game_section()
        self._navigation_section = self._create_navigation_section()
        self._application_section = self._create_application_section()

        self.content_layout.addWidget(
            self._game_section[0]
        )
        self.content_layout.addWidget(
            self._navigation_section[0]
        )
        self.content_layout.addWidget(
            self._application_section[0]
        )
        self.content_layout.addStretch(
            1
        )

        self.scroll_area.setWidget(
            self.scroll_content
        )
        root.addWidget(
            self.scroll_area,
            stretch=1,
        )

    def _create_section(
        self,
        title_key: str,
    ) -> tuple[QFrame, QLabel, QGridLayout]:
        frame = QFrame(
            self.scroll_content
        )
        frame.setObjectName(
            "iconsSection"
        )

        layout = QVBoxLayout(
            frame
        )
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        layout.setSpacing(
            12
        )

        title = QLabel(
            frame
        )
        title.setObjectName(
            "iconsSectionTitle"
        )
        title.setProperty(
            "translationKey",
            title_key,
        )
        layout.addWidget(
            title
        )

        cards_widget = QWidget(
            frame
        )
        cards_widget.setObjectName(
            "iconsCardsContainer"
        )
        grid = QGridLayout(
            cards_widget
        )
        grid.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        grid.setHorizontalSpacing(
            self.CARD_GAP
        )
        grid.setVerticalSpacing(
            self.CARD_GAP
        )
        grid.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(
            cards_widget
        )

        return frame, title, grid

    def _create_game_section(
        self,
    ) -> tuple[QFrame, QLabel, QGridLayout]:
        section = self._create_section(
            "icons.section.games"
        )
        grid = section[2]

        for game in all_games():
            game_id = _stable_game_id(
                game
            )

            card = IconCard(
                category="games",
                key=game_id,
                title_provider=(
                    lambda value=game: str(value.name)
                ),
                path_provider=(
                    lambda value=game_id: resolve_game_icon_path(value)
                ),
                parent=self,
            )
            card.changed.connect(
                self._on_card_changed
            )
            self._cards.append(
                card
            )
            grid.addWidget(
                card,
                0,
                len(self._cards) - 1,
            )

        return section

    def _create_navigation_section(
        self,
    ) -> tuple[QFrame, QLabel, QGridLayout]:
        section = self._create_section(
            "icons.section.navigation"
        )
        grid = section[2]

        for index, icon_id in enumerate(
            NAVIGATION_SLOTS
        ):
            fallback = NAVIGATION_FALLBACKS[
                icon_id
            ]

            card = IconCard(
                category="navigation",
                key=icon_id,
                title_provider=(
                    lambda value=icon_id: tr(
                        f"icons.navigation.{value}"
                    )
                ),
                path_provider=(
                    lambda value=icon_id: resolve_navigation_icon_path(value)
                ),
                fallback_icon_provider=(
                    lambda value=fallback: self.style().standardIcon(value)
                ),
                parent=self,
            )
            card.changed.connect(
                self._on_card_changed
            )
            self._cards.append(
                card
            )
            grid.addWidget(
                card,
                0,
                index,
            )

        return section

    def _create_application_section(
        self,
    ) -> tuple[QFrame, QLabel, QGridLayout]:
        section = self._create_section(
            "icons.section.application"
        )
        grid = section[2]

        card = IconCard(
            category="application",
            key="app",
            title_provider=(
                lambda: tr(
                    "icons.application.app"
                )
            ),
            path_provider=resolve_application_icon_path,
            fallback_icon_provider=(
                lambda: self.style().standardIcon(
                    QStyle.StandardPixmap.SP_ComputerIcon
                )
            ),
            parent=self,
        )
        card.changed.connect(
            self._on_card_changed
        )
        self._cards.append(
            card
        )
        grid.addWidget(
            card,
            0,
            0,
        )

        return section

    def _on_card_changed(
        self,
    ) -> None:
        self.icons_changed.emit()

    def _open_icon_folder(
        self,
        _checked: bool = False,
    ) -> None:
        folder = ensure_custom_icon_directory()
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(folder)
            )
        )

    def _reset_all_icons(
        self,
        _checked: bool = False,
    ) -> None:
        answer = QMessageBox.question(
            self,
            tr(
                "icons.reset_all.title"
            ),
            tr(
                "icons.reset_all.message"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            reset_all_custom_icons()
        except IconManagerError as error:
            QMessageBox.critical(
                self,
                tr(
                    "icons.error.title"
                ),
                str(error),
            )
            return

        self.refresh()
        self.icons_changed.emit()

    def refresh(
        self,
    ) -> None:
        for card in self._cards:
            card.refresh()

    def _section_grids(
        self,
    ) -> tuple[QGridLayout, ...]:
        return (
            self._game_section[2],
            self._navigation_section[2],
            self._application_section[2],
        )

    def _cards_for_grid(
        self,
        grid: QGridLayout,
    ) -> list[IconCard]:
        result: list[IconCard] = []

        for index in range(
            grid.count()
        ):
            item = grid.itemAt(
                index
            )
            widget = item.widget()
            if isinstance(
                widget,
                IconCard,
            ):
                result.append(
                    widget
                )

        return result

    def _reflow_grid(
        self,
        grid: QGridLayout,
        columns: int,
    ) -> None:
        cards = self._cards_for_grid(
            grid
        )

        for card in cards:
            grid.removeWidget(
                card
            )

        for index, card in enumerate(
            cards
        ):
            row = index // columns
            column = index % columns
            grid.addWidget(
                card,
                row,
                column,
                alignment=(
                    Qt.AlignmentFlag.AlignTop
                    | Qt.AlignmentFlag.AlignLeft
                ),
            )

    def _reflow_all_sections(
        self,
    ) -> None:
        width = max(
            self.scroll_area.viewport().width(),
            self.CARD_WIDTH,
        )
        columns = max(
            1,
            min(
                6,
                width
                // (
                    self.CARD_WIDTH
                    + self.CARD_GAP
                ),
            ),
        )

        if columns == self._current_columns:
            return

        for grid in self._section_grids():
            self._reflow_grid(
                grid,
                columns,
            )

        self._current_columns = columns

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )
        QTimer.singleShot(
            0,
            self._reflow_all_sections,
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "icons.title"
            )
        )
        self.description_label.setText(
            tr(
                "icons.description"
            )
        )
        self.open_folder_button.setText(
            tr(
                "icons.action.open_folder"
            )
        )
        self.reset_all_button.setText(
            tr(
                "icons.action.reset_all"
            )
        )

        for _frame, title, _grid in (
            self._game_section,
            self._navigation_section,
            self._application_section,
        ):
            key = title.property(
                "translationKey"
            )
            if isinstance(
                key,
                str,
            ):
                title.setText(
                    tr(key)
                )

        for card in self._cards:
            card.retranslate_ui(
                _language
            )

    def _apply_stylesheet(
        self,
    ) -> None:
        bundled_path = (
            Path(__file__).resolve().parents[1]
            / "styles"
            / "icons.qss"
        )
        style_path = resolve_component_path(
            "styles/icons.qss",
            bundled_path,
        )

        try:
            stylesheet = style_path.read_text(
                encoding="utf-8"
            )
        except OSError as error:
            raise RuntimeError(
                f"Icons stylesheet could not be loaded: {style_path}"
            ) from error

        self.setStyleSheet(
            stylesheet
        )


__all__ = [
    "IconsPage",
]
