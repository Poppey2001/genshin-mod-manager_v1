from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from shiboken6 import isValid

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
# Conflict Card
# ============================================================

class ConflictCard(QFrame):
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

        # Jede Karte besitzt absichtlich ihr
        # eigenes ConflictItem.
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

        self.check_button = QPushButton()

        self.copy_button = QPushButton()

        self.open_button = QPushButton()

        self.adopt_button = QPushButton()

        self.delete_button = QPushButton()

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
            18,
            16,
            18,
            16,
        )

        layout.setSpacing(
            9
        )

        # ====================================================
        # Header
        # ====================================================

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

        # ====================================================
        # Description
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
        # Hash
        # ====================================================

        self.hash_status_label.setObjectName(
            "conflictHashStatus"
        )

        self.hash_status_label.setWordWrap(
            True
        )

        layout.addWidget(
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

        layout.addWidget(
            self.crc_label
        )

        layout.addWidget(
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

        layout.addWidget(
            self.duplicate_label
        )

        # ====================================================
        # Actions
        # ====================================================

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

        actions.addWidget(
            self.open_button
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

        # ====================================================
        # Connections
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
    # Requests
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
        # Immer exakt das ConflictItem DIESER Karte.
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
        if self._duplicate_result is None:
            return

        self.delete_duplicate_requested.emit(
            self.conflict,
            self._duplicate_result,
        )

    # ========================================================
    # Duplicate UI
    # ========================================================

    def set_checking(
        self,
    ) -> None:
        self._hash_state = (
            "checking"
        )

        self._duplicate_result = None

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
        self._duplicate_result = result

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
        self._duplicate_result = None

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
                            result.duplicate_path
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
                pass


# ============================================================
# Conflicts Page
# ============================================================

class ConflictsPage(QWidget):
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
            tuple[Path, ...],
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

        # ====================================================
        # Widgets
        # ====================================================

        self.title_label = QLabel()

        self.description_label = QLabel()

        self.count_label = QLabel()

        self.refresh_button = QPushButton()

        self.empty_label = QLabel()

        self.scroll_area = QScrollArea()

        self.content = QWidget()

        self.content_layout = (
            QVBoxLayout(
                self.content
            )
        )

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

        self.set_report(
            ConflictReport()
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
            28,
            24,
            28,
            24,
        )

        layout.setSpacing(
            16
        )

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

        self.refresh_button.setObjectName(
            "secondaryButton"
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

        # ====================================================
        # Empty
        # ====================================================

        self.empty_label.setObjectName(
            "conflictsEmpty"
        )

        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.empty_label,
            stretch=1,
        )

        # ====================================================
        # Scroll
        # ====================================================

        self.content_layout.setContentsMargins(
            0,
            0,
            8,
            16,
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

        self.refresh_button.clicked.connect(
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

        for conflict in report.items:
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

        has_conflicts = bool(
            report.items
        )

        self.scroll_area.setVisible(
            has_conflicts
        )

        self.empty_label.setVisible(
            not has_conflicts
        )

        self.retranslate_ui()

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
            or not isValid(card)
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

        worker = ModDuplicateWorker(
            source=path,
            library_paths=tuple(
                self.library_paths_provider()
            ),
            game_id=(
                self.game_id_provider()
            ),
            service=self.duplicate_service,
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

    def _on_duplicate_finished(
        self,
        worker: ModDuplicateWorker,
        result: DuplicateCheckResult,
    ) -> None:
        self._workers.discard(
            worker
        )

        card = (
            self._card_for_source(
                str(
                    result.source
                    .expanduser()
                    .absolute()
                )
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

        for card in self._cards:
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
                source=result.source,
                library=duplicate_path,
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
                    error=error,
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

        self.empty_label.setText(
            tr(
                "conflicts.empty"
            )
        )

        self.count_label.setText(
            tr(
                "conflicts.count",
                count=self._report.count,
            )
        )

        for card in self._cards:
            if isValid(
                card
            ):
                card.retranslate_ui()


__all__ = [
    "ConflictsPage",
]