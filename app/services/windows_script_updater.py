from __future__ import annotations

import json
import logging
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


logger = logging.getLogger(
    __name__
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
# Update-Inhalte
# ============================================================

def _replace_items(
) -> tuple[
    str,
    ...,
]:
    """
    UPDATE_REPLACE_ITEMS bleibt die Basis.

    requirements.txt und scripts werden zusätzlich übernommen,
    falls sie im GitHub-ZIP vorhanden sind. Das macht Updates
    mit neuen Dependencies bzw. einem neuen Windows-Startscript
    möglich.
    """

    result = list(
        UPDATE_REPLACE_ITEMS
    )

    for item in (
        "requirements.txt",
        "scripts",
    ):
        if item not in result:
            result.append(
                item
            )

    return tuple(
        result
    )


# ============================================================
# Python Helper
# ============================================================

_UPDATE_HELPER_SOURCE = 'from __future__ import annotations\n\nimport ctypes\nimport json\nimport os\nimport shutil\nimport subprocess\nimport sys\nimport time\nimport traceback\n\nfrom pathlib import Path\n\n\nCREATE_NEW_PROCESS_GROUP = 0x00000200\nDETACHED_PROCESS = 0x00000008\n\n\ndef load_config(path: Path) -> dict:\n    with path.open(\n        "r",\n        encoding="utf-8",\n    ) as handle:\n        return json.load(handle)\n\n\ndef write_log(\n    log_path: Path,\n    message: str,\n) -> None:\n    log_path.parent.mkdir(\n        parents=True,\n        exist_ok=True,\n    )\n\n    timestamp = time.strftime(\n        "%Y-%m-%d %H:%M:%S"\n    )\n\n    with log_path.open(\n        "a",\n        encoding="utf-8",\n    ) as handle:\n        handle.write(\n            f"[{timestamp}] {message}\\n"\n        )\n\n\ndef wait_for_process(\n    process_id: int,\n    log_path: Path,\n) -> None:\n    """\n    Wartet unter Windows mit der Win32 API auf den alten\n    Mod-Manager-Prozess.\n\n    Der Helper selbst importiert absichtlich nichts aus app/,\n    damit app/ gefahrlos ersetzt werden kann.\n    """\n\n    kernel32 = ctypes.WinDLL(\n        "kernel32",\n        use_last_error=True,\n    )\n\n    synchronize = 0x00100000\n    infinite = 0xFFFFFFFF\n\n    kernel32.OpenProcess.argtypes = [\n        ctypes.c_uint32,\n        ctypes.c_int,\n        ctypes.c_uint32,\n    ]\n    kernel32.OpenProcess.restype = (\n        ctypes.c_void_p\n    )\n\n    kernel32.WaitForSingleObject.argtypes = [\n        ctypes.c_void_p,\n        ctypes.c_uint32,\n    ]\n    kernel32.WaitForSingleObject.restype = (\n        ctypes.c_uint32\n    )\n\n    kernel32.CloseHandle.argtypes = [\n        ctypes.c_void_p,\n    ]\n    kernel32.CloseHandle.restype = (\n        ctypes.c_int\n    )\n\n    handle = kernel32.OpenProcess(\n        synchronize,\n        False,\n        process_id,\n    )\n\n    if not handle:\n        error = ctypes.get_last_error()\n\n        # ERROR_INVALID_PARAMETER bedeutet hier normalerweise,\n        # dass der Prozess bereits beendet wurde.\n        if error == 87:\n            write_log(\n                log_path,\n                (\n                    "Alter Prozess war bereits beendet. "\n                    f"PID={process_id}"\n                ),\n            )\n            return\n\n        write_log(\n            log_path,\n            (\n                "OpenProcess konnte den alten Prozess "\n                f"nicht öffnen. PID={process_id}, "\n                f"WinError={error}. "\n                "Es wird trotzdem fortgefahren."\n            ),\n        )\n        return\n\n    try:\n        write_log(\n            log_path,\n            (\n                "Warte auf alten Mod Manager. "\n                f"PID={process_id}"\n            ),\n        )\n\n        kernel32.WaitForSingleObject(\n            handle,\n            infinite,\n        )\n    finally:\n        kernel32.CloseHandle(\n            handle\n        )\n\n    write_log(\n        log_path,\n        "Alter Mod Manager wurde beendet.",\n    )\n\n\ndef remove_path(path: Path) -> None:\n    if not path.exists() and not path.is_symlink():\n        return\n\n    if path.is_dir() and not path.is_symlink():\n        shutil.rmtree(\n            path\n        )\n    else:\n        path.unlink()\n\n\ndef copy_path(\n    source: Path,\n    destination: Path,\n) -> None:\n    destination.parent.mkdir(\n        parents=True,\n        exist_ok=True,\n    )\n\n    if source.is_dir():\n        shutil.copytree(\n            source,\n            destination,\n            copy_function=shutil.copy2,\n        )\n    else:\n        shutil.copy2(\n            source,\n            destination,\n        )\n\n\ndef backup_items(\n    *,\n    target_root: Path,\n    backup_root: Path,\n    replace_items: list[str],\n    log_path: Path,\n) -> None:\n    remove_path(\n        backup_root\n    )\n\n    backup_root.mkdir(\n        parents=True,\n        exist_ok=True,\n    )\n\n    for item in replace_items:\n        existing = (\n            target_root\n            / item\n        )\n\n        if not existing.exists():\n            continue\n\n        backup = (\n            backup_root\n            / item\n        )\n\n        write_log(\n            log_path,\n            f"Backup: {item}",\n        )\n\n        copy_path(\n            existing,\n            backup,\n        )\n\n\ndef install_items(\n    *,\n    payload_root: Path,\n    target_root: Path,\n    replace_items: list[str],\n    touched_items: list[str],\n    log_path: Path,\n) -> None:\n    for item in replace_items:\n        source = (\n            payload_root\n            / item\n        )\n\n        if not source.exists():\n            write_log(\n                log_path,\n                (\n                    "Nicht im Update enthalten, "\n                    f"übersprungen: {item}"\n                ),\n            )\n            continue\n\n        destination = (\n            target_root\n            / item\n        )\n\n        touched_items.append(\n            item\n        )\n\n        write_log(\n            log_path,\n            f"Installiere: {item}",\n        )\n\n        remove_path(\n            destination\n        )\n\n        copy_path(\n            source,\n            destination,\n        )\n\n\ndef rollback_items(\n    *,\n    target_root: Path,\n    backup_root: Path,\n    touched_items: list[str],\n    log_path: Path,\n) -> None:\n    write_log(\n        log_path,\n        "Rollback wird gestartet.",\n    )\n\n    for item in reversed(\n        touched_items\n    ):\n        destination = (\n            target_root\n            / item\n        )\n\n        backup = (\n            backup_root\n            / item\n        )\n\n        try:\n            remove_path(\n                destination\n            )\n\n            if backup.exists():\n                copy_path(\n                    backup,\n                    destination,\n                )\n\n                write_log(\n                    log_path,\n                    f"Rollback erfolgreich: {item}",\n                )\n            else:\n                write_log(\n                    log_path,\n                    (\n                        "Rollback: neu hinzugefügtes "\n                        f"Element entfernt: {item}"\n                    ),\n                )\n        except Exception as error:\n            write_log(\n                log_path,\n                (\n                    "Rollback fehlgeschlagen für "\n                    f"{item}: {error}"\n                ),\n            )\n\n\ndef start_application(\n    *,\n    target_root: Path,\n    python_executable: Path,\n    log_path: Path,\n) -> int:\n    """\n    Bevorzugt den normalen Windows-Startscript des Projekts.\n    Damit werden requirements.txt und .venv-windows genauso\n    behandelt wie bei einem manuellen Start.\n    """\n\n    run_script = (\n        target_root\n        / "scripts"\n        / "run_windows.ps1"\n    )\n\n    if run_script.is_file():\n        command = [\n            "powershell.exe",\n            "-NoProfile",\n            "-ExecutionPolicy",\n            "Bypass",\n            "-File",\n            str(\n                run_script\n            ),\n        ]\n\n        write_log(\n            log_path,\n            (\n                "Starte Anwendung über "\n                "scripts\\\\run_windows.ps1."\n            ),\n        )\n    else:\n        command = [\n            str(\n                python_executable\n            ),\n            str(\n                target_root\n                / "main.py"\n            ),\n        ]\n\n        write_log(\n            log_path,\n            (\n                "run_windows.ps1 nicht gefunden. "\n                "Starte direkt über Python."\n            ),\n        )\n\n    process = subprocess.Popen(\n        command,\n        cwd=str(\n            target_root\n        ),\n        stdin=subprocess.DEVNULL,\n        stdout=subprocess.DEVNULL,\n        stderr=subprocess.DEVNULL,\n        close_fds=True,\n        creationflags=(\n            CREATE_NEW_PROCESS_GROUP\n            | DETACHED_PROCESS\n        ),\n    )\n\n    write_log(\n        log_path,\n        (\n            "Neustartprozess erzeugt. "\n            f"PID={process.pid}"\n        ),\n    )\n\n    return int(\n        process.pid\n    )\n\n\ndef main() -> int:\n    if len(sys.argv) != 2:\n        return 2\n\n    config_path = (\n        Path(\n            sys.argv[1]\n        )\n        .resolve()\n    )\n\n    config = load_config(\n        config_path\n    )\n\n    target_root = Path(\n        config["target_root"]\n    )\n    payload_root = Path(\n        config["payload_root"]\n    )\n    backup_root = Path(\n        config["backup_root"]\n    )\n    log_path = Path(\n        config["log_path"]\n    )\n    installed_marker = Path(\n        config["installed_marker"]\n    )\n    failed_marker = Path(\n        config["failed_marker"]\n    )\n    python_executable = Path(\n        config["python_executable"]\n    )\n\n    process_id = int(\n        config["process_id"]\n    )\n\n    replace_items = [\n        str(\n            item\n        )\n        for item\n        in config["replace_items"]\n    ]\n\n    touched_items: list[str] = []\n\n    remove_path(\n        installed_marker\n    )\n    remove_path(\n        failed_marker\n    )\n\n    log_path.parent.mkdir(\n        parents=True,\n        exist_ok=True,\n    )\n\n    log_path.write_text(\n        "",\n        encoding="utf-8",\n    )\n\n    try:\n        write_log(\n            log_path,\n            "Python Update-Helper gestartet.",\n        )\n\n        write_log(\n            log_path,\n            f"Target: {target_root}",\n        )\n\n        write_log(\n            log_path,\n            f"Payload: {payload_root}",\n        )\n\n        wait_for_process(\n            process_id,\n            log_path,\n        )\n\n        # Windows einen Moment geben, letzte File-Handles\n        # des alten Prozesses zu schließen.\n        time.sleep(\n            0.75\n        )\n\n        backup_items(\n            target_root=target_root,\n            backup_root=backup_root,\n            replace_items=replace_items,\n            log_path=log_path,\n        )\n\n        install_items(\n            payload_root=payload_root,\n            target_root=target_root,\n            replace_items=replace_items,\n            touched_items=touched_items,\n            log_path=log_path,\n        )\n\n        write_log(\n            log_path,\n            "Update-Dateien wurden installiert.",\n        )\n\n        start_application(\n            target_root=target_root,\n            python_executable=python_executable,\n            log_path=log_path,\n        )\n\n        installed_marker.write_text(\n            "ok\\n",\n            encoding="utf-8",\n        )\n\n        write_log(\n            log_path,\n            "Update erfolgreich abgeschlossen.",\n        )\n\n        return 0\n\n    except Exception:\n        error_text = (\n            traceback.format_exc()\n        )\n\n        write_log(\n            log_path,\n            "UPDATE FEHLGESCHLAGEN:",\n        )\n\n        for line in error_text.splitlines():\n            write_log(\n                log_path,\n                line,\n            )\n\n        try:\n            failed_marker.write_text(\n                error_text,\n                encoding="utf-8",\n            )\n        except OSError:\n            pass\n\n        rollback_items(\n            target_root=target_root,\n            backup_root=backup_root,\n            touched_items=touched_items,\n            log_path=log_path,\n        )\n\n        try:\n            start_application(\n                target_root=target_root,\n                python_executable=python_executable,\n                log_path=log_path,\n            )\n        except Exception:\n            restart_error = (\n                traceback.format_exc()\n            )\n\n            for line in restart_error.splitlines():\n                write_log(\n                    log_path,\n                    (\n                        "Neustart nach Rollback: "\n                        f"{line}"\n                    ),\n                )\n\n        return 1\n\n\nif __name__ == "__main__":\n    raise SystemExit(\n        main()\n    )\n'


def _write_helper(
    *,
    helper_path: Path,
) -> None:
    try:
        helper_path.write_text(
            _UPDATE_HELPER_SOURCE,
            encoding="utf-8",
        )
    except OSError as error:
        raise WindowsUpdateError(
            (
                "Der Python Update-Helper "
                "konnte nicht geschrieben werden."
            )
        ) from error


# ============================================================
# Update starten
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

    cache_root = (
        staged.cache_root
    )

    backup_root = (
        cache_root
        / "backup"
    )

    helper_path = (
        cache_root
        / "update-helper.py"
    )

    helper_config_path = (
        cache_root
        / "update-helper.json"
    )

    log_path = (
        cache_root
        / "update.log"
    )

    installed_marker = (
        cache_root
        / ".installed"
    )

    failed_marker = (
        cache_root
        / ".failed"
    )

    python_executable = (
        Path(
            sys.executable
        )
        .resolve()
    )

    _write_helper(
        helper_path=helper_path,
    )

    helper_config = {
        "process_id": (
            os.getpid()
        ),
        "target_root": str(
            target_root
        ),
        "payload_root": str(
            staged.payload_root
        ),
        "backup_root": str(
            backup_root
        ),
        "log_path": str(
            log_path
        ),
        "installed_marker": str(
            installed_marker
        ),
        "failed_marker": str(
            failed_marker
        ),
        "python_executable": str(
            python_executable
        ),
        "replace_items": list(
            _replace_items()
        ),
    }

    try:
        helper_config_path.write_text(
            json.dumps(
                helper_config,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise WindowsUpdateError(
            (
                "Die Konfiguration für den "
                "Update-Helper konnte nicht "
                "geschrieben werden."
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
        str(
            python_executable
        ),
        str(
            helper_path
        ),
        str(
            helper_config_path
        ),
    ]

    logger.info(
        (
            "Python Update-Helper wird gestartet: "
            "%s"
        ),
        helper_path,
    )

    try:
        subprocess.Popen(
            command,
            cwd=str(
                target_root
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
        raise WindowsUpdateError(
            (
                "Der Python Update-Helper konnte "
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

    if not (
        updates_root
        .is_dir()
    ):
        return

    for cache_root in (
        updates_root.glob(
            "source-*"
        )
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

        # Fehlgeschlagene Updates absichtlich behalten,
        # damit update.log analysiert werden kann.
        if failed_marker.is_file():
            continue

        if not (
            installed_marker
            .is_file()
        ):
            continue

        try:
            shutil.rmtree(
                cache_root
            )
        except OSError:
            logger.exception(
                (
                    "Erfolgreichen Update-Cache "
                    "konnte nicht gelöscht werden: %s"
                ),
                cache_root,
            )


__all__ = [
    "WindowsUpdateError",
    "application_root",
    "cleanup_successful_update_cache",
    "is_windows",
    "launch_windows_update",
    "script_update_supported",
]
