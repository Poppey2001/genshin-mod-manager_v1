from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from app.gamebanana.client import GameBananaClient
from app.models.mod import ModInfo
from app.services.mod_metadata import load_mod_metadata


DOCUMENT_VERSION = 1
LOCAL_TIMESTAMP_TOLERANCE_SECONDS = 300


class ModUpdateStatus(str, Enum):
    NOT_LINKED = "not_linked"
    CURRENT = "current"
    UPDATE_AVAILABLE = "update_available"
    TRACKING_STARTED = "tracking_started"
    NO_DOWNLOAD = "no_download"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RemoteFileRevision:
    file_id: int | None
    file_name: str
    date_added: int | None
    size: int | None

    @property
    def signature(self) -> str:
        return "|".join(
            (
                str(self.file_id or 0),
                str(self.date_added or 0),
                self.file_name,
                str(self.size or 0),
            )
        )

    @property
    def order_key(self) -> tuple[int, int]:
        return (
            int(self.date_added or 0),
            int(self.file_id or 0),
        )


@dataclass(frozen=True, slots=True)
class ModUpdateResult:
    game_id: str
    mod_key: str
    mod_path: str
    mod_name: str
    gamebanana_mod_id: int | None
    status: ModUpdateStatus
    installed: RemoteFileRevision | None = None
    remote: RemoteFileRevision | None = None
    profile_url: str | None = None
    remote_mod_name: str | None = None
    checked_at: str | None = None
    message: str | None = None

    @property
    def update_available(self) -> bool:
        return self.status == ModUpdateStatus.UPDATE_AVAILABLE


class LibraryModUpdateError(RuntimeError):
    pass


def default_mod_update_state_path() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "Genshin Mod Manager" / "mod_update_state.json"

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Genshin Mod Manager"
            / "mod_update_state.json"
        )

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    root = (
        Path(xdg_data_home).expanduser()
        if xdg_data_home
        else Path.home() / ".local" / "share"
    )
    return root / "genshin-mod-manager" / "mod_update_state.json"


