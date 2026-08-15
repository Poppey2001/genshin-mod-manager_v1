from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

from pathlib import Path

from app.config import CACHE_DIR
from app.services.update_service import StagedUpdate
from app.update_config import UPDATE_REPLACE_ITEMS


logger = logging.getLogger(__name__)


class WindowsUpdateError(RuntimeError):
    pass


# ============================================================
# Platform
# ============================================================

def is_windows() -> bool:
    return sys.platform.casefold().startswith("win")


def is_frozen() -> bool:
    return bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    )


def application_root() -> Path:
    if not is_frozen():
        return (
            Path(__file__)
            .resolve()
            .parents[2]
        )

    return (
        Path(sys.executable)
        .resolve()
        .parent
    )


def script_update_supported() -> bool:
    if not is_windows():
        return False

    if is_frozen():
        return False

    root = application_root()

    return (
        (root / "main.py").is_file()
        and
        (
            root
            / "app"
            / "version.py"
        ).is_file()
    )


# ============================================================
# Update-Inhalte
# ============================================================

def _replace_items() -> tuple[str, ...]:
    """
    Neben den in update_config.py konfigurierten Dateien
    werden requirements.txt und scripts mitgenommen, sofern
    sie im GitHub-Archiv vorhanden sind.

    Damit kann ein Update auch neue Python-Abhängigkeiten und
    einen aktualisierten Windows-Startscript mitbringen.
    """

    items = list(
        UPDATE_REPLACE_ITEMS
    )

    for item in (
        "requirements.txt",
        "scripts",
    ):
        if item not in items:
            items.append(item)

    return tuple(items)


# ============================================================
# Restart
# ============================================================

def _restart_spec() -> tuple[
    str,
    tuple[str, ...],
]:
    """
    Bevorzugt scripts/run_windows.ps1.

    Der normale Windows-Startscript kümmert sich bereits um:
      - .venv-windows
      - pip install -r requirements.txt
      - Start von main.py

    Falls der Script nicht existiert, wird auf die aktuell
    verwendete Python-Executable zurückgefallen.
    """

    root = application_root()

    run_script = (
        root
        / "scripts"
        / "run_windows.ps1"
    )

    if run_script.is_file():
        return (
            "powershell.exe",
            (
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(run_script),
            ),
        )

    return (
        str(
            Path(sys.executable)
            .resolve()
        ),
        (
            str(
                root
                / "main.py"
            ),
        ),
    )


# ============================================================
# PowerShell Helper
# ============================================================

