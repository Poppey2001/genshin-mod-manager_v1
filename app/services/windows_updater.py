from __future__ import annotations

import os
import subprocess
import zipfile

from pathlib import Path

from app.config import (
    CACHE_DIR,
)

from app.services.runtime_platform import (
    application_root,
    is_windows,
    restart_arguments,
    restart_executable,
)

from app.update_config import (
    WINDOWS_REPLACE_ITEMS,
)


class WindowsUpdateError(
    RuntimeError
):
    pass


# ============================================================
# ZIP prüfen
# ============================================================

def validate_update_archive(
    archive_path: Path,
) -> None:
    archive_path = (
        Path(
            archive_path
        )
        .expanduser()
        .absolute()
    )

    if not archive_path.is_file():
        raise WindowsUpdateError(
            (
                "Das Update-Archiv "
                "wurde nicht gefunden."
            )
        )

    if not zipfile.is_zipfile(
        archive_path
    ):
        raise WindowsUpdateError(
            (
                "Das heruntergeladene "
                "Update ist kein gültiges "
                "ZIP-Archiv."
            )
        )

    with zipfile.ZipFile(
        archive_path,
        "r",
    ) as archive:
        names = {
            name
            .replace(
                "\\",
                "/",
            )
            .strip(
                "/"
            )
            for name
            in archive.namelist()
        }

    # --------------------------------------------------------
    # Mindestens app/ muss vorhanden sein.
    # --------------------------------------------------------

    has_app = any(
        (
            name == "app"
            or name.startswith(
                "app/"
            )
        )
        for name
        in names
    )

    if not has_app:
        raise WindowsUpdateError(
            (
                "Das Update-ZIP enthält "
                "keinen app/-Ordner."
            )
        )


# ============================================================
# Helper erzeugen
# ============================================================

def create_windows_update_helper(
    *,
    archive_path: Path,
) -> Path:
    if not is_windows():
        raise WindowsUpdateError(
            (
                "Windows-Updater wurde "
                "auf einem Nicht-Windows-System "
                "aufgerufen."
            )
        )

    validate_update_archive(
        archive_path
    )

    helper_directory = (
        CACHE_DIR
        / "updates"
    )

    helper_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    helper_path = (
        helper_directory
        / "xxmi-update-helper.ps1"
    )

    target_root = (
        application_root()
    )

    restart_program = (
        restart_executable()
    )

    restart_args = (
        restart_arguments()
    )

    replace_items = (
        WINDOWS_REPLACE_ITEMS
    )

    # --------------------------------------------------------
    # PowerShell Array
    # --------------------------------------------------------

    replace_ps = ", ".join(
        (
            "'"
            + item.replace(
                "'",
                "''",
            )
            + "'"
        )
        for item
        in replace_items
    )

    restart_args_ps = ", ".join(
        (
            "'"
            + argument.replace(
                "'",
                "''",
            )
            + "'"
        )
        for argument
        in restart_args
    )

    script = f"""
param(
    [Parameter(Mandatory=$true)]
    [int]$ProcessId,

    [Parameter(Mandatory=$true)]
    [string]$Archive,

    [Parameter(Mandatory=$true)]
    [string]$TargetRoot
)

$ErrorActionPreference = "Stop"

$ReplaceItems = @(
    {replace_ps}
)

$RestartProgram = '{str(restart_program).replace("'", "''")}'

$RestartArguments = @(
    {restart_args_ps}
)

$TempRoot = Join-Path `
    $env:TEMP `
    ("xxmi-update-" + [guid]::NewGuid().ToString())

$ExtractRoot = Join-Path `
    $TempRoot `
    "payload"

$BackupRoot = Join-Path `
    $TempRoot `
    "backup"

try {{
    Write-Host "Waiting for application to close..."

    try {{
        Wait-Process `
            -Id $ProcessId `
            -ErrorAction SilentlyContinue
    }}
    catch {{
    }}

    New-Item `
        -ItemType Directory `
        -Path $ExtractRoot `
        -Force `
        | Out-Null

    New-Item `
        -ItemType Directory `
        -Path $BackupRoot `
        -Force `
        | Out-Null

    Write-Host "Extracting update..."

    Expand-Archive `
        -LiteralPath $Archive `
        -DestinationPath $ExtractRoot `
        -Force

    # ========================================================
    # Backup
    # ========================================================

    foreach ($Item in $ReplaceItems) {{
        $Existing = Join-Path `
            $TargetRoot `
            $Item

        if (Test-Path -LiteralPath $Existing) {{
            $Backup = Join-Path `
                $BackupRoot `
                $Item

            $BackupParent = Split-Path `
                -Parent `
                $Backup

            if ($BackupParent) {{
                New-Item `
                    -ItemType Directory `
                    -Path $BackupParent `
                    -Force `
                    | Out-Null
            }}

            Copy-Item `
                -LiteralPath $Existing `
                -Destination $Backup `
                -Recurse `
                -Force
        }}
    }}

    # ========================================================
    # Replace
    # ========================================================

    foreach ($Item in $ReplaceItems) {{
        $Source = Join-Path `
            $ExtractRoot `
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

    Write-Host "Update installed."

    Start-Process `
        -FilePath $RestartProgram `
        -ArgumentList $RestartArguments `
        -WorkingDirectory $TargetRoot

    Start-Sleep `
        -Milliseconds 500

    Remove-Item `
        -LiteralPath $TempRoot `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue

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

    return helper_path


# ============================================================
# Start
# ============================================================

def stage_windows_update(
    *,
    archive_path: Path,
) -> Path:
    helper = (
        create_windows_update_helper(
            archive_path=(
                archive_path
            )
        )
    )

    target_root = (
        application_root()
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

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(
            helper
        ),
        "-ProcessId",
        str(
            os.getpid()
        ),
        "-Archive",
        str(
            Path(
                archive_path
            )
            .resolve()
        ),
        "-TargetRoot",
        str(
            target_root
        ),
    ]

    try:
        subprocess.Popen(
            command,
            cwd=str(
                target_root
            ),
            creationflags=(
                creation_flags
            ),
            close_fds=True,
        )

    except OSError as error:
        raise WindowsUpdateError(
            (
                "Der Windows-Update-Helper "
                "konnte nicht gestartet werden."
            )
        ) from error

    return helper