# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)


spec_file = Path(
    SPEC
).resolve()

project_root = (
    spec_file
    .parent
    .parent
)

print(
    f"[GMM SPEC] Spec file: {spec_file}"
)

print(
    f"[GMM SPEC] Project root: {project_root}"
)

main_py = (
    project_root
    / "main.py"
)

app_dir = (
    project_root
    / "app"
)

if not main_py.is_file():
    raise SystemExit(
        (
            "main.py not found. "
            f"Resolved project root: {project_root}; "
            f"expected: {main_py}"
        )
    )

if not app_dir.is_dir():
    raise SystemExit(
        (
            "app directory not found. "
            f"Resolved project root: {project_root}; "
            f"expected: {app_dir}"
        )
    )


datas = collect_data_files(
    "app"
)

# certifi is a fallback CA bundle when native truststore is unavailable.
datas += collect_data_files(
    "certifi"
)

assets_dir = (
    project_root
    / "assets"
)

if assets_dir.is_dir():
    datas.append(
        (
            str(
                assets_dir
            ),
            "assets",
        )
    )

for root_file in (
    "LICENSE",
    "THIRD_PARTY_NOTICES.txt",
):
    path = (
        project_root
        / root_file
    )

    if path.is_file():
        datas.append(
            (
                str(
                    path
                ),
                ".",
            )
        )

hiddenimports = collect_submodules(
    "app"
)

hiddenimports += collect_submodules(
    "truststore"
)

hiddenimports += collect_submodules(
    "certifi"
)

analysis = Analysis(
    [
        str(
            main_py
        )
    ],
    pathex=[
        str(
            project_root
        )
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(
    analysis.pure
)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GenshinModManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GenshinModManager",
)
