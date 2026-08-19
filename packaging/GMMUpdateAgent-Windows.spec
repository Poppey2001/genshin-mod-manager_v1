# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

spec_file = Path(SPEC).resolve()
project_root = spec_file.parent.parent
entry = project_root / "updater" / "windows_agent" / "main.py"

if not entry.is_file():
    raise SystemExit(f"Windows update agent entry point missing: {entry}")

hiddenimports = [
    "app.version",
    "app.update_config",
    "app.services.network_tls",
    "packaging.version",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]
hiddenimports += collect_submodules("truststore")
hiddenimports += collect_submodules("certifi")
hiddenimports += collect_submodules("updater.services")

datas = collect_data_files("certifi")

# The standalone Agent uses the same translation JSON files as GMM and its
# own QSS theme. Keep their paths stable inside the PyInstaller bundle so the
# shared Agent i18n/style services can load them in onefile builds.
for relative_source, destination in (
    ("app/i18n/locales/de.json", "app/i18n/locales"),
    ("app/i18n/locales/en.json", "app/i18n/locales"),
    ("updater/styles/update_agent.qss", "updater/styles"),
):
    source = project_root / relative_source
    if not source.is_file():
        raise SystemExit(f"Required Update Agent data file missing: {source}")
    datas.append((str(source), destination))

analysis = Analysis(
    [str(entry)],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="GMMUpdateAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
