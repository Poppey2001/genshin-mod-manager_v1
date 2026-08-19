# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)


project_root = Path(
    SPECPATH
).resolve().parent.parent

datas = collect_data_files(
    "app"
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

analysis = Analysis(
    [
        str(
            project_root
            / "main.py"
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