def launch_windows_update(
    staged: StagedUpdate,
) -> Path:
    if not script_update_supported():
        raise WindowsUpdateError(
            (
                "Die automatische Script-Installation "
                "ist auf diesem Build nicht verfügbar."
            )
        )

    if not staged.payload_root.is_dir():
        raise WindowsUpdateError(
            (
                "Der entpackte Update-Ordner "
                "wurde nicht gefunden."
            )
        )

    target_root = application_root()

    backup_root = (
        staged.cache_root
        / "backup"
    )

    helper_path = (
        staged.cache_root
        / "update-helper.ps1"
    )

    log_path = (
        staged.cache_root
        / "update.log"
    )

    installed_marker = (
        staged.cache_root
        / ".installed"
    )

    failed_marker = (
        staged.cache_root
        / ".failed"
    )

    (
        restart_program,
        restart_arguments,
    ) = _restart_spec()

    replace_items_ps = ", ".join(
        "'"
        + _ps(item)
        + "'"
        for item in _replace_items()
    )

    restart_arguments_ps = ", ".join(
        "'"
        + _ps(argument)
        + "'"
        for argument in restart_arguments
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

$LogPath = '{_ps(log_path)}'
$InstalledMarker = '{_ps(installed_marker)}'
$FailedMarker = '{_ps(failed_marker)}'

$RestartProgram = '{_ps(restart_program)}'

$RestartArguments = @(
    {restart_arguments_ps}
)

$ReplaceItems = @(
    {replace_items_ps}
)


function Write-UpdateLog {{
    param(
        [string]$Message
    )

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"

    Add-Content `
        -LiteralPath $LogPath `
        -Value "[$Timestamp] $Message" `
        -Encoding UTF8
}}


function Quote-ProcessArgument {{
    param(
        [string]$Value
    )

    if ($null -eq $Value) {{
        return '""'
    }}

    $Escaped = $Value.Replace(
        '"',
        '\\"'
    )

    return '"' + $Escaped + '"'
}}


function Start-Gmm {{
    Write-UpdateLog "Starte Anwendung neu."
    Write-UpdateLog "Programm: $RestartProgram"
    Write-UpdateLog (
        "Argumente: "
        + ($RestartArguments -join " | ")
    )

    $StartInfo = New-Object `
        System.Diagnostics.ProcessStartInfo

    $StartInfo.FileName = $RestartProgram
    $StartInfo.WorkingDirectory = $TargetRoot
    $StartInfo.UseShellExecute = $true

    $QuotedArguments = @()

    foreach ($Argument in $RestartArguments) {{
        $QuotedArguments += (
            Quote-ProcessArgument $Argument
        )
    }}

    $StartInfo.Arguments = (
        $QuotedArguments
        -join " "
    )

    $StartedProcess = (
        [System.Diagnostics.Process]::Start(
            $StartInfo
        )
    )

    if ($null -eq $StartedProcess) {{
        throw (
            "Windows konnte den "
            + "Neustartprozess nicht erzeugen."
        )
    }}

    Write-UpdateLog (
        "Neustartprozess gestartet. PID="
        + $StartedProcess.Id
    )
}}


# Alte Marker entfernen.
Remove-Item `
    -LiteralPath $InstalledMarker `
    -Force `
    -ErrorAction SilentlyContinue

Remove-Item `
    -LiteralPath $FailedMarker `
    -Force `
    -ErrorAction SilentlyContinue

Set-Content `
    -LiteralPath $LogPath `
    -Value "" `
    -Encoding UTF8


try {{
    # ========================================================
    # Auf alten Mod Manager warten
    # ========================================================

    Write-UpdateLog (
        "Update-Helper gestartet. "
        + "Warte auf PID $ProcessId."
    )

    try {{
        Wait-Process `
            -Id $ProcessId `
            -ErrorAction SilentlyContinue
    }}
    catch {{
        Write-UpdateLog (
            "Wait-Process meldete: "
            + $_.Exception.Message
        )
    }}

    # Kleine Pause, damit Windows alle Handles freigibt.
    Start-Sleep `
        -Milliseconds 500

    Write-UpdateLog (
        "Alter Prozess wurde beendet."
    )

    # ========================================================
    # Backup
    # ========================================================

    if (
        Test-Path `
            -LiteralPath $BackupRoot
    ) {{
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

    Write-UpdateLog (
        "Backup-Verzeichnis erstellt: "
        + $BackupRoot
    )

    foreach ($Item in $ReplaceItems) {{
        $Existing = Join-Path `
            $TargetRoot `
            $Item

        if (
            -not (
                Test-Path `
                    -LiteralPath $Existing
            )
        ) {{
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

        Write-UpdateLog (
            "Backup: "
            + $Item
        )

        Copy-Item `
            -LiteralPath $Existing `
            -Destination $Backup `
            -Recurse `
            -Force
    }}

    # ========================================================
    # Update installieren
    # ========================================================

    foreach ($Item in $ReplaceItems) {{
        $Source = Join-Path `
            $PayloadRoot `
            $Item

        if (
            -not (
                Test-Path `
                    -LiteralPath $Source
            )
        ) {{
            Write-UpdateLog (
                "Nicht im Update enthalten: "
                + $Item
            )

            continue
        }}

        $Destination = Join-Path `
            $TargetRoot `
            $Item

        Write-UpdateLog (
            "Installiere: "
            + $Item
        )

        if (
            Test-Path `
                -LiteralPath $Destination
        ) {{
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

    Write-UpdateLog (
        "Dateien wurden erfolgreich ersetzt."
    )

    # ========================================================
    # Anwendung neu starten
    # ========================================================

    Start-Gmm

    # Erst NACH erfolgreichem Process-Start markieren.
    Set-Content `
        -LiteralPath $InstalledMarker `
        -Value "ok" `
        -Encoding UTF8

    Write-UpdateLog (
        "Update erfolgreich abgeschlossen."
    )

    exit 0
}}
catch {{
    $Message = (
        $_
        | Out-String
    ).Trim()

    Write-UpdateLog (
        "UPDATE FEHLGESCHLAGEN: "
        + $Message
    )

    Set-Content `
        -LiteralPath $FailedMarker `
        -Value $Message `
        -Encoding UTF8

    # ========================================================
    # Rollback
    # ========================================================

    Write-UpdateLog (
        "Rollback wird gestartet."
    )

    foreach ($Item in $ReplaceItems) {{
        $Backup = Join-Path `
            $BackupRoot `
            $Item

        if (
            -not (
                Test-Path `
                    -LiteralPath $Backup
            )
        ) {{
            continue
        }}

        $Destination = Join-Path `
            $TargetRoot `
            $Item

        try {{
            if (
                Test-Path `
                    -LiteralPath $Destination
            ) {{
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

            Write-UpdateLog (
                "Rollback: "
                + $Item
            )
        }}
        catch {{
            Write-UpdateLog (
                "Rollback fehlgeschlagen für "
                + $Item
                + ": "
                + $_.Exception.Message
            )
        }}
    }}

    # Nach Rollback alte Version wieder starten.
    try {{
        Write-UpdateLog (
            "Versuche alte Version nach Rollback "
            + "neu zu starten."
        )

        Start-Gmm
    }}
    catch {{
        Write-UpdateLog (
            "Auch der Neustart nach Rollback "
            + "ist fehlgeschlagen: "
            + $_.Exception.Message
        )
    }}

    exit 1
}}
"""

    try:
        helper_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        helper_path.write_text(
            script.strip() + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise WindowsUpdateError(
            (
                "Der Windows Update-Helper "
                "konnte nicht geschrieben werden."
            )
        ) from error

    creation_flags = (
        getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
        |
        getattr(
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
        str(helper_path),
        "-ProcessId",
        str(os.getpid()),
    ]

    logger.info(
        "Windows Update-Helper wird gestartet: %s",
        helper_path,
    )

    try:
        subprocess.Popen(
            command,
            cwd=str(target_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as error:
        raise WindowsUpdateError(
            (
                "Der Windows Update-Helper konnte "
                "nicht gestartet werden."
            )
        ) from error

    return helper_path


# ============================================================
# Cache nach erfolgreichem Neustart löschen
# ============================================================

def cleanup_successful_update_cache() -> None:
    updates_root = (
        CACHE_DIR
        / "updates"
    )

    if not updates_root.is_dir():
        return

    for cache_root in updates_root.glob(
        "source-*"
    ):
        if not cache_root.is_dir():
            continue

        installed_marker = (
            cache_root
            / ".installed"
        )

        failed_marker = (
            cache_root
            / ".failed"
        )

        # Fehlgeschlagene Updates bewusst behalten,
        # damit update.log untersucht werden kann.
        if failed_marker.is_file():
            continue

        if not installed_marker.is_file():
            continue

        try:
            shutil.rmtree(
                cache_root
            )
        except OSError:
            logger.exception(
                (
                    "Update-Cache konnte nicht "
                    "gelöscht werden: %s"
                ),
                cache_root,
            )


# ============================================================
# Helper
# ============================================================

def _ps(
    value: Path | str,
) -> str:
    return (
        str(value)
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
