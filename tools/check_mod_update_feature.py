from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "app/services/library_mod_update_service.py",
    "app/workers/mod_update_check_worker.py",
    "app/dialogs/library_mod_update_dialog.py",
    "app/pages/library_page.py",
    "app/widgets/library/library_filter_bar.py",
    "app/widgets/library/library_mod_list.py",
    "app/widgets/library/library_gallery.py",
    "app/styles/library.qss",
    "app/i18n/locales/de.json",
    "app/i18n/locales/en.json",
)

for relative in REQUIRED:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"[MOD UPDATE] missing: {relative}")

for relative in REQUIRED:
    path = ROOT / relative
    if path.suffix == ".py":
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

de = json.loads((ROOT / "app/i18n/locales/de.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8"))
if set(de) != set(en):
    only_de = sorted(set(de) - set(en))
    only_en = sorted(set(en) - set(de))
    raise SystemExit(
        f"[MOD UPDATE] locale mismatch; only DE={only_de[:10]}, only EN={only_en[:10]}"
    )

required_keys = {
    "library.mod_updates.check_button",
    "library.mod_updates.filter.available",
    "library.mod_updates.badge",
    "library.mod_updates.dialog.title",
    "library.mod_updates.mark_current",
}
missing = sorted(key for key in required_keys if key not in de)
if missing:
    raise SystemExit(f"[MOD UPDATE] translation keys missing: {missing}")

qss = (ROOT / "app/styles/library.qss").read_text(encoding="utf-8")
if qss.count("{") != qss.count("}"):
    raise SystemExit("[MOD UPDATE] library.qss braces do not match")
if "QLabel#modUpdateBadge" not in qss:
    raise SystemExit("[MOD UPDATE] update badge QSS missing")

page = (ROOT / "app/pages/library_page.py").read_text(encoding="utf-8")
for marker in (
    "LibraryModUpdateService",
    "ModUpdateCheckWorker",
    "check_mod_updates",
    "selected_update_status",
):
    if marker not in page:
        raise SystemExit(f"[MOD UPDATE] LibraryPage marker missing: {marker}")

client = (ROOT / "app/gamebanana/client.py").read_text(encoding="utf-8")
if "verified_urlopen" not in client:
    raise SystemExit("[MOD UPDATE] GameBanana client is not using verified_urlopen")

print("[MOD UPDATE] OK")
print(f"Locale keys: {len(de)}")
