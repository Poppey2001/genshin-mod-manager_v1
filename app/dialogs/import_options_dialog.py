from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
)

from app.services.mod_importer import (
    ConflictPolicy,
    ImportOptions,
)


class ImportOptionsDialog(QDialog):
    """Fragt Zielstruktur und Konfliktverhalten ab."""

    def __init__(
        self,
        sources: list[Path],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.sources = sources

        self.character_input = QLineEdit()
        self.mod_type_input = QLineEdit()
        self.conflict_combobox = QComboBox()

        self.setWindowTitle(
            tr(
                "import.options.window_title"
            )
        )

        self.setMinimumWidth(
            520
        )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )
        layout.setSpacing(14)

        title_label = QLabel(
            tr(
                "import.options.title",
                count=len(self.sources),
            )
        )
        title_label.setObjectName(
            "dialogTitle"
        )

        source_preview = "\n".join(
            f"• {source.name}"
            for source in self.sources[:8]
        )

        if len(self.sources) > 8:
            source_preview += (
                "\n• "
                + tr(
                    "import.options.more_sources",
                    count=len(self.sources) - 8,
                )
            )

        source_label = QLabel(
            source_preview
        )
        source_label.setWordWrap(True)
        source_label.setObjectName(
            "sourcePreview"
        )

        description_label = QLabel(
            tr(
                "import.options.description"
            )
        )
        description_label.setWordWrap(True)

        self.character_input.setPlaceholderText(
            tr(
                "import.options.character_placeholder"
            )
        )

        self.mod_type_input.setPlaceholderText(
            tr(
                "import.options.mod_type_placeholder"
            )
        )

        self.conflict_combobox.addItem(
            tr(
                "import.options.conflict.rename"
            ),
            userData=ConflictPolicy.RENAME.value,
        )

        self.conflict_combobox.addItem(
            tr(
                "import.options.conflict.skip"
            ),
            userData=ConflictPolicy.SKIP.value,
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        form_layout.addRow(
            tr(
                "import.options.character_label"
            ),
            self.character_input,
        )

        form_layout.addRow(
            tr(
                "import.options.mod_type_label"
            ),
            self.mod_type_input,
        )

        form_layout.addRow(
            tr(
                "import.options.conflict_label"
            ),
            self.conflict_combobox,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        ok_button = buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )

        ok_button.setText(
            tr(
                "import.options.start"
            )
        )

        cancel_button = buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        cancel_button.setText(
            tr(
                "common.cancel"
            )
        )

        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(title_label)
        layout.addWidget(source_label)
        layout.addWidget(description_label)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #16181d;
                color: #f1f1f1;
            }

            QLabel#dialogTitle {
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
            }

            QLabel#sourcePreview {
                color: #b8bdc7;
                background-color: #20232a;
                border: 1px solid #30343d;
                border-radius: 7px;
                padding: 10px;
            }

            QLineEdit,
            QComboBox {
                min-height: 34px;
                padding: 0 9px;
                background-color: #20232a;
                color: #f1f1f1;
                border: 1px solid #3a3f49;
                border-radius: 6px;
            }

            QPushButton {
                min-height: 34px;
                padding: 0 14px;
            }
            """
        )

    def accept(self) -> None:
        character = (
            self.character_input.text().strip()
        )

        mod_type = (
            self.mod_type_input.text().strip()
        )

        if mod_type and not character:
            QMessageBox.warning(
                self,
                tr(
                    "import.options.character_missing.title"
                ),
                tr(
                    "import.options.character_missing.message"
                ),
            )
            return

        super().accept()

    def selected_options(self) -> ImportOptions:
        policy_value = (
            self.conflict_combobox.currentData()
        )

        try:
            conflict_policy = ConflictPolicy(
                policy_value
            )
        except ValueError:
            conflict_policy = ConflictPolicy.RENAME

        return ImportOptions(
            character=(
                self.character_input.text().strip()
                or None
            ),
            mod_type=(
                self.mod_type_input.text().strip()
                or None
            ),
            conflict_policy=conflict_policy,
        )