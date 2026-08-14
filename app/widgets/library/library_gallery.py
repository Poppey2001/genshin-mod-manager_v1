from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QPixmap,
    QResizeEvent,
)

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
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


CARD_TARGET_WIDTH = 390
CARD_MINIMUM_WIDTH = 320
CARD_MAXIMUM_WIDTH = 460

CARD_HEIGHT = 330
PREVIEW_HEIGHT = 220


# ============================================================
# Preview innerhalb einer Library-Card
# ============================================================

class LibraryCardPreview(
    QFrame
):
    """
    Zeigt für eine Library-Card genau ein Previewbild.

    Reihenfolge:

    1. lokales Preview
    2. GameBanana-Preview
    3. Placeholder

    Die eigentliche Suche wird vom
    LibraryPreviewWorker durchgeführt.
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

        self.setFixedHeight(
            PREVIEW_HEIGHT
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._request_token = 0

        self._local_pixmap: (
            QPixmap
            | None
        ) = None

        self._workers: set[
            LibraryPreviewWorker
        ] = set()

        # ----------------------------------------------------
        # Stack
        # ----------------------------------------------------

        self.stack = (
            QStackedWidget(
                self
            )
        )

        # ----------------------------------------------------
        # Placeholder
        # ----------------------------------------------------

        self.empty_label = QLabel(
            self
        )

        self.empty_label.setObjectName(
            "libraryCardPreviewEmpty"
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # ----------------------------------------------------
        # Lokales Bild
        # ----------------------------------------------------

        self.local_label = QLabel(
            self
        )

        self.local_label.setObjectName(
            "libraryCardPreviewLocal"
        )

        self.local_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # ----------------------------------------------------
        # Remote / GameBanana
        # ----------------------------------------------------

        self.remote_image = (
            GameBananaPreviewImage(
                parent=self,
                minimum_height=(
                    PREVIEW_HEIGHT
                ),
            )
        )

        self.remote_image.setObjectName(
            "libraryCardPreviewRemote"
        )

        self.remote_image.setFixedHeight(
            PREVIEW_HEIGHT
        )

        self._build_ui()

        self.clear_preview()

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

        self.stack.addWidget(
            self.empty_label
        )

        self.stack.addWidget(
            self.local_label
        )

        self.stack.addWidget(
            self.remote_image
        )

        layout.addWidget(
            self.stack
        )

    # ========================================================
    # Mod Preview laden
    # ========================================================

    def load_mod(
        self,
        mod: ModInfo,
    ) -> None:
        self._request_token += 1

        token = (
            self._request_token
        )

        self._local_pixmap = None

        self.local_label.clear()

        self.remote_image.set_preview_url(
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
            self._on_preview_loaded(
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
            self._on_preview_failed(
                worker=current_worker,
                token=current_token,
            )
        )

        QThreadPool.globalInstance().start(
            worker
        )

    # ========================================================
    # Worker Result
    # ========================================================

    def _on_preview_loaded(
        self,
        *,
        result,
        worker: LibraryPreviewWorker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        # Ein älterer Worker darf keine inzwischen
        # ausgewählte neue Preview überschreiben.
        if (
            token
            != self._request_token
        ):
            return

        # ----------------------------------------------------
        # Lokal bevorzugen
        # ----------------------------------------------------

        if result.local_images:
            path = (
                result.local_images[
                    0
                ]
            )

            pixmap = QPixmap(
                str(
                    path
                )
            )

            if not pixmap.isNull():
                self._local_pixmap = (
                    pixmap
                )

                self.stack.setCurrentWidget(
                    self.local_label
                )

                # Erst nach dem Layout skalieren.
                QTimer.singleShot(
                    0,
                    self._refresh_local_pixmap,
                )

                return

        # ----------------------------------------------------
        # GameBanana Fallback
        # ----------------------------------------------------

        if result.remote_images:
            self.remote_image.set_preview_url(
                result.remote_images[
                    0
                ]
            )

            self.stack.setCurrentWidget(
                self.remote_image
            )

            return

        self._show_empty()

    def _on_preview_failed(
        self,
        *,
        worker: LibraryPreviewWorker,
        token: int,
    ) -> None:
        self._workers.discard(
            worker
        )

        if (
            token
            != self._request_token
        ):
            return

        self._show_empty()

    # ========================================================
    # Placeholder
    # ========================================================

    def _show_empty(
        self,
    ) -> None:
        self._local_pixmap = None

        self.local_label.clear()

        self.remote_image.set_preview_url(
            None
        )

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
        self._request_token += 1

        self._show_empty()

    # ========================================================
    # Resize
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
        pixmap = (
            self._local_pixmap
        )

        if (
            pixmap is None
            or pixmap.isNull()
        ):
            return

        width = (
            self.local_label
            .contentsRect()
            .width()
        )

        height = (
            self.local_label
            .contentsRect()
            .height()
        )

        if (
            width <= 0
            or height <= 0
        ):
            return

        device_ratio = max(
            1.0,
            float(
                self.devicePixelRatioF()
            ),
        )

        target_width = max(
            1,
            int(
                width
                * device_ratio
            ),
        )

        target_height = max(
            1,
            int(
                height
                * device_ratio
            ),
        )

        scaled = pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        scaled.setDevicePixelRatio(
            device_ratio
        )

        self.local_label.setPixmap(
            scaled
        )


# ============================================================
# Einzelne Mod Card
# ============================================================

class LibraryModCard(
    QFrame
):
    toggle_requested = Signal(
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

        self._operation_running = (
            False
        )

        self.setObjectName(
            "libraryModCard"
        )

        # ----------------------------------------------------
        # DAS ist eine der entscheidenden Korrekturen.
        #
        # Die alte Card konnte im Grid auf wenige Pixel
        # zusammenschrumpfen.
        # ----------------------------------------------------

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
        # Labels
        # ----------------------------------------------------

        self.name_label = QLabel(
            self
        )

        self.name_label.setObjectName(
            "libraryCardTitle"
        )

        self.name_label.setWordWrap(
            True
        )

        self.meta_label = QLabel(
            self
        )

        self.meta_label.setObjectName(
            "libraryCardMeta"
        )

        self.meta_label.setWordWrap(
            True
        )

        self.status_label = QLabel(
            self
        )

        self.status_label.setObjectName(
            "libraryCardState"
        )

        # ----------------------------------------------------
        # Aktivieren / Deaktivieren
        # ----------------------------------------------------

        self.toggle_button = (
            QPushButton(
                self
            )
        )

        self.toggle_button.setObjectName(
            "libraryCardAction"
        )

        self.toggle_button.setMinimumWidth(
            120
        )

        self.toggle_button.setMaximumWidth(
            150
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
            10,
            10,
            10,
            12,
        )

        layout.setSpacing(
            9
        )

        layout.addWidget(
            self.preview
        )

        # ----------------------------------------------------
        # Unterer Card-Bereich
        # ----------------------------------------------------

        footer = QHBoxLayout()

        footer.setContentsMargins(
            4,
            1,
            4,
            1,
        )

        footer.setSpacing(
            12
        )

        info_layout = (
            QVBoxLayout()
        )

        info_layout.setSpacing(
            2
        )

        info_layout.addWidget(
            self.name_label
        )

        info_layout.addWidget(
            self.meta_label
        )

        info_layout.addWidget(
            self.status_label
        )

        footer.addLayout(
            info_layout,
            stretch=1,
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

        self.toggle_button.clicked.connect(
            self._emit_toggle
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

        self.meta_label.setText(
            (
                " • ".join(
                    parts
                )
                if parts
                else tr(
                    "common.unknown"
                )
            )
        )

    # ========================================================
    # State
    # ========================================================

    def set_state(
        self,
        state: ModState,
    ) -> None:
        self.state = state

        # ----------------------------------------------------
        # State Text
        # ----------------------------------------------------

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
            self.status_label.setText(
                tr(
                    state_key
                )
            )

        else:
            self.status_label.setText(
                state.value
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
                    (
                        "library.details.action."
                        "remove_broken"
                    )
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
                    (
                        "library.details.action."
                        "not_configured"
                    )
                )
            )

            action_available = False

        else:
            self.toggle_button.setText(
                tr(
                    (
                        "library.details.action."
                        "unavailable"
                    )
                )
            )

            action_available = False

        self.toggle_button.setEnabled(
            action_available
            and not self._operation_running
        )

        # ----------------------------------------------------
        # QSS State Property
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

    def set_operation_running(
        self,
        running: bool,
    ) -> None:
        self._operation_running = (
            bool(
                running
            )
        )

        self.set_state(
            self.state
        )

    # ========================================================
    # Signal
    # ========================================================

    def _emit_toggle(
        self,
    ) -> None:
        self.toggle_requested.emit(
            self.mod
        )


# ============================================================
# Library Gallery
# ============================================================

class LibraryGalleryWidget(
    QWidget
):
    toggle_requested = Signal(
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
        # Daten
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

        # ----------------------------------------------------
        # Scroll Area
        # ----------------------------------------------------

        self.scroll_area = (
            QScrollArea(
                self
            )
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
        # Scroll Content
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

        self.grid = (
            QGridLayout(
                self.content
            )
        )

        self.grid.setContentsMargins(
            8,
            8,
            14,
            20,
        )

        self.grid.setHorizontalSpacing(
            14
        )

        self.grid.setVerticalSpacing(
            14
        )

        # ----------------------------------------------------
        # SEHR WICHTIG:
        #
        # Das Layout bestimmt die Mindesthöhe des
        # Scroll-Contents. Ohne das können die Cards
        # in QScrollArea kollabieren.
        # ----------------------------------------------------

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
    # Mods setzen
    # ========================================================

    def set_mods(
        self,
        *,
        mods: list[
            ModInfo
        ]
        | tuple[
            ModInfo,
            ...,
        ],
        state_provider: StateProvider,
    ) -> None:
        self.clear()

        for mod in mods:
            state = (
                state_provider(
                    mod.path
                )
            )

            card = (
                LibraryModCard(
                    mod=mod,
                    state=state,
                    parent=self.content,
                )
            )

            card.set_operation_running(
                self._operation_running
            )

            card.toggle_requested.connect(
                self.toggle_requested
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

    # ========================================================
    # Clear
    # ========================================================

    def clear(
        self,
    ) -> None:
        for card in self._cards:
            self.grid.removeWidget(
                card
            )

            card.deleteLater()

        self._cards.clear()

        self._card_by_path.clear()

        self._current_columns = 0

        self.empty_label.setText(
            tr(
                "library.gallery.empty"
            )
        )

        self.empty_label.setVisible(
            True
        )

        self.scroll_area.setVisible(
            False
        )

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

        return (
            self._apply_current_filters()
        )

    def _apply_current_filters(
        self,
    ) -> int:
        visible_cards: list[
            LibraryModCard
        ] = []

        for card in self._cards:
            mod = (
                card.mod
            )

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
            # Mod Type
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
            # Suche
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
    # Card Status aktualisieren
    # ========================================================

    def update_mod_state(
        self,
        *,
        mod: ModInfo,
        state: ModState,
    ) -> None:
        card = (
            self._card_by_path.get(
                self._path_key(
                    mod.path
                )
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
        self._operation_running = (
            bool(
                running
            )
        )

        for card in self._cards:
            card.set_operation_running(
                self._operation_running
            )

    # ========================================================
    # Responsive Layout
    # ========================================================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

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
        if not cards:
            return

        available_width = max(
            CARD_MINIMUM_WIDTH,
            (
                self.scroll_area
                .viewport()
                .width()
                - 24
            ),
        )

        columns = max(
            1,
            available_width
            // CARD_TARGET_WIDTH,
        )

        if (
            not force
            and columns
            == self._current_columns
        ):
            return

        self._current_columns = (
            columns
        )

        # ----------------------------------------------------
        # Alte Positionen entfernen
        # ----------------------------------------------------

        for card in self._cards:
            self.grid.removeWidget(
                card
            )

        # ----------------------------------------------------
        # Neu anordnen
        # ----------------------------------------------------

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
                ),
            )

        for column in range(
            columns
        ):
            self.grid.setColumnStretch(
                column,
                1,
            )

        # Der Content muss sein Layout neu berechnen.
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