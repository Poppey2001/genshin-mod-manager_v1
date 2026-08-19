#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys


# ============================================================
# Konfiguration
# ============================================================

UI_CONSTRUCTORS = {
    "QLabel",
    "QPushButton",
    "QToolButton",
    "QCheckBox",
    "QRadioButton",
    "QGroupBox",
    "QAction",
}

VISIBLE_METHODS = {
    "setText",
    "setWindowTitle",
    "setPlaceholderText",
    "setToolTip",
    "setStatusTip",
    "setWhatsThis",
    "setTitle",
    "showMessage",
    "addAction",
    "addItem",
    "addTab",
    "setFormat",
    "setHeaderLabel",
    "setHeaderLabels",
    "setHorizontalHeaderLabels",
    "setVerticalHeaderLabels",
}

DIALOG_METHODS = {
    "warning",
    "critical",
    "information",
    "question",
    "about",
}

FILE_DIALOG_METHODS = {
    "getOpenFileName",
    "getOpenFileNames",
    "getSaveFileName",
    "getExistingDirectory",
}

INPUT_DIALOG_METHODS = {
    "getText",
    "getItem",
    "getInt",
    "getDouble",
}

NUMERIC_UI_METHODS = {
    "setMinimumWidth",
    "setMaximumWidth",
    "setFixedWidth",
    "setMinimumHeight",
    "setMaximumHeight",
    "setFixedHeight",
    "setMinimumSize",
    "setMaximumSize",
    "setFixedSize",
    "resize",
    "setContentsMargins",
    "setSpacing",
    "setHorizontalSpacing",
    "setVerticalSpacing",
    "setHandleWidth",
    "setSizes",
    "setIconSize",
    "setRowHeight",
    "setColumnWidth",
    "setMaxThreadCount",
    "setInterval",
    "setRange",
}

IGNORE_LITERAL_TEXT = {
    "",
    " ",
    "\n",
    "…",
    "...",
    "⋯",
    "✓",
    "!",
    "＋",
    "↻",
    "☷",
    "▦",
    "—",
    "-",
    "/",
    "#",
}

TECHNICAL_PATTERNS = (
    re.compile(r"^[A-Za-z0-9_.:/\\-]+$"),
    re.compile(r"^#[0-9A-Fa-f]{3,8}$"),
)

TRANSLATION_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$"
)


@dataclass(frozen=True)
class Finding:
    kind: str
    file: str
    line: int
    value: str
    context: str


# ============================================================
# AST helpers
# ============================================================

def dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []

    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value

    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))

    return None


def constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    if isinstance(node, ast.JoinedStr):
        # f-string: user-visible and hard-coded structure.
        pieces: list[str] = []

        for item in node.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                pieces.append(item.value)
            else:
                pieces.append("{...}")

        return "".join(pieces)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = constant_string(node.left)
        right = constant_string(node.right)

        if left is not None and right is not None:
            return left + right

    return None


def numeric_values(node: ast.AST) -> list[str]:
    values: list[str] = []

    if isinstance(node, ast.Constant) and isinstance(
        node.value,
        (int, float),
    ):
        values.append(repr(node.value))

    elif isinstance(node, (ast.List, ast.Tuple)):
        for item in node.elts:
            values.extend(
                numeric_values(item)
            )

    return values


def looks_user_visible(text: str) -> bool:
    text = text.strip()

    if text in IGNORE_LITERAL_TEXT:
        return False

    if not text:
        return False

    # Schon ein Translation-Key -> nicht als Hardcode zählen.
    if TRANSLATION_KEY_PATTERN.fullmatch(text):
        return False

    # ObjectName / reine technische Identifier möglichst ausfiltern.
    if (
        " " not in text
        and not any(ch in text for ch in "äöüÄÖÜß!?,:;()")
        and any(pattern.fullmatch(text) for pattern in TECHNICAL_PATTERNS)
    ):
        return False

    # Es muss wenigstens ein Buchstabe vorhanden sein.
    return any(
        ch.isalpha()
        for ch in text
    )


