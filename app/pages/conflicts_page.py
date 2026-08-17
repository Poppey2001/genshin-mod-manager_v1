from __future__ import annotations

from collections.abc import (
    Callable,
)

from pathlib import Path

from shiboken6 import (
    isValid,
)

from PySide6.QtCore import (
    Qt,
    QThreadPool,
    Signal,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.services.conflict_scanner import (
    ConflictItem,
    ConflictKind,
    ConflictReport,
)

from app.services.mod_duplicate_service import (
    DuplicateCheckResult,
    ModDuplicateService,
)

from app.workers.mod_duplicate_worker import (
    ModDuplicateWorker,
)

from app.widgets.common.state_panel import (
    StatePanel,
)


# ============================================================
# Conflict Card
# ============================================================

class ConflictCard(
    QFrame
):
    adopt_requested = Signal(
        object
    )

    open_requested = Signal(
        object
    )

    duplicate_check_requested = Signal(
        object
    )

    copy_to_library_requested = Signal(
        object
    )

    delete_duplicate_requested = Signal(
        object,
        object,
    )

    def __init__(
        self,
        *,
        conflict: ConflictItem,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.conflict = conflict

        self._duplicate_result: (
            DuplicateCheckResult
            | None
        ) = None

        self._hash_state = (
            "idle"
        )

        self._progress_data = (
            0,
            0,
            "",
        )

        self.setObjectName(
            "conflictCard"
        )

        self.setProperty(
            "conflictKind",
            conflict.kind.value,
        )

        # Wichtig:
        # Eine Konfliktkarte darf nicht die komplette freie Höhe
        # der ScrollArea übernehmen. Sie wächst horizontal, bleibt
        # vertikal aber auf ihrer tatsächlichen Inhaltshöhe.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        # ----------------------------------------------------
        # Labels
        # ----------------------------------------------------

        self.title_label = QLabel(
            conflict.title
        )

        self.type_label = QLabel()

        self.message_label = QLabel()

        self.path_label = QLabel(
            str(
                conflict.path
            )
        )

        self.hash_status_label = QLabel()

        self.crc_label = QLabel()

        self.sha_label = QLabel()

        self.duplicate_label = QLabel()

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        self.check_button = (
            QPushButton()
        )

        self.copy_button = (
            QPushButton()
        )

        self.open_button = (
            QPushButton()
        )

        self.adopt_button = (
            QPushButton()
        )

        self.delete_button = (
            QPushButton()
        )

        self._build_ui()

        self.retranslate_ui()

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
            16,
            12,
            16,
            12,
        )

        layout.setSpacing(
            6
        )

        # ----------------------------------------------------
        # Top
        # ----------------------------------------------------

        top = QHBoxLayout()

        self.title_label.setObjectName(
            "conflictTitle"
        )

        self.type_label.setObjectName(
            "conflictType"
        )

        top.addWidget(
            self.title_label,
            stretch=1,
        )

        top.addWidget(
            self.type_label
        )

        layout.addLayout(
            top
        )

        # ----------------------------------------------------
        # Message
        # ----------------------------------------------------

        self.message_label.setObjectName(
            "conflictMessage"
        )

        self.message_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.message_label
        )

        # ----------------------------------------------------
        # Path
        # ----------------------------------------------------

        self.path_label.setObjectName(
            "conflictPath"
        )

        self.path_label.setWordWrap(
            True
        )

        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        layout.addWidget(
            self.path_label
        )

        # ----------------------------------------------------
        # Hash information
        # ----------------------------------------------------

        self.hash_status_label.setObjectName(
            "conflictHashStatus"
        )

        self.hash_status_label.setWordWrap(
            True
        )

        hash_frame = QFrame(
            self
        )

        hash_frame.setObjectName(
            "conflictHashFrame"
        )

        hash_layout = QVBoxLayout(
            hash_frame
        )

        hash_layout.setContentsMargins(
            10,
            7,
            10,
            7,
        )

        hash_layout.setSpacing(
            4
        )

        hash_layout.addWidget(
            self.hash_status_label
        )

        self.crc_label.setObjectName(
            "conflictHash"
        )

        self.sha_label.setObjectName(
            "conflictHash"
        )

        self.sha_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        self.crc_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        hash_layout.addWidget(
            self.crc_label
        )

        hash_layout.addWidget(
            self.sha_label
        )

        self.duplicate_label.setObjectName(
            "conflictDuplicate"
        )

        self.duplicate_label.setWordWrap(
            True
        )

        self.duplicate_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        hash_layout.addWidget(
            self.duplicate_label
        )

        layout.addWidget(
            hash_frame
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        actions = QHBoxLayout()

        actions.setSpacing(
            8
        )

        self.check_button.setObjectName(
            "secondaryButton"
        )

        self.copy_button.setObjectName(
            "primaryButton"
        )

        self.open_button.setObjectName(
            "secondaryButton"
        )

        self.adopt_button.setObjectName(
            "warningActionButton"
        )

        self.delete_button.setObjectName(
            "dangerButton"
        )

        actions.addWidget(
            self.check_button
        )

        actions.addWidget(
            self.copy_button
        )

        actions.addStretch(
            1
        )

        if self.conflict.can_adopt:
            actions.addWidget(
                self.adopt_button
            )
        else:
            self.adopt_button.hide()

        actions.addWidget(
            self.delete_button
        )

        self.delete_button.hide()

        layout.addLayout(
            actions
        )

        # Im alten kompakten Design stand "Open folder"
        # bewusst in einer eigenen kleinen Zeile links.
        open_row = QHBoxLayout()

        open_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        open_row.addWidget(
            self.open_button
        )

        open_row.addStretch(
            1
        )

        layout.addLayout(
            open_row
        )

        # ----------------------------------------------------
        # Connections
        # ----------------------------------------------------

        self.check_button.clicked.connect(
            self._request_duplicate_check
        )

        self.copy_button.clicked.connect(
            self._request_copy
        )

        self.open_button.clicked.connect(
            self._request_open
        )

        self.adopt_button.clicked.connect(
            self._request_adopt
        )

        self.delete_button.clicked.connect(
            self._request_delete
        )

    def _refresh_compact_geometry(
        self,
    ) -> None:
        """
        Hash-/Duplicate-Texte können die notwendige Kartenhöhe
        verändern. Nach solchen Änderungen darf die Karte wachsen,
        aber nie die restliche ScrollArea-Höhe auffüllen.
        """

        layout = self.layout()

        if layout is not None:
            layout.invalidate()
            layout.activate()

        self.updateGeometry()

    # ========================================================
    # Signals
    # ========================================================

    def _request_duplicate_check(
        self,
        _checked: bool = False,
    ) -> None:
        self.duplicate_check_requested.emit(
            self.conflict
        )

    def _request_copy(
        self,
        _checked: bool = False,
    ) -> None:
        self.copy_to_library_requested.emit(
            self.conflict
        )

    def _request_open(
        self,
        _checked: bool = False,
    ) -> None:
        self.open_requested.emit(
            self.conflict
        )

    def _request_adopt(
        self,
        _checked: bool = False,
    ) -> None:
        self.adopt_requested.emit(
            self.conflict
        )

    def _request_delete(
        self,
        _checked: bool = False,
    ) -> None:
        if (
            self._duplicate_result
            is None
        ):
            return

        self.delete_duplicate_requested.emit(
            self.conflict,
            self._duplicate_result,
        )

    # ========================================================
    # Hash UI
    # ========================================================

    def set_checking(
        self,
    ) -> None:
        self._hash_state = (
            "checking"
        )

        self._duplicate_result = (
            None
        )

        self.check_button.setEnabled(
            False
        )

        self.delete_button.hide()

        self.crc_label.clear()
        self.sha_label.clear()
        self.duplicate_label.clear()

        self.retranslate_ui()

    def set_progress(
        self,
        *,
        current: int,
        total: int,
        name: str,
    ) -> None:
        self._progress_data = (
            current,
            total,
            name,
        )

        self._hash_state = (
            "checking"
        )

        self.retranslate_ui()

    def set_duplicate_result(
        self,
        result: DuplicateCheckResult,
    ) -> None:
        self._duplicate_result = (
            result
        )

        self._hash_state = (
            (
                "duplicate"
                if result.is_duplicate
                else "unique"
            )
        )

        self.check_button.setEnabled(
            True
        )

        self.delete_button.setVisible(
            result.is_duplicate
        )

        self.retranslate_ui()

    def set_duplicate_error(
        self,
        message: str,
    ) -> None:
        self._duplicate_result = (
            None
        )

        self._hash_state = (
            "error"
        )

        self.check_button.setEnabled(
            True
        )

        self.delete_button.hide()

        self.crc_label.clear()
        self.sha_label.clear()

        self.duplicate_label.setText(
            message
        )

        self.retranslate_ui(
            preserve_error=True
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
        *,
        preserve_error: bool = False,
    ) -> None:
        # ----------------------------------------------------
        # Type
        # ----------------------------------------------------

        type_key = {
            ConflictKind.LIBRARY: (
                "conflicts.type.library"
            ),
            ConflictKind.UNMANAGED_ACTIVE: (
                "conflicts.type.unmanaged"
            ),
            ConflictKind.INVALID_MARKER: (
                "conflicts.type.invalid_marker"
            ),
            ConflictKind.ORPHANED_MANAGED: (
                "conflicts.type.orphaned"
            ),
        }[
            self.conflict.kind
        ]

        self.type_label.setText(
            tr(
                type_key
            )
        )

        # ----------------------------------------------------
        # Message
        #
        # Wir zeigen nicht mehr den deutschen
        # hardcoded Scanner-Text an.
        # ----------------------------------------------------

        message_key = {
            ConflictKind.LIBRARY: (
                "conflicts.message.library"
            ),
            ConflictKind.UNMANAGED_ACTIVE: (
                "conflicts.message.unmanaged"
            ),
            ConflictKind.INVALID_MARKER: (
                "conflicts.message.invalid_marker"
            ),
            ConflictKind.ORPHANED_MANAGED: (
                "conflicts.message.orphaned"
            ),
        }[
            self.conflict.kind
        ]

        self.message_label.setText(
            tr(
                message_key
            )
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        self.check_button.setText(
            tr(
                "conflicts.action.check_duplicate"
            )
        )

        self.copy_button.setText(
            tr(
                "conflicts.action.copy_to_library"
            )
        )

        self.open_button.setText(
            tr(
                "conflicts.action.open"
            )
        )

        self.adopt_button.setText(
            tr(
                "conflicts.action.adopt"
            )
        )

        self.delete_button.setText(
            tr(
                "conflicts.action.delete_duplicate"
            )
        )

        # ----------------------------------------------------
        # Hash State
        # ----------------------------------------------------

        if (
            self._hash_state
            == "idle"
        ):
            self.hash_status_label.setText(
                tr(
                    "conflicts.hash.idle"
                )
            )

            self.crc_label.clear()
            self.sha_label.clear()
            self.duplicate_label.clear()

        elif (
            self._hash_state
            == "checking"
        ):
            (
                current,
                total,
                name,
            ) = self._progress_data

            self.hash_status_label.setText(
                tr(
                    "conflicts.hash.checking",
                    current=current,
                    total=total,
                    name=name,
                )
            )

        elif (
            self._hash_state
            in {
                "duplicate",
                "unique",
            }
        ):
            result = (
                self._duplicate_result
            )

            if result is None:
                return

            self.crc_label.setText(
                tr(
                    "conflicts.hash.crc32",
                    value=(
                        result
                        .source_fingerprint
                        .crc32
                    ),
                )
            )

            self.sha_label.setText(
                tr(
                    "conflicts.hash.sha256",
                    value=(
                        result
                        .source_fingerprint
                        .sha256
                    ),
                )
            )

            if result.is_duplicate:
                self.hash_status_label.setText(
                    tr(
                        "conflicts.hash.duplicate"
                    )
                )

                self.duplicate_label.setText(
                    tr(
                        "conflicts.hash.duplicate_path",
                        path=(
                            result
                            .duplicate_path
                        ),
                    )
                )

            else:
                self.hash_status_label.setText(
                    tr(
                        "conflicts.hash.no_duplicate"
                    )
                )

                self.duplicate_label.clear()

        elif (
            self._hash_state
            == "error"
        ):
            self.hash_status_label.setText(
                tr(
                    "conflicts.hash.failed"
                )
            )

            if not preserve_error:
                # Technische Fehlermeldung behalten.
                pass

        self._refresh_compact_geometry()


# ============================================================
# Page
# ============================================================

class ConflictsPage(
    QWidget
):
    refresh_requested = Signal()

    rescan_requested = Signal()

    adopt_requested = Signal(
        object
    )

    open_requested = Signal(
        object
    )

    copy_to_library_requested = Signal(
        object
    )

    def __init__(
        self,
        *,
        library_paths_provider: Callable[
            [],
            tuple[
                Path,
                ...,
            ],
        ],
        game_id_provider: Callable[
            [],
            str,
        ],
        active_root_provider: Callable[
            [],
            Path,
        ],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "conflictsPage"
        )

        self.library_paths_provider = (
            library_paths_provider
        )

        self.game_id_provider = (
            game_id_provider
        )

        self.active_root_provider = (
            active_root_provider
        )

        self._report = (
            ConflictReport()
        )

        self._cards: list[
            ConflictCard
        ] = []

        self._card_by_key: dict[
            str,
            ConflictCard,
        ] = {}

        self._workers: set[
            ModDuplicateWorker
        ] = set()

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.duplicate_service = (
            ModDuplicateService()
        )

        # ----------------------------------------------------
        # Widgets
        # ----------------------------------------------------

        self.title_label = QLabel()

        self.description_label = QLabel()

        self.count_label = QLabel()

        self.refresh_button = (
            QPushButton()
        )

        # ====================================================
        # Old compact summary bar
        # ====================================================

        self.summary_frame = QFrame(
            self
        )

        self.summary_icon_label = QLabel(
            self.summary_frame
        )

        self.summary_title_label = QLabel(
            self.summary_frame
        )

        self.summary_description_label = QLabel(
            self.summary_frame
        )

        self.summary_count_label = QLabel(
            self.summary_frame
        )

        # ====================================================
        # Unified Page State
        # ====================================================

        self.content_stack = (
            QStackedWidget(
                self
            )
        )

        self.content_stack.setObjectName(
            "conflictsContentStack"
        )

        self.state_panel = (
            StatePanel(
                self.content_stack
            )
        )

        self.state_panel.setObjectName(
            "conflictsStatePanel"
        )

        self._content_state_mode = (
            "loading"
        )

        self._content_state_message = ""

        self.scroll_area = (
            QScrollArea()
        )

        self.scroll_area.setObjectName(
            "conflictsScrollArea"
        )

        self.content = QWidget()
        self.content.setObjectName(
            "conflictsContent"
        )

        self.content_layout = (
            QVBoxLayout(
                self.content
            )
        )

        self._build_ui()
        self._apply_old_compact_style()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        # Bis der erste Report von der Library eintrifft,
        # zeigen wir keinen falschen "alles sauber"-Zustand.
        self._show_loading_state()

    # ========================================================
    # Build
    # ========================================================

    def _build_ui(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        layout.setSpacing(
            16
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = QHBoxLayout()

        texts = QVBoxLayout()

        self.title_label.setObjectName(
            "pageTitle"
        )

        self.description_label.setObjectName(
            "pageDescription"
        )

        self.description_label.setWordWrap(
            True
        )

        texts.addWidget(
            self.title_label
        )

        texts.addWidget(
            self.description_label
        )

        header.addLayout(
            texts,
            stretch=1,
        )

        right = QVBoxLayout()

        self.count_label.setObjectName(
            "conflictCount"
        )

        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        # Gleicher Widget-Stil wie "Neu scannen" in der Library.
        self.refresh_button.setObjectName(
            "refreshButton"
        )

        self.refresh_button.setMinimumHeight(
            36
        )

        right.addWidget(
            self.count_label
        )

        right.addWidget(
            self.refresh_button
        )

        header.addLayout(
            right
        )

        layout.addLayout(
            header
        )

        # ----------------------------------------------------
        # Compact summary bar
        # ----------------------------------------------------

        self.summary_frame.setObjectName(
            "conflictsSummary"
        )

        summary_layout = QHBoxLayout(
            self.summary_frame
        )

        summary_layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )

        summary_layout.setSpacing(
            10
        )

        self.summary_icon_label.setObjectName(
            "conflictsSummaryIcon"
        )

        self.summary_icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.summary_icon_label.setFixedSize(
            30,
            30,
        )

        summary_layout.addWidget(
            self.summary_icon_label
        )

        summary_text = QVBoxLayout()

        summary_text.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        summary_text.setSpacing(
            1
        )

        self.summary_title_label.setObjectName(
            "conflictsSummaryTitle"
        )

        self.summary_description_label.setObjectName(
            "conflictsSummaryDescription"
        )

        self.summary_description_label.setWordWrap(
            True
        )

        summary_text.addWidget(
            self.summary_title_label
        )

        summary_text.addWidget(
            self.summary_description_label
        )

        summary_layout.addLayout(
            summary_text,
            stretch=1,
        )

        self.summary_count_label.setObjectName(
            "conflictsSummaryCount"
        )

        self.summary_count_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        summary_layout.addWidget(
            self.summary_count_label
        )

        layout.addWidget(
            self.summary_frame
        )

        # ----------------------------------------------------
        # Content / Unified State
        # ----------------------------------------------------

        self.content_layout.setContentsMargins(
            0,
            0,
            8,
            16,
        )

        self.content_layout.setSpacing(
            10
        )

        # Karten wie in einer kompakten Liste oben halten.
        # Der Stretch nimmt nur den freien Rest unter den Karten ein.
        self.content_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.content_layout.addStretch(
            1
        )

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.scroll_area.setWidget(
            self.content
        )

        self.content_stack.addWidget(
            self.scroll_area
        )

        self.content_stack.addWidget(
            self.state_panel
        )

        layout.addWidget(
            self.content_stack,
            stretch=1,
        )

        self.refresh_button.clicked.connect(
            self._request_refresh
        )

        self.state_panel.primary_requested.connect(
            self._on_state_primary_requested
        )

    def _apply_old_compact_style(
        self,
    ) -> None:
        self.setStyleSheet(
            r"""
            QWidget#conflictsPage {
                background: transparent;
                color: #e7e9ef;
            }

            QStackedWidget#conflictsContentStack,
            QWidget#conflictsContent,
            QScrollArea#conflictsScrollArea,
            QScrollArea#conflictsScrollArea > QWidget > QWidget {
                background: transparent;
                border: none;
            }

            /* -------------------------------------------------
               Library-style scan / refresh button
               ------------------------------------------------- */

            QPushButton#refreshButton {
                min-height: 36px;
                padding-left: 13px;
                padding-right: 13px;

                background-color: #292e37;
                color: #e1e4e9;

                border: 1px solid #3a404b;
                border-radius: 8px;

                font-weight: 700;
            }

            QPushButton#refreshButton:hover {
                background-color: #343a45;
                border-color: #4a5260;
                color: #ffffff;
            }

            QPushButton#refreshButton:pressed {
                background-color: #252a32;
                border-color: #414955;
            }

            QPushButton#refreshButton:disabled {
                background-color: #252a32;
                color: #656c78;
                border-color: #323842;
            }

            /* -------------------------------------------------
               Summary
               ------------------------------------------------- */

            QFrame#conflictsSummary {
                background-color: #17201b;
                border: 1px solid #335843;
                border-left: 3px solid #4fc183;
                border-radius: 10px;
            }

            QFrame#conflictsSummary[hasConflicts="true"] {
                background-color: #211b10;
                border-color: #6b4c18;
                border-left-color: #d49528;
            }

            QLabel#conflictsSummaryIcon {
                background-color: #192820;
                color: #61d795;
                border: 1px solid #355e48;
                border-radius: 15px;
                font-size: 14px;
                font-weight: 900;
            }

            QFrame#conflictsSummary[hasConflicts="true"]
            QLabel#conflictsSummaryIcon {
                background-color: #2a2112;
                color: #e5a93d;
                border-color: #755421;
            }

            QLabel#conflictsSummaryTitle {
                background: transparent;
                color: #f1f3f5;
                font-size: 11px;
                font-weight: 850;
            }

            QLabel#conflictsSummaryDescription {
                background: transparent;
                color: #8f99a6;
                font-size: 9px;
            }

            QLabel#conflictsSummaryCount {
                min-height: 28px;
                padding-left: 13px;
                padding-right: 13px;
                background-color: #1d3427;
                color: #75dda3;
                border: 1px solid #38634b;
                border-radius: 8px;
                font-size: 9px;
                font-weight: 850;
            }

            QFrame#conflictsSummary[hasConflicts="true"]
            QLabel#conflictsSummaryCount {
                background-color: #3b2b0f;
                color: #f0bd58;
                border-color: #76521b;
            }

            /* -------------------------------------------------
               Conflict Cards
               ------------------------------------------------- */

            QFrame#conflictCard {
                background-color: #1a2028;
                border: 1px solid #303844;
                border-left: 3px solid #745cff;
                border-radius: 10px;
            }

            QFrame#conflictCard:hover {
                background-color: #1e252e;
                border-color: #46515f;
                border-left-color: #8068ff;
            }

            QLabel#conflictTitle {
                background: transparent;
                color: #f5f6f8;
                font-size: 11px;
                font-weight: 850;
            }

            QLabel#conflictType {
                min-height: 25px;
                padding-left: 10px;
                padding-right: 10px;
                background-color: #302450;
                color: #b69cff;
                border: 1px solid #58438d;
                border-radius: 7px;
                font-size: 8px;
                font-weight: 850;
            }

            QLabel#conflictMessage {
                background: transparent;
                color: #a5afbb;
                font-size: 9px;
            }

            QLabel#conflictPath {
                background-color: #151a20;
                color: #9aa4b1;
                border: 1px solid #2b333d;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 8px;
            }

            QFrame#conflictHashFrame {
                background-color: #11161c;
                border: 1px solid #29313a;
                border-radius: 7px;
            }

            QLabel#conflictHashStatus {
                background: transparent;
                color: #c4cad2;
                font-size: 8px;
                font-weight: 700;
            }

            QLabel#conflictHash {
                min-height: 17px;
                background-color: #10151a;
                color: #858f9d;
                border: 1px solid #252d36;
                border-radius: 4px;
                padding-left: 7px;
                padding-right: 7px;
                font-size: 8px;
            }

            QLabel#conflictDuplicate {
                background: transparent;
                color: #69d49a;
                font-size: 8px;
            }

            /* -------------------------------------------------
               Buttons
               ------------------------------------------------- */

            QFrame#conflictCard QPushButton {
                min-height: 30px;
                padding-left: 11px;
                padding-right: 11px;
                border-radius: 6px;
                font-size: 8px;
                font-weight: 800;
            }

            QFrame#conflictCard QPushButton#secondaryButton {
                background-color: #222a33;
                color: #d1d7df;
                border: 1px solid #36414d;
            }

            QFrame#conflictCard QPushButton#secondaryButton:hover {
                background-color: #2c3540;
                color: #ffffff;
                border-color: #4b5867;
            }

            QFrame#conflictCard QPushButton#primaryButton {
                background-color: #7158e8;
                color: #ffffff;
                border: 1px solid #856ff0;
            }

            QFrame#conflictCard QPushButton#primaryButton:hover {
                background-color: #8068f0;
            }

            QFrame#conflictCard QPushButton#warningActionButton {
                background-color: #3b2b0f;
                color: #f0bd58;
                border: 1px solid #76521b;
            }

            QFrame#conflictCard QPushButton#dangerButton {
                background-color: #3c2026;
                color: #ff9aa5;
                border: 1px solid #6b343d;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical,
            QScrollBar:horizontal {
                background: transparent;
            }
            """
        )

    # ========================================================
    # Report
    # ========================================================

    def set_report(
        self,
        report: ConflictReport,
    ) -> None:
        self._report = report

        self._clear_cards()

        for conflict in (
            report.items
        ):
            card = ConflictCard(
                conflict=conflict,
                parent=self.content,
            )

            card.adopt_requested.connect(
                self.adopt_requested
            )

            card.open_requested.connect(
                self.open_requested
            )

            card.copy_to_library_requested.connect(
                self.copy_to_library_requested
            )

            card.duplicate_check_requested.connect(
                self._start_duplicate_check
            )

            card.delete_duplicate_requested.connect(
                self._delete_duplicate
            )

            self._cards.append(
                card
            )

            self._card_by_key[
                conflict.key
            ] = card

            self.content_layout.insertWidget(
                self.content_layout.count()
                - 1,
                card,
                0,
                Qt.AlignmentFlag.AlignTop,
            )

        if report.items:
            self._show_content()
        else:
            self._show_empty_state()

        self._refresh_summary()
        self.retranslate_ui()

    # ========================================================
    # Compact Summary
    # ========================================================

    def _refresh_summary(
        self,
    ) -> None:
        count = int(
            self._report.count
        )

        has_conflicts = (
            count > 0
        )

        self.summary_frame.setProperty(
            "hasConflicts",
            has_conflicts,
        )

        self.summary_icon_label.setText(
            "!"
            if has_conflicts
            else "✓"
        )

        if has_conflicts:
            self.summary_title_label.setText(
                tr(
                    "conflicts.summary.attention_title"
                )
            )

            self.summary_description_label.setText(
                tr(
                    "conflicts.summary.attention_description"
                )
            )
        else:
            self.summary_title_label.setText(
                tr(
                    "conflicts.summary.clean_title"
                )
            )

            self.summary_description_label.setText(
                tr(
                    "conflicts.summary.clean_description"
                )
            )

        self.summary_count_label.setText(
            tr(
                "conflicts.count",
                count=count,
            )
        )

        for widget in (
            self.summary_frame,
            self.summary_icon_label,
            self.summary_count_label,
        ):
            style = widget.style()
            style.unpolish(
                widget
            )
            style.polish(
                widget
            )
            widget.update()

    # ========================================================
    # Unified Page States
    # ========================================================

    def _request_refresh(
        self,
        _checked: bool = False,
    ) -> None:
        """
        UI sofort auf Loading setzen und anschließend die
        bestehende Library-Konfliktprüfung anfordern.
        """

        self._show_loading_state()
        self.refresh_requested.emit()

    def _show_content(
        self,
    ) -> None:
        self._content_state_mode = (
            "content"
        )

        self._content_state_message = ""

        self.content_stack.setCurrentWidget(
            self.scroll_area
        )

    def _show_loading_state(
        self,
    ) -> None:
        self._content_state_mode = (
            "loading"
        )

        self._content_state_message = ""

        self.state_panel.show_loading(
            title=tr(
                "conflicts.refresh"
            ),
            description=tr(
                "conflicts.description"
            ),
        )

        self.content_stack.setCurrentWidget(
            self.state_panel
        )

    def _show_empty_state(
        self,
    ) -> None:
        self._content_state_mode = (
            "empty"
        )

        self._content_state_message = ""

        self.state_panel.show_success(
            title=tr(
                "conflicts.empty"
            ),
            description=tr(
                "conflicts.description"
            ),
            primary_text=tr(
                "conflicts.refresh"
            ),
        )

        self.content_stack.setCurrentWidget(
            self.state_panel
        )

    def set_error(
        self,
        message: str,
    ) -> None:
        """
        Öffentliche Fehler-Schnittstelle.

        Falls der Konflikt-Scan später einen eigenen Failure-
        Signalpfad erhält, kann MainWindow/Library diesen direkt
        auf conflicts_page.set_error(...) verbinden.
        """

        self._content_state_mode = (
            "error"
        )

        self._content_state_message = str(
            message
        ).strip()

        self.state_panel.show_error(
            title=tr(
                "conflicts.title"
            ),
            description=(
                self._content_state_message
                or tr(
                    "conflicts.description"
                )
            ),
            primary_text=tr(
                "conflicts.refresh"
            ),
        )

        self.content_stack.setCurrentWidget(
            self.state_panel
        )

    def _on_state_primary_requested(
        self,
    ) -> None:
        if self._content_state_mode in {
            "empty",
            "error",
        }:
            self._request_refresh()

    def _refresh_unified_state_texts(
        self,
    ) -> None:
        mode = self._content_state_mode

        if mode == "loading":
            self._show_loading_state()

        elif mode == "empty":
            self._show_empty_state()

        elif mode == "error":
            self.set_error(
                self._content_state_message
            )

    def _clear_cards(
        self,
    ) -> None:
        cards = tuple(
            self._cards
        )

        self._cards.clear()

        self._card_by_key.clear()

        for card in cards:
            self.content_layout.removeWidget(
                card
            )

            card.deleteLater()

    # ========================================================
    # Duplicate Check
    # ========================================================

    def _start_duplicate_check(
        self,
        conflict: ConflictItem,
    ) -> None:
        card = (
            self._card_by_key.get(
                conflict.key
            )
        )

        if (
            card is None
            or not isValid(
                card
            )
        ):
            return

        path = Path(
            conflict.path
        )

        if not path.is_dir():
            card.set_duplicate_error(
                tr(
                    "conflicts.hash.invalid_source"
                )
            )

            return

        card.set_checking()

        worker = (
            ModDuplicateWorker(
                source=path,
                library_paths=(
                    tuple(
                        self.library_paths_provider()
                    )
                ),
                game_id=(
                    self.game_id_provider()
                ),
                service=(
                    self.duplicate_service
                ),
            )
        )

        worker.signals.progress.connect(
            self._on_duplicate_progress
        )

        worker.signals.finished.connect(
            self._on_duplicate_finished
        )

        worker.signals.failed.connect(
            self._on_duplicate_failed
        )

        self._workers.add(
            worker
        )

        self.thread_pool.start(
            worker
        )

    def _on_duplicate_progress(
        self,
        source_key: str,
        current: int,
        total: int,
        name: str,
    ) -> None:
        card = self._card_for_source(
            source_key
        )

        if card is None:
            return

        card.set_progress(
            current=current,
            total=total,
            name=name,
        )

    def _on_duplicate_finished(
        self,
        worker: ModDuplicateWorker,
        result: DuplicateCheckResult,
    ) -> None:
        self._workers.discard(
            worker
        )

        card = self._card_for_source(
            str(
                result.source
                .expanduser()
                .absolute()
            )
        )

        if card is None:
            return

        card.set_duplicate_result(
            result
        )

    def _on_duplicate_failed(
        self,
        worker: ModDuplicateWorker,
        source_key: str,
        message: str,
    ) -> None:
        self._workers.discard(
            worker
        )

        card = self._card_for_source(
            source_key
        )

        if card is None:
            return

        card.set_duplicate_error(
            message
        )

    def _card_for_source(
        self,
        source_key: str,
    ) -> ConflictCard | None:
        normalized = str(
            Path(
                source_key
            )
            .expanduser()
            .absolute()
        )

        for card in (
            self._cards
        ):
            if not isValid(
                card
            ):
                continue

            card_path = str(
                Path(
                    card.conflict.path
                )
                .expanduser()
                .absolute()
            )

            if (
                card_path
                == normalized
            ):
                return card

        return None

    # ========================================================
    # Delete Duplicate
    # ========================================================

    def _delete_duplicate(
        self,
        conflict: ConflictItem,
        result: DuplicateCheckResult,
    ) -> None:
        if not result.is_duplicate:
            return

        duplicate_path = (
            result.duplicate_path
        )

        if duplicate_path is None:
            return

        answer = QMessageBox.question(
            self,
            tr(
                "conflicts.delete.title"
            ),
            tr(
                "conflicts.delete.message",
                source=(
                    result.source
                ),
                library=(
                    duplicate_path
                ),
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            self.duplicate_service.delete_confirmed_duplicate(
                result=result,
                active_root=(
                    self.active_root_provider()
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                tr(
                    "conflicts.delete.failed.title"
                ),
                tr(
                    "conflicts.delete.failed.message",
                    error=(
                        error
                    ),
                ),
            )

            return

        QMessageBox.information(
            self,
            tr(
                "conflicts.delete.completed.title"
            ),
            tr(
                "conflicts.delete.completed.message"
            ),
        )

        self.rescan_requested.emit()

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "conflicts.title"
            )
        )

        self.description_label.setText(
            tr(
                "conflicts.description"
            )
        )

        self.refresh_button.setText(
            tr(
                "conflicts.refresh"
            )
        )

        self.count_label.setText(
            tr(
                "conflicts.count",
                count=(
                    self._report.count
                ),
            )
        )

        for card in (
            self._cards
        ):
            if isValid(
                card
            ):
                card.retranslate_ui()

        self._refresh_summary()
        self._refresh_unified_state_texts()


__all__ = [
    "ConflictsPage",
]