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


# ============================================================
# Local Conflicts Styles
# ============================================================

CONFLICTS_PAGE_QSS = r"""
QWidget#conflictsPage {
    background-color: #101319;
    color: #e7e9ef;
}


/* ============================================================
   PAGE HEADER
   ============================================================ */

QWidget#conflictsPage QLabel#pageTitle {
    background-color: transparent;

    color: #f5f6f8;

    font-size: 27px;
    font-weight: 850;
}

QWidget#conflictsPage QLabel#pageDescription {
    background-color: transparent;

    color: #838d9b;

    font-size: 12px;
}


/* ============================================================
   HEADER ACTIONS
   ============================================================ */

QFrame#conflictsHeaderActions {
    background-color: #15191f;

    border: 1px solid #292f38;
    border-radius: 11px;
}

QPushButton#conflictsRefreshButton,
QPushButton#conflictsEmptyRefreshButton {
    min-height: 36px;

    padding-left: 15px;
    padding-right: 15px;

    background-color: #20252d;

    color: #d8dce3;

    border: 1px solid #303742;
    border-radius: 7px;

    font-size: 11px;
    font-weight: 750;
}

QPushButton#conflictsRefreshButton:hover,
QPushButton#conflictsEmptyRefreshButton:hover {
    background-color: #292f39;

    color: #ffffff;

    border-color: #434c59;
}

QPushButton#conflictsRefreshButton:pressed,
QPushButton#conflictsEmptyRefreshButton:pressed {
    background-color: #1a1f26;
}


/* ============================================================
   SUMMARY
   ============================================================ */

QFrame#conflictsSummary {
    min-height: 62px;

    background-color: #171c22;

    border: 1px solid #2b323b;
    border-left: 3px solid #4f5966;
    border-radius: 11px;
}

QFrame#conflictsSummary[hasConflicts="true"] {
    background-color: #241e14;

    border: 1px solid #604721;
    border-left: 3px solid #e2a43a;
}

QLabel#conflictsSummaryIcon {
    background-color: #252c35;

    color: #98a4b4;

    border: 1px solid #343d48;
    border-radius: 19px;

    font-size: 16px;
    font-weight: 900;
}

QFrame#conflictsSummary[hasConflicts="true"]
QLabel#conflictsSummaryIcon {
    background-color: #443118;

    color: #ffc66d;

    border-color: #725021;
}

QLabel#conflictsSummaryTitle {
    background-color: transparent;

    color: #edf0f4;

    font-size: 13px;
    font-weight: 850;
}

QLabel#conflictsSummaryDescription {
    background-color: transparent;

    color: #828c99;

    font-size: 10px;
    font-weight: 600;
}

QLabel#conflictCount {
    min-width: 72px;
    min-height: 28px;

    padding-left: 10px;
    padding-right: 10px;

    background-color: #242a32;

    color: #aeb6c1;

    border: 1px solid #363e49;
    border-radius: 8px;

    font-size: 10px;
    font-weight: 850;
}

QLabel#conflictCount[hasConflicts="true"] {
    background-color: #443118;

    color: #ffc66d;

    border-color: #725021;
}


/* ============================================================
   SCROLL AREA
   ============================================================ */

QScrollArea#conflictsScroll {
    background-color: transparent;

    border: none;
}

QScrollArea#conflictsScroll > QWidget,
QScrollArea#conflictsScroll > QWidget > QWidget,
QWidget#conflictsContent {
    background-color: #101319;
}


/* ============================================================
   EMPTY STATE
   ============================================================ */

QFrame#conflictsEmptyCard {
    background-color: #14181e;

    border: 1px solid #282e37;
    border-radius: 12px;
}

QLabel#conflictsEmptyIcon {
    background-color: transparent;

    color: #57cf91;

    font-size: 42px;
    font-weight: 900;
}

QLabel#conflictsEmptyTitle {
    background-color: transparent;

    color: #edf1f4;

    font-size: 17px;
    font-weight: 850;
}

QLabel#conflictsEmpty {
    background-color: transparent;

    color: #7f8997;

    font-size: 11px;
}


/* ============================================================
   CONFLICT CARD
   ============================================================ */

QFrame#conflictCard {
    background-color: #181d24;

    border: 1px solid #303641;
    border-left: 3px solid #d89b38;
    border-radius: 11px;
}

QFrame#conflictCard:hover {
    background-color: #1c222a;

    border-color: #3a424e;
}


/* ------------------------------------------------------------
   Different conflict types
   ------------------------------------------------------------ */

QFrame#conflictCard[conflictKind="library"] {
    border-left-color: #d89b38;
}

QFrame#conflictCard[conflictKind="unmanaged_active"] {
    border-left-color: #8067ff;
}

QFrame#conflictCard[conflictKind="invalid_marker"] {
    border-left-color: #e25d6a;
}

QFrame#conflictCard[conflictKind="orphaned_managed"] {
    border-left-color: #4d9fea;
}


/* ============================================================
   CARD TEXT
   ============================================================ */

QLabel#conflictTitle {
    background-color: transparent;

    color: #f3f5f7;

    font-size: 13px;
    font-weight: 850;
}

QLabel#conflictType {
    min-height: 23px;

    padding-left: 9px;
    padding-right: 9px;

    background-color: #392b17;

    color: #f0b659;

    border: 1px solid #60471f;
    border-radius: 7px;

    font-size: 9px;
    font-weight: 850;
}


/* unmanaged */

QLabel#conflictType[conflictKind="unmanaged_active"] {
    background-color: #2a2445;

    color: #b5a7ff;

    border-color: #4a3d80;
}


/* invalid marker */

QLabel#conflictType[conflictKind="invalid_marker"] {
    background-color: #402026;

    color: #ff9aa4;

    border-color: #663139;
}


/* orphaned */

QLabel#conflictType[conflictKind="orphaned_managed"] {
    background-color: #172b3d;

    color: #8cc8ff;

    border-color: #285173;
}


QLabel#conflictMessage {
    background-color: transparent;

    color: #a9b0bb;

    font-size: 11px;
}


/* ============================================================
   PATH
   ============================================================ */

QLabel#conflictPath {
    min-height: 28px;

    padding: 7px 9px;

    background-color: #11151a;

    color: #8f99a7;

    border: 1px solid #29313a;
    border-radius: 7px;

    font-family: monospace;
    font-size: 10px;
}


/* ============================================================
   HASH PANEL
   ============================================================ */

QFrame#conflictHashPanel {
    background-color: #14191f;

    border: 1px solid #292f38;
    border-radius: 8px;
}


/* Checking */

QFrame#conflictHashPanel[hashState="checking"] {
    background-color: #201c14;

    border-color: #554321;
}


/* Duplicate */

QFrame#conflictHashPanel[hashState="duplicate"] {
    background-color: #142019;

    border-color: #28563e;
}


/* Unique */

QFrame#conflictHashPanel[hashState="unique"] {
    background-color: #151d25;

    border-color: #2b4961;
}


/* Error */

QFrame#conflictHashPanel[hashState="error"] {
    background-color: #25171a;

    border-color: #633039;
}


QLabel#conflictHashStatus {
    background-color: transparent;

    color: #c0c7d1;

    font-size: 10px;
    font-weight: 750;
}

QLabel#conflictHash {
    background-color: transparent;

    color: #818c99;

    font-family: monospace;
    font-size: 9px;
}

QLabel#conflictDuplicate {
    background-color: transparent;

    color: #69d39a;

    font-size: 10px;
    font-weight: 700;
}


/* ============================================================
   ACTION AREA
   ============================================================ */

QFrame#conflictActions {
    background-color: transparent;

    border: none;
}


/* ------------------------------------------------------------
   Normal action
   ------------------------------------------------------------ */

QPushButton#conflictCheckButton,
QPushButton#conflictOpenButton {
    min-height: 34px;

    padding-left: 13px;
    padding-right: 13px;

    background-color: #20262e;

    color: #ccd2da;

    border: 1px solid #303843;
    border-radius: 7px;

    font-size: 10px;
    font-weight: 750;
}

QPushButton#conflictCheckButton:hover,
QPushButton#conflictOpenButton:hover {
    background-color: #29313a;

    color: #ffffff;

    border-color: #424c59;
}


/* ------------------------------------------------------------
   Copy
   ------------------------------------------------------------ */

QPushButton#conflictCopyButton {
    min-height: 34px;

    padding-left: 14px;
    padding-right: 14px;

    background-color: #6651d7;

    color: #ffffff;

    border: 1px solid #7b66eb;
    border-radius: 7px;

    font-size: 10px;
    font-weight: 800;
}

QPushButton#conflictCopyButton:hover {
    background-color: #7560ea;

    border-color: #9180f5;
}


/* ------------------------------------------------------------
   Adopt
   ------------------------------------------------------------ */

QPushButton#conflictAdoptButton {
    min-height: 34px;

    padding-left: 13px;
    padding-right: 13px;

    background-color: #3d3018;

    color: #f1ba63;

    border: 1px solid #654b20;
    border-radius: 7px;

    font-size: 10px;
    font-weight: 800;
}

QPushButton#conflictAdoptButton:hover {
    background-color: #4c3a1b;

    border-color: #816028;
}


/* ------------------------------------------------------------
   Delete
   ------------------------------------------------------------ */

QPushButton#conflictDeleteButton {
    min-height: 34px;

    padding-left: 13px;
    padding-right: 13px;

    background-color: #3d2026;

    color: #ff9da7;

    border: 1px solid #67313b;
    border-radius: 7px;

    font-size: 10px;
    font-weight: 800;
}

QPushButton#conflictDeleteButton:hover {
    background-color: #512831;

    color: #ffb1b9;

    border-color: #82404b;
}


/* ------------------------------------------------------------
   Disabled
   ------------------------------------------------------------ */

QWidget#conflictsPage QPushButton:disabled {
    background-color: #181d23;

    color: #59616d;

    border-color: #252c34;
}
"""


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

        self._duplicate_error = ""

        # ====================================================
        # Widget
        # ====================================================

        self.setObjectName(
            "conflictCard"
        )

        self.setProperty(
            "conflictKind",
            conflict.kind.value,
        )

        # ====================================================
        # Labels
        # ====================================================

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

        # ====================================================
        # Buttons
        # ====================================================

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

        # ====================================================
        # Build
        # ====================================================

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
            14,
            16,
            14,
        )

        layout.setSpacing(
            9
        )

        # ====================================================
        # Header
        # ====================================================

        top = QHBoxLayout()

        top.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        top.setSpacing(
            10
        )

        self.title_label.setObjectName(
            "conflictTitle"
        )

        self.title_label.setWordWrap(
            True
        )

        top.addWidget(
            self.title_label,
            stretch=1,
        )

        self.type_label.setObjectName(
            "conflictType"
        )

        self.type_label.setProperty(
            "conflictKind",
            self.conflict.kind.value,
        )

        self.type_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        top.addWidget(
            self.type_label,
            alignment=(
                Qt.AlignmentFlag.AlignTop
                | Qt.AlignmentFlag.AlignRight
            ),
        )

        layout.addLayout(
            top
        )

        # ====================================================
        # Message
        # ====================================================

        self.message_label.setObjectName(
            "conflictMessage"
        )

        self.message_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.message_label
        )

        # ====================================================
        # Path
        # ====================================================

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

        # ====================================================
        # Hash / Duplicate Panel
        # ====================================================

        self.hash_frame = QFrame(
            self
        )

        self.hash_frame.setObjectName(
            "conflictHashPanel"
        )

        self.hash_frame.setProperty(
            "hashState",
            self._hash_state,
        )

        hash_layout = QVBoxLayout(
            self.hash_frame
        )

        hash_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        hash_layout.setSpacing(
            5
        )

        self.hash_status_label.setObjectName(
            "conflictHashStatus"
        )

        self.hash_status_label.setWordWrap(
            True
        )

        hash_layout.addWidget(
            self.hash_status_label
        )

        # ----------------------------------------------------
        # CRC
        # ----------------------------------------------------

        self.crc_label.setObjectName(
            "conflictHash"
        )

        self.crc_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        hash_layout.addWidget(
            self.crc_label
        )

        # ----------------------------------------------------
        # SHA
        # ----------------------------------------------------

        self.sha_label.setObjectName(
            "conflictHash"
        )

        self.sha_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        hash_layout.addWidget(
            self.sha_label
        )

        # ----------------------------------------------------
        # Duplicate
        # ----------------------------------------------------

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
            self.hash_frame
        )

        # ====================================================
        # Actions
        # ====================================================

        self.actions_frame = QFrame(
            self
        )

        self.actions_frame.setObjectName(
            "conflictActions"
        )

        actions_layout = QVBoxLayout(
            self.actions_frame
        )

        actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        actions_layout.setSpacing(
            6
        )

        # ----------------------------------------------------
        # First row
        # ----------------------------------------------------

        first_row = QHBoxLayout()

        first_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        first_row.setSpacing(
            7
        )

        self.check_button.setObjectName(
            "conflictCheckButton"
        )

        self.copy_button.setObjectName(
            "conflictCopyButton"
        )

        first_row.addWidget(
            self.check_button
        )

        first_row.addWidget(
            self.copy_button
        )

        first_row.addStretch(
            1
        )

        actions_layout.addLayout(
            first_row
        )

        # ----------------------------------------------------
        # Second row
        # ----------------------------------------------------

        second_row = QHBoxLayout()

        second_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        second_row.setSpacing(
            7
        )

        self.open_button.setObjectName(
            "conflictOpenButton"
        )

        self.adopt_button.setObjectName(
            "conflictAdoptButton"
        )

        self.delete_button.setObjectName(
            "conflictDeleteButton"
        )

        second_row.addWidget(
            self.open_button
        )

        if self.conflict.can_adopt:
            second_row.addWidget(
                self.adopt_button
            )

        else:
            self.adopt_button.hide()

        second_row.addWidget(
            self.delete_button
        )

        second_row.addStretch(
            1
        )

        self.delete_button.hide()

        actions_layout.addLayout(
            second_row
        )

        layout.addWidget(
            self.actions_frame
        )

        # ====================================================
        # Signals
        # ====================================================

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
        result = (
            self._duplicate_result
        )

        if result is None:
            return

        if not result.is_duplicate:
            return

        self.delete_duplicate_requested.emit(
            self.conflict,
            result,
        )

    # ========================================================
    # Hash State
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

        self._duplicate_error = ""

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

        self._duplicate_error = ""

        self._hash_state = (
            "duplicate"
            if result.is_duplicate
            else "unique"
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

        self._duplicate_error = (
            message
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

        self.retranslate_ui()

    # ========================================================
    # Visual State
    # ========================================================

    def _refresh_hash_style(
        self,
    ) -> None:
        self.hash_frame.setProperty(
            "hashState",
            self._hash_state,
        )

        self.hash_frame.style().unpolish(
            self.hash_frame
        )

        self.hash_frame.style().polish(
            self.hash_frame
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        # ====================================================
        # Type
        # ====================================================

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

        # ====================================================
        # Message
        # ====================================================

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

        # ====================================================
        # Buttons
        # ====================================================

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

        # ====================================================
        # Hash Status
        # ====================================================

        if self._hash_state == "idle":
            self.hash_status_label.setText(
                tr(
                    "conflicts.hash.idle"
                )
            )

            self.crc_label.clear()
            self.sha_label.clear()
            self.duplicate_label.clear()

        elif self._hash_state == "checking":
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

            self.crc_label.clear()
            self.sha_label.clear()
            self.duplicate_label.clear()

        elif self._hash_state in {
            "duplicate",
            "unique",
        }:
            result = (
                self._duplicate_result
            )

            if result is not None:
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

        elif self._hash_state == "error":
            self.hash_status_label.setText(
                tr(
                    "conflicts.hash.failed"
                )
            )

            self.crc_label.clear()
            self.sha_label.clear()

            self.duplicate_label.setText(
                self._duplicate_error
            )

        self._refresh_hash_style()


# ============================================================
# Conflicts Page
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

        # ====================================================
        # Providers
        # ====================================================

        self.library_paths_provider = (
            library_paths_provider
        )

        self.game_id_provider = (
            game_id_provider
        )

        self.active_root_provider = (
            active_root_provider
        )

        # ====================================================
        # State
        # ====================================================

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

        # ====================================================
        # Services
        # ====================================================

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.duplicate_service = (
            ModDuplicateService()
        )

        # ====================================================
        # Header
        # ====================================================

        self.title_label = QLabel(
            self
        )

        self.description_label = QLabel(
            self
        )

        self.refresh_button = QPushButton(
            self
        )

        # ====================================================
        # Summary
        # ====================================================

        self.summary_frame = QFrame(
            self
        )

        self.summary_frame.setObjectName(
            "conflictsSummary"
        )

        self.summary_icon_label = QLabel(
            self.summary_frame
        )

        self.summary_icon_label.setObjectName(
            "conflictsSummaryIcon"
        )

        self.summary_title_label = QLabel(
            self.summary_frame
        )

        self.summary_title_label.setObjectName(
            "conflictsSummaryTitle"
        )

        self.summary_description_label = QLabel(
            self.summary_frame
        )

        self.summary_description_label.setObjectName(
            "conflictsSummaryDescription"
        )

        self.summary_description_label.setWordWrap(
            True
        )

        self.count_label = QLabel(
            self.summary_frame
        )

        # ====================================================
        # Empty State
        # ====================================================

        self.empty_frame = QFrame(
            self
        )

        self.empty_frame.setObjectName(
            "conflictsEmptyCard"
        )

        self.empty_icon_label = QLabel(
            self.empty_frame
        )

        self.empty_icon_label.setObjectName(
            "conflictsEmptyIcon"
        )

        self.empty_title_label = QLabel(
            self.empty_frame
        )

        self.empty_title_label.setObjectName(
            "conflictsEmptyTitle"
        )

        self.empty_label = QLabel(
            self.empty_frame
        )

        self.empty_refresh_button = QPushButton(
            self.empty_frame
        )

        self.empty_refresh_button.setObjectName(
            "conflictsEmptyRefreshButton"
        )

        # ====================================================
        # Conflict List
        # ====================================================

        self.scroll_area = QScrollArea(
            self
        )

        self.scroll_area.setObjectName(
            "conflictsScroll"
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

        # ====================================================
        # Build
        # ====================================================

        self._build_ui()

        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self.set_report(
            ConflictReport()
        )

    # ========================================================
    # Stylesheet
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        """
        Lädt zuerst das Library-Stylesheet
        und ergänzt danach die Conflict-spezifischen Styles.

        Dadurch bleibt die Seite auch unter Windows vollständig
        dunkel und unabhängig von der nativen Qt-Palette.
        """

        style_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "styles"
            / "library.qss"
        )

        try:
            base_stylesheet = (
                style_path.read_text(
                    encoding="utf-8"
                )
            )

        except OSError:
            base_stylesheet = ""

        self.setStyleSheet(
            base_stylesheet
            + "\n"
            + CONFLICTS_PAGE_QSS
        )

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
            22,
            20,
            22,
            16,
        )

        layout.setSpacing(
            14
        )

        # ====================================================
        # Header
        # ====================================================

        header = QHBoxLayout()

        header.setContentsMargins(
            2,
            2,
            2,
            2,
        )

        header.setSpacing(
            18
        )

        # ----------------------------------------------------
        # Header text
        # ----------------------------------------------------

        texts = QVBoxLayout()

        texts.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        texts.setSpacing(
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

        # ----------------------------------------------------
        # Refresh
        # ----------------------------------------------------

        header_actions = QFrame(
            self
        )

        header_actions.setObjectName(
            "conflictsHeaderActions"
        )

        header_actions_layout = (
            QHBoxLayout(
                header_actions
            )
        )

        header_actions_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        self.refresh_button.setObjectName(
            "conflictsRefreshButton"
        )

        self.refresh_button.setMinimumHeight(
            40
        )

        self.refresh_button.setMinimumWidth(
            120
        )

        header_actions_layout.addWidget(
            self.refresh_button
        )

        header.addWidget(
            header_actions,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        layout.addLayout(
            header
        )

        # ====================================================
        # Summary Card
        # ====================================================

        summary_layout = QHBoxLayout(
            self.summary_frame
        )

        summary_layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )

        summary_layout.setSpacing(
            12
        )

        self.summary_icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.summary_icon_label.setFixedSize(
            38,
            38,
        )

        summary_layout.addWidget(
            self.summary_icon_label,
            alignment=(
                Qt.AlignmentFlag.AlignVCenter
            ),
        )

        # ----------------------------------------------------
        # Summary text
        # ----------------------------------------------------

        summary_texts = QVBoxLayout()

        summary_texts.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        summary_texts.setSpacing(
            2
        )

        summary_texts.addWidget(
            self.summary_title_label
        )

        summary_texts.addWidget(
            self.summary_description_label
        )

        summary_layout.addLayout(
            summary_texts,
            stretch=1,
        )

        # ----------------------------------------------------
        # Count
        # ----------------------------------------------------

        self.count_label.setObjectName(
            "conflictCount"
        )

        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        summary_layout.addWidget(
            self.count_label,
            alignment=(
                Qt.AlignmentFlag.AlignVCenter
            ),
        )

        layout.addWidget(
            self.summary_frame
        )

        # ====================================================
        # Empty State
        # ====================================================

        empty_layout = QVBoxLayout(
            self.empty_frame
        )

        empty_layout.setContentsMargins(
            32,
            36,
            32,
            36,
        )

        empty_layout.setSpacing(
            8
        )

        empty_layout.addStretch(
            1
        )

        # ----------------------------------------------------
        # Icon
        # ----------------------------------------------------

        self.empty_icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_icon_label.setText(
            "✓"
        )

        empty_layout.addWidget(
            self.empty_icon_label
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        self.empty_title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        empty_layout.addWidget(
            self.empty_title_label
        )

        # ----------------------------------------------------
        # Description
        # ----------------------------------------------------

        self.empty_label.setObjectName(
            "conflictsEmpty"
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setWordWrap(
            True
        )

        empty_layout.addWidget(
            self.empty_label
        )

        empty_layout.addSpacing(
            10
        )

        # ----------------------------------------------------
        # Refresh
        # ----------------------------------------------------

        self.empty_refresh_button.setMinimumHeight(
            36
        )

        self.empty_refresh_button.setMinimumWidth(
            130
        )

        empty_layout.addWidget(
            self.empty_refresh_button,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        empty_layout.addStretch(
            1
        )

        layout.addWidget(
            self.empty_frame,
            stretch=1,
        )

        # ====================================================
        # Scroll Area
        # ====================================================

        self.content_layout.setContentsMargins(
            0,
            0,
            8,
            18,
        )

        self.content_layout.setSpacing(
            12
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

        layout.addWidget(
            self.scroll_area,
            stretch=1,
        )

        # ====================================================
        # Connections
        # ====================================================

        self.refresh_button.clicked.connect(
            self.refresh_requested
        )

        self.empty_refresh_button.clicked.connect(
            self.refresh_requested
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

        # ====================================================
        # Build Cards
        # ====================================================

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
            )

        # ====================================================
        # Page State
        # ====================================================

        has_conflicts = bool(
            report.items
        )

        self.summary_frame.setProperty(
            "hasConflicts",
            has_conflicts,
        )

        self.count_label.setProperty(
            "hasConflicts",
            has_conflicts,
        )

        # ----------------------------------------------------
        # Force QSS update
        # ----------------------------------------------------

        for widget in (
            self.summary_frame,
            self.count_label,
        ):
            widget.style().unpolish(
                widget
            )

            widget.style().polish(
                widget
            )

        # ----------------------------------------------------
        # Content
        # ----------------------------------------------------

        self.scroll_area.setVisible(
            has_conflicts
        )

        self.empty_frame.setVisible(
            not has_conflicts
        )

        self.retranslate_ui()

    # ========================================================
    # Clear Cards
    # ========================================================

    def _clear_cards(
        self,
    ) -> None:
        cards = tuple(
            self._cards
        )

        self._cards.clear()

        self._card_by_key.clear()

        for card in cards:
            if not isValid(
                card
            ):
                continue

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

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------

        card.set_checking()

        # ----------------------------------------------------
        # Worker
        # ----------------------------------------------------

        worker = ModDuplicateWorker(
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

    # ========================================================
    # Duplicate Progress
    # ========================================================

    def _on_duplicate_progress(
        self,
        source_key: str,
        current: int,
        total: int,
        name: str,
    ) -> None:
        card = (
            self._card_for_source(
                source_key
            )
        )

        if card is None:
            return

        card.set_progress(
            current=current,
            total=total,
            name=name,
        )

    # ========================================================
    # Duplicate Finished
    # ========================================================

    def _on_duplicate_finished(
        self,
        worker: ModDuplicateWorker,
        result: DuplicateCheckResult,
    ) -> None:
        self._workers.discard(
            worker
        )

        source_key = str(
            result.source
            .expanduser()
            .absolute()
        )

        card = (
            self._card_for_source(
                source_key
            )
        )

        if card is None:
            return

        card.set_duplicate_result(
            result
        )

    # ========================================================
    # Duplicate Failed
    # ========================================================

    def _on_duplicate_failed(
        self,
        worker: ModDuplicateWorker,
        source_key: str,
        message: str,
    ) -> None:
        self._workers.discard(
            worker
        )

        card = (
            self._card_for_source(
                source_key
            )
        )

        if card is None:
            return

        card.set_duplicate_error(
            message
        )

    # ========================================================
    # Card Lookup
    # ========================================================

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

        # ----------------------------------------------------
        # Confirmation
        # ----------------------------------------------------

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
                QMessageBox
                .StandardButton
                .Yes
                |
                QMessageBox
                .StandardButton
                .No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        # ----------------------------------------------------
        # Delete
        # ----------------------------------------------------

        try:
            (
                self.duplicate_service
                .delete_confirmed_duplicate(
                    result=result,
                    active_root=(
                        self.active_root_provider()
                    ),
                )
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

        # ----------------------------------------------------
        # Completed
        # ----------------------------------------------------

        QMessageBox.information(
            self,
            tr(
                "conflicts.delete.completed.title"
            ),
            tr(
                "conflicts.delete.completed.message"
            ),
        )

        # Der Zustand im Mods-Ordner hat sich geändert.
        self.rescan_requested.emit()

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        count = (
            self._report.count
        )

        has_conflicts = (
            count > 0
        )

        # ====================================================
        # Header
        # ====================================================

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
            "↻  "
            + tr(
                "conflicts.refresh"
            )
        )

        # ====================================================
        # Summary
        # ====================================================

        if has_conflicts:
            self.summary_icon_label.setText(
                "!"
            )

            self.summary_title_label.setText(
                tr(
                    "conflicts.count",
                    count=count,
                )
            )

        else:
            self.summary_icon_label.setText(
                "✓"
            )

            self.summary_title_label.setText(
                tr(
                    "conflicts.empty"
                )
            )

        self.summary_description_label.setText(
            tr(
                "conflicts.description"
            )
        )

        # ====================================================
        # Count
        # ====================================================

        self.count_label.setText(
            tr(
                "conflicts.count",
                count=count,
            )
        )

        # ====================================================
        # Empty State
        # ====================================================

        self.empty_title_label.setText(
            tr(
                "conflicts.empty"
            )
        )

        self.empty_label.setText(
            tr(
                "conflicts.description"
            )
        )

        self.empty_refresh_button.setText(
            "↻  "
            + tr(
                "conflicts.refresh"
            )
        )

        # ====================================================
        # Cards
        # ====================================================

        for card in (
            self._cards
        ):
            if isValid(
                card
            ):
                card.retranslate_ui()


__all__ = [
    "ConflictsPage",
]