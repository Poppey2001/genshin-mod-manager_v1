from __future__ import annotations

import logging
import os
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


def launch_windows_installer_update(
    downloaded_file: Path,
) -> Path:
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
    )

    try:
        installer = (
            installer.resolve()
        )
    except OSError:
        installer = (
            installer.absolute()
        )

    if not (
        installer.is_file()
    ):
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.missing"
            )
        )

    if (
        installer.suffix.casefold()
        != ".exe"
    ):
        raise WindowsInstallerUpdateError(
            tr(
                "updates.error.windows_installer.invalid"
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

    log_path = (
        log_directory
        / "windows-installer-update.log"
    )

    command = [
        str(
            installer
        ),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/NORESTARTAPPLICATIONS",
        (
            f'/LOG="{log_path}"'
        ),
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
            "Windows Installer Update "
            "wird gestartet: %s"
        ),
        installer,
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
