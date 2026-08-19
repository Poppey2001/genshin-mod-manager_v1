from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import locale
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.services.network_tls import verified_urlopen
from app.update_config import GITHUB_API_VERSION, GITHUB_OWNER, GITHUB_REPOSITORY
from app.version import APP_VERSION
from updater.services.component_update_service import (
    ComponentUpdateResult,
    ComponentUpdateService,
)
from updater.services.component_worker import ComponentUpdateWorker


APP_NAME = "Genshin Mod Manager"
AGENT_NAME = "GMM Update Agent"
USER_AGENT = "GMM-Linux-Update-Agent"
DEFAULT_INTERVAL_MINUTES = 20
MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 1440
CHECK_TIMEOUT = 25
DOWNLOAD_TIMEOUT = 60


def _xdg_path(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    return Path(value).expanduser() if value else fallback


HOME = Path.home()
CONFIG_HOME = _xdg_path("XDG_CONFIG_HOME", HOME / ".config")
CACHE_HOME = _xdg_path("XDG_CACHE_HOME", HOME / ".cache")
RUNTIME_HOME = _xdg_path("XDG_RUNTIME_DIR", CACHE_HOME / "runtime")
DATA_HOME = _xdg_path("XDG_DATA_HOME", HOME / ".local" / "share")

CONFIG_DIR = CONFIG_HOME / "genshin-mod-manager"
CACHE_DIR = CACHE_HOME / "genshin-mod-manager" / "update-agent"
RUNTIME_DIR = RUNTIME_HOME / "genshin-mod-manager"
AUTOSTART_DIR = CONFIG_HOME / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "gmm-update-agent.desktop"
DEFAULT_INSTALL_DIR = HOME / ".local" / "opt" / "genshin-mod-manager"
DEFAULT_APPIMAGE = DEFAULT_INSTALL_DIR / "GenshinModManager.AppImage"
DEFAULT_AGENT = DEFAULT_INSTALL_DIR / "GMMUpdateAgent"
CONFIG_FILE = CONFIG_DIR / "update-agent.json"
COMMAND_FILE = RUNTIME_DIR / "update-agent-command.json"
LOCK_FILE = RUNTIME_DIR / "update-agent.lock"
LOG_FILE = CACHE_DIR / "update-agent.log"
COMPONENT_ROOT = DATA_HOME / "genshin-mod-manager" / "components"
COMPONENT_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/"
    "gmm-components/manifest.json"
)


