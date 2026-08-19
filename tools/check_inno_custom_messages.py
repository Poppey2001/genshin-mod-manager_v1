from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "windows" / "installer.iss"

# Messages supplied by Inno Setup's language files and used by this installer.
INNO_BUILTIN_MESSAGES = {
    "AdditionalIcons",
    "CreateDesktopIcon",
    "LaunchProgram",
}


def main() -> int:
    text = INSTALLER.read_text(encoding="utf-8")

    references = sorted(
        set(re.findall(r"\{cm:([A-Za-z0-9_]+)", text))
    )

    localized: dict[str, set[str]] = {}
    for language, key in re.findall(
        r"^(english|german)\.([A-Za-z0-9_]+)=",
        text,
        flags=re.MULTILINE,
    ):
        localized.setdefault(key, set()).add(language)

    errors: list[str] = []

    for key in references:
        if key in INNO_BUILTIN_MESSAGES:
            continue

        languages = localized.get(key, set())
        if not languages:
            errors.append(
                f"Missing [CustomMessages] definition for {{cm:{key}}}"
            )
            continue

        for required in ("english", "german"):
            if required not in languages:
                errors.append(
                    f"Missing {required}.{key} in [CustomMessages]"
                )

    if errors:
        print("Inno Setup custom-message validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Inno Setup custom-message validation OK")
    print("Resolved cm references:")
    for key in references:
        source = "Inno built-in" if key in INNO_BUILTIN_MESSAGES else "CustomMessages"
        print(f"  - {key}: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
