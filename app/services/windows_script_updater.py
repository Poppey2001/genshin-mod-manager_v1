from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from pathlib import Path

from app.config import (
    CACHE_DIR,
)

from app.services.update_service import (
    StagedUpdate,
)

from app.update_config import (
    UPDATE_REPLACE_ITEMS,
)


class WindowsUpdateError(
    RuntimeError
):
    pass


# ============================================================
# Platform
# ============================================================

def is_windows(
) -> bool:
    return (
        sys.platform
        .casefold()
        .startswith(
            "win"
        )
    )


def is_frozen(
) -> bool:
    return bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    )


def application_root(
) -> Path:
    # --------------------------------------------------------
    # Script-Installation
    # --------------------------------------------------------

    if not is_frozen():
        return (
            Path(
                __file__
            )
            .resolve()
            .parents[
                2
            ]
        )

    # --------------------------------------------------------
    # Für einen späteren externen Windows-Build.
    #
    # Aktuell wird ein eingebetteter PyInstaller-Build
    # absichtlich nicht als Script-Updater unterstützt.
    # --------------------------------------------------------

    return (
        Path(
            sys.executable
        )
        .resolve()
        .parent
    )


def script_update_supported(
) -> bool:
    if not is_windows():
        return False

    # Ein normaler PyInstaller-Build würde weiterhin
    # eingebetteten Python-Code ausführen.
    if is_frozen():
        return False

    root = (
        application_root()
    )

    return (
        (
            root
            / "main.py"
        ).is_file()
        and (
            root
            / "app"
            / "version.py"
        ).is_file()
    )


# ============================================================
# Neustart
# ============================================================

def _restart_command(
) -> tuple[
    Path,
    tuple[
        str,
        ...,
    ],
]:
    return (
        Path(
            sys.executable
        ).resolve(),
        (
            str(
                application_root()
                / "main.py"
            ),
        ),
    )


# ============================================================
# PowerShell Helper starten
# ============================================================

