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
            "Mods importieren"
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
            f"{len(self.sources)} Quelle(n) importieren"
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
                f"\n• … und {len(self.sources) - 8} weitere"
            )

        source_label = QLabel(
            source_preview
        )
        source_label.setWordWrap(True)
        source_label.setObjectName(
            "sourcePreview"
        )

        description_label = QLabel(
            "Charakter und Mod-Typ sind optional. "
            "Ohne Angaben wird die vorhandene Struktur "
            "des Ordners oder Archivs übernommen."
        )
        description_label.setWordWrap(True)

        self.character_input.setPlaceholderText(
            "Zum Beispiel: Chiori"
        )

        self.mod_type_input.setPlaceholderText(
            "Zum Beispiel: Character Skin"
        )

        self.conflict_combobox.addItem(
            "Automatisch umbenennen",
            userData=ConflictPolicy.RENAME.value,
        )

        self.conflict_combobox.addItem(
            "Vorhandenen Mod überspringen",
            userData=ConflictPolicy.SKIP.value,
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        form_layout.addRow(
            "Charakter:",
            self.character_input,
        )

        form_layout.addRow(
            "Mod-Typ:",
            self.mod_type_input,
        )

        form_layout.addRow(
            "Bei Namenskonflikt:",
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
            "Import starten"
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
                "Charakter fehlt",
                (
                    "Wenn du einen Mod-Typ angibst, musst du "
                    "auch einen Charakter angeben."
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