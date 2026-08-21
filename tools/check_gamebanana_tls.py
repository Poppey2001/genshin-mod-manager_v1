from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "app" / "gamebanana" / "browser.py",
    ROOT / "app" / "gamebanana" / "client.py",
    ROOT / "app" / "gamebanana" / "downloader.py",
    ROOT / "app" / "workers" / "gamebanana_preview_image_worker.py",
)


def main() -> int:
    failed = False
    for path in TARGETS:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        raw_import = False
        raw_call = False
        verified_call = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
                if any(alias.name == "urlopen" for alias in node.names):
                    raw_import = True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "urlopen":
                    raw_call = True
                if node.func.id == "verified_urlopen":
                    verified_call = True

        relative = path.relative_to(ROOT)
        if raw_import or raw_call or not verified_call:
            failed = True
            print(
                f"[FAIL] {relative}: raw_import={raw_import}, "
                f"raw_call={raw_call}, verified_call={verified_call}"
            )
        else:
            print(f"[OK]   {relative}: verified_urlopen")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