def _language() -> str:
    for value in (
        os.environ.get("LANGUAGE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ):
        if value.lower().startswith("de"):
            return "de"
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    return "de" if loc.lower().startswith("de") else "en"


LANG = _language()


TEXT = {
    "de": {
        "tray.check": "Jetzt nach Updates suchen",
        "tray.auto": "Automatisch nach Updates suchen",
        "tray.autostart": "Update Agent automatisch starten",
        "tray.launch": "Genshin Mod Manager starten",
        "tray.settings": "Update-Agent-Einstellungen …",
        "tray.quit": "Update Agent beenden",
        "tray.title": "GMM Update Agent",
        "check.running": "Eine Update-Prüfung läuft bereits.",
        "check.uptodate": "Du verwendest bereits die aktuelle Version {version}.",
        "check.failed": "Die Update-Prüfung ist fehlgeschlagen.\n\n{error}",
        "component.updated": "{count} kleine Update-Komponente(n) wurden installiert.",
        "component.restart": "Die Änderungen werden beim nächsten Start des Mod Managers aktiv.",
        "update.title": "Genshin Mod Manager Update",
        "update.available": "Eine neue Version ist verfügbar",
        "update.versions": "Installiert: {current}\nVerfügbar: {new}",
        "update.notes": "Änderungen",
        "update.install": "Update installieren",
        "update.later": "Später",
        "update.skip": "Diese Version überspringen",
        "update.download": "Update wird heruntergeladen und geprüft …",
        "update.stop": "Genshin Mod Manager wird beendet …",
        "update.replace": "Update wird installiert …",
        "update.done": "Update {version} wurde installiert.",
        "update.failed": "Update fehlgeschlagen.\n\n{error}",
        "setup.title": "Linux Update Agent einrichten",
        "setup.info": "Der GMM Update Agent läuft unabhängig vom Mod Manager und kann im Hintergrund nach Updates suchen.",
        "setup.autostart": "Update Agent bei der Anmeldung automatisch starten",
        "setup.auto": "Automatisch nach Updates suchen",
        "setup.interval": "Prüfintervall (Minuten)",
        "setup.skipped": "Übersprungene Version: {version}",
        "setup.no_skipped": "Keine Version wird übersprungen.",
        "setup.reset_skip": "Übersprungene Version zurücksetzen",
        "setup.saved": "Die Update-Agent-Einstellungen wurden gespeichert.",
        "error.no_appimage": "Das installierte GMM-AppImage wurde nicht gefunden: {path}",
        "error.no_asset": "Dieses Release enthält kein passendes Linux-AppImage.",
        "error.digest": "Für {name} konnte keine gültige SHA-256-Prüfsumme gefunden werden.",
        "error.hash": "Die SHA-256-Prüfsumme von {name} stimmt nicht überein.",
        "error.download": "Download von {name} fehlgeschlagen: {error}",
        "error.replace": "Das AppImage konnte nicht ersetzt werden: {error}",
    },
    "en": {
        "tray.check": "Check for updates now",
        "tray.auto": "Automatically check for updates",
        "tray.autostart": "Start Update Agent automatically",
        "tray.launch": "Launch Genshin Mod Manager",
        "tray.settings": "Update Agent settings …",
        "tray.quit": "Quit Update Agent",
        "tray.title": "GMM Update Agent",
        "check.running": "An update check is already running.",
        "check.uptodate": "You are already using the current version {version}.",
        "check.failed": "The update check failed.\n\n{error}",
        "component.updated": "{count} small update component(s) were installed.",
        "component.restart": "The changes will become active the next time the Mod Manager starts.",
        "update.title": "Genshin Mod Manager Update",
        "update.available": "A new version is available",
        "update.versions": "Installed: {current}\nAvailable: {new}",
        "update.notes": "What's new",
        "update.install": "Install update",
        "update.later": "Later",
        "update.skip": "Skip this version",
        "update.download": "Downloading and verifying the update …",
        "update.stop": "Closing Genshin Mod Manager …",
        "update.replace": "Installing the update …",
        "update.done": "Update {version} was installed.",
        "update.failed": "Update failed.\n\n{error}",
        "setup.title": "Configure Linux Update Agent",
        "setup.info": "The GMM Update Agent runs independently from the Mod Manager and can check for updates in the background.",
        "setup.autostart": "Start Update Agent automatically when signing in",
        "setup.auto": "Automatically check for updates",
        "setup.interval": "Check interval (minutes)",
        "setup.skipped": "Skipped version: {version}",
        "setup.no_skipped": "No version is currently skipped.",
        "setup.reset_skip": "Reset skipped version",
        "setup.saved": "Update Agent settings were saved.",
        "error.no_appimage": "The installed GMM AppImage was not found: {path}",
        "error.no_asset": "This release does not contain a matching Linux AppImage.",
        "error.digest": "No valid SHA-256 checksum could be found for {name}.",
        "error.hash": "The SHA-256 checksum for {name} does not match.",
        "error.download": "Download of {name} failed: {error}",
        "error.replace": "The AppImage could not be replaced: {error}",
    },
}


def tr(key: str, **kwargs: object) -> str:
    template = TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))
    return template.format(**kwargs)


@dataclass(slots=True)
class AgentConfig:
    auto_check_enabled: bool = True
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    skipped_version: str = ""
    channel: str = "prerelease"
    appimage_path: str = str(DEFAULT_APPIMAGE)
    agent_path: str = str(DEFAULT_AGENT)
    installed_version: str = APP_VERSION

    @classmethod
    def load(cls) -> "AgentConfig":
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.is_file():
            config = cls()
            config.save()
            return config
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("update-agent.json is not an object")
            config = cls(
                auto_check_enabled=bool(data.get("auto_check_enabled", True)),
                interval_minutes=int(data.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)),
                skipped_version=str(data.get("skipped_version", "") or ""),
                channel=str(data.get("channel", "prerelease") or "prerelease"),
                appimage_path=str(data.get("appimage_path", DEFAULT_APPIMAGE)),
                agent_path=str(data.get("agent_path", DEFAULT_AGENT)),
                installed_version=str(data.get("installed_version", APP_VERSION) or APP_VERSION),
            )
        except Exception:
            logging.exception("Update-Agent-Konfiguration konnte nicht geladen werden.")
            config = cls()
        config.interval_minutes = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, config.interval_minutes))
        if config.channel not in {"stable", "prerelease"}:
            config.channel = "prerelease"
        return config

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temporary = CONFIG_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(CONFIG_FILE)


