from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import sys
import time

from pathlib import Path

from app.config import (
    CACHE_DIR,
)

from app.i18n import tr


logger = logging.getLogger(
    __name__
)


REGISTRY_SUBKEY = (
    r"Software\Poppey2001\GenshinModManager"
)

REGISTRY_INSTALL_DIR_VALUE = (
    "InstallDir"
)


class WindowsInstallerUpdateError(
    RuntimeError
):
    pass


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


def _registry_install_directory(
) -> Path | None:
    if not is_windows():
        return None

    try:
        import winreg

    except ImportError:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_SUBKEY,
        ) as key:
            value, _kind = (
                winreg.QueryValueEx(
                    key,
                    REGISTRY_INSTALL_DIR_VALUE,
                )
            )

    except OSError:
        return None

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    path = Path(
        value
    ).expanduser()

    try:
        return path.resolve()

    except OSError:
        return path.absolute()


def current_application_directory(
) -> Path:
    return (
        Path(
            sys.executable
        )
        .resolve()
        .parent
    )


def is_windows_installer_runtime(
) -> bool:
    if not is_windows():
        return False

    if not is_frozen():
        return False

    install_directory = (
        _registry_install_directory()
    )

    if install_directory is None:
        return False

    try:
        current = (
            current_application_directory()
            .resolve()
        )

    except OSError:
        current = (
            current_application_directory()
            .absolute()
        )

    try:
        expected = (
            install_directory.resolve()
        )

    except OSError:
        expected = (
            install_directory.absolute()
        )

    return (
        current
        == expected
    )


def _powershell_executable(
) -> Path | None:
    candidate = shutil.which(
        "powershell.exe"
    )

    if candidate:
        return Path(
            candidate
        )

    system_root = os.environ.get(
        "SystemRoot",
        r"C:\Windows",
    )

    fallback = (
        Path(
            system_root
        )
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )

    if fallback.is_file():
        return fallback

    return None