class LibraryModUpdateService:
    """
    Tracks GameBanana file revisions for Library mods.

    The service detects whether the newest downloadable GameBanana file is
    newer than the revision GMM considers installed.  File replacement itself
    remains isolated in LibraryModUpdateInstaller, which adds transactional
    backup and rollback semantics around this tracking state.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = (
            Path(path).expanduser()
            if path is not None
            else default_mod_update_state_path()
        )
        self._lock = threading.RLock()
        self._cached_document: dict[str, Any] | None = None
        self._cached_mtime_ns: int | None = None

    @staticmethod
    def normalize_game_id(game_id: str) -> str:
        value = str(game_id).strip()
        if not value:
            raise LibraryModUpdateError("game_id must not be empty")
        return value

    @staticmethod
    def normalize_mod_key(value: str | Path) -> str:
        text = str(value).strip().replace("\\", "/")
        if not text:
            raise LibraryModUpdateError("mod key must not be empty")

        parts = [
            part
            for part in PurePosixPath(text).parts
            if part not in {"", ".", "/"}
        ]
        if not parts or any(part == ".." for part in parts):
            raise LibraryModUpdateError("mod key is not a safe relative path")
        return "/".join(parts)

    def mod_key(self, mod: ModInfo) -> str:
        return self.normalize_mod_key(
            mod.relative_path or Path(mod.path).name
        )

    @staticmethod
    def _new_document() -> dict[str, Any]:
        return {"version": DOCUMENT_VERSION, "games": {}}

    def _read_document(self) -> dict[str, Any]:
        if not self.path.is_file():
            if self._cached_document is None:
                self._cached_document = self._new_document()
            self._cached_mtime_ns = None
            return self._cached_document

        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None

        if (
            self._cached_document is not None
            and mtime_ns is not None
            and self._cached_mtime_ns == mtime_ns
        ):
            return self._cached_document

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raw = self._new_document()

        if not isinstance(raw, dict):
            raw = self._new_document()

        games = raw.get("games")
        if not isinstance(games, dict):
            games = {}

        self._cached_document = {
            "version": DOCUMENT_VERSION,
            "games": games,
        }
        self._cached_mtime_ns = mtime_ns
        return self._cached_document

    def _write_document(self, document: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        ) + "\n"

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)

            temporary_path.replace(self.path)
            self._cached_document = document
            try:
                self._cached_mtime_ns = self.path.stat().st_mtime_ns
            except OSError:
                self._cached_mtime_ns = None
        except OSError as error:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise LibraryModUpdateError(str(error)) from error

    @staticmethod
    def _game_bucket(
        document: dict[str, Any],
        game_id: str,
        *,
        create: bool,
    ) -> dict[str, Any] | None:
        games = document.setdefault("games", {})
        if not isinstance(games, dict):
            games = {}
            document["games"] = games

        bucket = games.get(game_id)
        if not isinstance(bucket, dict):
            if not create:
                return None
            bucket = {"mods": {}}
            games[game_id] = bucket

        if not isinstance(bucket.get("mods"), dict):
            bucket["mods"] = {}
        return bucket

    @staticmethod
    def _revision_from_dict(value: Any) -> RemoteFileRevision | None:
        if not isinstance(value, dict):
            return None
        name = str(value.get("file_name", "")).strip()
        if not name:
            return None
        try:
            file_id = value.get("file_id")
            file_id = int(file_id) if file_id is not None else None
        except (TypeError, ValueError):
            file_id = None
        try:
            date_added = value.get("date_added")
            date_added = int(date_added) if date_added is not None else None
        except (TypeError, ValueError):
            date_added = None
        try:
            size = value.get("size")
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            size = None
        return RemoteFileRevision(
            file_id=file_id,
            file_name=name,
            date_added=date_added,
            size=size,
        )

    @staticmethod
    def _revision_to_dict(revision: RemoteFileRevision | None) -> dict[str, Any] | None:
        if revision is None:
            return None
        return asdict(revision)

    @staticmethod
    def _remote_revision(remote_file) -> RemoteFileRevision:
        return RemoteFileRevision(
            file_id=(
                int(remote_file.id)
                if remote_file.id is not None
                else None
            ),
            file_name=str(remote_file.name),
            date_added=(
                int(remote_file.date_added)
                if remote_file.date_added is not None
                else None
            ),
            size=(
                int(remote_file.size)
                if remote_file.size is not None
                else None
            ),
        )

    @staticmethod
    def _is_remote_newer(
        installed: RemoteFileRevision,
        remote: RemoteFileRevision,
    ) -> bool:
        installed_order = installed.order_key
        remote_order = remote.order_key

        if remote_order != (0, 0) or installed_order != (0, 0):
            return remote_order > installed_order

        return remote.signature != installed.signature

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def cached_result(
        self,
        *,
        game_id: str,
        mod: ModInfo,
    ) -> ModUpdateResult:
        game_id = self.normalize_game_id(game_id)
        mod_key = self.mod_key(mod)

        try:
            metadata = load_mod_metadata(mod.path)
            mod_id = metadata.gamebanana_mod_id
        except Exception as error:
            return ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=None,
                status=ModUpdateStatus.ERROR,
                message=str(error),
            )

        if mod_id is None:
            return ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=None,
                status=ModUpdateStatus.NOT_LINKED,
            )

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            entry = None
            if bucket is not None:
                entry = bucket.get("mods", {}).get(mod_key)

            if not isinstance(entry, dict):
                return ModUpdateResult(
                    game_id=game_id,
                    mod_key=mod_key,
                    mod_path=str(mod.path),
                    mod_name=mod.name,
                    gamebanana_mod_id=int(mod_id),
                    status=ModUpdateStatus.CURRENT,
                    message="tracking-not-checked",
                )

            if int(entry.get("gamebanana_mod_id", 0) or 0) != int(mod_id):
                return ModUpdateResult(
                    game_id=game_id,
                    mod_key=mod_key,
                    mod_path=str(mod.path),
                    mod_name=mod.name,
                    gamebanana_mod_id=int(mod_id),
                    status=ModUpdateStatus.CURRENT,
                    message="tracking-reset-needed",
                )

            installed = self._revision_from_dict(entry.get("installed"))
            remote = self._revision_from_dict(entry.get("last_remote"))
            profile_url = entry.get("profile_url")
            checked_at = entry.get("last_checked")
            remote_mod_name = entry.get("remote_mod_name")
            last_error = entry.get("last_error")

            if last_error:
                status = ModUpdateStatus.ERROR
            elif remote is None:
                status = ModUpdateStatus.CURRENT
            elif installed is None:
                status = ModUpdateStatus.TRACKING_STARTED
            elif self._is_remote_newer(installed, remote):
                status = ModUpdateStatus.UPDATE_AVAILABLE
            else:
                status = ModUpdateStatus.CURRENT

            return ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=int(mod_id),
                status=status,
                installed=installed,
                remote=remote,
                profile_url=(str(profile_url) if profile_url else None),
                remote_mod_name=(str(remote_mod_name) if remote_mod_name else None),
                checked_at=(str(checked_at) if checked_at else None),
                message=(str(last_error) if last_error else None),
            )

    def check_mod(
        self,
        *,
        game_id: str,
        mod: ModInfo,
        client: GameBananaClient | None = None,
    ) -> ModUpdateResult:
        game_id = self.normalize_game_id(game_id)
        mod_key = self.mod_key(mod)
        checked_at = self._now_iso()

        try:
            metadata = load_mod_metadata(mod.path)
            mod_id = metadata.gamebanana_mod_id
        except Exception as error:
            return ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=None,
                status=ModUpdateStatus.ERROR,
                checked_at=checked_at,
                message=str(error),
            )

        if mod_id is None:
            return ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=None,
                status=ModUpdateStatus.NOT_LINKED,
                checked_at=checked_at,
            )

        client = client or GameBananaClient(timeout=20.0)

        try:
            remote_mod = client.fetch_mod(
                int(mod_id),
                include_screenshots=False,
            )
            remote_file = remote_mod.default_file()
            if remote_file is None:
                result = ModUpdateResult(
                    game_id=game_id,
                    mod_key=mod_key,
                    mod_path=str(mod.path),
                    mod_name=mod.name,
                    gamebanana_mod_id=int(mod_id),
                    status=ModUpdateStatus.NO_DOWNLOAD,
                    profile_url=remote_mod.profile_url,
                    remote_mod_name=remote_mod.name,
                    checked_at=checked_at,
                )
                self._persist_result(result)
                return result

            remote = self._remote_revision(remote_file)

        except Exception as error:
            result = ModUpdateResult(
                game_id=game_id,
                mod_key=mod_key,
                mod_path=str(mod.path),
                mod_name=mod.name,
                gamebanana_mod_id=int(mod_id),
                status=ModUpdateStatus.ERROR,
                checked_at=checked_at,
                message=f"{type(error).__name__}: {error}",
            )
            self._persist_result(result)
            return result

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=True)
            assert bucket is not None
            mods = bucket["mods"]
            entry = mods.get(mod_key)

            if (
                not isinstance(entry, dict)
                or int(entry.get("gamebanana_mod_id", 0) or 0) != int(mod_id)
            ):
                entry = {
                    "gamebanana_mod_id": int(mod_id),
                    "installed": None,
                }
                mods[mod_key] = entry

            installed = self._revision_from_dict(entry.get("installed"))
            first_tracking = installed is None

            if installed is None:
                local_modified = getattr(mod, "modified_at", None)
                remote_date = remote.date_added
                if (
                    isinstance(local_modified, (int, float))
                    and remote_date is not None
                    and int(remote_date)
                    > int(local_modified) + LOCAL_TIMESTAMP_TOLERANCE_SECONDS
                ):
                    installed = RemoteFileRevision(
                        file_id=None,
                        file_name="local-install",
                        date_added=int(local_modified),
                        size=None,
                    )
                else:
                    installed = remote

                entry["installed"] = self._revision_to_dict(installed)

            update_available = self._is_remote_newer(installed, remote)
            if update_available:
                status = ModUpdateStatus.UPDATE_AVAILABLE
            elif first_tracking:
                status = ModUpdateStatus.TRACKING_STARTED
            else:
                status = ModUpdateStatus.CURRENT

            entry.update(
                {
                    "gamebanana_mod_id": int(mod_id),
                    "last_remote": self._revision_to_dict(remote),
                    "profile_url": remote_mod.profile_url,
                    "remote_mod_name": remote_mod.name,
                    "last_checked": checked_at,
                    "last_error": None,
                }
            )
            self._write_document(document)

        return ModUpdateResult(
            game_id=game_id,
            mod_key=mod_key,
            mod_path=str(mod.path),
            mod_name=mod.name,
            gamebanana_mod_id=int(mod_id),
            status=status,
            installed=installed,
            remote=remote,
            profile_url=remote_mod.profile_url,
            remote_mod_name=remote_mod.name,
            checked_at=checked_at,
        )

    def _persist_result(self, result: ModUpdateResult) -> None:
        if result.gamebanana_mod_id is None:
            return

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, result.game_id, create=True)
            assert bucket is not None
            mods = bucket["mods"]
            entry = mods.get(result.mod_key)
            if not isinstance(entry, dict):
                entry = {}
                mods[result.mod_key] = entry

            entry.update(
                {
                    "gamebanana_mod_id": int(result.gamebanana_mod_id),
                    "last_checked": result.checked_at,
                    "profile_url": result.profile_url,
                    "remote_mod_name": result.remote_mod_name,
                    "last_error": (
                        result.message
                        if result.status == ModUpdateStatus.ERROR
                        else None
                    ),
                }
            )
            if result.remote is not None:
                entry["last_remote"] = self._revision_to_dict(result.remote)
            self._write_document(document)

    def set_installed_revision(
        self,
        result: ModUpdateResult,
        revision: RemoteFileRevision | None,
    ) -> ModUpdateResult:
        """Persist the revision that is really installed locally.

        This method is used by the transactional update/rollback layer.  It is
        deliberately separate from ``mark_current`` so restoring an older
        backup can immediately make a newer GameBanana file visible again.
        """
        if result.gamebanana_mod_id is None:
            raise LibraryModUpdateError("mod is not linked to GameBanana")

        checked_at = self._now_iso()
        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, result.game_id, create=True)
            assert bucket is not None
            mods = bucket["mods"]
            entry = mods.get(result.mod_key)
            if not isinstance(entry, dict):
                entry = {}
                mods[result.mod_key] = entry

            entry.update(
                {
                    "gamebanana_mod_id": int(result.gamebanana_mod_id),
                    "installed": self._revision_to_dict(revision),
                    "last_remote": self._revision_to_dict(result.remote),
                    "profile_url": result.profile_url,
                    "remote_mod_name": result.remote_mod_name,
                    "last_checked": checked_at,
                    "last_error": None,
                }
            )
            self._write_document(document)

        if result.remote is None:
            status = ModUpdateStatus.CURRENT
        elif revision is None:
            status = ModUpdateStatus.TRACKING_STARTED
        elif self._is_remote_newer(revision, result.remote):
            status = ModUpdateStatus.UPDATE_AVAILABLE
        else:
            status = ModUpdateStatus.CURRENT

        return ModUpdateResult(
            game_id=result.game_id,
            mod_key=result.mod_key,
            mod_path=result.mod_path,
            mod_name=result.mod_name,
            gamebanana_mod_id=result.gamebanana_mod_id,
            status=status,
            installed=revision,
            remote=result.remote,
            profile_url=result.profile_url,
            remote_mod_name=result.remote_mod_name,
            checked_at=checked_at,
        )

    def mark_current(self, result: ModUpdateResult) -> ModUpdateResult:
        if result.remote is None:
            raise LibraryModUpdateError("no remote revision is available")
        return self.set_installed_revision(result, result.remote)

    def reset_tracking(
        self,
        *,
        game_id: str,
        mod: ModInfo,
    ) -> None:
        game_id = self.normalize_game_id(game_id)
        mod_key = self.mod_key(mod)
        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            if bucket is None:
                return
            mods = bucket.get("mods", {})
            if isinstance(mods, dict):
                mods.pop(mod_key, None)
            self._write_document(document)


__all__ = [
    "LibraryModUpdateError",
    "LibraryModUpdateService",
    "ModUpdateResult",
    "ModUpdateStatus",
    "RemoteFileRevision",
    "default_mod_update_state_path",
]
