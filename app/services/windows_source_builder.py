from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

from collections.abc import (
    Callable,
)

from pathlib import Path

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.request import (
    Request,
)

from app.services.network_tls import (
    certificate_verification_reason,
    verified_urlopen,
)

from packaging.version import (
    InvalidVersion,
    Version,
)

from app.config import (
    CACHE_DIR,
)

from app.i18n import tr


logger = logging.getLogger(
    __name__
)


StatusCallback = Callable[
    [str],
    None,
]

ProgressCallback = Callable[
    [int, int],
    None,
]

CancelCallback = Callable[
    [],
    bool,
]


class WindowsSourceBuildError(
    RuntimeError
):
    pass


def _is_windows(
) -> bool:
    return (
        os.name
        == "nt"
    )


def _registry_python_candidates(
) -> tuple[
    Path,
    ...,
]:
    if not _is_windows():
        return ()

    try:
        import winreg
    except ImportError:
        return ()

    candidates: list[
        Path
    ] = []

    root_keys = [
        winreg.HKEY_CURRENT_USER,
        winreg.HKEY_LOCAL_MACHINE,
    ]

    access_modes = [
        winreg.KEY_READ,
    ]

    if (
        hasattr(
            winreg,
            "KEY_WOW64_64KEY",
        )
    ):
        access_modes.extend(
            [
                (
                    winreg.KEY_READ
                    | winreg.KEY_WOW64_64KEY
                ),
                (
                    winreg.KEY_READ
                    | winreg.KEY_WOW64_32KEY
                ),
            ]
        )

    for root_key in root_keys:
        for access in access_modes:
            try:
                with winreg.OpenKey(
                    root_key,
                    r"Software\Python\PythonCore",
                    0,
                    access,
                ) as versions_key:
                    version_count = (
                        winreg.QueryInfoKey(
                            versions_key
                        )[0]
                    )

                    for index in range(
                        version_count
                    ):
                        try:
                            version_name = (
                                winreg.EnumKey(
                                    versions_key,
                                    index,
                                )
                            )

                            version = Version(
                                version_name
                            )

                        except (
                            OSError,
                            InvalidVersion,
                        ):
                            continue

                        if (
                            version
                            < Version(
                                "3.12"
                            )
                        ):
                            continue

                        install_key_name = (
                            "Software\\Python\\PythonCore\\"
                            f"{version_name}\\InstallPath"
                        )

                        try:
                            with winreg.OpenKey(
                                root_key,
                                install_key_name,
                                0,
                                access,
                            ) as install_key:
                                try:
                                    executable, _ = (
                                        winreg.QueryValueEx(
                                            install_key,
                                            "ExecutablePath",
                                        )
                                    )

                                except OSError:
                                    executable = None

                                if isinstance(
                                    executable,
                                    str,
                                ):
                                    path = Path(
                                        executable
                                    )

                                    if path.is_file():
                                        candidates.append(
                                            path
                                        )
                                        continue

                                try:
                                    install_path, _ = (
                                        winreg.QueryValueEx(
                                            install_key,
                                            "",
                                        )
                                    )

                                except OSError:
                                    install_path = None

                                if isinstance(
                                    install_path,
                                    str,
                                ):
                                    path = (
                                        Path(
                                            install_path
                                        )
                                        / "python.exe"
                                    )

                                    if path.is_file():
                                        candidates.append(
                                            path
                                        )

                        except OSError:
                            continue

            except OSError:
                continue

    unique: list[
        Path
    ] = []

    seen: set[
        str
    ] = set()

    for path in candidates:
        key = str(
            path.resolve()
        ).casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            path
        )

    return tuple(
        unique
    )