def _ps_single_quote(
    value: str | Path,
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


def _encoded_powershell_command(
    *,
    installer: Path,
    parent_pid: int,
    setup_log: Path,
    handoff_log: Path,
    ready_marker: Path,
) -> str:
    installer_text = (
        _ps_single_quote(
            installer
        )
    )

    setup_log_text = (
        _ps_single_quote(
            setup_log
        )
    )

    handoff_log_text = (
        _ps_single_quote(
            handoff_log
        )
    )

    ready_marker_text = (
        _ps_single_quote(
            ready_marker
        )
    )

    # Windows PowerShell -EncodedCommand expects UTF-16LE.
    #
    # The helper owns a tiny WinForms progress window. It writes the
    # ready marker only after that window is actually visible. The GMM
    # process waits for this marker before it exits, so a broken helper
    # can no longer make the application disappear without starting the
    # update.
    script = f"""
$ErrorActionPreference = 'Stop'

$parentPid = {int(parent_pid)}
$installer = '{installer_text}'
$setupLog = '{setup_log_text}'
$handoffLog = '{handoff_log_text}'
$readyMarker = '{ready_marker_text}'

$form = $null
$statusLabel = $null
$detailLabel = $null
$progressBar = $null
$closeButton = $null

function Write-HandoffLog([string]$Message) {{
    try {{
        $timestamp = [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss.fff')
        Add-Content -LiteralPath $handoffLog -Value "[$timestamp] $Message"
    }}
    catch {{
    }}
}}

function Pump-Ui() {{
    try {{
        [System.Windows.Forms.Application]::DoEvents()
    }}
    catch {{
    }}
}}

function Set-Status(
    [string]$Status,
    [string]$Detail
) {{
    if ($null -ne $statusLabel) {{
        $statusLabel.Text = $Status
    }}

    if ($null -ne $detailLabel) {{
        $detailLabel.Text = $Detail
    }}

    Pump-Ui
}}

function Remove-ReadyMarker() {{
    try {{
        Remove-Item -LiteralPath $readyMarker -Force -ErrorAction SilentlyContinue
    }}
    catch {{
    }}
}}

try {{
    Write-HandoffLog "Handoff helper started."

    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    [System.Windows.Forms.Application]::EnableVisualStyles()

    $isGerman = (
        [System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName
        -eq 'de'
    )

    if ($isGerman) {{
        $windowTitle = 'Genshin Mod Manager Update'
        $waitingText = 'Update wird vorbereitet ...'
        $waitingDetail = 'Der Mod Manager wird gleich geschlossen.'
        $installingText = 'Update wird installiert ...'
        $installingDetail = 'Bitte das Fenster nicht schließen.'
        $doneText = 'Update abgeschlossen.'
        $doneDetail = 'Die neue Version wird gestartet.'
        $failedText = 'Update fehlgeschlagen.'
        $closeText = 'Schließen'
    }}
    else {{
        $windowTitle = 'Genshin Mod Manager Update'
        $waitingText = 'Preparing update ...'
        $waitingDetail = 'The Mod Manager will close in a moment.'
        $installingText = 'Installing update ...'
        $installingDetail = 'Please do not close this window.'
        $doneText = 'Update complete.'
        $doneDetail = 'The new version is starting.'
        $failedText = 'Update failed.'
        $closeText = 'Close'
    }}

    $form = New-Object System.Windows.Forms.Form
    $form.Text = $windowTitle
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.ClientSize = New-Object System.Drawing.Size(560, 188)
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ControlBox = $false
    $form.ShowInTaskbar = $true
    $form.TopMost = $true

    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.Location = New-Object System.Drawing.Point(24, 22)
    $statusLabel.Size = New-Object System.Drawing.Size(512, 32)
    $statusLabel.Font = New-Object System.Drawing.Font(
        'Segoe UI',
        12,
        [System.Drawing.FontStyle]::Bold
    )
    $statusLabel.Text = $waitingText

    $detailLabel = New-Object System.Windows.Forms.Label
    $detailLabel.Location = New-Object System.Drawing.Point(24, 58)
    $detailLabel.Size = New-Object System.Drawing.Size(512, 36)
    $detailLabel.Font = New-Object System.Drawing.Font(
        'Segoe UI',
        9
    )
    $detailLabel.Text = $waitingDetail

    $progressBar = New-Object System.Windows.Forms.ProgressBar
    $progressBar.Location = New-Object System.Drawing.Point(24, 108)
    $progressBar.Size = New-Object System.Drawing.Size(512, 24)
    $progressBar.Style = 'Marquee'
    $progressBar.MarqueeAnimationSpeed = 24

    $closeButton = New-Object System.Windows.Forms.Button
    $closeButton.Location = New-Object System.Drawing.Point(416, 146)
    $closeButton.Size = New-Object System.Drawing.Size(120, 30)
    $closeButton.Text = $closeText
    $closeButton.Visible = $false
    $closeButton.Add_Click({{
        if ($null -ne $form) {{
            $form.Close()
        }}
    }})

    $form.Controls.Add($statusLabel)
    $form.Controls.Add($detailLabel)
    $form.Controls.Add($progressBar)
    $form.Controls.Add($closeButton)

    $form.Show()
    $form.Activate()
    Pump-Ui

    # The parent process waits for this exact marker before quitting.
    Set-Content -LiteralPath $readyMarker -Value 'ready' -Encoding ASCII

    Write-HandoffLog "Progress window is visible. Ready marker written."
    Write-HandoffLog "Waiting for GMM PID $parentPid to exit."

    $deadline = [DateTime]::UtcNow.AddSeconds(20)

    while ($true) {{
        $process = Get-Process -Id $parentPid -ErrorAction SilentlyContinue

        if ($null -eq $process) {{
            break
        }}

        if ([DateTime]::UtcNow -ge $deadline) {{
            Write-HandoffLog "GMM did not exit within 20 seconds. Forcing shutdown."

            Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue

            Start-Sleep -Milliseconds 700

            break
        }}

        Pump-Ui
        Start-Sleep -Milliseconds 120
    }}

    Write-HandoffLog "Old GMM process is no longer running."

    Set-Status $installingText $installingDetail

    Write-HandoffLog "Starting Windows installer."

    $arguments = @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        ('/LOG="' + $setupLog + '"')
    )

    $setup = Start-Process `
        -FilePath $installer `
        -ArgumentList $arguments `
        -PassThru

    while (-not $setup.HasExited) {{
        Pump-Ui
        Start-Sleep -Milliseconds 120
        $setup.Refresh()
    }}

    $exitCode = [int]$setup.ExitCode

    Write-HandoffLog (
        "Windows installer exited with code " +
        $exitCode
    )

    if ($exitCode -ne 0) {{
        throw "Windows installer exit code: $exitCode"
    }}

    $progressBar.Style = 'Continuous'
    $progressBar.MarqueeAnimationSpeed = 0
    $progressBar.Minimum = 0
    $progressBar.Maximum = 100
    $progressBar.Value = 100

    Set-Status $doneText $doneDetail

    Write-HandoffLog "Update completed successfully."

    Start-Sleep -Milliseconds 900
    Pump-Ui

    if ($null -ne $form) {{
        $form.Close()
    }}

    Remove-ReadyMarker
    exit 0
}}
catch {{
    $message = $_.Exception.Message

    Write-HandoffLog (
        "Windows update helper failed: " +
        $message
    )

    if ($null -ne $form) {{
        try {{
            $progressBar.Style = 'Continuous'
            $progressBar.MarqueeAnimationSpeed = 0
            $progressBar.Minimum = 0
            $progressBar.Maximum = 100
            $progressBar.Value = 0

            Set-Status $failedText $message

            $closeButton.Visible = $true
            $form.ControlBox = $true
            $form.TopMost = $false
            $form.Activate()
            Pump-Ui

            while ($form.Visible) {{
                Pump-Ui
                Start-Sleep -Milliseconds 100
            }}
        }}
        catch {{
        }}
    }}

    Remove-ReadyMarker
    exit 1
}}
""".strip()

    return base64.b64encode(
        script.encode(
            "utf-16-le"
        )
    ).decode(
        "ascii"
    )


def launch_windows_installer_update(
    downloaded_file: Path,
) -> Path:
    """
    Schedule a detached updater handoff.

    IMPORTANT:
    The Inno Setup process is NOT started while GMM is still running.

    A detached Windows PowerShell process waits until the current GMM PID
    exits and only then starts the installer. This prevents a deadlock where
    Inno Setup waits for GMM to release files while GMM waits in the update UI.
    """

    if not (
        is_windows_installer_runtime()
    ):
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.not_installed_runtime"
            )
        )

    installer = (
        Path(
            downloaded_file
        )
        .expanduser()
        .absolute()
    )

    if not installer.is_file():
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.missing"
            )
        )

    if (
        installer.suffix
        .casefold()
        != ".exe"
    ):
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.invalid"
            )
        )

    powershell = (
        _powershell_executable()
    )

    if powershell is None:
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.powershell_missing"
            )
        )

    log_directory = (
        CACHE_DIR
        / "updates"
    )

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    setup_log = (
        log_directory
        / "windows-installer-update.log"
    )

    handoff_log = (
        log_directory
        / "windows-update-handoff.log"
    )

    ready_marker = (
        log_directory
        / "windows-update-handoff.ready"
    )

    try:
        ready_marker.unlink(
            missing_ok=True
        )
    except OSError:
        pass

    try:
        handoff_log.write_text(
            (
                "Genshin Mod Manager Windows update handoff\n"
                f"Parent PID: {os.getpid()}\n"
                f"Installer: {installer}\n"
            ),
            encoding="utf-8",
        )

    except OSError:
        # Logging must never block an otherwise valid update handoff.
        pass

    encoded_command = (
        _encoded_powershell_command(
            installer=installer,
            parent_pid=os.getpid(),
            setup_log=setup_log,
            handoff_log=handoff_log,
            ready_marker=ready_marker,
        )
    )

    command = [
        str(
            powershell
        ),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-STA",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded_command,
    ]

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

    logger.info(
        (
            "Windows update handoff wird gestartet: "
            "installer=%s, pid=%s"
        ),
        installer,
        os.getpid(),
    )

    try:
        process = subprocess.Popen(
            command,
            cwd=str(
                installer.parent
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=(
                creation_flags
            ),
        )

    except OSError as error:
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.launch_failed"
            )
        ) from error

    # Do not let the main application exit until the detached helper has
    # actually created and displayed its own progress window. This avoids
    # the old failure mode where GMM vanished even though PowerShell exited
    # immediately afterwards.
    deadline = (
        time.monotonic()
        + 8.0
    )

    while time.monotonic() < deadline:
        if ready_marker.is_file():
            logger.info(
                (
                    "Windows update handoff ist bereit: "
                    "helper_pid=%s"
                ),
                process.pid,
            )

            return installer

        return_code = process.poll()

        if return_code is not None:
            logger.error(
                (
                    "Windows update handoff wurde vor dem "
                    "Ready-Signal beendet: exit_code=%s"
                ),
                return_code,
            )

            raise WindowsInstallerUpdateError(
                tr(
                    "updates.error.windows_installer.launch_failed"
                )
            )

        time.sleep(
            0.05
        )

    logger.error(
        "Windows update handoff lieferte kein Ready-Signal."
    )

    try:
        process.terminate()
    except OSError:
        pass

    try:
        ready_marker.unlink(
            missing_ok=True
        )
    except OSError:
        pass

    raise WindowsInstallerUpdateError(
        tr(
            "updates.error.windows_installer.launch_failed"
        )
    )


__all__ = [
    "WindowsInstallerUpdateError",
    "current_application_directory",
    "is_frozen",
    "is_windows",
    "is_windows_installer_runtime",
    "launch_windows_installer_update",
]