def expression_is_tr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tr"
    )


# ============================================================
# Scanner
# ============================================================

class Scanner(ast.NodeVisitor):
    def __init__(
        self,
        *,
        relative_file: str,
    ) -> None:
        self.relative_file = relative_file
        self.findings: list[Finding] = []

    def add_text(
        self,
        *,
        node: ast.AST,
        text: str,
        context: str,
    ) -> None:
        if not looks_user_visible(text):
            return

        self.findings.append(
            Finding(
                kind="TEXT",
                file=self.relative_file,
                line=getattr(node, "lineno", 0),
                value=text.replace("\n", "\\n"),
                context=context,
            )
        )

    def add_number(
        self,
        *,
        node: ast.AST,
        value: str,
        context: str,
    ) -> None:
        # 0/1 sind in Qt-API sehr häufig und meist semantisch,
        # daher standardmäßig ausblenden.
        if value in {"0", "1", "0.0", "1.0"}:
            return

        self.findings.append(
            Finding(
                kind="NUMBER",
                file=self.relative_file,
                line=getattr(node, "lineno", 0),
                value=value,
                context=context,
            )
        )

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        name = dotted_name(
            node.func
        )

        if name is None:
            self.generic_visit(node)
            return

        leaf = name.rsplit(".", 1)[-1]

        # ----------------------------------------------------
        # Widget-Konstruktoren mit sichtbarem Literal
        # QLabel("Text"), QPushButton("Text"), ...
        # ----------------------------------------------------

        if leaf in UI_CONSTRUCTORS and node.args:
            first = node.args[0]

            if not expression_is_tr(first):
                text = constant_string(first)

                if text is not None:
                    self.add_text(
                        node=node,
                        text=text,
                        context=f"{leaf}(...)",
                    )

        # ----------------------------------------------------
        # Sichtbare Setter / addItem / addAction
        # ----------------------------------------------------

        if leaf in VISIBLE_METHODS and node.args:
            candidate_indexes = [0]

            # addTab(widget, "Text")
            if leaf == "addTab" and len(node.args) >= 2:
                candidate_indexes = [1]

            # addItem("Text", data)
            if leaf == "addItem":
                candidate_indexes = [0]

            for index in candidate_indexes:
                if index >= len(node.args):
                    continue

                arg = node.args[index]

                if expression_is_tr(arg):
                    continue

                text = constant_string(arg)

                if text is not None:
                    self.add_text(
                        node=node,
                        text=text,
                        context=name,
                    )

        # ----------------------------------------------------
        # QMessageBox
        # ----------------------------------------------------

        if (
            leaf in DIALOG_METHODS
            and name.startswith("QMessageBox.")
        ):
            # self, title, message, ...
            for index in (1, 2):
                if index >= len(node.args):
                    continue

                arg = node.args[index]

                if expression_is_tr(arg):
                    continue

                text = constant_string(arg)

                if text is not None:
                    self.add_text(
                        node=node,
                        text=text,
                        context=name,
                    )

        # ----------------------------------------------------
        # QFileDialog
        # ----------------------------------------------------

        if (
            leaf in FILE_DIALOG_METHODS
            and name.startswith("QFileDialog.")
        ):
            # parent, caption, ...
            if len(node.args) >= 2:
                arg = node.args[1]

                if not expression_is_tr(arg):
                    text = constant_string(arg)

                    if text is not None:
                        self.add_text(
                            node=node,
                            text=text,
                            context=name,
                        )

        # ----------------------------------------------------
        # QInputDialog
        # ----------------------------------------------------

        if (
            leaf in INPUT_DIALOG_METHODS
            and name.startswith("QInputDialog.")
        ):
            # parent, title, label, ...
            for index in (1, 2):
                if index >= len(node.args):
                    continue

                arg = node.args[index]

                if expression_is_tr(arg):
                    continue

                text = constant_string(arg)

                if text is not None:
                    self.add_text(
                        node=node,
                        text=text,
                        context=name,
                    )

        # ----------------------------------------------------
        # Harte UI-Zahlen
        # ----------------------------------------------------

        if leaf in NUMERIC_UI_METHODS:
            for arg in node.args:
                for value in numeric_values(arg):
                    self.add_number(
                        node=node,
                        value=value,
                        context=name,
                    )

        # QTimer.singleShot(ms, ...)
        if name == "QTimer.singleShot" and node.args:
            for value in numeric_values(
                node.args[0]
            ):
                self.add_number(
                    node=node,
                    value=value,
                    context=name,
                )

        self.generic_visit(node)