def configure_logging() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stderr)],
    )


def desktop_exec(path: Path, *args: str) -> str:
    def quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
        return f'"{escaped}"'
    return " ".join([quote(str(path)), *(quote(arg) for arg in args)])


def set_autostart(enabled: bool, agent_path: Path) -> None:
    if enabled:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={AGENT_NAME}",
                    "Comment=Background updater for Genshin Mod Manager",
                    f"Exec={desktop_exec(agent_path, '--background')}",
                    "Terminal=false",
                    "NoDisplay=true",
                    "X-GNOME-Autostart-enabled=true",
                    "StartupNotify=false",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        AUTOSTART_FILE.chmod(0o644)
    else:
        AUTOSTART_FILE.unlink(missing_ok=True)


def autostart_enabled() -> bool:
    return AUTOSTART_FILE.is_file()


def write_command(command: str, **payload: object) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    data = {"command": command, "created": time.time(), **payload}
    temp = COMMAND_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    temp.replace(COMMAND_FILE)


def _github_request(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
    )
    with verified_urlopen(request, timeout=CHECK_TIMEOUT) as response:
        return response.read()


@dataclass(frozen=True, slots=True)
class RemoteAsset:
    name: str
    url: str
    size: int
    digest: str
    checksum_url: str = ""


@dataclass(frozen=True, slots=True)
class RemoteRelease:
    version: str
    tag: str
    name: str
    notes: str
    page_url: str
    appimage: RemoteAsset
    agent: RemoteAsset | None


def _asset_digest(asset: dict[str, Any], checksum_assets: dict[str, str]) -> tuple[str, str]:
    digest = str(asset.get("digest") or "").strip()
    if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        return digest.split(":", 1)[1].lower(), ""
    checksum_name = f"{asset.get('name', '')}.sha256"
    return "", checksum_assets.get(checksum_name, "")


def _pick_release(current_version: str, channel: str) -> RemoteRelease | None:
    try:
        current = Version(current_version.lstrip("vV"))
    except InvalidVersion:
        current = Version(APP_VERSION.lstrip("vV"))

    api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases?per_page=20"
    raw = _github_request(api)
    releases = json.loads(raw.decode("utf-8"))
    if not isinstance(releases, list):
        raise RuntimeError("GitHub returned an unexpected release response")

    candidates: list[tuple[Version, dict[str, Any]]] = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if channel == "stable" and release.get("prerelease"):
            continue
        tag = str(release.get("tag_name") or "").strip()
        try:
            version = Version(tag.lstrip("vV"))
        except InvalidVersion:
            continue
        if version > current:
            candidates.append((version, release))

    if not candidates:
        return None

    version, release = max(candidates, key=lambda item: item[0])
    raw_assets = release.get("assets") or []
    if not isinstance(raw_assets, list):
        raw_assets = []

    checksum_assets: dict[str, str] = {}
    for item in raw_assets:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
            url = str(item.get("browser_download_url") or "")
            if name.endswith(".sha256") and url:
                checksum_assets[name] = url

    app_item: dict[str, Any] | None = None
    agent_item: dict[str, Any] | None = None
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        lowered = name.lower()
        if lowered.endswith(".appimage") and ("x86_64" in lowered or "amd64" in lowered):
            app_item = item
        elif (
            lowered.startswith("gmmupdateagent-")
            and ("x86_64" in lowered or "amd64" in lowered)
            and not lowered.endswith(".sha256")
            and not lowered.endswith(".exe")
            and ("linux" in lowered or "." not in Path(name).suffix)
        ):
            agent_item = item

    if app_item is None:
        raise RuntimeError(tr("error.no_asset"))

    def convert(item: dict[str, Any]) -> RemoteAsset:
        digest, checksum_url = _asset_digest(item, checksum_assets)
        return RemoteAsset(
            name=str(item.get("name") or ""),
            url=str(item.get("browser_download_url") or ""),
            size=int(item.get("size") or 0),
            digest=digest,
            checksum_url=checksum_url,
        )

    return RemoteRelease(
        version=str(version),
        tag=str(release.get("tag_name") or ""),
        name=str(release.get("name") or release.get("tag_name") or version),
        notes=str(release.get("body") or ""),
        page_url=str(release.get("html_url") or ""),
        appimage=convert(app_item),
        agent=convert(agent_item) if agent_item is not None else None,
    )


