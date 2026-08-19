#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys

from pathlib import Path


PLACEHOLDER_RE = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:![^}:]+)?"
    r"(?::[^}]+)?\}"
)


def parse_args(
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate German/English translation files "
            "against static tr() calls."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=(
            "Project root. Defaults to the current "
            "working directory."
        ),
    )

    return parser.parse_args()


def load_locale(
    path: Path,
) -> dict[str, str]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except FileNotFoundError as error:
        raise RuntimeError(
            f"Locale file not found: {path}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            (
                f"Invalid JSON in {path}: "
                f"line {error.lineno}, "
                f"column {error.colno}: "
                f"{error.msg}"
            )
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            (
                "Locale root must be a JSON object: "
                f"{path}"
            )
        )

    normalized: dict[
        str,
        str,
    ] = {}

    for key, value in data.items():
        if not isinstance(
            key,
            str,
        ):
            raise RuntimeError(
                f"Non-string locale key in {path}"
            )

        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError(
                (
                    "Locale value must be a string: "
                    f"{path} -> {key}"
                )
            )

        normalized[
            key
        ] = value

    return normalized


def python_files(
    root: Path,
) -> list[Path]:
    files: list[
        Path
    ] = []

    main_py = (
        root
        / "main.py"
    )

    if main_py.is_file():
        files.append(
            main_py
        )

    source_dirs = (
        root / "app",
        root / "updater",
    )

    for source_dir in source_dirs:
        if source_dir.is_dir():
            files.extend(
                sorted(
                    source_dir.rglob(
                        "*.py"
                    )
                )
            )

    return files


def collect_tr_keys(
    root: Path,
) -> tuple[
    dict[
        str,
        list[str],
    ],
    list[str],
]:
    static: dict[
        str,
        list[str],
    ] = {}

    dynamic: list[
        str
    ] = []

    for path in python_files(
        root
    ):
        relative = (
            path.relative_to(
                root
            )
        )

        try:
            tree = ast.parse(
                path.read_text(
                    encoding="utf-8"
                ),
                filename=str(
                    relative
                ),
            )

        except SyntaxError as error:
            raise RuntimeError(
                (
                    "Python syntax error while scanning "
                    f"{relative}:{error.lineno}: "
                    f"{error.msg}"
                )
            ) from error

        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            function = (
                node.func
            )

            is_tr = (
                isinstance(
                    function,
                    ast.Name,
                )
                and function.id
                == "tr"
            )

            if not is_tr:
                continue

            location = (
                f"{relative}:{node.lineno}"
            )

            if not node.args:
                dynamic.append(
                    location
                )
                continue

            first = (
                node.args[0]
            )

            if (
                isinstance(
                    first,
                    ast.Constant,
                )
                and isinstance(
                    first.value,
                    str,
                )
            ):
                static.setdefault(
                    first.value,
                    [],
                ).append(
                    location
                )

            else:
                dynamic.append(
                    location
                )

    return (
        static,
        dynamic,
    )


def placeholder_names(
    value: str,
) -> set[str]:
    return set(
        PLACEHOLDER_RE.findall(
            value
        )
    )


def print_missing(
    *,
    locale_name: str,
    missing: list[str],
    static_keys: dict[
        str,
        list[str],
    ],
) -> None:
    if not missing:
        return

    print(
        (
            f"Static tr() keys missing from "
            f"{locale_name}:"
        )
    )

    for key in missing:
        locations = ", ".join(
            static_keys.get(
                key,
                [],
            )
        )

        print(
            f"  {key} -> {locations}"
        )

    print()


def main(
) -> int:
    args = parse_args()

    root = (
        args.root
        .expanduser()
        .resolve()
    )

    de_path = (
        root
        / "app"
        / "i18n"
        / "locales"
        / "de.json"
    )

    en_path = (
        root
        / "app"
        / "i18n"
        / "locales"
        / "en.json"
    )

    try:
        de = load_locale(
            de_path
        )

        en = load_locale(
            en_path
        )

        static_keys, dynamic_calls = (
            collect_tr_keys(
                root
            )
        )

    except RuntimeError as error:
        print(
            "[I18N] FAILED",
            file=sys.stderr,
        )

        print(
            str(
                error
            ),
            file=sys.stderr,
        )

        return 1

    failed = False

    de_keys = set(
        de
    )

    en_keys = set(
        en
    )

    only_de = sorted(
        de_keys
        - en_keys
    )

    only_en = sorted(
        en_keys
        - de_keys
    )

    if only_de:
        failed = True

        print(
            "Keys only present in de.json:"
        )

        for key in only_de:
            print(
                f"  {key}"
            )

        print()

    if only_en:
        failed = True

        print(
            "Keys only present in en.json:"
        )

        for key in only_en:
            print(
                f"  {key}"
            )

        print()

    used = set(
        static_keys
    )

    missing_de = sorted(
        used
        - de_keys
    )

    missing_en = sorted(
        used
        - en_keys
    )

    if missing_de:
        failed = True

    if missing_en:
        failed = True

    print_missing(
        locale_name="de.json",
        missing=missing_de,
        static_keys=static_keys,
    )

    print_missing(
        locale_name="en.json",
        missing=missing_en,
        static_keys=static_keys,
    )

    empty_de = sorted(
        key
        for key, value
        in de.items()
        if not value.strip()
    )

    empty_en = sorted(
        key
        for key, value
        in en.items()
        if not value.strip()
    )

    if empty_de:
        failed = True

        print(
            "Empty values in de.json:"
        )

        for key in empty_de:
            print(
                f"  {key}"
            )

        print()

    if empty_en:
        failed = True

        print(
            "Empty values in en.json:"
        )

        for key in empty_en:
            print(
                f"  {key}"
            )

        print()

    placeholder_errors: list[
        tuple[
            str,
            set[str],
            set[str],
        ]
    ] = []

    for key in sorted(
        de_keys
        & en_keys
    ):
        de_fields = (
            placeholder_names(
                de[key]
            )
        )

        en_fields = (
            placeholder_names(
                en[key]
            )
        )

        if (
            de_fields
            != en_fields
        ):
            placeholder_errors.append(
                (
                    key,
                    de_fields,
                    en_fields,
                )
            )

    if placeholder_errors:
        failed = True

        print(
            "Placeholder mismatches:"
        )

        for (
            key,
            de_fields,
            en_fields,
        ) in placeholder_errors:
            print(
                (
                    f"  {key}: "
                    f"DE={sorted(de_fields)} "
                    f"EN={sorted(en_fields)}"
                )
            )

        print()

    if failed:
        print(
            "[I18N] FAILED"
        )

        return 1

    print(
        "[I18N] OK"
    )

    print(
        (
            "[I18N] Locale keys: "
            f"{len(de_keys)}"
        )
    )

    print(
        (
            "[I18N] Static tr() keys: "
            f"{len(used)}"
        )
    )

    print(
        (
            "[I18N] Dynamic tr() calls "
            "(informational): "
            f"{len(dynamic_calls)}"
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