def find_build_python(
) -> Path | None:
    for path in (
        _registry_python_candidates()
    ):
        return path

    executable = shutil.which(
        "python"
    )

    if executable:
        path = Path(
            executable
        )

        try:
            result = subprocess.run(
                [
                    str(path),
                    "-c",
                    (
                        "import sys;"
                        "raise SystemExit("
                        "0 if sys.version_info >= (3,12) else 1"
                        ")"
                    ),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )

        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return None

        if result.returncode == 0:
            return path

    return None


def local_windows_build_available(
) -> bool:
    if not _is_windows():
        return False

    if (
        find_build_python()
        is None
    ):
        return False

    powershell = shutil.which(
        "powershell.exe"
    )

    return bool(
        powershell
    )


def _cancelled(
    cancel_callback: CancelCallback | None,
) -> bool:
    return bool(
        cancel_callback
        and cancel_callback()
    )


def _safe_extract_repository_zip(
    archive_path: Path,
    destination: Path,
) -> Path:
    """
    Extract a GitHub repository ZIP directly into a short destination.

    GitHub ZIPs contain one wrapper directory such as:
        repository-<commit>/

    Keeping that wrapper made the Windows updater path unnecessarily long.
    It is stripped here while traversal outside destination remains blocked.
    """

    destination = destination.resolve()

    with zipfile.ZipFile(
        archive_path,
        "r",
    ) as archive:
        members = archive.infolist()

        top_level_names: set[
            str
        ] = set()

        for member in members:
            raw_name = (
                member.filename
                .replace(
                    "\\",
                    "/",
                )
                .lstrip(
                    "/"
                )
            )

            if not raw_name:
                continue

            parts = [
                part
                for part in raw_name.split(
                    "/"
                )
                if part
            ]

            if not parts:
                continue

            top_level_names.add(
                parts[0]
            )

        if len(
            top_level_names
        ) != 1:
            raise WindowsSourceBuildError(
                tr(
                    "updates.error.local_build.archive_root"
                )
            )

        wrapper = next(
            iter(
                top_level_names
            )
        )

        for member in members:
            raw_name = (
                member.filename
                .replace(
                    "\\",
                    "/",
                )
                .lstrip(
                    "/"
                )
            )

            if not raw_name:
                continue

            parts = [
                part
                for part in raw_name.split(
                    "/"
                )
                if part
            ]

            if (
                not parts
                or parts[0]
                != wrapper
            ):
                continue

            relative_parts = (
                parts[1:]
            )

            if not relative_parts:
                continue

            relative_path = Path(
                *relative_parts
            )

            target = (
                destination
                / relative_path
            ).resolve()

            try:
                target.relative_to(
                    destination
                )

            except ValueError as error:
                raise WindowsSourceBuildError(
                    tr(
                        "updates.error.local_build.unsafe_archive"
                    )
                ) from error

            if member.is_dir():
                target.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                continue

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with (
                archive.open(
                    member,
                    "r",
                ) as source,
                target.open(
                    "wb"
                ) as output,
            ):
                shutil.copyfileobj(
                    source,
                    output,
                    length=(
                        1024
                        * 1024
                    ),
                )

    return destination

def build_windows_installer_from_source(
    *,
    owner: str,
    repository: str,
    version: str,
    source_commit: str,
    status_callback: StatusCallback | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> Path:
    if not _is_windows():
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.windows_only"
            )
        )

    if not re.fullmatch(
        r"[0-9a-fA-F]{40}",
        source_commit,
    ):
        raise WindowsSourceBuildError(
            tr(
                "updates.error.source.commit_invalid"
            )
        )

    python_executable = (
        find_build_python()
    )

    if python_executable is None:
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.python_missing"
            )
        )

    powershell = shutil.which(
        "powershell.exe"
    )

    if not powershell:
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.powershell_missing"
            )
        )

    try:
        normalized_version = str(
            Version(
                version
            )
        )

    except InvalidVersion as error:
        raise WindowsSourceBuildError(
            tr(
                "updates.error.version_file.invalid",
                version=version,
            )
        ) from error

    # Keep build paths deliberately short on Windows.
    #
    # The previous workspace lived below:
    # %LOCALAPPDATA%\genshin-mod-manager\Cache\updates\local-build-...
    # and GitHub's repository wrapper directory added another 50+ chars.
    # Inno Setup / packaged Qt files can then hit legacy path limits.
    #
    # New build root example:
    # %TEMP%\gmmu\dc7447a1\
    short_build_root = (
        Path(
            tempfile.gettempdir()
        )
        / "gmmu"
        / source_commit[:8]
    )

    persistent_update_root = (
        CACHE_DIR
        / "updates"
    )

    persistent_log_root = (
        persistent_update_root
        / "logs"
    )

    persistent_update_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    persistent_log_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    if short_build_root.exists():
        shutil.rmtree(
            short_build_root,
            ignore_errors=True,
        )

    short_build_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive_path = (
        short_build_root
        / "s.zip"
    )

    source_root = (
        short_build_root
        / "s"
    )

    source_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    build_log = (
        short_build_root
        / "build.log"
    )

    persistent_build_log = (
        persistent_log_root
        / (
            "windows-local-build-"
            f"{normalized_version}-"
            f"{source_commit[:8]}.log"
        )
    )

    if _cancelled(
        cancel_callback
    ):
        raise WindowsSourceBuildError(
            tr(
                "updates.error.download.cancelled"
            )
        )

    if status_callback:
        status_callback(
            "download_source"
        )

    archive_url = (
        "https://github.com/"
        f"{owner}/{repository}"
        f"/archive/{source_commit}.zip"
    )

    partial = (
        archive_path
        .with_suffix(
            ".zip.part"
        )
    )

    partial.unlink(
        missing_ok=True
    )

    request = Request(
        archive_url,
        headers={
            "User-Agent": (
                "Genshin-Mod-Manager-Updater"
            ),
            "Accept": (
                "application/zip"
            ),
        },
    )

    received = 0

    try:
        with verified_urlopen(
            request,
            timeout=60,
        ) as response:
            length_header = (
                response.headers.get(
                    "Content-Length"
                )
            )

            try:
                total = int(
                    length_header
                )

            except (
                TypeError,
                ValueError,
            ):
                total = 0

            with partial.open(
                "wb"
            ) as output:
                while True:
                    if _cancelled(
                        cancel_callback
                    ):
                        raise WindowsSourceBuildError(
                            tr(
                                "updates.error.download.cancelled"
                            )
                        )

                    chunk = response.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    output.write(
                        chunk
                    )

                    received += len(
                        chunk
                    )

                    if progress_callback:
                        progress_callback(
                            received,
                            total,
                        )

    except HTTPError as error:
        partial.unlink(
            missing_ok=True
        )

        raise WindowsSourceBuildError(
            tr(
                "updates.error.download.http",
                code=error.code,
            )
        ) from error

    except URLError as error:
        partial.unlink(
            missing_ok=True
        )

        certificate_reason = (
            certificate_verification_reason(
                error
            )
        )

        if certificate_reason is not None:
            raise WindowsSourceBuildError(
                tr(
                    "updates.error.tls.certificate",
                    reason=certificate_reason,
                )
            ) from error

        reason = getattr(
            error,
            "reason",
            error,
        )

        raise WindowsSourceBuildError(
            tr(
                "updates.error.download.network",
                reason=reason,
            )
        ) from error

    except TimeoutError as error:
        partial.unlink(
            missing_ok=True
        )

        raise WindowsSourceBuildError(
            tr(
                "updates.error.download.timeout"
            )
        ) from error

    partial.replace(
        archive_path
    )

    if _cancelled(
        cancel_callback
    ):
        raise WindowsSourceBuildError(
            tr(
                "updates.error.download.cancelled"
            )
        )

    if status_callback:
        status_callback(
            "extract_source"
        )

    source_root = (
        _safe_extract_repository_zip(
            archive_path,
            source_root,
        )
    )

    version_file = (
        source_root
        / "app"
        / "version.py"
    )

    build_script = (
        source_root
        / "scripts"
        / "build_windows_installer.ps1"
    )

    if not version_file.is_file():
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.version_file_missing"
            )
        )

    if not build_script.is_file():
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.script_missing"
            )
        )

    if status_callback:
        status_callback(
            "build_windows"
        )

    environment = os.environ.copy()

    python_directory = str(
        python_executable.parent
    )

    environment[
        "PATH"
    ] = (
        python_directory
        + os.pathsep
        + environment.get(
            "PATH",
            "",
        )
    )

    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(
            build_script
        ),
        "-Version",
        normalized_version,
    ]

    logger.info(
        "Lokaler Windows-Update-Build: %s",
        command,
    )

    with build_log.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log_file:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(
                    source_root
                ),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=(
                    getattr(
                        subprocess,
                        "CREATE_NO_WINDOW",
                        0,
                    )
                ),
            )

        except OSError as error:
            raise WindowsSourceBuildError(
                tr(
                    "updates.error.local_build.start_failed"
                )
            ) from error

        while True:
            return_code = (
                process.poll()
            )

            if (
                return_code
                is not None
            ):
                break

            if _cancelled(
                cancel_callback
            ):
                try:
                    process.terminate()
                except OSError:
                    pass

                try:
                    process.wait(
                        timeout=10
                    )
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except OSError:
                        pass

                raise WindowsSourceBuildError(
                    tr(
                        "updates.error.download.cancelled"
                    )
                )

            time.sleep(
                0.25
            )

    try:
        if build_log.is_file():
            shutil.copy2(
                build_log,
                persistent_build_log,
            )
    except OSError:
        pass

    if return_code != 0:
        try:
            log_text = build_log.read_text(
                encoding="utf-8",
                errors="replace",
            )

            lines = log_text.splitlines()

            error_pattern = re.compile(
                (
                    r"(?i)(error|fatal|exception|failed|"
                    r"out of memory|not enough memory|"
                    r"insufficient memory|access denied|"
                    r"no space|disk full|cannot|could not)"
                )
            )

            error_lines = [
                line
                for line in lines
                if error_pattern.search(line)
            ]

            if error_lines:
                summary = "\n".join(
                    error_lines[-18:]
                )
            else:
                summary = "\n".join(
                    lines[-25:]
                )

        except OSError:
            summary = ""

        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.failed",
                code=return_code,
                log=summary,
                log_path=(
                    persistent_build_log
                    if persistent_build_log.exists()
                    else build_log
                ),
            )
        )

    installer = (
        source_root
        / "release"
        / (
            "Genshin-Mod-Manager-Setup-"
            f"{normalized_version}-"
            "x86_64.exe"
        )
    )

    if not installer.is_file():
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.output_missing",
                path=installer,
            )
        )

    final_installer = (
        persistent_update_root
        / installer.name
    )

    shutil.copy2(
        installer,
        final_installer,
    )

    if status_callback:
        status_callback(
            "build_complete"
        )

    try:
        shutil.rmtree(
            short_build_root,
            ignore_errors=True,
        )
    except OSError:
        pass

    return final_installer


__all__ = [
    "WindowsSourceBuildError",
    "build_windows_installer_from_source",
    "find_build_python",
    "local_windows_build_available",
]
