from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.dialogs.library_mod_backup_dialog import LibraryModBackupDialog
from app.i18n import tr, translation_manager
from app.services.library_mod_backup_service import ModBackupRecord
from app.services.library_mod_update_service import (
    ModUpdateResult,
    ModUpdateStatus,
)


MarkCurrentCallback = Callable[[ModUpdateResult], ModUpdateResult]
ChangedCallback = Callable[[ModUpdateResult], None]
BackupsProvider = Callable[[ModUpdateResult], tuple[ModBackupRecord, ...]]


class LibraryModUpdateDialog(QDialog):
    """GameBanana update center with install and rollback actions."""

    install_requested = Signal(object)
    restore_requested = Signal(object, object)

    def __init__(
        self,
        *,
        results: tuple[ModUpdateResult, ...],
        mark_current_callback: MarkCurrentCallback,
        backups_provider: BackupsProvider,
        changed_callback: ChangedCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("libraryModUpdateDialog")
        self.total_mod_count = len(results)
        self.results = [
            result for result in results if result.gamebanana_mod_id is not None
        ]
        self.mark_current_callback = mark_current_callback
        self.backups_provider = backups_provider
        self.changed_callback = changed_callback
        self._busy = False

        self.title_label = QLabel(self)
        self.title_label.setObjectName("modUpdateDialogTitle")
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("modUpdateDialogSummary")
        self.summary_label.setWordWrap(True)

        self.table = QTableWidget(self)
        self.table.setObjectName("modUpdateTable")
        self.table.setColumnCount(5)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        # Two action rows are used deliberately.  This avoids the Windows/Qt
        # style clipping seen with one narrow table row at high DPI.
        self.table.verticalHeader().setMinimumSectionSize(86)
        self.table.verticalHeader().setDefaultSectionSize(86)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 180)

        self.operation_label = QLabel(self)
        self.operation_label.setObjectName("modUpdateOperationLabel")
        self.operation_label.setWordWrap(True)
        self.operation_label.hide()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("modUpdateProgress")
        self.progress_bar.hide()

        self.close_button = QPushButton(self)
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.operation_label)
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.setMinimumSize(1180, 680)
        self._apply_initial_size()
        translation_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()
        self._rebuild_table()

    def _apply_initial_size(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1400, 760)
            return
        available = screen.availableGeometry()
        self.resize(
            min(1540, max(1180, int(available.width() * 0.90))),
            min(900, max(680, int(available.height() * 0.86))),
        )

    @staticmethod
    def _status_key(status: ModUpdateStatus) -> str:
        return {
            ModUpdateStatus.NOT_LINKED: "library.mod_updates.status.not_linked",
            ModUpdateStatus.CURRENT: "library.mod_updates.status.current",
            ModUpdateStatus.UPDATE_AVAILABLE: "library.mod_updates.status.available",
            ModUpdateStatus.TRACKING_STARTED: "library.mod_updates.status.tracking_started",
            ModUpdateStatus.NO_DOWNLOAD: "library.mod_updates.status.no_download",
            ModUpdateStatus.ERROR: "library.mod_updates.status.error",
        }[status]

    @staticmethod
    def _revision_text(revision) -> str:
        if revision is None:
            return "—"
        parts: list[str] = []
        if revision.file_name and revision.file_name != "local-install":
            parts.append(revision.file_name)
        elif revision.file_name == "local-install":
            parts.append(tr("library.mod_updates.local_install"))
        if revision.date_added:
            try:
                parts.append(
                    datetime.fromtimestamp(int(revision.date_added)).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                )
            except (OSError, OverflowError, ValueError):
                pass
        if revision.file_id:
            parts.append(f"#{revision.file_id}")
        return " · ".join(parts) if parts else "—"

    def _summary_text(self) -> str:
        updates = sum(
            result.status == ModUpdateStatus.UPDATE_AVAILABLE
            for result in self.results
        )
        errors = sum(result.status == ModUpdateStatus.ERROR for result in self.results)
        return tr(
            "library.mod_updates.summary",
            total=self.total_mod_count,
            linked=len(self.results),
            updates=updates,
            errors=errors,
        )

    def _rebuild_table(self) -> None:
        self.table.clearContents()
        self.table.setRowCount(len(self.results))
        for row, result in enumerate(self.results):
            installed_text = self._revision_text(result.installed)
            remote_text = self._revision_text(result.remote)
            items = [
                QTableWidgetItem(result.mod_name),
                QTableWidgetItem(tr(self._status_key(result.status))),
                QTableWidgetItem(installed_text),
                QTableWidgetItem(remote_text),
            ]
            items[0].setToolTip(result.mod_name)
            items[2].setToolTip(installed_text)
            items[3].setToolTip(remote_text)
            if result.message:
                items[1].setToolTip(result.message)
            for column, item in enumerate(items):
                self.table.setItem(row, column, item)
            self.table.setCellWidget(row, 4, self._actions_widget(row, result))
            self.table.setRowHeight(row, 86)
        self.summary_label.setText(self._summary_text())

    @staticmethod
    def _make_action_button(text: str, parent: QWidget) -> QPushButton:
        button = QPushButton(text, parent)
        button.setObjectName("modUpdateActionButton")
        button.setFixedHeight(34)
        button.setMinimumWidth(118)
        return button

    def _actions_widget(self, row: int, result: ModUpdateResult) -> QWidget:
        widget = QWidget(self.table)
        widget.setObjectName("modUpdateActionsWidget")
        layout = QGridLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        actions: list[QPushButton] = []
        if result.status == ModUpdateStatus.UPDATE_AVAILABLE and result.remote is not None:
            install_button = self._make_action_button(
                tr("library.mod_updates.action.install"), widget
            )
            install_button.clicked.connect(
                lambda _checked=False, current=result: self.install_requested.emit(current)
            )
            actions.append(install_button)

        open_button = self._make_action_button(
            tr("library.mod_updates.open_gamebanana"), widget
        )
        open_button.setEnabled(bool(result.profile_url))
        open_button.clicked.connect(
            lambda _checked=False, current=result: self._open(current)
        )
        actions.append(open_button)

        backups = self.backups_provider(result)
        if backups:
            backup_button = self._make_action_button(
                tr("library.mod_updates.action.backups", count=len(backups)), widget
            )
            backup_button.clicked.connect(
                lambda _checked=False, current=result: self._open_backups(current)
            )
            actions.append(backup_button)

        if result.status == ModUpdateStatus.UPDATE_AVAILABLE and result.remote is not None:
            current_button = self._make_action_button(
                tr("library.mod_updates.mark_current"), widget
            )
            current_button.clicked.connect(
                lambda _checked=False, current=result, current_row=row:
                self._mark_current(current_row, current)
            )
            actions.append(current_button)

        for index, button in enumerate(actions):
            button.setEnabled(button.isEnabled() and not self._busy)
            layout.addWidget(button, index // 2, index % 2)
        return widget

    def _open_backups(self, result: ModUpdateResult) -> None:
        records = self.backups_provider(result)
        if not records:
            return
        dialog = LibraryModBackupDialog(
            mod_name=result.mod_name,
            records=records,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        record = dialog.selected_record()
        if record is not None:
            self.restore_requested.emit(result, record)

    @staticmethod
    def _open(result: ModUpdateResult) -> None:
        if result.profile_url:
            QDesktopServices.openUrl(QUrl(result.profile_url))

    def _mark_current(self, row: int, result: ModUpdateResult) -> None:
        if self._busy:
            return
        try:
            updated = self.mark_current_callback(result)
        except Exception:
            return
        self.results[row] = updated
        if self.changed_callback is not None:
            self.changed_callback(updated)
        self._rebuild_table()

    def replace_result(self, updated: ModUpdateResult) -> None:
        for index, current in enumerate(self.results):
            if current.mod_key == updated.mod_key and current.game_id == updated.game_id:
                self.results[index] = updated
                break
        self._rebuild_table()

    def set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = bool(busy)
        self.close_button.setEnabled(not self._busy)
        self.operation_label.setVisible(self._busy or bool(text))
        self.progress_bar.setVisible(self._busy)
        if text:
            self.operation_label.setText(text)
        if self._busy:
            self.progress_bar.setRange(0, 0)
        self._rebuild_table()

    def update_progress(self, current: int, total: int, text: str) -> None:
        self.operation_label.setText(text)
        self.operation_label.show()
        self.progress_bar.show()
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(max(0, min(current, total)))
        else:
            self.progress_bar.setRange(0, 0)

    def show_status(self, text: str) -> None:
        self.operation_label.setText(text)
        self.operation_label.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            event.ignore()
            return
        super().closeEvent(event)

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.setWindowTitle(tr("library.mod_updates.dialog.title"))
        self.title_label.setText(tr("library.mod_updates.dialog.heading"))
        self.close_button.setText(tr("common.close"))
        self.table.setHorizontalHeaderLabels(
            [
                tr("library.mod_updates.column.mod"),
                tr("library.mod_updates.column.status"),
                tr("library.mod_updates.column.installed"),
                tr("library.mod_updates.column.available"),
                tr("library.mod_updates.column.actions"),
            ]
        )
        self.summary_label.setText(self._summary_text())
        if not self._busy:
            self._rebuild_table()


__all__ = ["LibraryModUpdateDialog"]