def _checksum_from_url(url: str, asset_name: str) -> str:
    if not url:
        raise RuntimeError(tr("error.digest", name=asset_name))
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with verified_urlopen(request, timeout=CHECK_TIMEOUT) as response:
        text = response.read().decode("utf-8", errors="replace")
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not match:
        raise RuntimeError(tr("error.digest", name=asset_name))
    return match.group(1).lower()


def _expected_digest(asset: RemoteAsset) -> str:
    if asset.digest:
        return asset.digest.lower()
    return _checksum_from_url(asset.checksum_url, asset.name)


class CheckSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class CheckWorker(QRunnable):
    def __init__(self, current_version: str, channel: str) -> None:
        super().__init__()
        self.current_version = current_version
        self.channel = channel
        self.signals = CheckSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            release = _pick_release(self.current_version, self.channel)
        except Exception as error:
            self.signals.failed.emit(str(error))
            return
        self.signals.finished.emit(release)


class DownloadSignals(QObject):
    progress = Signal(int, int)
    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)


class DownloadWorker(QRunnable):
    def __init__(self, release: RemoteRelease) -> None:
        super().__init__()
        self.release = release
        self.signals = DownloadSignals()
        self.setAutoDelete(True)

    def _download_asset(self, asset: RemoteAsset, destination: Path, overall_received: int, overall_total: int) -> int:
        expected = _expected_digest(asset)
        request = Request(asset.url, headers={"User-Agent": USER_AGENT})
        hasher = hashlib.sha256()
        received = 0
        temp = destination.with_suffix(destination.suffix + ".part")
        temp.unlink(missing_ok=True)
        try:
            with verified_urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, temp.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    hasher.update(chunk)
                    received += len(chunk)
                    self.signals.progress.emit(overall_received + received, overall_total)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            temp.unlink(missing_ok=True)
            raise RuntimeError(tr("error.download", name=asset.name, error=error)) from error
        actual = hasher.hexdigest().lower()
        if actual != expected:
            temp.unlink(missing_ok=True)
            raise RuntimeError(tr("error.hash", name=asset.name))
        temp.replace(destination)
        destination.chmod(destination.stat().st_mode | 0o111)
        return received

    @Slot()
    def run(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="update-", dir=CACHE_DIR))
        app_path = work / self.release.appimage.name
        agent_path: Path | None = None
        assets = [self.release.appimage]
        if self.release.agent is not None:
            assets.append(self.release.agent)
        total = sum(max(asset.size, 0) for asset in assets)
        if total <= 0:
            total = 1
        received = 0
        try:
            self.signals.status.emit(tr("update.download"))
            received += self._download_asset(self.release.appimage, app_path, received, total)
            if self.release.agent is not None:
                agent_path = work / self.release.agent.name
                received += self._download_asset(self.release.agent, agent_path, received, total)
        except Exception as error:
            shutil.rmtree(work, ignore_errors=True)
            self.signals.failed.emit(str(error))
            return
        self.signals.progress.emit(total, total)
        self.signals.finished.emit({"work": work, "appimage": app_path, "agent": agent_path})


class UpdateDialog(QDialog):
    install_requested = Signal()
    skip_requested = Signal()

    def __init__(self, release: RemoteRelease, current_version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.release = release
        self.setWindowTitle(tr("update.title"))
        self.resize(620, 480)
        layout = QVBoxLayout(self)
        title = QLabel(f"<b>{tr('update.available')}</b>")
        layout.addWidget(title)
        version = QLabel(tr("update.versions", current=current_version, new=release.version))
        layout.addWidget(version)
        layout.addWidget(QLabel(tr("update.notes")))
        self.notes = QTextBrowser(self)
        self.notes.setOpenExternalLinks(True)
        self.notes.setPlainText(release.notes.strip() or "—")
        layout.addWidget(self.notes, 1)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        buttons = QHBoxLayout()
        self.skip_button = QPushButton(tr("update.skip"), self)
        self.later_button = QPushButton(tr("update.later"), self)
        self.install_button = QPushButton(tr("update.install"), self)
        self.install_button.setDefault(True)
        buttons.addWidget(self.skip_button)
        buttons.addStretch(1)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)
        self.skip_button.clicked.connect(self.skip_requested.emit)
        self.later_button.clicked.connect(self.reject)
        self.install_button.clicked.connect(self.install_requested.emit)

    def begin_download(self) -> None:
        self.status.setText(tr("update.download"))
        self.status.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.skip_button.setEnabled(False)

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.show()

    def set_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(received * 100 / total))))
        else:
            self.progress.setRange(0, 0)

    def set_indeterminate(self, text: str) -> None:
        self.set_status(text)
        self.progress.setRange(0, 0)
        self.progress.show()

    def set_failed(self, message: str) -> None:
        self.set_status(tr("update.failed", error=message))
        self.progress.hide()
        self.install_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.skip_button.setEnabled(True)


