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


class WindowsScriptUpdateError(
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


def application_root(
) -> Path:
    if bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    ):
        return (
            Path(
                sys.executable
            )
            .resolve()
            .parent
        )

    return (
        Path(
            __file__
        )
        .resolve()
        .parents[
            2
        ]
    )


def external_scripts_available(
) -> bool:
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
# Restart
# ============================================================

def _restart_program(
) -> tuple[
    Path,
    tuple[
        str,
        ...,
    ],
]:
    if bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    ):
        return (
            Path(
                sys.executable
            ).resolve(),
            (),
        )

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
# Stage / Helper
# ============================================================

def launch_script_update_helper(
    staged: StagedUpdate,
) -> Path:
    if not is_windows():
        raise WindowsScriptUpdateError(
            (
                "Script-Installation ist "
                "nur unter Windows verfügbar."
            )
        )

    if not external_scripts_available():
        raise WindowsScriptUpdateError(
            (
                "Dieser Windows-Build lädt "
                "keine externen Python-Scripts. "
                "Der Script-Updater kann diesen "
                "Build deshalb nicht aktualisieren."
            )
        )

    target_root = (
        application_root()
    )

    if not (
        staged.manifest_path
        .is_file()
    ):
        raise WindowsScriptUpdateError(
            "Update-Manifest fehlt."
        )

    manifest = json.loads(
        staged.manifest_path
        .read_text(
            encoding="utf-8"
        )
    )

    files = (
        manifest.get(
            "files"
        )
    )

    if not isinstance(
        files,
        list,
    ):
        raise WindowsScriptUpdateError(
            "Ungültiges Update-Manifest."
        )

    (
        restart_program,
        restart_args,
    ) = (
        _restart_program()
    )

    helper_path = (
        staged.cache_root
        / "update-helper.ps1"
    )

    backup_root = (
        staged.cache_root
        / "backup"
    )

    installed_marker = (
        staged.cache_root
        / ".installed"
    )

    restart_args_ps = ", ".join(
        (
            "'"
            + arg.replace(
                "'",
                "''",
            )
            + "'"
        )
        for arg
        in restart_args
    )

    script = f"""
param(
    [Parameter(Mandatory=$true)]
    [int]$ProcessId
)

$ErrorActionPreference = "Stop"

$TargetRoot = '{str(target_root).replace("'", "''")}'
$PayloadRoot = '{str(staged.payload_root).replace("'", "''")}'
$ManifestPath = '{str(staged.manifest_path).replace("'", "''")}'
$BackupRoot = '{str(backup_root).replace("'", "''")}'
$InstalledMarker = '{str(installed_marker).replace("'", "''")}'

$RestartProgram = '{str(restart_program).replace("'", "''")}'

$RestartArguments = @(
    {restart_args_ps}
)

$CreatedFiles = New-Object `
    System.Collections.Generic.List[string]

try {{
    # ========================================================
    # Auf Hauptprogramm warten
    # ========================================================

    try {{
        Wait-Process `
            -Id $ProcessId `
            -ErrorAction SilentlyContinue
    }}
    catch {{
    }}

    # ========================================================
    # Manifest
    # ========================================================

    $Manifest = Get-Content `
        -LiteralPath $ManifestPath `
        -Raw `
        | ConvertFrom-Json

    New-Item `
        -ItemType Directory `
        -Path $BackupRoot `
        -Force `
        | Out-Null

    # ========================================================
    # Dateien austauschen
    # ========================================================

    foreach ($File in $Manifest.files) {{
        $RelativePath = `
            [string]$File.path

        $Source = Join-Path `
            $PayloadRoot `
            $RelativePath

        $Destination = Join-Path `
            $TargetRoot `
            $RelativePath

        if (-not (Test-Path -LiteralPath $Source)) {{
            throw "Payload file missing: $RelativePath"
        }}

        $DestinationParent = Split-Path `
            -Parent `
            $Destination

        if ($DestinationParent) {{
            New-Item `
                -ItemType Directory `
                -Path $DestinationParent `
                -Force `
                | Out-Null
        }}

        if (Test-Path -LiteralPath $Destination) {{
            $Backup = Join-Path `
                $BackupRoot `
                $RelativePath

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
                -LiteralPath $Destination `
                -Destination $Backup `
                -Force
        }}
        else {{
            $CreatedFiles.Add(
                $RelativePath
            )
        }}

        Copy-Item `
            -LiteralPath $Source `
            -Destination $Destination `
            -Force
    }}

    # ========================================================
    # Erfolgsmarker
    # ========================================================

    Set-Content `
        -LiteralPath $InstalledMarker `
        -Value "ok" `
        -Encoding UTF8

    # ========================================================
    # Neustart
    # ========================================================

    Start-Process `
        -FilePath $RestartProgram `
        -ArgumentList $RestartArguments `
        -WorkingDirectory $TargetRoot

    exit 0
}}
catch {{
    Write-Host $_

    # ========================================================
    # Rollback
    # ========================================================

    if (Test-Path -LiteralPath $ManifestPath) {{
        $Manifest = Get-Content `
            -LiteralPath $ManifestPath `
            -Raw `
            | ConvertFrom-Json

        foreach ($File in $Manifest.files) {{
            $RelativePath = `
                [string]$File.path

            $Backup = Join-Path `
                $BackupRoot `
                $RelativePath

            $Destination = Join-Path `
                $TargetRoot `
                $RelativePath

            if (Test-Path -LiteralPath $Backup) {{
                $Parent = Split-Path `
                    -Parent `
                    $Destination

                if ($Parent) {{
                    New-Item `
                        -ItemType Directory `
                        -Path $Parent `
                        -Force `
                        | Out-Null
                }}

                Copy-Item `
                    -LiteralPath $Backup `
                    -Destination $Destination `
                    -Force
            }}
        }}
    }}

    foreach ($RelativePath in $CreatedFiles) {{
        $Destination = Join-Path `
            $TargetRoot `
            $RelativePath

        if (Test-Path -LiteralPath $Destination) {{
            Remove-Item `
                -LiteralPath $Destination `
                -Force `
                -ErrorAction SilentlyContinue
        }}
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
        raise WindowsScriptUpdateError(
            (
                "Der Windows Update Helper "
                "konnte nicht gestartet werden."
            )
        ) from error

    return helper_path


# ============================================================
# Cache Cleanup
# ============================================================

def cleanup_successful_update_cache(
) -> None:
    updates_root = (
        CACHE_DIR
        / "updates"
    )

    if not updates_root.is_dir():
        return

    for path in (
        updates_root.glob(
            "script-*"
        )
    ):
        if not path.is_dir():
            continue

        marker = (
            path
            / ".installed"
        )

        if not marker.is_file():
            continue

        try:
            shutil.rmtree(
                path
            )

        except OSError:
            pass


__all__ = [
    "WindowsScriptUpdateError",
    "application_root",
    "cleanup_successful_update_cache",
    "external_scripts_available",
    "is_windows",
    "launch_script_update_helper",
]