def launch_windows_update(
    staged: StagedUpdate,
) -> Path:
    if not script_update_supported():
        raise WindowsUpdateError(
            (
                "Die automatische "
                "Script-Installation ist "
                "auf diesem Build nicht "
                "verfügbar."
            )
        )

    if not (
        staged.payload_root
        .is_dir()
    ):
        raise WindowsUpdateError(
            (
                "Der entpackte Update-Ordner "
                "wurde nicht gefunden."
            )
        )

    target_root = (
        application_root()
    )

    backup_root = (
        staged.cache_root
        / "backup"
    )

    helper_path = (
        staged.cache_root
        / "update-helper.ps1"
    )

    installed_marker = (
        staged.cache_root
        / ".installed"
    )

    (
        restart_program,
        restart_arguments,
    ) = (
        _restart_command()
    )

    replace_items_ps = (
        ", ".join(
            "'"
            + item.replace(
                "'",
                "''",
            )
            + "'"
            for item
            in UPDATE_REPLACE_ITEMS
        )
    )

    restart_arguments_ps = (
        ", ".join(
            "'"
            + value.replace(
                "'",
                "''",
            )
            + "'"
            for value
            in restart_arguments
        )
    )

    script = f"""
param(
    [Parameter(Mandatory=$true)]
    [int]$ProcessId
)

$ErrorActionPreference = "Stop"

$TargetRoot = '{_ps(target_root)}'
$PayloadRoot = '{_ps(staged.payload_root)}'
$BackupRoot = '{_ps(backup_root)}'
$InstalledMarker = '{_ps(installed_marker)}'

$RestartProgram = '{_ps(restart_program)}'

$RestartArguments = @(
    {restart_arguments_ps}
)

$ReplaceItems = @(
    {replace_items_ps}
)

try {{
    # ========================================================
    # Warten bis XXMI Mod Manager beendet ist
    # ========================================================

    try {{
        Wait-Process `
            -Id $ProcessId `
            -ErrorAction SilentlyContinue
    }}
    catch {{
    }}

    # ========================================================
    # Backup
    # ========================================================

    if (Test-Path -LiteralPath $BackupRoot) {{
        Remove-Item `
            -LiteralPath $BackupRoot `
            -Recurse `
            -Force
    }}

    New-Item `
        -ItemType Directory `
        -Path $BackupRoot `
        -Force `
        | Out-Null

    foreach ($Item in $ReplaceItems) {{
        $Existing = Join-Path `
            $TargetRoot `
            $Item

        if (-not (Test-Path -LiteralPath $Existing)) {{
            continue
        }}

        $Backup = Join-Path `
            $BackupRoot `
            $Item

        $Parent = Split-Path `
            -Parent `
            $Backup

        if ($Parent) {{
            New-Item `
                -ItemType Directory `
                -Path $Parent `
                -Force `
                | Out-Null
        }}

        Copy-Item `
            -LiteralPath $Existing `
            -Destination $Backup `
            -Recurse `
            -Force
    }}

    # ========================================================
    # Neue Version installieren
    # ========================================================

    foreach ($Item in $ReplaceItems) {{
        $Source = Join-Path `
            $PayloadRoot `
            $Item

        if (-not (Test-Path -LiteralPath $Source)) {{
            continue
        }}

        $Destination = Join-Path `
            $TargetRoot `
            $Item

        if (Test-Path -LiteralPath $Destination) {{
            Remove-Item `
                -LiteralPath $Destination `
                -Recurse `
                -Force
        }}

        Copy-Item `
            -LiteralPath $Source `
            -Destination $Destination `
            -Recurse `
            -Force
    }}

    # ========================================================
    # Installation erfolgreich
    # ========================================================

    Set-Content `
        -LiteralPath $InstalledMarker `
        -Value "ok" `
        -Encoding UTF8

    # ========================================================
    # Neue Version starten
    # ========================================================

    Start-Process `
        -FilePath $RestartProgram `
        -ArgumentList $RestartArguments `
        -WorkingDirectory $TargetRoot

    exit 0
}}
catch {{
    Write-Host "Update failed:"
    Write-Host $_

    # ========================================================
    # Rollback
    # ========================================================

    foreach ($Item in $ReplaceItems) {{
        $Backup = Join-Path `
            $BackupRoot `
            $Item

        if (-not (Test-Path -LiteralPath $Backup)) {{
            continue
        }}

        $Destination = Join-Path `
            $TargetRoot `
            $Item

        if (Test-Path -LiteralPath $Destination) {{
            Remove-Item `
                -LiteralPath $Destination `
                -Recurse `
                -Force `
                -ErrorAction SilentlyContinue
        }}

        Copy-Item `
            -LiteralPath $Backup `
            -Destination $Destination `
            -Recurse `
            -Force
    }}

    Start-Process `
        -FilePath $RestartProgram `
        -ArgumentList $RestartArguments `
        -WorkingDirectory $TargetRoot

    exit 1
}}
"""

    helper_path.write_text(
        script.strip()
        + "\n",
        encoding="utf-8",
    )

    creation_flags = (
        getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
        | getattr(
            subprocess,
            "DETACHED_PROCESS",
            0,
        )
    )

    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(
                    helper_path
                ),
                "-ProcessId",
                str(
                    os.getpid()
                ),
            ],
            cwd=str(
                target_root
            ),
            close_fds=True,
            creationflags=(
                creation_flags
            ),
        )

    except OSError as error:
        raise WindowsUpdateError(
            (
                "Der Windows "
                "Update-Helper konnte "
                "nicht gestartet werden."
            )
        ) from error

    return helper_path


# ============================================================
# Cache nach erfolgreichem Neustart löschen
# ============================================================

def cleanup_successful_update_cache(
) -> None:
    updates_root = (
        CACHE_DIR
        / "updates"
    )

    if not updates_root.is_dir():
        return

    for cache_root in (
        updates_root.glob(
            "source-*"
        )
    ):
        if not cache_root.is_dir():
            continue

        marker = (
            cache_root
            / ".installed"
        )

        if not marker.is_file():
            continue

        try:
            shutil.rmtree(
                cache_root
            )

        except OSError:
            pass


# ============================================================
# Helper
# ============================================================

def _ps(
    value: Path | str,
) -> str:
    return (
        str(
            value
        )
        .replace(
            "'",
            "''",
        )
    )


__all__ = [
    "WindowsUpdateError",
    "application_root",
    "cleanup_successful_update_cache",
    "is_windows",
    "launch_windows_update",
    "script_update_supported",
]