class SetupDialog(QDialog):
    def __init__(self, config: AgentConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(tr("setup.title"))
        self.resize(520, 260)
        layout = QVBoxLayout(self)
        info = QLabel(tr("setup.info"), self)
        info.setWordWrap(True)
        layout.addWidget(info)
        self.autostart = QCheckBox(tr("setup.autostart"), self)
        self.autostart.setChecked(autostart_enabled())
        self.auto = QCheckBox(tr("setup.auto"), self)
        self.auto.setChecked(config.auto_check_enabled)
        layout.addWidget(self.autostart)
        layout.addWidget(self.auto)
        form = QFormLayout()
        self.interval = QSpinBox(self)
        self.interval.setRange(MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES)
        self.interval.setValue(config.interval_minutes)
        form.addRow(tr("setup.interval"), self.interval)
        layout.addLayout(form)
        self.skipped_label = QLabel(self)
        self.skipped_label.setWordWrap(True)
        self.reset_skip_button = QPushButton(tr("setup.reset_skip"), self)
        self.reset_skip_button.clicked.connect(self._reset_skip)
        layout.addWidget(self.skipped_label)
        layout.addWidget(self.reset_skip_button)
        self._refresh_skip_label()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_skip_label(self) -> None:
        if self.config.skipped_version:
            self.skipped_label.setText(tr("setup.skipped", version=self.config.skipped_version))
            self.reset_skip_button.setEnabled(True)
        else:
            self.skipped_label.setText(tr("setup.no_skipped"))
            self.reset_skip_button.setEnabled(False)

    def _reset_skip(self) -> None:
        self.config.skipped_version = ""
        self._refresh_skip_label()


class UpdateAgent(QObject):
    def __init__(self, application: QApplication, config: AgentConfig) -> None:
        super().__init__()
        self.application = application
        self.config = config
        self.pool = QThreadPool.globalInstance()
        self.check_worker: CheckWorker | None = None
        self.component_worker: ComponentUpdateWorker | None = None
        self.download_worker: DownloadWorker | None = None
        self.dialog: UpdateDialog | None = None
        self.manual_check = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.check_for_updates(manual=False))
        self.command_timer = QTimer(self)
        self.command_timer.setInterval(1000)
        self.command_timer.timeout.connect(self._process_command_file)
        self.command_timer.start()
        self.tray = self._build_tray()
        self._apply_timer()
        QTimer.singleShot(30_000, self._initial_check)

    def _build_tray(self) -> QSystemTrayIcon:
        style = self.application.style()
        icon = style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(AGENT_NAME)
        menu = QMenu()
        check_action = QAction(tr("tray.check"), menu)
        check_action.triggered.connect(lambda: self.check_for_updates(manual=True))
        menu.addAction(check_action)
        self.auto_action = QAction(tr("tray.auto"), menu)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(self.config.auto_check_enabled)
        self.auto_action.toggled.connect(self._toggle_auto_check)
        menu.addAction(self.auto_action)
        self.autostart_action = QAction(tr("tray.autostart"), menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart_enabled())
        self.autostart_action.toggled.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        launch_action = QAction(tr("tray.launch"), menu)
        launch_action.triggered.connect(self.launch_gmm)
        menu.addAction(launch_action)
        settings_action = QAction(tr("tray.settings"), menu)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        quit_action = QAction(tr("tray.quit"), menu)
        quit_action.triggered.connect(self.application.quit)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray.show()
        return tray

    def _toggle_auto_check(self, enabled: bool) -> None:
        self.config.auto_check_enabled = bool(enabled)
        self.config.save()
        self._apply_timer()

    def _toggle_autostart(self, enabled: bool) -> None:
        set_autostart(bool(enabled), Path(self.config.agent_path).expanduser())

    def _apply_timer(self) -> None:
        if self.config.auto_check_enabled:
            self.timer.start(max(MIN_INTERVAL_MINUTES, self.config.interval_minutes) * 60_000)
        else:
            self.timer.stop()
        if hasattr(self, "auto_action"):
            self.auto_action.blockSignals(True)
            self.auto_action.setChecked(self.config.auto_check_enabled)
            self.auto_action.blockSignals(False)

    def _initial_check(self) -> None:
        if self.config.auto_check_enabled:
            self.check_for_updates(manual=False)

    def _process_command_file(self) -> None:
        if not COMMAND_FILE.is_file():
            return
        try:
            data = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Agent-Kommando konnte nicht gelesen werden.")
            COMMAND_FILE.unlink(missing_ok=True)
            return
        COMMAND_FILE.unlink(missing_ok=True)
        if not isinstance(data, dict):
            return
        if time.time() - float(data.get("created", 0)) > 60:
            return
        command = str(data.get("command") or "")
        if command == "check_now":
            self.check_for_updates(manual=True)
        elif command == "reload_config":
            self.config = AgentConfig.load()
            self._apply_timer()
        elif command == "show_settings":
            self.show_settings()
        elif command == "shutdown":
            self.application.quit()

    def show_settings(self) -> None:
        dialog = SetupDialog(self.config)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.config.auto_check_enabled = dialog.auto.isChecked()
        self.config.interval_minutes = dialog.interval.value()
        self.config.save()
        set_autostart(dialog.autostart.isChecked(), Path(self.config.agent_path).expanduser())
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(autostart_enabled())
        self.autostart_action.blockSignals(False)
        self._apply_timer()

    def check_for_updates(self, manual: bool) -> None:
        if self.component_worker is not None or self.check_worker is not None:
            if manual:
                self._message(tr("check.running"))
            return

        service = ComponentUpdateService(
            manifest_url=COMPONENT_MANIFEST_URL,
            component_root=COMPONENT_ROOT,
            platform_name="linux",
            app_version=(self.config.installed_version or APP_VERSION),
            user_agent=USER_AGENT + "-Components",
            timeout=CHECK_TIMEOUT,
        )
        worker = ComponentUpdateWorker(service)
        self.component_worker = worker
        worker.signals.finished.connect(
            lambda result: self._components_finished(result, manual)
        )
        worker.signals.failed.connect(
            lambda message: self._components_failed(message, manual)
        )
        self.pool.start(worker)

    def _components_finished(self, result_object: object, manual: bool) -> None:
        self.component_worker = None
        if isinstance(result_object, ComponentUpdateResult) and result_object.updated:
            message = tr("component.updated", count=len(result_object.updated))
            if result_object.restart_required:
                message += "\n" + tr("component.restart")
            self._message(message)
        self._check_main_update(manual)

    def _components_failed(self, message: str, manual: bool) -> None:
        self.component_worker = None
        # Component feed errors must never block normal GMM release checks.
        logging.warning("Component update check failed: %s", message)
        self._check_main_update(manual)

    def _check_main_update(self, manual: bool) -> None:
        if self.check_worker is not None:
            if manual:
                self._message(tr("check.running"))
            return
        self.manual_check = manual
        current = self.config.installed_version or APP_VERSION
        worker = CheckWorker(current, self.config.channel)
        self.check_worker = worker
        worker.signals.finished.connect(self._check_finished)
        worker.signals.failed.connect(self._check_failed)
        self.pool.start(worker)

    def _check_finished(self, release_object: object) -> None:
        manual = self.manual_check
        self.check_worker = None
        if release_object is None:
            if manual:
                self._message(tr("check.uptodate", version=self.config.installed_version or APP_VERSION))
            return
        if not isinstance(release_object, RemoteRelease):
            return
        release = release_object
        if not manual and self.config.skipped_version == release.version:
            return
        self._show_release(release)

    def _check_failed(self, message: str) -> None:
        manual = self.manual_check
        self.check_worker = None
        logging.warning("Update check failed: %s", message)
        if manual:
            QMessageBox.warning(None, tr("tray.title"), tr("check.failed", error=message))

    def _show_release(self, release: RemoteRelease) -> None:
        if self.dialog is not None:
            try:
                self.dialog.raise_()
                self.dialog.activateWindow()
                return
            except RuntimeError:
                self.dialog = None
        dialog = UpdateDialog(release, self.config.installed_version or APP_VERSION)
        self.dialog = dialog
        dialog.install_requested.connect(lambda: self._install_release(release))
        dialog.skip_requested.connect(lambda: self._skip_release(release))
        dialog.finished.connect(lambda _result: self._clear_dialog(dialog))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _clear_dialog(self, dialog: UpdateDialog) -> None:
        if self.dialog is dialog:
            self.dialog = None

    def _skip_release(self, release: RemoteRelease) -> None:
        self.config.skipped_version = release.version
        self.config.save()
        if self.dialog is not None:
            self.dialog.accept()

    def _install_release(self, release: RemoteRelease) -> None:
        if self.download_worker is not None:
            return
        if self.dialog is not None:
            self.dialog.begin_download()
        worker = DownloadWorker(release)
        self.download_worker = worker
        worker.signals.progress.connect(self._download_progress)
        worker.signals.status.connect(self._download_status)
        worker.signals.finished.connect(lambda result: self._download_finished(release, result))
        worker.signals.failed.connect(self._download_failed)
        self.pool.start(worker)

    def _download_progress(self, received: int, total: int) -> None:
        if self.dialog is not None:
            self.dialog.set_progress(received, total)

    def _download_status(self, text: str) -> None:
        if self.dialog is not None:
            self.dialog.set_status(text)

    def _download_failed(self, message: str) -> None:
        self.download_worker = None
        logging.error("Update download failed: %s", message)
        if self.dialog is not None:
            self.dialog.set_failed(message)

    def _download_finished(self, release: RemoteRelease, result_object: object) -> None:
        self.download_worker = None
        if not isinstance(result_object, dict):
            self._download_failed("Invalid download result")
            return
        work = Path(result_object["work"])
        downloaded_appimage = Path(result_object["appimage"])
        downloaded_agent = Path(result_object["agent"]) if result_object.get("agent") else None
        try:
            if self.dialog is not None:
                self.dialog.set_indeterminate(tr("update.stop"))
            appimage = Path(self.config.appimage_path).expanduser().resolve()
            if not appimage.is_file():
                raise RuntimeError(tr("error.no_appimage", path=appimage))
            was_running = self._stop_running_gmm(appimage)
            if self.dialog is not None:
                self.dialog.set_indeterminate(tr("update.replace"))
            self._replace_appimage(appimage, downloaded_appimage)
            self._replace_agent_if_possible(downloaded_agent)
            self.config.installed_version = release.version
            self.config.skipped_version = ""
            self.config.save()
            if was_running:
                self.launch_gmm()
            if self.dialog is not None:
                self.dialog.progress.setRange(0, 100)
                self.dialog.progress.setValue(100)
                self.dialog.set_status(tr("update.done", version=release.version))
                QTimer.singleShot(1200, self.dialog.accept)
        except Exception as error:
            logging.exception("Update installation failed")
            if self.dialog is not None:
                self.dialog.set_failed(str(error))
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _replace_appimage(self, target: Path, downloaded: Path) -> None:
        backup = target.with_name(target.name + ".old")
        backup.unlink(missing_ok=True)
        try:
            os.replace(target, backup)
            shutil.copy2(downloaded, target)
            target.chmod(target.stat().st_mode | 0o111)
        except Exception as error:
            try:
                target.unlink(missing_ok=True)
                if backup.is_file():
                    os.replace(backup, target)
            except Exception:
                logging.exception("Rollback failed")
            raise RuntimeError(tr("error.replace", error=error)) from error
        backup.unlink(missing_ok=True)

    def _replace_agent_if_possible(self, downloaded: Path | None) -> None:
        if downloaded is None:
            return
        target = Path(self.config.agent_path).expanduser()
        if not target.parent.is_dir() or not os.access(target.parent, os.W_OK):
            logging.warning("Agent self-update skipped: directory not writable: %s", target.parent)
            return
        temporary = target.with_name(target.name + ".new")
        shutil.copy2(downloaded, temporary)
        temporary.chmod(temporary.stat().st_mode | 0o111)
        os.replace(temporary, target)
        logging.info("Update Agent binary replaced: %s", target)

    def _matching_gmm_pids(self, appimage: Path) -> list[int]:
        expected = str(appimage)
        found: list[int] = []
        proc = Path("/proc")
        if not proc.is_dir():
            return found
        for child in proc.iterdir():
            if not child.name.isdigit():
                continue
            pid = int(child.name)
            if pid == os.getpid():
                continue
            try:
                raw = (child / "environ").read_bytes()
            except (OSError, PermissionError):
                continue
            for entry in raw.split(b"\0"):
                if entry.startswith(b"APPIMAGE="):
                    value = entry.split(b"=", 1)[1].decode("utf-8", errors="ignore")
                    try:
                        candidate = str(Path(value).expanduser().resolve())
                    except OSError:
                        candidate = value
                    if candidate == expected:
                        found.append(pid)
                    break
        return found

    def _stop_running_gmm(self, appimage: Path) -> bool:
        pids = self._matching_gmm_pids(appimage)
        if not pids:
            return False
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            alive = [pid for pid in pids if Path(f"/proc/{pid}").exists()]
            if not alive:
                return True
            QApplication.processEvents()
            time.sleep(0.1)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True

    def launch_gmm(self) -> None:
        path = Path(self.config.appimage_path).expanduser()
        if not path.is_file():
            QMessageBox.warning(None, tr("tray.title"), tr("error.no_appimage", path=path))
            return
        try:
            subprocess.Popen([str(path)], start_new_session=True, close_fds=True)
        except OSError as error:
            QMessageBox.warning(None, tr("tray.title"), str(error))

    def _message(self, text: str) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable() and self.tray.isVisible():
            self.tray.showMessage(tr("tray.title"), text, QSystemTrayIcon.MessageIcon.Information, 5000)
        else:
            QMessageBox.information(None, tr("tray.title"), text)


