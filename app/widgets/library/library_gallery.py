from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QDesktopServices,
    QMouseEvent,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import (
    isValid,
)

from app.i18n import (
    tr,
)
from app.models.mod import (
    ModInfo,
)
from app.services.mod_manager import (
    ModState,
)
from app.services.mod_metadata import (
    load_mod_metadata,
)
from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)
from app.workers.library_preview_worker import (
    LibraryPreviewWorker,
)


StateProvider = Callable[
    [Path],
    ModState,
]


# ============================================================
# Gallery layout
# ============================================================
#
# Ziel:
# - kompakter als die alte 390px / 330px Gallery
# - mehr Karten gleichzeitig auf 1080p und 1440p
# - Preview bleibt groß genug, um Mods visuell zu erkennen
# - Open Folder und GameBanana funktionieren direkt in der Gallery
# - Mod-Info wird über info_requested an LibraryPage weitergereicht
# ============================================================

CARD_TARGET_WIDTH = 320
CARD_MINIMUM_WIDTH = 275
CARD_MAXIMUM_WIDTH = 350

CARD_HEIGHT = 300

PREVIEW_MINIMUM_HEIGHT = 165
PREVIEW_MAXIMUM_HEIGHT = 185


# ============================================================
# Preview
# ============================================================

class LibraryCardPreview(
    QFrame
):
    """
    Preview innerhalb einer Gallery-Card.

    Reihenfolge:
    1. lokale Preview
    2. GameBanana Preview
    3. Platzhalter

    Die Preview-Worker laufen asynchron. Ergebnisse von alten
    Requests werden über einen Token ignoriert.
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "libraryCardPreview"
        )

        self._disposed = False
        self._request_token = 0

        self._workers: set[
            LibraryPreviewWorker
        ] = set()

        self._local_pixmap: (
            QPixmap
            | None
        ) = None

        # ----------------------------------------------------
        # Widgets
        # ----------------------------------------------------

        self.stack = QStackedWidget(
            self
        )

        self.empty_label = QLabel(
            self
        )

        self.local_label = QLabel(
            self
        )

        self.remote_label = (
            GameBananaPreviewImage(
                parent=self,
                minimum_height=(
                    PREVIEW_MINIMUM_HEIGHT
                ),
            )
        )

        self._build_ui()
        self.clear_preview()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        self.setMinimumHeight(
            PREVIEW_MINIMUM_HEIGHT
        )

        self.setMaximumHeight(
            PREVIEW_MAXIMUM_HEIGHT
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

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

        # ----------------------------------------------------
        # Empty / loading
        # ----------------------------------------------------

        self.empty_label.setObjectName(
            "libraryCardPreviewEmpty"
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setWordWrap(
            True
        )

        # ----------------------------------------------------
        # Local preview
        # ----------------------------------------------------

        self.local_label.setObjectName(
            "libraryCardPreviewLocal"
        )

        self.local_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.local_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # ----------------------------------------------------
        # Remote preview
        # ----------------------------------------------------

        self.remote_label.setObjectName(
            "libraryCardPreviewRemote"
        )

        # ----------------------------------------------------
        # Stack
        # ----------------------------------------------------

        self.stack.addWidget(
            self.empty_label
        )

        self.stack.addWidget(
            self.local_label
        )

        self.stack.addWidget(
            self.remote_label
        )

        layout.addWidget(
            self.stack
        )

    # ========================================================
    # Mod laden
    # ========================================================

    def load_mod(
        self,
        mod: ModInfo,
    ) -> None:
        if (
            self._disposed
            or not isValid(
                self
            )
        ):
            return

        self._request_token += 1
        token = self._request_token

        self._local_pixmap = None

        if isValid(
            self.local_label
        ):
            self.local_label.clear()

        if isValid(
            self.remote_label
        ):
            self.remote_label.set_preview_url(
                None
            )

        self.empty_label.setText(
            tr(
                "library.preview.loading"
            )
        )

        self.stack.setCurrentWidget(
            self.empty_label
        )

        worker = (
            LibraryPreviewWorker(
                mod_path=mod.path
            )
        )

        self._workers.add(
            worker
        )

        worker.signals.finished.connect(
            lambda _path,
            result,
            current_worker=worker,
            current_token=token:
            self._on_loaded(
                result=result,
                worker=current_worker,
                token=current_token,
            )
        )

        worker.signals.failed.connect(
            lambda _path,
            _message,
            current_worker=worker,
            current_token=token:
            self._on_failed(
                worker=current_worker,
                token=current_token,
            )
        )

        QThreadPool.globalInstance().start(
            worker
        )

    # ========================================================
    # Worker
    # ========================================================

    def _on_loaded(
        self,
        *,
        result,
        worker: LibraryPreviewWorker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            self._disposed
            or not isValid(
                self
            )
        ):
            return

        if (
            token
            != self._request_token
        ):
            return

        # ----------------------------------------------------
        # 1. lokale Preview
        # ----------------------------------------------------

        if result.local_images:
            local_path = (
                result.local_images[
                    0
                ]
            )

            pixmap = QPixmap(
                str(
                    local_path
                )
            )

            if not pixmap.isNull():
                self._local_pixmap = (
                    pixmap
                )

                if isValid(
                    self.local_label
                ):
                    self.stack.setCurrentWidget(
                        self.local_label
                    )

                    self._refresh_local_pixmap()
                    return

        # ----------------------------------------------------
        # 2. GameBanana Preview
        # ----------------------------------------------------

        if result.remote_images:
            if isValid(
                self.remote_label
            ):
                self.remote_label.set_preview_url(
                    result.remote_images[
                        0
                    ]
                )

                self.stack.setCurrentWidget(
                    self.remote_label
                )

                return

        # ----------------------------------------------------
        # 3. keine Preview
        # ----------------------------------------------------

        self._show_empty()

    def _on_failed(
        self,
        *,
        worker: LibraryPreviewWorker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            self._disposed
            or not isValid(
                self
            )
        ):
            return

        if (
            token
            != self._request_token
        ):
            return

        self._show_empty()

    # ========================================================
    # Empty
    # ========================================================

    def _show_empty(
        self,
    ) -> None:
        if (
            self._disposed
            or not isValid(
                self
            )
        ):
            return

        self._local_pixmap = None

        if isValid(
            self.local_label
        ):
            self.local_label.clear()

        if isValid(
            self.remote_label
        ):
            self.remote_label.set_preview_url(
                None
            )

        if isValid(
            self.empty_label
        ):
            self.empty_label.setText(
                tr(
                    "library.preview.none"
                )
            )

            self.stack.setCurrentWidget(
                self.empty_label
            )

    def clear_preview(
        self,
    ) -> None:
        if self._disposed:
            return

        self._request_token += 1
        self._local_pixmap = None

        if isValid(
            self.local_label
        ):
            self.local_label.clear()

        if isValid(
            self.remote_label
        ):
            self.remote_label.set_preview_url(
                None
            )

        if isValid(
            self.empty_label
        ):
            self.empty_label.setText(
                tr(
                    "library.preview.none"
                )
            )

            self.stack.setCurrentWidget(
                self.empty_label
            )

    # ========================================================
    # Local image scaling
    # ========================================================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._refresh_local_pixmap()

    def _refresh_local_pixmap(
        self,
    ) -> None:
        """
        Die lokale Preview wird wie ein modernes Cover-Bild behandelt:
        Sie füllt den verfügbaren Bereich aus und wird mittig beschnitten,
        statt große leere Balken zu erzeugen.
        """

        if (
            self._disposed
            or not isValid(
                self
            )
            or not isValid(
                self.local_label
            )
        ):
            return

        pixmap = (
            self._local_pixmap
        )

        if (
            pixmap is None
            or pixmap.isNull()
        ):
            return

        target = (
            self.local_label
            .contentsRect()
            .size()
        )

        if (
            target.width() <= 0
            or target.height() <= 0
        ):
            return

        scaled = pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(
            0,
            (
                scaled.width()
                - target.width()
            )
            // 2,
        )

        y = max(
            0,
            (
                scaled.height()
                - target.height()
            )
            // 2,
        )

        cropped = scaled.copy(
            x,
            y,
            min(
                target.width(),
                scaled.width(),
            ),
            min(
                target.height(),
                scaled.height(),
            ),
        )

        self.local_label.setPixmap(
            cropped
        )

    # ========================================================
    # Lifecycle
    # ========================================================

    def dispose(
        self,
    ) -> None:
        if self._disposed:
            return

        self._disposed = True
        self._request_token += 1

        # ----------------------------------------------------
        # Preview Worker trennen
        # ----------------------------------------------------

        for worker in tuple(
            self._workers
        ):
            try:
                worker.signals.finished.disconnect()

            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                worker.signals.failed.disconnect()

            except (
                RuntimeError,
                TypeError,
            ):
                pass

        self._workers.clear()

        # ----------------------------------------------------
        # Remote Preview trennen
        # ----------------------------------------------------

        if hasattr(
            self,
            "remote_label",
        ):
            remote_label = (
                self.remote_label
            )

            if isValid(
                remote_label
            ):
                dispose_remote = getattr(
                    remote_label,
                    "dispose",
                    None,
                )

                if callable(
                    dispose_remote
                ):
                    dispose_remote()

        self._local_pixmap = None


# ============================================================
# Mod Card
# ============================================================

class LibraryModCard(
    QFrame
):
    toggle_requested = Signal(
        object
    )

    info_requested = Signal(
        object
    )

    selected_requested = Signal(
        object
    )

    def __init__(
        self,
        *,
        mod: ModInfo,
        state: ModState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.mod = mod
        self.state = state

        metadata = load_mod_metadata(
            self.mod.path
        )

        self._gamebanana_mod_id = (
            metadata.gamebanana_mod_id
        )

        self._operation_running = (
            False
        )

        self.setObjectName(
            "libraryModCard"
        )

        self.setMinimumWidth(
            CARD_MINIMUM_WIDTH
        )

        self.setMaximumWidth(
            CARD_MAXIMUM_WIDTH
        )

        self.setFixedHeight(
            CARD_HEIGHT
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # ----------------------------------------------------
        # Preview
        # ----------------------------------------------------

        self.preview = (
            LibraryCardPreview(
                parent=self
            )
        )

        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        self.name_label = QLabel(
            self
        )

        self.name_label.setObjectName(
            "libraryCardTitle"
        )

        self.name_label.setWordWrap(
            False
        )

        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        self.meta_label = QLabel(
            self
        )

        self.meta_label.setObjectName(
            "libraryCardMeta"
        )

        self.meta_label.setWordWrap(
            False
        )

        self.status_label = QLabel(
            self
        )

        self.status_label.setObjectName(
            "libraryCardState"
        )

        # ----------------------------------------------------
        # More menu
        # ----------------------------------------------------

        self.more_button = QToolButton(
            self
        )

        self.more_button.setObjectName(
            "libraryCardMoreButton"
        )

        self.more_button.setText(
            "⋯"
        )

        self.more_button.setFixedSize(
            30,
            30,
        )

        self.more_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        self.more_menu = QMenu(
            self.more_button
        )

        self.more_menu.setObjectName(
            "libraryCardMenu"
        )

        self.open_folder_action = (
            self.more_menu.addAction(
                tr(
                    "conflicts.action.open"
                )
            )
        )

        self.info_action = (
            self.more_menu.addAction(
                tr(
                    "library.details.action.info"
                )
            )
        )

        self.more_menu.addSeparator()

        self.gamebanana_action = (
            self.more_menu.addAction(
                tr(
                    "gamebanana.open_page"
                )
            )
        )

        self.gamebanana_action.setVisible(
            self._gamebanana_mod_id
            is not None
        )

        self.more_button.setMenu(
            self.more_menu
        )

        # ----------------------------------------------------
        # Action
        # ----------------------------------------------------

        self.toggle_button = QPushButton(
            self
        )

        self.toggle_button.setObjectName(
            "libraryCardAction"
        )

        self.toggle_button.setMinimumWidth(
            100
        )

        self.toggle_button.setMaximumWidth(
            122
        )

        self._build_ui()
        self._refresh_mod_text()

        self.set_state(
            state
        )

        self.preview.load_mod(
            self.mod
        )

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            9,
            9,
            9,
            10,
        )

        layout.setSpacing(
            7
        )

        # ====================================================
        # Preview
        # ====================================================

        layout.addWidget(
            self.preview
        )

        # ====================================================
        # Title row
        # ====================================================

        title_row = QHBoxLayout()

        title_row.setContentsMargins(
            3,
            0,
            0,
            0,
        )

        title_row.setSpacing(
            6
        )

        title_row.addWidget(
            self.name_label,
            stretch=1,
        )

        title_row.addWidget(
            self.more_button,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        layout.addLayout(
            title_row
        )

        # ====================================================
        # Meta
        # ====================================================

        meta_layout = QHBoxLayout()

        meta_layout.setContentsMargins(
            3,
            0,
            3,
            0,
        )

        meta_layout.setSpacing(
            0
        )

        meta_layout.addWidget(
            self.meta_label,
            stretch=1,
        )

        layout.addLayout(
            meta_layout
        )

        # ====================================================
        # Footer
        # ====================================================

        footer = QHBoxLayout()

        footer.setContentsMargins(
            3,
            0,
            3,
            0,
        )

        footer.setSpacing(
            8
        )

        footer.addWidget(
            self.status_label,
            stretch=1,
            alignment=(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        footer.addWidget(
            self.toggle_button,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        layout.addLayout(
            footer
        )

        # ====================================================
        # Signals
        # ====================================================

        self.toggle_button.clicked.connect(
            self._emit_toggle
        )

        self.open_folder_action.triggered.connect(
            self._open_mod_folder
        )

        self.info_action.triggered.connect(
            self._emit_info
        )

        self.gamebanana_action.triggered.connect(
            self._open_gamebanana
        )

    # ========================================================
    # Text
    # ========================================================

    def _refresh_mod_text(
        self,
    ) -> None:
        self.name_label.setText(
            self.mod.name
        )

        self.name_label.setToolTip(
            self.mod.name
        )

        parts: list[
            str
        ] = []

        if self.mod.characters:
            parts.append(
                ", ".join(
                    self.mod.characters
                )
            )

        if self.mod.mod_type:
            parts.append(
                self.mod.mod_type
            )

        meta_text = (
            " • ".join(
                parts
            )
            if parts
            else tr(
                "common.unknown"
            )
        )

        self.meta_label.setText(
            meta_text
        )

        self.meta_label.setToolTip(
            meta_text
        )

    # ========================================================
    # State
    # ========================================================

    def set_state(
        self,
        state: ModState,
    ) -> None:
        self.state = state

        state_key = {
            ModState.ENABLED: (
                "mod.state.enabled"
            ),
            ModState.DISABLED: (
                "mod.state.disabled"
            ),
            ModState.CONFLICT: (
                "mod.state.conflict"
            ),
            ModState.BROKEN: (
                "mod.state.broken"
            ),
            ModState.NOT_CONFIGURED: (
                "mod.state.not_configured"
            ),
        }.get(
            state
        )

        if state_key:
            state_text = tr(
                state_key
            )
        else:
            state_text = (
                state.value
            )

        self.status_label.setText(
            state_text
        )

        self.status_label.setProperty(
            "modState",
            state.value,
        )

        # ----------------------------------------------------
        # Button
        # ----------------------------------------------------

        if state == ModState.DISABLED:
            self.toggle_button.setText(
                tr(
                    "library.details.action.enable"
                )
            )

            action_available = True

        elif state == ModState.ENABLED:
            self.toggle_button.setText(
                tr(
                    "library.details.action.disable"
                )
            )

            action_available = True

        elif state == ModState.BROKEN:
            self.toggle_button.setText(
                tr(
                    "library.details.action.remove_broken"
                )
            )

            action_available = True

        elif state == ModState.CONFLICT:
            self.toggle_button.setText(
                tr(
                    "library.details.action.conflict"
                )
            )

            action_available = False

        elif (
            state
            == ModState.NOT_CONFIGURED
        ):
            self.toggle_button.setText(
                tr(
                    "library.details.action.not_configured"
                )
            )

            action_available = False

        else:
            self.toggle_button.setText(
                tr(
                    "library.details.action.unavailable"
                )
            )

            action_available = False

        self.toggle_button.setEnabled(
            action_available
            and not self._operation_running
        )

        # ----------------------------------------------------
        # Card state for QSS
        # ----------------------------------------------------

        self.setProperty(
            "modState",
            state.value,
        )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

        self.status_label.style().unpolish(
            self.status_label
        )

        self.status_label.style().polish(
            self.status_label
        )

    def set_operation_running(
        self,
        running: bool,
    ) -> None:
        self._operation_running = bool(
            running
        )

        self.set_state(
            self.state
        )

    # ========================================================
    # Selection
    # ========================================================

    def set_selected(
        self,
        selected: bool,
    ) -> None:
        self.setProperty(
            "selected",
            bool(
                selected
            ),
        )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.selected_requested.emit(
                self.mod
            )

        super().mousePressEvent(
            event
        )

    # ========================================================
    # Actions
    # ========================================================

    def _emit_toggle(
        self,
    ) -> None:
        self.toggle_requested.emit(
            self.mod
        )

    def _emit_info(
        self,
    ) -> None:
        self.info_requested.emit(
            self.mod
        )

    def _open_mod_folder(
        self,
    ) -> None:
        path = (
            Path(
                self.mod.path
            )
            .expanduser()
            .absolute()
        )

        if not path.is_dir():
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(
                    path
                )
            )
        )

    def _open_gamebanana(
        self,
    ) -> None:
        mod_id = (
            self._gamebanana_mod_id
        )

        if mod_id is None:
            return

        QDesktopServices.openUrl(
            QUrl(
                (
                    "https://gamebanana.com/mods/"
                    f"{mod_id}"
                )
            )
        )

    # ========================================================
    # Lifecycle
    # ========================================================

    def dispose(
        self,
    ) -> None:
        dispose_preview = getattr(
            self.preview,
            "dispose",
            None,
        )

        if callable(
            dispose_preview
        ):
            dispose_preview()

        try:
            self.toggle_button.clicked.disconnect()

        except (
            RuntimeError,
            TypeError,
        ):
            pass

        for action in (
            self.open_folder_action,
            self.info_action,
            self.gamebanana_action,
        ):
            try:
                action.triggered.disconnect()

            except (
                RuntimeError,
                TypeError,
            ):
                pass


# ============================================================
# Gallery
# ============================================================

class LibraryGalleryWidget(
    QWidget
):
    toggle_requested = Signal(
        object
    )

    info_requested = Signal(
        object
    )

    # Wird ausgelöst, wenn der Benutzer
    # eine Gallery-Card auswählt.
    selection_changed = Signal(
        object
    )

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "libraryGallery"
        )

        # ----------------------------------------------------
        # Data
        # ----------------------------------------------------

        self._cards: list[
            LibraryModCard
        ] = []

        self._card_by_path: dict[
            str,
            LibraryModCard,
        ] = {}

        self._search_term = ""
        self._character = None
        self._mod_type = None
        self._status = None

        self._operation_running = (
            False
        )

        self._current_columns = 0

        self._selected_card: (
            LibraryModCard
            | None
        ) = None

        # ----------------------------------------------------
        # Scroll
        # ----------------------------------------------------

        self.scroll_area = QScrollArea(
            self
        )

        self.scroll_area.setObjectName(
            "libraryGalleryScroll"
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

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # ----------------------------------------------------
        # Content
        # ----------------------------------------------------

        self.content = QWidget()

        self.content.setObjectName(
            "libraryGalleryContent"
        )

        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        # ----------------------------------------------------
        # Grid
        # ----------------------------------------------------

        self.grid = QGridLayout(
            self.content
        )

        self.grid.setContentsMargins(
            16,
            16,
            16,
            18,
        )

        self.grid.setHorizontalSpacing(
            14
        )

        self.grid.setVerticalSpacing(
            14
        )

        self.grid.setSizeConstraint(
            QLayout.SizeConstraint.SetMinAndMaxSize
        )

        self.grid.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.scroll_area.setWidget(
            self.content
        )

        # ----------------------------------------------------
        # Empty
        # ----------------------------------------------------

        self.empty_label = QLabel(
            self
        )

        self.empty_label.setObjectName(
            "libraryGalleryEmpty"
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setWordWrap(
            True
        )

        self.empty_label.hide()

        self._build_ui()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
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

        layout.addWidget(
            self.empty_label,
            stretch=1,
        )

        layout.addWidget(
            self.scroll_area,
            stretch=1,
        )

    # ========================================================
    # Mods
    # ========================================================

    def set_mods(
        self,
        *,
        mods: (
            list[
                ModInfo
            ]
            | tuple[
                ModInfo,
                ...,
            ]
        ),
        state_provider: StateProvider,
    ) -> None:
        self.clear()

        for mod in mods:
            state = state_provider(
                mod.path
            )

            card = LibraryModCard(
                mod=mod,
                state=state,
                parent=self.content,
            )

            card.set_operation_running(
                self._operation_running
            )

            card.toggle_requested.connect(
                self.toggle_requested
            )

            card.info_requested.connect(
                self.info_requested
            )

            card.selected_requested.connect(
                self._select_mod
            )

            self._cards.append(
                card
            )

            self._card_by_path[
                self._path_key(
                    mod.path
                )
            ] = card

        self._apply_current_filters()

        # QScrollArea kennt seine endgültige Breite häufig erst
        # einen Event-Loop später.
        QTimer.singleShot(
            0,
            self._reflow_visible_cards,
        )

    # ========================================================
    # Clear
    # ========================================================

    def clear(
        self,
    ) -> None:
        cards = tuple(
            self._cards
        )

        had_selection = (
            self._selected_card
            is not None
        )

        self._cards.clear()
        self._card_by_path.clear()

        self._selected_card = None

        if had_selection:
            self.selection_changed.emit(
                None
            )

        for card in cards:
            self.grid.removeWidget(
                card
            )

            try:
                card.toggle_requested.disconnect(
                    self.toggle_requested
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                card.info_requested.disconnect(
                    self.info_requested
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                card.selected_requested.disconnect(
                    self._select_mod
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            card.dispose()
            card.deleteLater()

        self._current_columns = 0

        self.empty_label.setText(
            tr(
                "library.gallery.empty"
            )
        )

        self.empty_label.show()
        self.scroll_area.hide()

    # ========================================================
    # Filter
    # ========================================================

    def apply_filters(
        self,
        *,
        search_term: str = "",
        character=None,
        mod_type=None,
        status=None,
    ) -> int:
        self._search_term = (
            search_term
            .strip()
            .casefold()
        )

        self._character = (
            character
        )

        self._mod_type = (
            mod_type
        )

        self._status = (
            status
        )

        return self._apply_current_filters()

    def _apply_current_filters(
        self,
    ) -> int:
        visible_cards: list[
            LibraryModCard
        ] = []

        for card in self._cards:
            mod = card.mod

            # ------------------------------------------------
            # Character
            # ------------------------------------------------

            if self._character is None:
                character_matches = True

            elif (
                self._character
                == "__unknown__"
            ):
                character_matches = (
                    not mod.characters
                )

            else:
                character_matches = any(
                    value.casefold()
                    == str(
                        self._character
                    ).casefold()
                    for value
                    in mod.characters
                )

            # ------------------------------------------------
            # Mod type
            # ------------------------------------------------

            type_matches = (
                self._mod_type is None
                or (
                    mod.mod_type
                    or ""
                ).casefold()
                == str(
                    self._mod_type
                ).casefold()
            )

            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            status_matches = (
                self._status is None
                or card.state.value
                == self._status
            )

            # ------------------------------------------------
            # Search
            # ------------------------------------------------

            searchable = " ".join(
                (
                    mod.name,
                    " ".join(
                        mod.characters
                    ),
                    mod.mod_type
                    or "",
                    mod.relative_path
                    or "",
                    str(
                        mod.path
                    ),
                )
            ).casefold()

            search_matches = (
                not self._search_term
                or self._search_term
                in searchable
            )

            visible = (
                character_matches
                and type_matches
                and status_matches
                and search_matches
            )

            card.setVisible(
                visible
            )

            if visible:
                visible_cards.append(
                    card
                )

        self._reflow(
            visible_cards,
            force=True,
        )

        has_cards = bool(
            visible_cards
        )

        self.scroll_area.setVisible(
            has_cards
        )

        self.empty_label.setVisible(
            not has_cards
        )

        if not has_cards:
            self.empty_label.setText(
                tr(
                    "library.gallery.empty"
                )
            )

        return len(
            visible_cards
        )

    # ========================================================
    # Selection
    # ========================================================

    def _select_mod(
        self,
        mod: ModInfo,
    ) -> None:
        card = self._card_by_path.get(
            self._path_key(
                mod.path
            )
        )

        if card is None:
            return

        previous = (
            self._selected_card
        )

        if (
            previous is not None
            and previous is not card
        ):
            previous.set_selected(
                False
            )

        self._selected_card = card

        card.set_selected(
            True
        )

        # Auswahl an LibraryPage melden.
        self.selection_changed.emit(
            mod
        )
        
    def selected_mod(
        self,
    ) -> ModInfo | None:
        """
        Liefert den aktuell in der Gallery
        ausgewählten Mod.
        """

        card = (
            self._selected_card
        )

        if card is None:
            return None

        return card.mod
        
    # ========================================================
    # State
    # ========================================================

    def update_mod_state(
        self,
        *,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        card = self._card_by_path.get(
            self._path_key(
                mod.path
            )
        )

        if card is None:
            return

        card.set_state(
            state
        )

        self._apply_current_filters()

    # ========================================================
    # Operation
    # ========================================================

    def set_operation_running(
        self,
        running: bool,
    ) -> None:
        self._operation_running = bool(
            running
        )

        for card in self._cards:
            card.set_operation_running(
                self._operation_running
            )

    # ========================================================
    # Responsive layout
    # ========================================================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self._reflow_visible_cards()

    def _reflow_visible_cards(
        self,
    ) -> None:
        visible_cards = [
            card
            for card
            in self._cards
            if not card.isHidden()
        ]

        self._reflow(
            visible_cards
        )

    def _reflow(
        self,
        cards: list[
            LibraryModCard
        ],
        *,
        force: bool = False,
    ) -> None:
        # Alte Positionen zuerst entfernen, damit auch ein Filter,
        # der 0 Treffer liefert, keine unsichtbaren Layout-Reste
        # zurücklässt.
        for card in self._cards:
            self.grid.removeWidget(
                card
            )

        if not cards:
            self._current_columns = 0
            self.content.adjustSize()
            return

        available_width = max(
            CARD_MINIMUM_WIDTH,
            (
                self.scroll_area
                .viewport()
                .width()
                - 32
            ),
        )

        columns = max(
            1,
            available_width
            // CARD_TARGET_WIDTH,
        )

        # Durch MaxWidth niemals so viele Spalten anlegen, dass
        # die Cards schmaler als CARD_MINIMUM_WIDTH würden.
        while (
            columns > 1
            and (
                available_width
                // columns
            )
            < CARD_MINIMUM_WIDTH
        ):
            columns -= 1

        if (
            not force
            and columns
            == self._current_columns
        ):
            # Karten müssen nach removeWidget trotzdem wieder
            # eingesetzt werden.
            pass

        self._current_columns = (
            columns
        )

        for (
            index,
            card,
        ) in enumerate(
            cards
        ):
            row = (
                index
                // columns
            )

            column = (
                index
                % columns
            )

            self.grid.addWidget(
                card,
                row,
                column,
                alignment=(
                    Qt.AlignmentFlag.AlignTop
                    | Qt.AlignmentFlag.AlignHCenter
                ),
            )

        for column in range(
            columns
        ):
            self.grid.setColumnStretch(
                column,
                1,
            )

        self.content.adjustSize()

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _path_key(
        path: Path,
    ) -> str:
        return str(
            Path(
                path
            )
            .expanduser()
            .absolute()
        )


__all__ = [
    "LibraryGalleryWidget",
    "LibraryModCard",
    "LibraryCardPreview",
]
