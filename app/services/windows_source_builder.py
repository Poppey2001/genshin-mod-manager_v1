from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
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
    urlopen,
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


def _safe_extract_zip(
    archive_path: Path,
    destination: Path,
) -> Path:
    destination = (
        destination.resolve()
    )

    with zipfile.ZipFile(
        archive_path,
        "r",
    ) as archive:
        members = (
            archive.infolist()
        )

        for member in members:
            target = (
                destination
                / member.filename
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

        archive.extractall(
            destination
        )

    roots = [
        path
        for path in destination.iterdir()
        if path.is_dir()
    ]

    if len(roots) != 1:
        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.archive_root"
            )
        )

    return roots[0]


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

    update_root = (
        CACHE_DIR
        / "updates"
        / (
            "local-build-"
            f"{normalized_version}-"
            f"{source_commit[:12]}"
        )
    )

    archive_path = (
        update_root
        / "source.zip"
    )

    extract_root = (
        update_root
        / "source"
    )

    build_log = (
        update_root
        / "windows-local-build.log"
    )

    update_root.mkdir(
        parents=True,
        exist_ok=True,
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
        with urlopen(
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

    if extract_root.exists():
        shutil.rmtree(
            extract_root
        )

    extract_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_root = (
        _safe_extract_zip(
            archive_path,
            extract_root,
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

    if return_code != 0:
        try:
            log_text = (
                build_log.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

            lines = (
                log_text.splitlines()
            )

            tail = "\n".join(
                lines[-35:]
            )

        except OSError:
            tail = ""

        raise WindowsSourceBuildError(
            tr(
                "updates.error.local_build.failed",
                code=return_code,
                log=tail,
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
        update_root
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

    return final_installer


__all__ = [
    "WindowsSourceBuildError",
    "build_windows_installer_from_source",
    "find_build_python",
    "local_windows_build_available",
]
