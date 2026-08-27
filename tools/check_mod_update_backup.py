from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = [
    ROOT / "app/services/library_mod_backup_service.py",
    ROOT / "app/services/library_mod_update_installer.py",
    ROOT / "app/services/library_mod_update_service.py",
    ROOT / "app/services/mod_manager.py",
    ROOT / "app/workers/mod_update_install_worker.py",
    ROOT / "app/dialogs/library_mod_backup_dialog.py",
    ROOT / "app/dialogs/library_mod_update_dialog.py",
    ROOT / "app/pages/library_page.py",
]

for path in PYTHON_FILES:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

de = json.loads((ROOT / "app/i18n/locales/de.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8"))
if set(de) != set(en):
    raise SystemExit("DE/EN translation keys do not match")

required = {
    "library.mod_updates.action.install",
    "library.mod_updates.action.backups",
    "library.mod_updates.action.restore",
    "library.mod_updates.progress.backup",
    "library.mod_updates.progress.download",
    "library.mod_updates.restore.confirm.title",
}
missing = required - set(de)
if missing:
    raise SystemExit(f"Missing translation keys: {sorted(missing)}")

manager = (ROOT / "app/services/mod_manager.py").read_text(encoding="utf-8")
for token in ("def managed_copy_for", "def refresh_from_library", "def restore_managed_copy"):
    if token not in manager:
        raise SystemExit(f"Missing ModManager API: {token}")

installer = (ROOT / "app/services/library_mod_update_installer.py").read_text(encoding="utf-8")
for token in ("create_backup(", "extract_archive_securely(", "restore_library(", "set_installed_revision("):
    if token not in installer:
        raise SystemExit(f"Missing transactional update step: {token}")

qss = (ROOT / "app/styles/library.qss").read_text(encoding="utf-8")
if qss.count("{") != qss.count("}"):
    raise SystemExit("library.qss braces are unbalanced")
if "min-height: 34px" not in qss:
    raise SystemExit("V21.8 action button sizing rule missing")

print("[V21.8] OK")
print(f"Python files checked: {len(PYTHON_FILES)}")
print(f"Translation keys: {len(de)}")
