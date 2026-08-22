from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translation_manager
from app.services.library_category_service import (
    LibraryCategoryError,
    LibraryCategoryService,
)


CATEGORY_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 20


class LibraryCategoryManagerDialog(QDialog):
    categories_changed = Signal()

    def __init__(
        self,
        *,
        service: LibraryCategoryService,
        game_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.game_id = str(game_id)

        self.setObjectName("libraryCategoryDialog")
        self.setModal(True)
        self.resize(520, 430)

        self.title_label = QLabel()
        self.title_label.setObjectName("categoryDialogTitle")
        self.description_label = QLabel()
        self.description_label.setObjectName("categoryDialogDescription")
        self.description_label.setWordWrap(True)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        self.category_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.add_button = QPushButton()
        self.rename_button = QPushButton()
        self.delete_button = QPushButton()
        self.close_button = QPushButton()

        self.add_button.setObjectName("primaryActionButton")
        self.rename_button.setObjectName("secondaryActionButton")
        self.delete_button.setObjectName("dangerButton")
        self.close_button.setObjectName("secondaryActionButton")

        self._build_ui()
        self._connect_signals()
        self._reload()
        translation_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.category_list, stretch=1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.rename_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self._add_category)
        self.rename_button.clicked.connect(self._rename_category)
        self.delete_button.clicked.connect(self._delete_category)
        self.close_button.clicked.connect(self.accept)
        self.category_list.itemSelectionChanged.connect(self._update_buttons)
        self.category_list.itemDoubleClicked.connect(
            lambda _item: self._rename_category()
        )

    def _reload(self, select_id: str | None = None) -> None:
        self.category_list.clear()
        for category in self.service.categories(self.game_id):
            item = QListWidgetItem(category.name)
            item.setData(CATEGORY_ID_ROLE, category.id)
            self.category_list.addItem(item)
            if category.id == select_id:
                self.category_list.setCurrentItem(item)
        self._update_buttons()

    def _selected(self) -> tuple[str, str] | None:
        item = self.category_list.currentItem()
        if item is None:
            return None
        category_id = str(item.data(CATEGORY_ID_ROLE) or "").strip()
        if not category_id:
            return None
        return category_id, item.text()

    def _ask_name(self, *, title_key: str, initial: str = "") -> str | None:
        value, accepted = QInputDialog.getText(
            self,
            tr(title_key),
            tr("library.categories.name_prompt"),
            text=initial,
        )
        if not accepted:
            return None
        value = value.strip()
        if not value:
            QMessageBox.warning(
                self,
                tr("library.categories.error.title"),
                tr("library.categories.error.empty"),
            )
            return None
        return value

    def _show_error(self, error: Exception) -> None:
        message = str(error)
        if "already exists" in message:
            message = tr("library.categories.error.duplicate")
        elif "at most" in message:
            message = tr("library.categories.error.too_long")
        QMessageBox.critical(
            self,
            tr("library.categories.error.title"),
            message,
        )

    def _add_category(self, _checked: bool = False) -> None:
        name = self._ask_name(title_key="library.categories.add_title")
        if name is None:
            return
        try:
            category = self.service.create_category(self.game_id, name)
        except LibraryCategoryError as error:
            self._show_error(error)
            return
        self._reload(category.id)
        self.categories_changed.emit()

    def _rename_category(self, _checked: bool = False) -> None:
        selected = self._selected()
        if selected is None:
            return
        category_id, old_name = selected
        name = self._ask_name(
            title_key="library.categories.rename_title",
            initial=old_name,
        )
        if name is None or name == old_name:
            return
        try:
            category = self.service.rename_category(
                self.game_id,
                category_id,
                name,
            )
        except LibraryCategoryError as error:
            self._show_error(error)
            return
        self._reload(category.id)
        self.categories_changed.emit()

    def _delete_category(self, _checked: bool = False) -> None:
        selected = self._selected()
        if selected is None:
            return
        category_id, name = selected
        answer = QMessageBox.question(
            self,
            tr("library.categories.delete_title"),
            tr("library.categories.delete_message", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_category(self.game_id, category_id)
        except LibraryCategoryError as error:
            self._show_error(error)
            return
        self._reload()
        self.categories_changed.emit()

    def _update_buttons(self) -> None:
        has_selection = self._selected() is not None
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.setWindowTitle(tr("library.categories.title"))
        self.title_label.setText(tr("library.categories.title"))
        self.description_label.setText(tr("library.categories.description"))
        self.add_button.setText(tr("library.categories.add"))
        self.rename_button.setText(tr("library.categories.rename"))
        self.delete_button.setText(tr("library.categories.delete"))
        self.close_button.setText(tr("common.close"))


class LibraryModCategoryDialog(QDialog):
    """Assign zero or more existing categories to one Library mod."""

    def __init__(
        self,
        *,
        service: LibraryCategoryService,
        game_id: str,
        mod_key: str,
        mod_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.game_id = str(game_id)
        self.mod_key = service.normalize_mod_key(mod_key)
        self.mod_name = str(mod_name)

        self.setObjectName("libraryCategoryAssignmentDialog")
        self.setModal(True)
        self.resize(500, 450)

        self.title_label = QLabel()
        self.title_label.setObjectName("categoryDialogTitle")
        self.description_label = QLabel()
        self.description_label.setObjectName("categoryDialogDescription")
        self.description_label.setWordWrap(True)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("categoryEmptyLabel")
        self.empty_label.setWordWrap(True)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryAssignmentList")

        self.manage_button = QPushButton()
        self.manage_button.setObjectName("secondaryActionButton")

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        self._build_ui()
        self._connect_signals()
        self._reload()
        translation_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.category_list, stretch=1)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.manage_button)
        layout.addWidget(self.buttons)

    def _connect_signals(self) -> None:
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.manage_button.clicked.connect(self._manage_categories)

    def _reload(self) -> None:
        selected = set(
            self.service.category_ids_for_mod(self.game_id, self.mod_key)
        )
        self.category_list.clear()
        categories = self.service.categories(self.game_id)
        for category in categories:
            item = QListWidgetItem(category.name)
            item.setData(CATEGORY_ID_ROLE, category.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if category.id in selected
                else Qt.CheckState.Unchecked
            )
            self.category_list.addItem(item)
        has_categories = bool(categories)
        self.category_list.setVisible(has_categories)
        self.empty_label.setVisible(not has_categories)

    def _manage_categories(self, _checked: bool = False) -> None:
        dialog = LibraryCategoryManagerDialog(
            service=self.service,
            game_id=self.game_id,
            parent=self,
        )
        dialog.exec()
        self._reload()

    def selected_category_ids(self) -> tuple[str, ...]:
        result: list[str] = []
        for index in range(self.category_list.count()):
            item = self.category_list.item(index)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            category_id = str(item.data(CATEGORY_ID_ROLE) or "").strip()
            if category_id:
                result.append(category_id)
        return tuple(result)

    def accept(self) -> None:
        try:
            self.service.set_categories_for_mod(
                self.game_id,
                self.mod_key,
                self.selected_category_ids(),
            )
        except LibraryCategoryError as error:
            QMessageBox.critical(
                self,
                tr("library.categories.error.title"),
                str(error),
            )
            return
        super().accept()

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.setWindowTitle(tr("library.categories.assign_title"))
        self.title_label.setText(tr("library.categories.assign_title"))
        self.description_label.setText(
            tr(
                "library.categories.assign_description",
                mod_name=self.mod_name,
            )
        )
        self.empty_label.setText(tr("library.categories.assign_empty"))
        self.manage_button.setText(tr("library.categories.manage"))
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(tr("library.categories.save"))
        if cancel_button is not None:
            cancel_button.setText(tr("common.cancel"))


__all__ = [
    "LibraryCategoryManagerDialog",
    "LibraryModCategoryDialog",
]
