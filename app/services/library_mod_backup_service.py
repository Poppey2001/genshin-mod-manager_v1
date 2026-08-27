from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.library_mod_update_service import RemoteFileRevision


BACKUP_DOCUMENT_VERSION = 1
DEFAULT_KEEP_BACKUPS = 5


class LibraryModBackupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModBackupRecord:
    backup_id: str
    game_id: str
    mod_key: str
    mod_name: str
    created_at: str
    backup_path: Path
    installed_revision: RemoteFileRevision | None
    managed_state: str | None = None
    has_managed_copy: bool = False

    @property
    def library_path(self) -> Path:
        return self.backup_path / "library"

    @property
    def managed_path(self) -> Path:
        return self.backup_path / "managed"



def default_mod_backup_root() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "Genshin Mod Manager" / "mod_backups"

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Genshin Mod Manager"
            / "mod_backups"
        )

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    root = (
        Path(xdg_data_home).expanduser()
        if xdg_data_home
        else Path.home() / ".local" / "share"
    )
    return root / "genshin-mod-manager" / "mod_backups"


class LibraryModBackupService:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        keep_backups: int = DEFAULT_KEEP_BACKUPS,
    ) -> None:
        self.root = (
            Path(root).expanduser()
            if root is not None
            else default_mod_backup_root()
        )
        self.keep_backups = max(1, int(keep_backups))

    @staticmethod
    def _safe_game_id(game_id: str) -> str:
        value = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in str(game_id).strip()
        ).strip("-")
        if not value:
            raise LibraryModBackupError("game_id must not be empty")
        return value

    @staticmethod
    def _mod_bucket_name(mod_key: str, mod_name: str) -> str:
        digest = hashlib.sha256(
            str(mod_key).encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        readable = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in str(mod_name).strip()
        ).strip("-")[:48]
        if not readable:
            readable = "mod"
        return f"{readable}-{digest}"

    def _bucket(self, game_id: str, mod_key: str, mod_name: str) -> Path:
        return (
            self.root
            / self._safe_game_id(game_id)
            / self._mod_bucket_name(mod_key, mod_name)
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _revision_to_dict(
        revision: RemoteFileRevision | None,
    ) -> dict[str, Any] | None:
        return asdict(revision) if revision is not None else None

    @staticmethod
    def _revision_from_dict(value: Any) -> RemoteFileRevision | None:
        if not isinstance(value, dict):
            return None
        name = str(value.get("file_name", "")).strip()
        if not name:
            return None

        def optional_int(key: str) -> int | None:
            raw = value.get(key)
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        return RemoteFileRevision(
            file_id=optional_int("file_id"),
            file_name=name,
            date_added=optional_int("date_added"),
            size=optional_int("size"),
        )

    def create_backup(
        self,
        *,
        game_id: str,
        mod_key: str,
        mod_name: str,
        library_path: Path | str,
        installed_revision: RemoteFileRevision | None,
        managed_state: str | None = None,
        managed_path: Path | str | None = None,
        prune: bool = True,
    ) -> ModBackupRecord:
        source = Path(library_path).expanduser().absolute()
        if not source.is_dir() or source.is_symlink():
            raise LibraryModBackupError(
                f"Mod library folder is not a normal directory: {source}"
            )

        bucket = self._bucket(game_id, mod_key, mod_name)
        bucket.mkdir(parents=True, exist_ok=True)

        created_at = self._now_iso()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
        final_directory = bucket / backup_id

        temporary_directory = Path(
            tempfile.mkdtemp(
                prefix=f".{backup_id}.",
                dir=bucket,
            )
        )

        try:
            shutil.copytree(
                source,
                temporary_directory / "library",
                symlinks=True,
                copy_function=shutil.copy2,
            )

            has_managed_copy = False
            normalized_managed_path: Path | None = None
            if managed_path is not None:
                candidate = Path(managed_path).expanduser().absolute()
                try:
                    same_as_library = candidate.samefile(source)
                except (OSError, ValueError):
                    same_as_library = candidate == source

                if (
                    not same_as_library
                    and candidate.is_dir()
                    and not candidate.is_symlink()
                ):
                    shutil.copytree(
                        candidate,
                        temporary_directory / "managed",
                        symlinks=True,
                        copy_function=shutil.copy2,
                    )
                    has_managed_copy = True
                    normalized_managed_path = candidate

            manifest = {
                "version": BACKUP_DOCUMENT_VERSION,
                "backup_id": backup_id,
                "game_id": str(game_id),
                "mod_key": str(mod_key),
                "mod_name": str(mod_name),
                "created_at": created_at,
                "installed_revision": self._revision_to_dict(
                    installed_revision
                ),
                "managed_state": managed_state,
                "has_managed_copy": has_managed_copy,
                "source_library_path": str(source),
                "source_managed_path": (
                    str(normalized_managed_path)
                    if normalized_managed_path is not None
                    else None
                ),
            }
            (temporary_directory / "backup.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            temporary_directory.rename(final_directory)
        except Exception as error:
            shutil.rmtree(temporary_directory, ignore_errors=True)
            raise LibraryModBackupError(str(error)) from error

        record = ModBackupRecord(
            backup_id=backup_id,
            game_id=str(game_id),
            mod_key=str(mod_key),
            mod_name=str(mod_name),
            created_at=created_at,
            backup_path=final_directory,
            installed_revision=installed_revision,
            managed_state=managed_state,
            has_managed_copy=has_managed_copy,
        )
        if prune:
            self.prune_backups(
                game_id=game_id,
                mod_key=mod_key,
                mod_name=mod_name,
            )
        return record

    def list_backups(
        self,
        *,
        game_id: str,
        mod_key: str,
        mod_name: str,
    ) -> tuple[ModBackupRecord, ...]:
        bucket = self._bucket(game_id, mod_key, mod_name)
        if not bucket.is_dir():
            return ()

        records: list[ModBackupRecord] = []
        for directory in bucket.iterdir():
            if not directory.is_dir():
                continue
            manifest_path = directory / "backup.json"
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            if str(raw.get("game_id", "")) != str(game_id):
                continue
            if str(raw.get("mod_key", "")) != str(mod_key):
                continue

            records.append(
                ModBackupRecord(
                    backup_id=str(raw.get("backup_id") or directory.name),
                    game_id=str(game_id),
                    mod_key=str(mod_key),
                    mod_name=str(raw.get("mod_name") or mod_name),
                    created_at=str(raw.get("created_at") or ""),
                    backup_path=directory,
                    installed_revision=self._revision_from_dict(
                        raw.get("installed_revision")
                    ),
                    managed_state=(
                        str(raw.get("managed_state"))
                        if raw.get("managed_state")
                        else None
                    ),
                    has_managed_copy=bool(raw.get("has_managed_copy")),
                )
            )

        records.sort(key=lambda record: record.created_at, reverse=True)
        return tuple(records)

    def restore_library(
        self,
        *,
        record: ModBackupRecord,
        destination: Path | str,
    ) -> None:
        source = record.library_path
        target = Path(destination).expanduser().absolute()
        if not source.is_dir():
            raise LibraryModBackupError(
                f"Backup library data is missing: {source}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.parent / f".{target.name}.gmm-restore-{uuid.uuid4().hex}.tmp"
        previous = target.parent / f".{target.name}.gmm-restore-old-{uuid.uuid4().hex}.tmp"

        try:
            shutil.copytree(
                source,
                staging,
                symlinks=True,
                copy_function=shutil.copy2,
            )

            had_target = target.exists() or target.is_symlink()
            if had_target:
                target.rename(previous)
            staging.rename(target)

            if previous.exists() or previous.is_symlink():
                self._remove_path(previous)
        except Exception as error:
            try:
                if target.exists() or target.is_symlink():
                    self._remove_path(target)
                if previous.exists() or previous.is_symlink():
                    previous.rename(target)
                if staging.exists() or staging.is_symlink():
                    self._remove_path(staging)
            except OSError:
                pass
            raise LibraryModBackupError(str(error)) from error

    def delete_backup(self, record: ModBackupRecord) -> None:
        try:
            if record.backup_path.exists():
                shutil.rmtree(record.backup_path)
        except OSError as error:
            raise LibraryModBackupError(str(error)) from error

    def prune_backups(
        self,
        *,
        game_id: str,
        mod_key: str,
        mod_name: str,
    ) -> None:
        records = self.list_backups(
            game_id=game_id,
            mod_key=mod_key,
            mod_name=mod_name,
        )
        for record in records[self.keep_backups :]:
            try:
                self.delete_backup(record)
            except LibraryModBackupError:
                pass

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


__all__ = [
    "DEFAULT_KEEP_BACKUPS",
    "LibraryModBackupError",
    "LibraryModBackupService",
    "ModBackupRecord",
    "default_mod_backup_root",
]
