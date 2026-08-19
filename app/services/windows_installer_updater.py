from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import sys

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

    # Windows PowerShell -EncodedCommand expects UTF-16LE.
    script = f"""
$ErrorActionPreference = 'Stop'

$parentPid = {int(parent_pid)}
$installer = '{installer_text}'
$setupLog = '{setup_log_text}'
$handoffLog = '{handoff_log_text}'

function Write-HandoffLog([string]$Message) {{
    try {{
        $timestamp = [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss.fff')
        Add-Content -LiteralPath $handoffLog -Value "[$timestamp] $Message"
    }}
    catch {{
    }}
}}

Write-HandoffLog "Handoff helper started."
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

    Start-Sleep -Milliseconds 200
}}

Write-HandoffLog "Old GMM process is no longer running."
Write-HandoffLog "Starting Windows installer."

$arguments = @(
    '/VERYSILENT',
    '/SUPPRESSMSGBOXES',
    '/NORESTART',
    ('/LOG="' + $setupLog + '"')
)

try {{
    $setup = Start-Process `
        -FilePath $installer `
        -ArgumentList $arguments `
        -PassThru `
        -Wait

    Write-HandoffLog (
        "Windows installer exited with code " +
        $setup.ExitCode
    )

    exit $setup.ExitCode
}}
catch {{
    Write-HandoffLog (
        "Windows installer launch failed: " +
        $_.Exception.Message
    )

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
        )
    )

    command = [
        str(
            powershell
        ),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
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
        subprocess.Popen(
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

    return installer


__all__ = [
    "WindowsInstallerUpdateError",
    "current_application_directory",
    "is_frozen",
    "is_windows",
    "is_windows_installer_runtime",
    "launch_windows_installer_update",
]
