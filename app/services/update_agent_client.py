from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HOME = Path.home()
IS_WINDOWS = sys.platform.casefold().startswith("win")
IS_LINUX = sys.platform.casefold().startswith("linux")


def _linux_paths() -> tuple[Path, Path, Path]:
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", HOME / ".config")
    ).expanduser()
    cache_home = Path(
        os.environ.get("XDG_CACHE_HOME", HOME / ".cache")
    ).expanduser()
    runtime_home = Path(
        os.environ.get("XDG_RUNTIME_DIR", cache_home / "runtime")
    ).expanduser()
    config_file = config_home / "genshin-mod-manager" / "update-agent.json"
    command_file = runtime_home / "genshin-mod-manager" / "update-agent-command.json"
    default_agent = HOME / ".local" / "opt" / "genshin-mod-manager" / "GMMUpdateAgent"
    return config_file, command_file, default_agent


def _windows_install_dir() -> Path:
    local_appdata = Path(
        os.environ.get(
            "LOCALAPPDATA",
            str(HOME / "AppData" / "Local"),
        )
    ).expanduser()
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Poppey2001\GenshinModManager",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "InstallDir")
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
    except (ImportError, OSError):
        pass
    return local_appdata / "Programs" / "Genshin Mod Manager"


def _windows_paths() -> tuple[Path, Path, Path]:
    local_appdata = Path(
        os.environ.get(
            "LOCALAPPDATA",
            str(HOME / "AppData" / "Local"),
        )
    ).expanduser()
    config_dir = local_appdata / "Genshin Mod Manager" / "UpdateAgent"
    config_file = config_dir / "update-agent.json"
    command_file = config_dir / "update-agent-command.json"
    default_agent = _windows_install_dir() / "GMMUpdateAgent.exe"
    return config_file, command_file, default_agent


def _paths() -> tuple[Path, Path, Path]:
    if IS_WINDOWS:
        return _windows_paths()
    if IS_LINUX:
        return _linux_paths()
    return Path(), Path(), Path()


AGENT_CONFIG_FILE, COMMAND_FILE, DEFAULT_AGENT_PATH = _paths()


def _agent_path() -> Path:
    if AGENT_CONFIG_FILE:
        try:
            data = json.loads(AGENT_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                value = str(data.get("agent_path") or "").strip()
                if value:
                    candidate = Path(value).expanduser()
                    if candidate.is_file():
                        return candidate
        except Exception:
            pass
    return DEFAULT_AGENT_PATH


def is_update_agent_installed() -> bool:
    if not (IS_WINDOWS or IS_LINUX):
        return False
    path = _agent_path()
    if not path.is_file():
        return False
    if IS_LINUX:
        return os.access(path, os.X_OK)
    return path.suffix.casefold() == ".exe"


def _spawn(*args: str) -> bool:
    path = _agent_path()
    if not is_update_agent_installed():
        return False

    kwargs: dict[str, object] = {
        "close_fds": True,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if IS_WINDOWS:
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen([str(path), *args], **kwargs)
    except OSError:
        return False
    return True


def request_update_agent_check() -> bool:
    return _spawn("--check-now")


def sync_update_agent_settings(*, auto_check: bool, channel: str) -> bool:
    normalized_channel = channel if channel in {"stable", "prerelease"} else "prerelease"
    updated = _spawn(
        "--write-config",
        "--auto-check",
        "yes" if auto_check else "no",
        "--channel",
        normalized_channel,
        "--reload-running-agent",
    )
    if not updated:
        return False

    # If autostart is enabled, make sure the independent agent is actually
    # alive. Starting a second copy is harmless because the agent owns a
    # single-instance lock and the duplicate exits immediately.
    if bool(update_agent_settings().get("autostart_enabled", False)):
        _spawn("--background")

    return True


def _windows_autostart_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "GMMUpdateAgent")
        return bool(str(value).strip())
    except (ImportError, OSError):
        return False


def _linux_autostart_enabled() -> bool:
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", HOME / ".config")
    ).expanduser()
    return (config_home / "autostart" / "gmm-update-agent.desktop").is_file()


def update_agent_settings() -> dict[str, object]:
    data: dict[str, object] = {}
    if AGENT_CONFIG_FILE:
        try:
            raw = json.loads(AGENT_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
        except Exception:
            pass

    if IS_WINDOWS:
        data["autostart_enabled"] = _windows_autostart_enabled()
    elif IS_LINUX:
        data["autostart_enabled"] = _linux_autostart_enabled()
    else:
        data["autostart_enabled"] = False

    return data


def configure_update_agent(
    *,
    autostart: bool | None = None,
    interval_minutes: int | None = None,
    reset_skipped_version: bool = False,
) -> bool:
    if not is_update_agent_installed():
        return False

    args = ["--write-config"]
    if autostart is not None:
        args.extend(["--autostart", "yes" if autostart else "no"])
    if interval_minutes is not None:
        args.extend(["--interval", str(max(15, int(interval_minutes)))])

    if reset_skipped_version:
        data = update_agent_settings()
        data.pop("autostart_enabled", None)
        data["skipped_version"] = ""
        try:
            AGENT_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = AGENT_CONFIG_FILE.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(AGENT_CONFIG_FILE)
        except OSError:
            return False

    args.append("--reload-running-agent")
    updated = _spawn(*args)
    if not updated:
        return False

    if autostart is False:
        _spawn("--shutdown")
    elif autostart is True:
        _spawn("--background")

    return True


# Compatibility aliases for V19 code and older callers.
def is_linux_update_agent_installed() -> bool:
    return IS_LINUX and is_update_agent_installed()


def request_linux_agent_check() -> bool:
    return IS_LINUX and request_update_agent_check()


def sync_linux_agent_settings(*, auto_check: bool, channel: str) -> bool:
    return IS_LINUX and sync_update_agent_settings(
        auto_check=auto_check,
        channel=channel,
    )


def linux_update_agent_settings() -> dict[str, object]:
    return update_agent_settings() if IS_LINUX else {}


def configure_linux_update_agent(
    *,
    autostart: bool | None = None,
    interval_minutes: int | None = None,
    reset_skipped_version: bool = False,
) -> bool:
    if not IS_LINUX:
        return False
    return configure_update_agent(
        autostart=autostart,
        interval_minutes=interval_minutes,
        reset_skipped_version=reset_skipped_version,
    )


__all__ = [
    "configure_linux_update_agent",
    "configure_update_agent",
    "is_linux_update_agent_installed",
    "is_update_agent_installed",
    "linux_update_agent_settings",
    "request_linux_agent_check",
    "request_update_agent_check",
    "sync_linux_agent_settings",
    "sync_update_agent_settings",
    "update_agent_settings",
]