def acquire_lock() -> object | None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    handle = LOCK_FILE.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "ja", "an"}


def update_config_from_args(config: AgentConfig, args: argparse.Namespace) -> None:
    if args.appimage:
        config.appimage_path = str(Path(args.appimage).expanduser().resolve())
    if args.agent_path:
        config.agent_path = str(Path(args.agent_path).expanduser().resolve())
    if args.installed_version:
        config.installed_version = args.installed_version.lstrip("vV")
        if config.skipped_version == config.installed_version:
            config.skipped_version = ""
    if args.auto_check is not None:
        config.auto_check_enabled = parse_bool(args.auto_check)
    if args.interval is not None:
        config.interval_minutes = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, int(args.interval)))
    if args.channel:
        config.channel = args.channel
    config.save()
    if args.autostart is not None:
        set_autostart(parse_bool(args.autostart), Path(config.agent_path).expanduser())


def configure_install_graphical(config: AgentConfig) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(AGENT_NAME)
    dialog = SetupDialog(config)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return 2
    config.auto_check_enabled = dialog.auto.isChecked()
    config.interval_minutes = dialog.interval.value()
    config.save()
    set_autostart(dialog.autostart.isChecked(), Path(config.agent_path).expanduser())
    QMessageBox.information(None, tr("setup.title"), tr("setup.saved"))
    return 0


