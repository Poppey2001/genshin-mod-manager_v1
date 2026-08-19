from __future__ import annotations

import html
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from app.i18n import (
    tr,
)

from app.platform_support import (
    PlatformSupportError,
    reveal_in_file_manager,
)
from app.models.ini_analysis import (
    IniAssignment,
    IniFileAnalysis,
    IniKeyBinding,
    ModIniAnalysis,
)


class ModInfoDialog(QDialog):
    """Zeigt die erkannten Steuerungen eines Mods."""

    def __init__(
        self,
        mod_name: str,
        analysis: ModIniAnalysis,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.analysis = analysis

        self.setWindowTitle(
            tr(
                "mod_info.window_title",
                mod_name=mod_name,
            )
        )

        self.setMinimumSize(
            760,
            560,
        )

        self.resize(
            900,
            680,
        )

        self._build_ui(
            mod_name=mod_name
        )

    def _build_ui(
        self,
        mod_name: str,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )
        layout.setSpacing(12)

        title_label = QLabel(
            tr(
                "mod_info.title",
                mod_name=mod_name,
            )
        )
        title_label.setObjectName(
            "dialogTitle"
        )

        path_label = QLabel(
            str(self.analysis.root_path)
        )
        path_label.setObjectName(
            "dialogPath"
        )
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(
            path_label.textInteractionFlags()
            | path_label.textInteractionFlags().TextSelectableByMouse
        )

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(
            False
        )
        self.browser.setHtml(
            _build_analysis_html(
                mod_name=mod_name,
                analysis=self.analysis,
            )
        )

        bottom_layout = QHBoxLayout()

        open_folder_button = QPushButton(
            tr(
                "mod_info.open_folder"
            )
        )
        open_folder_button.clicked.connect(
            self._open_mod_folder
        )

        close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )

        close_buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(
            tr(
                "common.close"
            )
        )
        close_buttons.rejected.connect(
            self.reject
        )

        bottom_layout.addWidget(
            open_folder_button
        )
        bottom_layout.addStretch()
        bottom_layout.addWidget(
            close_buttons
        )

        layout.addWidget(title_label)
        layout.addWidget(path_label)
        layout.addWidget(
            self.browser,
            stretch=1,
        )
        layout.addLayout(bottom_layout)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #16181d;
                color: #f1f1f1;
            }

            QLabel#dialogTitle {
                font-size: 22px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#dialogPath {
                color: #969ca8;
                font-size: 12px;
            }

            QTextBrowser {
                background-color: #20232a;
                color: #e5e7eb;
                border: 1px solid #30343d;
                border-radius: 8px;
                padding: 12px;
            }

            QPushButton {
                min-height: 34px;
                padding: 0 14px;
                background-color: #30343d;
                color: #f1f1f1;
                border: 1px solid #414651;
                border-radius: 6px;
            }

            QPushButton:hover {
                background-color: #3a3f49;
            }
            """
        )

    def _open_mod_folder(
        self,
    ) -> None:
        try:
            reveal_in_file_manager(
                self.analysis.root_path
            )

        except PlatformSupportError as error:
            QMessageBox.critical(
                self,
                tr(
                    "mod_info.open_folder_failed"
                ),
                str(error),
            )

def _build_analysis_html(
    mod_name: str,
    analysis: ModIniAnalysis,
) -> str:
    parts = [
        """
        <style>
            body {
                color: #e5e7eb;
                font-family: sans-serif;
            }

            h2 {
                color: #ffffff;
                margin-top: 18px;
            }

            h3 {
                color: #b7a7ff;
                margin-top: 18px;
                margin-bottom: 6px;
            }

            h4 {
                color: #ffffff;
                margin-bottom: 4px;
            }

            code {
                color: #c4b5fd;
                background-color: #17191e;
            }

            table {
                border-collapse: collapse;
                width: 100%;
                margin-top: 6px;
                margin-bottom: 12px;
            }

            th, td {
                border: 1px solid #3a3f49;
                padding: 6px;
                text-align: left;
            }

            th {
                background-color: #292d35;
                color: #ffffff;
            }

            .warning {
                color: #fbbf24;
            }

            .muted {
                color: #9ca3af;
            }
        </style>
        """,
        f"<h2>{html.escape(mod_name)}</h2>",
    ]

    if analysis.warnings:
        parts.append(
            f"<h3>{html.escape(tr('mod_info.html.warnings'))}</h3><ul>"
        )

        for warning in analysis.warnings:
            parts.append(
                "<li class='warning'>"
                f"{html.escape(warning)}"
                "</li>"
            )

        parts.append("</ul>")

    if not analysis.files:
        parts.append(
            "<p class='warning'>"
            + html.escape(
                tr(
                    "mod_info.html.no_control_ini"
                )
            )
            + "</p>"
        )

        return "".join(parts)

    for file_analysis in analysis.files:
        parts.append(
            _build_file_html(
                root_path=analysis.root_path,
                file_analysis=file_analysis,
            )
        )

    parts.append(
        "<p class='muted'>"
        + html.escape(
            tr(
                "mod_info.html.technical_note"
            )
        )
        + "</p>"
    )

    return "".join(parts)


def _build_file_html(
    root_path: Path,
    file_analysis: IniFileAnalysis,
) -> str:
    try:
        relative_path = file_analysis.path.relative_to(
            root_path
        )
    except ValueError:
        relative_path = file_analysis.path

    parts = [
        f"<h2>{html.escape(file_analysis.path.name)}</h2>",
        "<p><code>",
        html.escape(str(relative_path)),
        "</code></p>",
    ]

    if file_analysis.namespace:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.namespace'))}:</b> "
            f"<code>{html.escape(file_analysis.namespace)}</code>"
            "</p>"
        )

    if file_analysis.merged_sources:
        parts.append(
            f"<h3>{html.escape(tr('mod_info.html.merged_mods'))}</h3><ol start='0'>"
        )

        for source in file_analysis.merged_sources:
            parts.append(
                f"<li>{html.escape(_source_label(source))}"
                f" <span class='muted'>"
                f"({html.escape(source)})"
                "</span></li>"
            )

        parts.append("</ol>")

    for warning in file_analysis.warnings:
        parts.append(
            "<p class='warning'>"
            f"{html.escape(warning)}"
            "</p>"
        )

    if not file_analysis.key_bindings:
        return "".join(parts)

    for binding in file_analysis.key_bindings:
        parts.append(
            _build_binding_html(
                binding=binding,
                merged_sources=file_analysis.merged_sources,
            )
        )

    return "".join(parts)


def _build_binding_html(
    binding: IniKeyBinding,
    merged_sources: tuple[str, ...],
) -> str:
    keys = (
        ", ".join(binding.keys)
        if binding.keys
        else tr(
            "mod_info.html.no_key"
        )
    )

    parts = [
        f"<h3>[{html.escape(binding.section_name)}]</h3>",
        f"<p><b>{html.escape(tr('mod_info.html.key'))}:</b> ",
        f"<code>{html.escape(keys)}</code></p>",
        f"<p><b>{html.escape(tr('mod_info.html.type'))}:</b> ",
        html.escape(
            _key_type_description(
                binding.key_type
            )
        ),
        "</p>",
    ]

    if binding.back_keys:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.reverse'))}:</b> "
            f"<code>{html.escape(', '.join(binding.back_keys))}</code>"
            "</p>"
        )

    if binding.condition:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.condition'))}:</b> "
            f"<code>{html.escape(binding.condition)}</code>"
            "</p>"
        )

    if binding.smart is not None:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.smart_cycle'))}:</b> "
            f"<code>{html.escape(binding.smart)}</code>"
            "</p>"
        )

    if binding.wrap is not None:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.wrap'))}:</b> "
            f"<code>{html.escape(binding.wrap)}</code>"
            "</p>"
        )

    if binding.run_commands:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.command_lists'))}:</b> "
            f"<code>{html.escape(', '.join(binding.run_commands))}</code>"
            "</p>"
        )

    if binding.assignments:
        parts.append(
            (
                "<table><tr>"
                f"<th>{html.escape(tr('mod_info.html.assignment'))}</th>"
                f"<th>{html.escape(tr('mod_info.html.values'))}</th>"
                f"<th>{html.escape(tr('mod_info.html.interpretation'))}</th>"
                "</tr>"
            )
        )

        for assignment in binding.assignments:
            parts.append(
                "<tr>"
                f"<td><code>{html.escape(assignment.name)}</code></td>"
                f"<td><code>{html.escape(assignment.raw_value)}</code></td>"
                f"<td>{html.escape(_assignment_description(assignment))}</td>"
                "</tr>"
            )

        parts.append("</table>")

    state_html = _build_state_html(
        binding=binding,
        merged_sources=merged_sources,
    )

    if state_html:
        parts.append(state_html)

    if binding.comments:
        parts.append(
            f"<p><b>{html.escape(tr('mod_info.html.comments'))}:</b></p><ul>"
        )

        for comment in binding.comments[:10]:
            parts.append(
                f"<li>{html.escape(comment)}</li>"
            )

        parts.append("</ul>")

    return "".join(parts)


def _build_state_html(
    binding: IniKeyBinding,
    merged_sources: tuple[str, ...],
) -> str:
    multi_value_assignments = [
        assignment
        for assignment in binding.assignments
        if len(assignment.values) > 1
    ]

    if not multi_value_assignments:
        return ""

    state_count = max(
        len(assignment.values)
        for assignment in multi_value_assignments
    )

    comment_labels = {
        state.index: state.label
        for state in binding.state_labels
    }

    parts = [
        f"<h4>{html.escape(tr('mod_info.html.detected_states'))}</h4>",
        (
            "<table><tr>"
            f"<th>{html.escape(tr('mod_info.html.state'))}</th>"
            f"<th>{html.escape(tr('mod_info.html.description'))}</th>"
            f"<th>{html.escape(tr('mod_info.html.set_values'))}</th>"
            "</tr>"
        ),
    ]

    for state_index in range(state_count):
        description = comment_labels.get(
            state_index
        )

        if (
            description is None
            and state_index < len(merged_sources)
        ):
            description = _source_label(
                merged_sources[state_index]
            )

        if description is None:
            description = (
                tr(
                    "mod_info.html.technical_state",
                    index=state_index,
                )
            )

        state_values: list[str] = []

        for assignment in multi_value_assignments:
            if state_index >= len(
                assignment.values
            ):
                continue

            state_values.append(
                f"{assignment.name} = "
                f"{assignment.values[state_index]}"
            )

        parts.append(
            "<tr>"
            f"<td>{state_index}</td>"
            f"<td>{html.escape(description)}</td>"
            f"<td><code>{html.escape(' | '.join(state_values))}</code></td>"
            "</tr>"
        )

    parts.append("</table>")

    return "".join(parts)


def _key_type_description(
    key_type: str,
) -> str:
    description_keys = {
        "cycle": "mod_info.type.cycle",
        "toggle": "mod_info.type.toggle",
        "hold": "mod_info.type.hold",
        "activate": "mod_info.type.activate",
    }

    key = description_keys.get(
        key_type.casefold()
    )

    if key is not None:
        return tr(
            key
        )

    return tr(
        "mod_info.type.unknown",
        key_type=key_type,
    )


def _assignment_description(
    assignment: IniAssignment,
) -> str:
    value_count = len(
        assignment.values
    )

    if value_count > 1:
        return tr(
            "mod_info.assignment.multiple",
            count=value_count,
        )

    if assignment.name.startswith("$"):
        return tr(
            "mod_info.assignment.mod_variable"
        )

    return tr(
        "mod_info.assignment.3dmigoto_setting"
    )


def _source_label(
    source: str,
) -> str:
    normalized_source = source.replace(
        "\\",
        "/",
    )

    path = PurePosixPath(
        normalized_source
    )

    if path.parent.name:
        return path.parent.name

    if path.stem:
        return path.stem

    return source