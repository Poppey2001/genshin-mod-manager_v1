from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translation_manager
from app.services.library_mod_backup_service import ModBackupRecord


class LibraryModBackupDialog(QDialog):
    def __init__(
        self,
        *,
        mod_name: str,
        records: tuple[ModBackupRecord, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("libraryModBackupDialog")
        self.mod_name = mod_name
        self.records = records

        self.title_label = QLabel(self)
        self.title_label.setObjectName("modBackupDialogTitle")
        self.help_label = QLabel(self)
        self.help_label.setObjectName("modBackupDialogHelp")
        self.help_label.setWordWrap(True)

        self.table = QTableWidget(self)
        self.table.setObjectName("modBackupTable")
        self.table.setColumnCount(3)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.restore_button = QPushButton(self)
        self.restore_button.setObjectName("primaryButton")
        self.restore_button.clicked.connect(self.accept)
        self.close_button = QPushButton(self)
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.help_label)
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.restore_button)
        layout.addLayout(buttons)

        self.setMinimumSize(760, 440)
        self.resize(860, 520)

        self.table.itemSelectionChanged.connect(self._sync_buttons)
        translation_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()
        self._rebuild()

    @staticmethod
    def _date_text(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return value or "—"

    @staticmethod
    def _revision_text(record: ModBackupRecord) -> str:
        revision = record.installed_revision
        if revision is None:
            return tr("library.mod_updates.backups.unknown_revision")
        parts = []
        if revision.file_name:
            parts.append(revision.file_name)
        if revision.file_id:
            parts.append(f"#{revision.file_id}")
        return " · ".join(parts) or "—"

    @staticmethod
    def _state_text(record: ModBackupRecord) -> str:
        return tr(
            {
                "enabled": "library.mod_updates.backups.state.enabled",
                "disabled": "library.mod_updates.backups.state.disabled",
                "not_configured": "library.mod_updates.backups.state.not_configured",
            }.get(
                record.managed_state or "",
                "library.mod_updates.backups.state.library_only",
            )
        )

    def _rebuild(self) -> None:
        self.table.clearContents()
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            date_item = QTableWidgetItem(self._date_text(record.created_at))
            version_item = QTableWidgetItem(self._revision_text(record))
            state_item = QTableWidgetItem(self._state_text(record))
            date_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 0, date_item)
            self.table.setItem(row, 1, version_item)
            self.table.setItem(row, 2, state_item)
        if self.records:
            self.table.selectRow(0)
        self._sync_buttons()

    def selected_record(self) -> ModBackupRecord | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.records):
            return self.records[row]
        return None

    def _sync_buttons(self) -> None:
        self.restore_button.setEnabled(self.selected_record() is not None)

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.setWindowTitle(tr("library.mod_updates.backups.dialog.title"))
        self.title_label.setText(
            tr("library.mod_updates.backups.dialog.heading", mod_name=self.mod_name)
        )
        self.help_label.setText(tr("library.mod_updates.backups.dialog.help"))
        self.table.setHorizontalHeaderLabels(
            [
                tr("library.mod_updates.backups.column.date"),
                tr("library.mod_updates.backups.column.version"),
                tr("library.mod_updates.backups.column.state"),
            ]
        )
        self.restore_button.setText(tr("library.mod_updates.action.restore"))
        self.close_button.setText(tr("common.close"))


__all__ = ["LibraryModBackupDialog"]