def run_agent(initial_manual_check: bool = False) -> int:
    lock = acquire_lock()
    if lock is None:
        if initial_manual_check:
            write_command("check_now")
        return 0
    application = QApplication(sys.argv)
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName(AGENT_NAME)
    config = AgentConfig.load()
    agent = UpdateAgent(application, config)
    if initial_manual_check:
        QTimer.singleShot(500, lambda: agent.check_for_updates(manual=True))
    exit_code = application.exec()
    del agent
    del lock
    return exit_code


def spawn_background_agent() -> None:
    executable = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    args = [str(executable), "--background"]
    if not getattr(sys, "frozen", False):
        args = [sys.executable, str(executable), "--background"]
    subprocess.Popen(args, start_new_session=True, close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=AGENT_NAME)
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--check-now", action="store_true")
    parser.add_argument("--configure-install", action="store_true")
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--reload-running-agent", action="store_true")
    parser.add_argument("--autostart-enabled", action="store_true")
    parser.add_argument("--shutdown", action="store_true")
    parser.add_argument("--appimage")
    parser.add_argument("--agent-path")
    parser.add_argument("--installed-version")
    parser.add_argument("--auto-check")
    parser.add_argument("--autostart")
    parser.add_argument("--interval", type=int)
    parser.add_argument("--channel", choices=["stable", "prerelease"])
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()
    config = AgentConfig.load()

    if args.appimage or args.agent_path or args.installed_version or args.auto_check is not None or args.autostart is not None or args.interval is not None or args.channel:
        update_config_from_args(config, args)

    if args.autostart_enabled:
        return 0 if autostart_enabled() else 1

    if args.shutdown:
        write_command("shutdown")
        return 0

    if args.write_config:
        if args.reload_running_agent:
            write_command("reload_config")
        return 0

    if args.configure_install:
        return configure_install_graphical(config)

    if args.check_now:
        write_command("check_now")
        lock = acquire_lock()
        if lock is None:
            return 0
        del lock
        spawn_background_agent()
        return 0

    return run_agent(initial_manual_check=False)


if __name__ == "__main__":
    raise SystemExit(main())
