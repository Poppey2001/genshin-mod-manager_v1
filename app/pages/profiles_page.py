from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QThreadPool,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import (
    tr,
    translation_manager,
)
from app.models.mod import ModInfo
from app.models.profile import (
    ModProfile,
    ProfileApplyResult,
)
from app.services.mod_manager import (
    ModManager,
    ModState,
)
from app.services.profile_service import (
    ProfileAlreadyExistsError,
    ProfileError,
    ProfileService,
)
from app.widgets.profiles.profile_card import (
    ProfileCard,
)
from app.workers.profile_apply_worker import (
    ProfileApplyWorker,
)


ModsProvider = Callable[[], tuple[ModInfo, ...]]
StateProvider = Callable[[Path], ModState]
ModManagerProvider = Callable[[], ModManager]
StringProvider = Callable[[], str]
BoolProvider = Callable[[], bool]
VoidCallback = Callable[[], object]


class ProfilesPage(
    QWidget
):
    """
    Verwaltet persistente Mod-Profile für das aktuell ausgewählte Spiel.

    Profile speichern nur Zustände von Library-Mods, die sicher vom
    Mod Manager verwaltet werden können. Unmanaged Konflikte werden weder
    gespeichert noch bei einem Profilwechsel automatisch übernommen.
    """

    profile_activated = Signal(
        str
    )
    busy_changed = Signal(
        bool
    )

    def __init__(
        self,
        *,
        config: AppConfig,
        profile_service: ProfileService,
        game_id_provider: StringProvider,
        mods_provider: ModsProvider,
        state_provider: StateProvider,
        mod_manager_provider: ModManagerProvider,
        operation_busy_provider: BoolProvider,
        scan_callback: VoidCallback,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "profilesPage"
        )

        self.config = config
        self.profile_service = profile_service
        self.game_id_provider = game_id_provider
        self.mods_provider = mods_provider
        self.state_provider = state_provider
        self.mod_manager_provider = mod_manager_provider
        self.operation_busy_provider = operation_busy_provider
        self.scan_callback = scan_callback

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self._cards: list[
            ProfileCard
        ] = []
        self._profiles: tuple[
            ModProfile,
            ...,
        ] = ()
        self._worker: (
            ProfileApplyWorker
            | None
        ) = None
        self._applying_profile: (
            ModProfile
            | None
        ) = None
        self._busy = False
        self._current_columns = 0

        # ====================================================
        # Header
        # ====================================================

        self.title_label = QLabel(
            self
        )
        self.description_label = QLabel(
            self
        )

        self.new_button = QPushButton(
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
        self.summary_title_label = QLabel(
            self.summary_frame
        )
        self.summary_value_label = QLabel(
            self.summary_frame
        )
        self.summary_count_label = QLabel(
            self.summary_frame
        )

        # ====================================================
        # Empty state
        # ====================================================

        self.empty_frame = QFrame(
            self
        )
        self.empty_icon_label = QLabel(
            self.empty_frame
        )
        self.empty_title_label = QLabel(
            self.empty_frame
        )
        self.empty_description_label = QLabel(
            self.empty_frame
        )
        self.empty_new_button = QPushButton(
            self.empty_frame
        )

        # ====================================================
        # Cards
        # ====================================================

        self.scroll_area = QScrollArea(
            self
        )
        self.cards_content = QWidget()
        self.cards_grid = QGridLayout(
            self.cards_content
        )

        # ====================================================
        # Operation
        # ====================================================

        self.operation_frame = QFrame(
            self
        )
        self.operation_label = QLabel(
            self.operation_frame
        )
        self.operation_progress = QProgressBar(
            self.operation_frame
        )
        self.cancel_button = QPushButton(
            self.operation_frame
        )

        self._build_ui()
        self._connect_signals()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self.refresh()

    # ========================================================
    # UI
    # ========================================================

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

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = QHBoxLayout()
        header.setContentsMargins(
            2,
            2,
            2,
            2,
        )
        header.setSpacing(
            16
        )

        header_text = QVBoxLayout()
        header_text.setContentsMargins(
            0,
            0,
            0,
            0,
        )
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

        actions = QFrame(
            self
        )
        actions.setObjectName(
            "profilesHeaderActions"
        )
        actions_layout = QHBoxLayout(
            actions
        )
        actions_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )
        actions_layout.setSpacing(
            6
        )

        self.refresh_button.setObjectName(
            "profilesRefreshButton"
        )
        self.new_button.setObjectName(
            "profilesNewButton"
        )

        self.refresh_button.setMinimumHeight(
            40
        )
        self.new_button.setMinimumHeight(
            40
        )

        actions_layout.addWidget(
            self.refresh_button
        )
        actions_layout.addWidget(
            self.new_button
        )

        header.addWidget(
            actions,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
        )

        root.addLayout(
            header
        )

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        self.summary_frame.setObjectName(
            "profilesSummary"
        )
        summary_layout = QHBoxLayout(
            self.summary_frame
        )
        summary_layout.setContentsMargins(
            16,
            11,
            16,
            11,
        )
        summary_layout.setSpacing(
            10
        )

        summary_text = QVBoxLayout()
        summary_text.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        summary_text.setSpacing(
            2
        )

        self.summary_title_label.setObjectName(
            "profilesSummaryTitle"
        )
        self.summary_value_label.setObjectName(
            "profilesSummaryValue"
        )
        self.summary_count_label.setObjectName(
            "profilesSummaryCount"
        )
        self.summary_count_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        summary_text.addWidget(
            self.summary_title_label
        )
        summary_text.addWidget(
            self.summary_value_label
        )

        summary_layout.addLayout(
            summary_text,
            stretch=1,
        )
        summary_layout.addWidget(
            self.summary_count_label,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        root.addWidget(
            self.summary_frame
        )

        # ----------------------------------------------------
        # Empty state
        # ----------------------------------------------------

        self.empty_frame.setObjectName(
            "profilesEmptyState"
        )
        empty_layout = QVBoxLayout(
            self.empty_frame
        )
        empty_layout.setContentsMargins(
            32,
            42,
            32,
            42,
        )
        empty_layout.setSpacing(
            8
        )

        empty_layout.addStretch(
            1
        )

        self.empty_icon_label.setObjectName(
            "profilesEmptyIcon"
        )
        self.empty_icon_label.setText(
            "◇"
        )
        self.empty_icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_title_label.setObjectName(
            "profilesEmptyTitle"
        )
        self.empty_title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.empty_description_label.setObjectName(
            "profilesEmptyDescription"
        )
        self.empty_description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.empty_description_label.setWordWrap(
            True
        )

        self.empty_new_button.setObjectName(
            "profilesNewButton"
        )
        self.empty_new_button.setMinimumHeight(
            38
        )

        empty_layout.addWidget(
            self.empty_icon_label
        )
        empty_layout.addWidget(
            self.empty_title_label
        )
        empty_layout.addWidget(
            self.empty_description_label
        )
        empty_layout.addSpacing(
            8
        )
        empty_layout.addWidget(
            self.empty_new_button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        empty_layout.addStretch(
            1
        )

        root.addWidget(
            self.empty_frame,
            stretch=1,
        )

        # ----------------------------------------------------
        # Profile cards
        # ----------------------------------------------------

        self.scroll_area.setObjectName(
            "profilesScrollArea"
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

        self.cards_content.setObjectName(
            "profilesCardsContent"
        )
        self.cards_grid.setContentsMargins(
            0,
            0,
            8,
            12,
        )
        self.cards_grid.setHorizontalSpacing(
            12
        )
        self.cards_grid.setVerticalSpacing(
            12
        )

        self.scroll_area.setWidget(
            self.cards_content
        )

        root.addWidget(
            self.scroll_area,
            stretch=1,
        )

        # ----------------------------------------------------
        # Operation bar
        # ----------------------------------------------------

        self.operation_frame.setObjectName(
            "profilesOperationBar"
        )
        operation_layout = QHBoxLayout(
            self.operation_frame
        )
        operation_layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )
        operation_layout.setSpacing(
            10
        )

        self.operation_label.setObjectName(
            "profilesOperationLabel"
        )
        self.operation_progress.setObjectName(
            "profilesOperationProgress"
        )
        self.operation_progress.setMinimumWidth(
            260
        )
        self.operation_progress.setTextVisible(
            True
        )

        self.cancel_button.setObjectName(
            "profilesCancelButton"
        )

        operation_layout.addWidget(
            self.operation_label,
            stretch=1,
        )
        operation_layout.addWidget(
            self.operation_progress
        )
        operation_layout.addWidget(
            self.cancel_button
        )

        self.operation_frame.hide()

        root.addWidget(
            self.operation_frame
        )

    def _connect_signals(
        self,
    ) -> None:
        self.new_button.clicked.connect(
            self._create_profile
        )
        self.empty_new_button.clicked.connect(
            self._create_profile
        )
        self.refresh_button.clicked.connect(
            self.refresh
        )
        self.cancel_button.clicked.connect(
            self.cancel_apply
        )

    # ========================================================
    # Public API
    # ========================================================

    def is_applying(
        self,
    ) -> bool:
        return self._worker is not None

    def can_change_game(
        self,
    ) -> bool:
        return not self.is_applying()

    def on_game_changed(
        self,
        _game_id: str,
    ) -> None:
        if self.is_applying():
            return

        self.refresh()

    def refresh(
        self,
    ) -> None:
        if self.is_applying():
            return

        game_id = self._game_id()

        try:
            self._profiles = (
                self.profile_service
                .list_profiles(
                    game_id
                )
            )
        except ProfileError as error:
            QMessageBox.critical(
                self,
                tr(
                    "profiles.error.title"
                ),
                str(error),
            )
            self._profiles = ()

        self._rebuild_cards()
        self._refresh_summary()
        self._refresh_empty_state()

    def cancel_apply(
        self,
    ) -> None:
        worker = self._worker

        if worker is None:
            return

        worker.cancel()
        self.cancel_button.setEnabled(
            False
        )
        self.operation_label.setText(
            tr(
                "profiles.status.cancelling"
            )
        )

    # ========================================================
    # Create / Save / Rename / Delete
    # ========================================================

    def _create_profile(
        self,
        _checked: bool = False,
    ) -> None:
        if not self._prepare_edit_operation():
            return

        name, accepted = QInputDialog.getText(
            self,
            tr(
                "profiles.dialog.create.title"
            ),
            tr(
                "profiles.dialog.create.label"
            ),
        )

        if not accepted:
            return

        name = name.strip()

        if not name:
            return

        mods = tuple(
            self.mods_provider()
        )

        if not self._has_capturable_mods(
            mods
        ):
            self._show_no_capturable_mods()
            return

        try:
            profile = (
                self.profile_service
                .capture_profile(
                    name=name,
                    game_id=self._game_id(),
                    mods=mods,
                    state_provider=self.state_provider,
                    overwrite=False,
                )
            )
        except ProfileAlreadyExistsError:
            QMessageBox.warning(
                self,
                tr(
                    "profiles.warning.title"
                ),
                tr(
                    "profiles.warning.name_exists",
                    name=name,
                ),
            )
            return
        except ProfileError as error:
            self._show_profile_error(
                error
            )
            return

        self._set_selected_profile(
            profile.name
        )
        self.refresh()

    def _save_current_profile(
        self,
        profile: ModProfile,
    ) -> None:
        if not self._prepare_edit_operation():
            return

        answer = QMessageBox.question(
            self,
            tr(
                "profiles.dialog.overwrite.title"
            ),
            tr(
                "profiles.dialog.overwrite.message",
                name=profile.name,
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        mods = tuple(
            self.mods_provider()
        )

        if not self._has_capturable_mods(
            mods
        ):
            self._show_no_capturable_mods()
            return

        try:
            self.profile_service.capture_profile(
                name=profile.name,
                game_id=self._game_id(),
                mods=mods,
                state_provider=self.state_provider,
                overwrite=True,
            )
        except ProfileError as error:
            self._show_profile_error(
                error
            )
            return

        self._set_selected_profile(
            profile.name
        )
        self.refresh()

    def _rename_profile(
        self,
        profile: ModProfile,
    ) -> None:
        if not self._prepare_edit_operation():
            return

        new_name, accepted = QInputDialog.getText(
            self,
            tr(
                "profiles.dialog.rename.title"
            ),
            tr(
                "profiles.dialog.rename.label"
            ),
            text=profile.name,
        )

        if not accepted:
            return

        new_name = new_name.strip()

        if (
            not new_name
            or new_name == profile.name
        ):
            return

        try:
            renamed = (
                self.profile_service
                .rename_profile(
                    game_id=self._game_id(),
                    old_name=profile.name,
                    new_name=new_name,
                )
            )
        except ProfileAlreadyExistsError:
            QMessageBox.warning(
                self,
                tr(
                    "profiles.warning.title"
                ),
                tr(
                    "profiles.warning.name_exists",
                    name=new_name,
                ),
            )
            return
        except ProfileError as error:
            self._show_profile_error(
                error
            )
            return

        if (
            self.config.selected_profile
            == profile.name
        ):
            self._set_selected_profile(
                renamed.name
            )

        self.refresh()

    def _delete_profile(
        self,
        profile: ModProfile,
    ) -> None:
        if not self._prepare_edit_operation():
            return

        answer = QMessageBox.question(
            self,
            tr(
                "profiles.dialog.delete.title"
            ),
            tr(
                "profiles.dialog.delete.message",
                name=profile.name,
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
            self.profile_service.delete_profile(
                game_id=self._game_id(),
                name=profile.name,
            )
        except ProfileError as error:
            self._show_profile_error(
                error
            )
            return

        if (
            self.config.selected_profile
            == profile.name
        ):
            self._set_selected_profile(
                "Default"
            )

        self.refresh()

    # ========================================================
    # Apply
    # ========================================================

    def _activate_profile(
        self,
        profile: ModProfile,
    ) -> None:
        if self.is_applying():
            return

        if self.operation_busy_provider():
            self._show_busy_warning()
            return

        current_game = self._game_id()

        if profile.game_id != current_game:
            QMessageBox.warning(
                self,
                tr(
                    "profiles.warning.title"
                ),
                tr(
                    "profiles.warning.game_mismatch"
                ),
            )
            return

        answer = QMessageBox.question(
            self,
            tr(
                "profiles.dialog.activate.title"
            ),
            tr(
                "profiles.dialog.activate.message",
                name=profile.name,
                total=profile.total_count,
                enabled=profile.enabled_count,
                disabled=profile.disabled_count,
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.Yes,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        mods = tuple(
            self.mods_provider()
        )

        worker = ProfileApplyWorker(
            profile=profile,
            mods=mods,
            mod_manager=(
                self.mod_manager_provider()
            ),
        )

        worker.signals.progress.connect(
            self._on_apply_progress
        )
        worker.signals.finished.connect(
            self._on_apply_finished
        )
        worker.signals.failed.connect(
            self._on_apply_failed
        )

        self._worker = worker
        self._applying_profile = profile

        self._set_busy(
            True
        )

        total = max(
            profile.total_count,
            1,
        )
        self.operation_progress.setRange(
            0,
            total,
        )
        self.operation_progress.setValue(
            0
        )
        self.operation_progress.setFormat(
            f"0/{profile.total_count}"
        )
        self.operation_label.setText(
            tr(
                "profiles.status.applying",
                name=profile.name,
            )
        )
        self.cancel_button.setEnabled(
            True
        )
        self.operation_frame.show()

        self.thread_pool.start(
            worker
        )

    def _on_apply_progress(
        self,
        current: int,
        total: int,
        name: str,
    ) -> None:
        total_for_bar = max(
            total,
            1,
        )

        self.operation_progress.setRange(
            0,
            total_for_bar,
        )
        self.operation_progress.setValue(
            min(
                current,
                total_for_bar,
            )
        )
        self.operation_progress.setFormat(
            f"{current}/{total}"
        )
        self.operation_label.setText(
            tr(
                "profiles.status.progress",
                current=current,
                total=total,
                name=name,
            )
        )

    def _on_apply_finished(
        self,
        result: ProfileApplyResult,
    ) -> None:
        profile = self._applying_profile

        self._finish_apply_ui()

        if result.cancelled:
            QMessageBox.information(
                self,
                tr(
                    "profiles.result.title"
                ),
                tr(
                    "profiles.status.cancelled"
                ),
            )
        elif result.has_warnings:
            QMessageBox.warning(
                self,
                tr(
                    "profiles.result.title"
                ),
                tr(
                    "profiles.result.warning",
                    changed=result.changed_count,
                    unchanged=result.unchanged_count,
                    missing=result.missing_count,
                    blocked=result.blocked_count,
                    failed=result.failed_count,
                ),
            )
        else:
            profile_name = (
                profile.name
                if profile is not None
                else result.profile_name
            )

            self._set_selected_profile(
                profile_name
            )
            self.profile_activated.emit(
                profile_name
            )

            QMessageBox.information(
                self,
                tr(
                    "profiles.result.title"
                ),
                tr(
                    "profiles.result.success",
                    name=profile_name,
                    changed=result.changed_count,
                    unchanged=result.unchanged_count,
                ),
            )

        self.refresh()
        QTimer.singleShot(
            0,
            self.scan_callback,
        )

    def _on_apply_failed(
        self,
        message: str,
    ) -> None:
        self._finish_apply_ui()

        QMessageBox.critical(
            self,
            tr(
                "profiles.error.title"
            ),
            tr(
                "profiles.error.apply_failed",
                error=message,
            ),
        )

        self.refresh()
        QTimer.singleShot(
            0,
            self.scan_callback,
        )

    def _finish_apply_ui(
        self,
    ) -> None:
        self._worker = None
        self._applying_profile = None

        self.operation_frame.hide()
        self.operation_progress.setValue(
            0
        )
        self.operation_label.clear()
        self.cancel_button.setEnabled(
            True
        )

        self._set_busy(
            False
        )

    # ========================================================
    # Cards
    # ========================================================

    def _rebuild_cards(
        self,
    ) -> None:
        old_cards = tuple(
            self._cards
        )
        self._cards.clear()

        for card in old_cards:
            self.cards_grid.removeWidget(
                card
            )
            card.deleteLater()

        selected_profile = str(
            getattr(
                self.config,
                "selected_profile",
                "Default",
            )
        )

        for profile in self._profiles:
            card = ProfileCard(
                profile=profile,
                active=(
                    profile.name
                    == selected_profile
                ),
                parent=self.cards_content,
            )

            card.activate_requested.connect(
                self._activate_profile
            )
            card.save_current_requested.connect(
                self._save_current_profile
            )
            card.rename_requested.connect(
                self._rename_profile
            )
            card.delete_requested.connect(
                self._delete_profile
            )

            card.set_busy(
                self._busy
            )
            self._cards.append(
                card
            )

        self._current_columns = 0
        QTimer.singleShot(
            0,
            self._reflow_cards,
        )

    def _reflow_cards(
        self,
    ) -> None:
        if not self._cards:
            return

        width = max(
            self.scroll_area.viewport().width(),
            1,
        )

        if width >= 1280:
            columns = 3
        elif width >= 760:
            columns = 2
        else:
            columns = 1

        if columns == self._current_columns:
            return

        for card in self._cards:
            self.cards_grid.removeWidget(
                card
            )

        for index, card in enumerate(
            self._cards
        ):
            row = index // columns
            column = index % columns

            self.cards_grid.addWidget(
                card,
                row,
                column,
            )

        for column in range(
            3
        ):
            self.cards_grid.setColumnStretch(
                column,
                1 if column < columns else 0,
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
            self._reflow_cards,
        )

    # ========================================================
    # State helpers
    # ========================================================

    def _set_busy(
        self,
        busy: bool,
    ) -> None:
        if self._busy == busy:
            return

        self._busy = busy

        self.new_button.setEnabled(
            not busy
        )
        self.empty_new_button.setEnabled(
            not busy
        )
        self.refresh_button.setEnabled(
            not busy
        )

        for card in self._cards:
            card.set_busy(
                busy
            )

        self.busy_changed.emit(
            busy
        )

    def _prepare_edit_operation(
        self,
    ) -> bool:
        if self.is_applying():
            self._show_busy_warning()
            return False

        if self.operation_busy_provider():
            self._show_busy_warning()
            return False

        return True

    def _has_capturable_mods(
        self,
        mods: tuple[ModInfo, ...],
    ) -> bool:
        for mod in mods:
            try:
                state = self.state_provider(
                    Path(mod.path)
                )
            except Exception:
                continue

            if state in {
                ModState.ENABLED,
                ModState.DISABLED,
                ModState.BROKEN,
            }:
                return True

        return False

    def _set_selected_profile(
        self,
        name: str,
    ) -> None:
        self.config.selected_profile = name

        try:
            self.config.save()
        except OSError as error:
            QMessageBox.critical(
                self,
                tr(
                    "profiles.error.title"
                ),
                tr(
                    "profiles.error.save_config",
                    error=error,
                ),
            )

    def _game_id(
        self,
    ) -> str:
        return str(
            self.game_id_provider()
        )

    # ========================================================
    # Summary / Empty state
    # ========================================================

    def _active_profile_name(
        self,
    ) -> str | None:
        selected = str(
            getattr(
                self.config,
                "selected_profile",
                "Default",
            )
        )

        if any(
            profile.name == selected
            for profile in self._profiles
        ):
            return selected

        return None

    def _refresh_summary(
        self,
    ) -> None:
        active = self._active_profile_name()

        self.summary_value_label.setText(
            tr(
                "profiles.summary.active",
                name=active,
            )
            if active is not None
            else tr(
                "profiles.summary.none"
            )
        )

        self.summary_count_label.setText(
            tr(
                "profiles.summary.count",
                count=len(
                    self._profiles
                ),
            )
        )

    def _refresh_empty_state(
        self,
    ) -> None:
        has_profiles = bool(
            self._profiles
        )

        self.scroll_area.setVisible(
            has_profiles
        )
        self.empty_frame.setVisible(
            not has_profiles
        )

    # ========================================================
    # Dialog helpers
    # ========================================================

    def _show_busy_warning(
        self,
    ) -> None:
        QMessageBox.warning(
            self,
            tr(
                "profiles.warning.title"
            ),
            tr(
                "profiles.warning.busy"
            ),
        )

    def _show_no_capturable_mods(
        self,
    ) -> None:
        QMessageBox.warning(
            self,
            tr(
                "profiles.warning.title"
            ),
            tr(
                "profiles.warning.no_mods"
            ),
        )

    def _show_profile_error(
        self,
        error: Exception,
    ) -> None:
        QMessageBox.critical(
            self,
            tr(
                "profiles.error.title"
            ),
            str(error),
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr(
                "profiles.title"
            )
        )
        self.description_label.setText(
            tr(
                "profiles.description"
            )
        )

        self.new_button.setText(
            "＋  "
            + tr(
                "profiles.action.new"
            )
        )
        self.refresh_button.setText(
            "↻  "
            + tr(
                "profiles.action.refresh"
            )
        )

        self.summary_title_label.setText(
            tr(
                "profiles.summary.title"
            )
        )

        self.empty_title_label.setText(
            tr(
                "profiles.empty.title"
            )
        )
        self.empty_description_label.setText(
            tr(
                "profiles.empty.description"
            )
        )
        self.empty_new_button.setText(
            "＋  "
            + tr(
                "profiles.action.new"
            )
        )

        self.cancel_button.setText(
            tr(
                "common.cancel"
            )
        )

        for card in self._cards:
            card.retranslate_ui(
                _language
            )

        self._refresh_summary()

    # ========================================================
    # Stylesheet
    # ========================================================

    def _apply_stylesheet(
        self,
    ) -> None:
        style_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "styles"
            / "profiles.qss"
        )

        try:
            stylesheet = style_path.read_text(
                encoding="utf-8"
            )
        except OSError as error:
            raise RuntimeError(
                f"Profiles stylesheet could not be loaded: {style_path}"
            ) from error

        self.setStyleSheet(
            stylesheet
        )


__all__ = [
    "ProfilesPage",
]