# ============================================================
# Projektprüfung
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Findet wahrscheinliche hart codierte sichtbare Texte "
            "und feste UI-Zahlen im Projekt."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Projektwurzel. Standard: Parent von tools/.",
    )

    parser.add_argument(
        "--mode",
        choices=("text", "numbers", "all"),
        default="all",
        help="Was geprüft werden soll.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optionaler Report-Pfad.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = (
        args.root.expanduser().resolve()
        if args.root is not None
        else Path(__file__).resolve().parents[1]
    )

    files = list(
        (root / "app").rglob("*.py")
    )

    main_py = root / "main.py"

    if main_py.is_file():
        files.append(
            main_py
        )

    all_findings: list[Finding] = []
    syntax_errors: list[str] = []

    for path in sorted(
        set(files)
    ):
        try:
            text = path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                text,
                filename=str(path),
            )

        except Exception as error:
            syntax_errors.append(
                f"{path.relative_to(root)}: {error}"
            )
            continue

        scanner = Scanner(
            relative_file=str(
                path.relative_to(root)
            )
        )

        scanner.visit(
            tree
        )

        all_findings.extend(
            scanner.findings
        )

    if args.mode == "text":
        findings = [
            item
            for item in all_findings
            if item.kind == "TEXT"
        ]

    elif args.mode == "numbers":
        findings = [
            item
            for item in all_findings
            if item.kind == "NUMBER"
        ]

    else:
        findings = all_findings

    findings.sort(
        key=lambda item: (
            item.kind,
            item.file,
            item.line,
            item.context,
            item.value,
        )
    )

    text_count = sum(
        item.kind == "TEXT"
        for item in findings
    )

    number_count = sum(
        item.kind == "NUMBER"
        for item in findings
    )

    lines = [
        "GMM Hardcoded Values Audit",
        "==========================",
        "",
        f"Project: {root}",
        f"Hard-coded visible text candidates: {text_count}",
        f"Fixed numeric UI candidates: {number_count}",
        "",
    ]

    current_kind = None

    for item in findings:
        if item.kind != current_kind:
            current_kind = item.kind
            lines.extend(
                [
                    "",
                    (
                        "VISIBLE TEXT"
                        if current_kind == "TEXT"
                        else "FIXED UI / BEHAVIOR NUMBERS"
                    ),
                    "-" * 40,
                ]
            )

        lines.append(
            (
                f"{item.file}:{item.line} | "
                f"{item.context} | {item.value}"
            )
        )

    if syntax_errors:
        lines.extend(
            [
                "",
                "SYNTAX / READ ERRORS",
                "-" * 40,
                *syntax_errors,
            ]
        )

    result = "\n".join(
        lines
    ) + "\n"

    print(
        result,
        end="",
    )

    if args.output is not None:
        output = (
            args.output
            if args.output.is_absolute()
            else root / args.output
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            result,
            encoding="utf-8",
        )

        print(
            f"\nReport written to: {output}"
        )

    # Der Scanner ist ein Audit-Tool, kein CI-Fehlercheck:
    # Treffer führen absichtlich NICHT zu Returncode 1.
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
