from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.models.ini_analysis import (
    IniAssignment,
    IniFileAnalysis,
    IniKeyBinding,
    IniStateLabel,
    ModIniAnalysis,
)


MAX_DISCOVERED_INI_FILES = 250
MAX_ANALYZED_INI_FILES = 30
MAX_INI_FILE_SIZE = 2 * 1024 * 1024
MAX_SCAN_DEPTH = 10

IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
}

PREFERRED_INI_NAMES = {
    "master.ini",
    "merge.ini",
    "merged.ini",
}

SECTION_PATTERN = re.compile(
    r"^\s*\[([^\]]+)]\s*(?:[;#].*)?$"
)

PROPERTY_PATTERN = re.compile(
    r"^\s*([^=]+?)\s*=\s*(.*?)\s*$"
)

KEY_SECTION_PATTERN = re.compile(
    r"^\s*\[key[^\]]*]",
    flags=re.IGNORECASE | re.MULTILINE,
)

NAMESPACE_PATTERN = re.compile(
    r"^\s*namespace\s*=\s*(.+?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

MERGED_MOD_PATTERN = re.compile(
    r"^\s*[;#]\s*merged\s+mod\s*:\s*(.+?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

STATE_LABEL_PATTERN = re.compile(
    r"\b(?:cycle|state|option|preset)\s*"
    r"(\d+)\s*[:=\-]\s*(.+)",
    flags=re.IGNORECASE,
)

CONTROL_PROPERTIES = {
    "key",
    "back",
    "type",
    "condition",
    "smart",
    "wrap",
    "delay",
    "release_delay",
    "transition",
    "release_transition",
    "transition_type",
    "release_transition_type",
}


@dataclass(slots=True)
class ParsedSection:
    name: str
    leading_comments: list[str]
    lines: list[str]


def analyze_mod_ini(
    root_path: Path | str,
) -> ModIniAnalysis:
    """
    Analysiert Merge-, Master- und andere INI-Dateien
    mit [Key...]-Sektionen.
    """
    root = Path(root_path).expanduser()

    if not root.exists():
        return ModIniAnalysis(
            root_path=root,
            files=(),
            warnings=(
                f"Der Mod-Ordner existiert nicht: {root}",
            ),
        )

    if not root.is_dir():
        return ModIniAnalysis(
            root_path=root,
            files=(),
            warnings=(
                f"Der Mod-Pfad ist kein Ordner: {root}",
            ),
        )

    discovered_files, discovery_warnings = (
        _discover_ini_files(root)
    )

    preferred_files = [
        path
        for path in discovered_files
        if _is_preferred_ini(path)
    ]

    # Falls keine Datei Merge/Master heißt, suchen wir als
    # Fallback nach beliebigen INIs mit [Key...]-Sektionen.
    if not preferred_files:
        for path in discovered_files:
            try:
                content = _read_ini_text(
                    path,
                    size_limit=256 * 1024,
                )
            except OSError:
                continue

            if KEY_SECTION_PATTERN.search(content):
                preferred_files.append(path)

    preferred_files.sort(
        key=_ini_sort_key
    )

    warnings = list(discovery_warnings)

    if len(preferred_files) > MAX_ANALYZED_INI_FILES:
        warnings.append(
            "Es wurden mehr steuernde INI-Dateien gefunden, "
            f"als analysiert werden können. Es werden nur die "
            f"ersten {MAX_ANALYZED_INI_FILES} angezeigt."
        )

    analyses: list[IniFileAnalysis] = []

    for ini_path in preferred_files[
        :MAX_ANALYZED_INI_FILES
    ]:
        try:
            analyses.append(
                _analyze_ini_file(ini_path)
            )

        except OSError as error:
            warnings.append(
                f"{ini_path}: {error}"
            )

    return ModIniAnalysis(
        root_path=root,
        files=tuple(analyses),
        warnings=tuple(warnings),
    )


def _discover_ini_files(
    root: Path,
) -> tuple[list[Path], list[str]]:
    found_files: list[Path] = []
    warnings: list[str] = []

    root_depth = len(root.parts)

    def on_walk_error(
        error: OSError,
    ) -> None:
        warnings.append(str(error))

    for current_directory, directory_names, file_names in os.walk(
        root,
        followlinks=False,
        onerror=on_walk_error,
    ):
        current_path = Path(current_directory)

        depth = (
            len(current_path.parts)
            - root_depth
        )

        if depth >= MAX_SCAN_DEPTH:
            directory_names[:] = []
        else:
            directory_names[:] = [
                name
                for name in directory_names
                if (
                    name not in IGNORED_DIRECTORIES
                    and not name.startswith(".")
                )
            ]

        for file_name in file_names:
            if (
                Path(file_name).suffix.casefold()
                != ".ini"
            ):
                continue

            found_files.append(
                current_path / file_name
            )

            if (
                len(found_files)
                >= MAX_DISCOVERED_INI_FILES
            ):
                warnings.append(
                    "Die INI-Suche wurde begrenzt, weil mehr "
                    f"als {MAX_DISCOVERED_INI_FILES} Dateien "
                    "gefunden wurden."
                )

                return found_files, warnings

    found_files.sort(
        key=lambda path: str(path).casefold()
    )

    return found_files, warnings


def _is_preferred_ini(
    path: Path,
) -> bool:
    name = path.name.casefold()
    stem = path.stem.casefold()

    return (
        name in PREFERRED_INI_NAMES
        or "merge" in stem
        or "master" in stem
    )


def _ini_sort_key(
    path: Path,
) -> tuple[int, str]:
    name = path.name.casefold()

    priority = {
        "master.ini": 0,
        "merge.ini": 1,
        "merged.ini": 2,
    }.get(
        name,
        3,
    )

    return priority, str(path).casefold()


def _analyze_ini_file(
    path: Path,
) -> IniFileAnalysis:
    warnings: list[str] = []

    try:
        file_size = path.stat().st_size
    except OSError as error:
        raise OSError(
            f"Dateigröße konnte nicht gelesen werden: {error}"
        ) from error

    if file_size > MAX_INI_FILE_SIZE:
        return IniFileAnalysis(
            path=path,
            namespace=None,
            merged_sources=(),
            key_bindings=(),
            warnings=(
                "Die Datei ist größer als 2 MiB und wurde "
                "aus Sicherheitsgründen nicht analysiert.",
            ),
        )

    text = _read_ini_text(
        path,
        size_limit=MAX_INI_FILE_SIZE,
    )

    namespace = _find_namespace(text)
    merged_sources = _find_merged_sources(text)

    sections = _split_sections(text)
    key_bindings: list[IniKeyBinding] = []

    for section in sections:
        if not section.name.casefold().startswith(
            "key"
        ):
            continue

        binding = _analyze_key_section(
            section
        )

        key_bindings.append(binding)

    if not key_bindings:
        warnings.append(
            "In dieser Datei wurden keine "
            "[Key...]-Sektionen gefunden."
        )

    return IniFileAnalysis(
        path=path,
        namespace=namespace,
        merged_sources=merged_sources,
        key_bindings=tuple(key_bindings),
        warnings=tuple(warnings),
    )


def _read_ini_text(
    path: Path,
    size_limit: int,
) -> str:
    with path.open("rb") as file:
        raw_data = file.read(
            size_limit + 1
        )

    if len(raw_data) > size_limit:
        raise OSError(
            "Die INI-Datei überschreitet das Leselimit."
        )

    # UTF-8 ist üblich. errors=replace verhindert,
    # dass einzelne ungültige Zeichen die Analyse abbrechen.
    return raw_data.decode(
        "utf-8-sig",
        errors="replace",
    )


def _find_namespace(
    text: str,
) -> str | None:
    match = NAMESPACE_PATTERN.search(text)

    if match is None:
        return None

    return _remove_inline_comment(
        match.group(1)
    ).strip() or None


def _find_merged_sources(
    text: str,
) -> tuple[str, ...]:
    match = MERGED_MOD_PATTERN.search(text)

    if match is None:
        return ()

    return tuple(
        value.strip()
        for value in _split_value_list(
            match.group(1)
        )
        if value.strip()
    )


def _split_sections(
    text: str,
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []

    current_section: ParsedSection | None = None
    pending_comments: list[str] = []

    for raw_line in text.splitlines():
        header_match = SECTION_PATTERN.match(
            raw_line
        )

        if header_match:
            if current_section is not None:
                sections.append(
                    current_section
                )

            current_section = ParsedSection(
                name=header_match.group(1).strip(),
                leading_comments=list(
                    pending_comments
                ),
                lines=[],
            )

            pending_comments.clear()
            continue

        stripped_line = raw_line.strip()

        if current_section is None:
            if stripped_line.startswith(
                (";", "#")
            ):
                pending_comments.append(
                    _clean_comment(stripped_line)
                )

            elif stripped_line:
                pending_comments.clear()

            continue

        current_section.lines.append(
            raw_line
        )

    if current_section is not None:
        sections.append(current_section)

    return sections


def _analyze_key_section(
    section: ParsedSection,
) -> IniKeyBinding:
    properties: list[
        tuple[str, str, str]
    ] = []

    comments = list(
        section.leading_comments
    )

    for raw_line in section.lines:
        stripped_line = raw_line.strip()

        if not stripped_line:
            continue

        if stripped_line.startswith(
            (";", "#")
        ):
            comments.append(
                _clean_comment(stripped_line)
            )
            continue

        property_match = PROPERTY_PATTERN.match(
            raw_line
        )

        if property_match is None:
            continue

        original_name = (
            property_match.group(1).strip()
        )

        normalized_name = (
            original_name.casefold()
        )

        value = _remove_inline_comment(
            property_match.group(2)
        ).strip()

        properties.append(
            (
                original_name,
                normalized_name,
                value,
            )
        )

    keys = tuple(
        value
        for _original, normalized, value in properties
        if normalized == "key" and value
    )

    back_keys = tuple(
        value
        for _original, normalized, value in properties
        if normalized == "back" and value
    )

    key_type = _first_property(
        properties,
        "type",
    ) or "activate"

    condition = _first_property(
        properties,
        "condition",
    )

    smart = _first_property(
        properties,
        "smart",
    )

    wrap = _first_property(
        properties,
        "wrap",
    )

    run_commands = tuple(
        value
        for _original, normalized, value in properties
        if normalized == "run" and value
    )

    assignments: list[IniAssignment] = []

    for original_name, normalized_name, value in properties:
        if (
            normalized_name in CONTROL_PROPERTIES
            or normalized_name == "run"
        ):
            continue

        assignments.append(
            IniAssignment(
                name=original_name,
                raw_value=value,
                values=tuple(
                    _split_value_list(value)
                ),
            )
        )

    state_labels = _extract_state_labels(
        comments
    )

    return IniKeyBinding(
        section_name=section.name,
        keys=keys,
        back_keys=back_keys,
        key_type=key_type.casefold(),
        condition=condition,
        assignments=tuple(assignments),
        run_commands=run_commands,
        comments=tuple(
            comment
            for comment in comments
            if comment
        ),
        state_labels=state_labels,
        smart=smart,
        wrap=wrap,
    )


def _first_property(
    properties: list[
        tuple[str, str, str]
    ],
    requested_name: str,
) -> str | None:
    for _original, normalized, value in properties:
        if normalized == requested_name:
            return value or None

    return None


def _extract_state_labels(
    comments: list[str],
) -> tuple[IniStateLabel, ...]:
    labels: list[IniStateLabel] = []

    for comment in comments:
        match = STATE_LABEL_PATTERN.search(
            comment
        )

        if match is None:
            continue

        labels.append(
            IniStateLabel(
                index=int(match.group(1)),
                label=match.group(2).strip(),
            )
        )

    return tuple(labels)


def _clean_comment(
    value: str,
) -> str:
    return value.lstrip(
        ";#"
    ).strip()


def _remove_inline_comment(
    value: str,
) -> str:
    """
    Entfernt Kommentare, wenn vor ; oder # ein Leerzeichen
    steht. Dadurch bleiben viele Pfade und Ausdrücke erhalten.
    """
    for marker in (
        " ;",
        "\t;",
        " #",
        "\t#",
    ):
        marker_position = value.find(
            marker
        )

        if marker_position >= 0:
            value = value[
                :marker_position
            ]

    return value.rstrip()


def _split_value_list(
    value: str,
) -> list[str]:
    """
    Trennt Kommawerte, berücksichtigt aber einfache
    Klammern und Anführungszeichen.
    """
    values: list[str] = []
    current: list[str] = []

    bracket_depth = 0
    quote_character: str | None = None

    for character in value:
        if quote_character is not None:
            current.append(character)

            if character == quote_character:
                quote_character = None

            continue

        if character in {
            '"',
            "'",
        }:
            quote_character = character
            current.append(character)
            continue

        if character in "([{":
            bracket_depth += 1
            current.append(character)
            continue

        if character in ")]}":
            bracket_depth = max(
                0,
                bracket_depth - 1,
            )
            current.append(character)
            continue

        if (
            character == ","
            and bracket_depth == 0
        ):
            values.append(
                "".join(current).strip()
            )
            current.clear()
            continue

        current.append(character)

    values.append(
        "".join(current).strip()
    )

    return [
        item
        for item in values
        if item
    ]