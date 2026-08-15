from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from shiboken6 import (
    isValid,
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
    Preview für eine Library-Card.

    Reihenfolge:
    1. lokale Preview
    2. GameBanana Preview
    3. Platzhalter

    Worker laufen asynchron. Beim Löschen der Card
    werden ihre Signale zuerst getrennt.
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

        # ====================================================
        # Lifecycle
        # ====================================================

        self._disposed = False

        self._request_token = 0

        self._workers: set[
            LibraryPreviewWorker
        ] = set()

        self._local_pixmap: (
            QPixmap
            | None
        ) = None

        # ====================================================
        # Widgets
        #
        # WICHTIG:
        # ALLE Widgets werden erstellt, BEVOR
        # _build_ui() oder clear_preview() aufgerufen wird.
        # ====================================================

        self.stack = (
            QStackedWidget(
                self
            )
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
                minimum_height=210,
            )
        )

        # ====================================================
        # UI
        # ====================================================

        self._build_ui()

        # Erst JETZT darf clear_preview() laufen.
        self.clear_preview()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        self.setMinimumHeight(
            210
        )

        self.setMaximumHeight(
            240
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
        # Empty
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
        # Lokal
        # ----------------------------------------------------

        self.local_label.setObjectName(
            "libraryCardPreviewLocal"
        )

        self.local_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # ----------------------------------------------------
        # Remote / GameBanana
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

        # Alten Request ungültig machen.
        self._request_token += 1

        token = (
            self._request_token
        )

        # ----------------------------------------------------
        # Anzeige zurücksetzen, ohne Lifecycle zu zerstören
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Preview Worker
        # ----------------------------------------------------

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
    # Worker fertig
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
        # 1. Lokale Preview bevorzugen
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
        # 2. GameBanana-Fallback
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
        # 3. Keine Preview
        # ----------------------------------------------------

        self._show_empty()

    # ========================================================
    # Worker Fehler
    # ========================================================

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

    # ========================================================
    # Public Reset
    # ========================================================

    def clear_preview(
        self,
    ) -> None:
        if self._disposed:
            return

        # Alle früheren Worker-Ergebnisse ungültig.
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
        if (
            self._disposed
            or not isValid(
                self
            )
        ):
            return

        if not isValid(
            self.local_label
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
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.local_label.setPixmap(
            scaled
        )

    # ========================================================
    # Lifecycle
    # ========================================================

    def dispose(
        self,
    ) -> None:
        """
        Wird von LibraryModCard.dispose() aufgerufen,
        BEVOR die Card mit deleteLater() gelöscht wird.
        """

        if self._disposed:
            return

        self._disposed = True

        # Alle alten Antworten ungültig.
        self._request_token += 1

        # ----------------------------------------------------
        # Library Preview Worker abkoppeln
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
        # GameBanana Preview Worker abkoppeln
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
        """
        Entfernt alle Gallery-Cards sicher.


        Wichtig:
        Preview-Worker werden zuerst von ihren Widgets
        getrennt und erst danach werden die Qt-Widgets
        gelöscht.
        """


        cards = tuple(
            self._cards
        )


        self._cards.clear()


        self._card_by_path.clear()


        for card in cards:
            self.grid.removeWidget(
                card
            )


            # -----------------------------------------------
            # Erst asynchrone Callbacks abkoppeln.
            # -----------------------------------------------


            card.dispose()


            # -----------------------------------------------
            # Erst danach Qt-Objekt löschen.
            # -----------------------------------------------


            card.deleteLater()


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
        """
        Speichert die aktuellen Filter und
        aktualisiert anschließend alle Cards.

        Rückgabe:
            Anzahl sichtbarer Cards.
        """

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