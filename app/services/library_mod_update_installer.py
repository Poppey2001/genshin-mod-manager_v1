from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from app.gamebanana.client import GameBananaClient
from app.gamebanana.downloader import (
    GameBananaDownloadCancelled,
    GameBananaDownloader,
)
from app.models.mod import ModInfo
from app.services.archive_extractor import (
    ArchiveExtractionCancelled,
    extract_archive_securely,
)
from app.services.archive_security import is_supported_archive
from app.services.library_mod_backup_service import (
    LibraryModBackupService,
    ModBackupRecord,
)
from app.services.library_mod_update_service import (
    LibraryModUpdateService,
    ModUpdateResult,
    ModUpdateStatus,
    RemoteFileRevision,
)
from app.services.mod_manager import ModManager, ModState
from app.services.mod_metadata import set_gamebanana_mod_id


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


class LibraryModUpdateInstallError(RuntimeError):
    pass


class LibraryModUpdateInstallCancelled(LibraryModUpdateInstallError):
    pass


@dataclass(frozen=True, slots=True)
class ModUpdateInstallResult:
    update_result: ModUpdateResult
    backup_record: ModBackupRecord
    downloaded_file: str
    bytes_written: int


@dataclass(frozen=True, slots=True)
class ModUpdateRestoreResult:
    update_result: ModUpdateResult
    restored_backup: ModBackupRecord
    safety_backup: ModBackupRecord


class LibraryModUpdateInstaller:
    """Transactional GameBanana update + local backup/rollback layer."""

    def __init__(
        self,
        *,
        update_service: LibraryModUpdateService,
        backup_service: LibraryModBackupService,
    ) -> None:
        self.update_service = update_service
        self.backup_service = backup_service

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        current: int,
        total: int,
        stage: str,
    ) -> None:
        if callback is not None:
            callback(current, total, stage)

    @staticmethod
    def _cancelled(callback: CancelCallback | None) -> bool:
        return bool(callback is not None and callback())

    @classmethod
    def _check_cancelled(cls, callback: CancelCallback | None) -> None:
        if cls._cancelled(callback):
            raise LibraryModUpdateInstallCancelled("operation cancelled")

    @staticmethod
    def _revision_from_file(remote_file) -> RemoteFileRevision:
        return RemoteFileRevision(
            file_id=(int(remote_file.id) if remote_file.id is not None else None),
            file_name=str(remote_file.name),
            date_added=(
                int(remote_file.date_added)
                if remote_file.date_added is not None
                else None
            ),
            size=(int(remote_file.size) if remote_file.size is not None else None),
        )

    @staticmethod
    def _select_extracted_root(extraction_root: Path) -> Path:
        entries = [
            entry
            for entry in extraction_root.iterdir()
            if entry.name not in {"__MACOSX", ".DS_Store"}
        ]
        if (
            len(entries) == 1
            and entries[0].is_dir()
            and not entries[0].is_symlink()
        ):
            return entries[0]
        return extraction_root

    @staticmethod
    def _replace_library_directory(*, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        staging = destination.parent / f".{destination.name}.gmm-update-{token}"
        previous = destination.parent / f".{destination.name}.gmm-old-{token}"
        try:
            shutil.copytree(source, staging, symlinks=False, copy_function=shutil.copy2)
            had_previous = destination.exists() or destination.is_symlink()
            if had_previous:
                destination.rename(previous)
            staging.rename(destination)
            if previous.exists() or previous.is_symlink():
                if previous.is_dir() and not previous.is_symlink():
                    shutil.rmtree(previous)
                else:
                    previous.unlink(missing_ok=True)
        except Exception:
            if staging.exists() or staging.is_symlink():
                if staging.is_dir() and not staging.is_symlink():
                    shutil.rmtree(staging, ignore_errors=True)
                else:
                    staging.unlink(missing_ok=True)
            if previous.exists() and not destination.exists():
                try:
                    previous.rename(destination)
                except OSError:
                    pass
            raise

    def _managed_snapshot(
        self,
        *,
        mod: ModInfo,
        mod_manager: ModManager,
    ) -> tuple[Path | None, ModState]:
        state = mod_manager.get_state(mod.path)
        if state in {ModState.CONFLICT, ModState.BROKEN}:
            raise LibraryModUpdateInstallError(
                "Der Mod besitzt einen Konflikt oder eine defekte Active-Mods-Kopie."
            )
        if state == ModState.NOT_CONFIGURED:
            return None, state
        managed_path, managed_state = mod_manager.managed_copy_for(mod.path)
        return managed_path, managed_state

    def install(
        self,
        *,
        result: ModUpdateResult,
        mod: ModInfo,
        mod_manager: ModManager,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> ModUpdateInstallResult:
        if (
            result.gamebanana_mod_id is None
            or result.status != ModUpdateStatus.UPDATE_AVAILABLE
        ):
            raise LibraryModUpdateInstallError("Für diesen Mod ist kein Update verfügbar.")

        self._check_cancelled(cancel_callback)
        managed_path, managed_state = self._managed_snapshot(
            mod=mod,
            mod_manager=mod_manager,
        )

        self._emit(progress_callback, 0, 0, "backup")
        backup = self.backup_service.create_backup(
            game_id=result.game_id,
            mod_key=result.mod_key,
            mod_name=result.mod_name,
            library_path=mod.path,
            installed_revision=result.installed,
            managed_state=managed_state.value,
            managed_path=managed_path,
        )

        self._check_cancelled(cancel_callback)
        client = GameBananaClient(timeout=30.0)
        remote_mod = client.fetch_mod(
            int(result.gamebanana_mod_id),
            include_screenshots=False,
        )

        remote_file = None
        if result.remote is not None and result.remote.file_id is not None:
            remote_file = next(
                (
                    item
                    for item in remote_mod.files
                    if item.id is not None
                    and int(item.id) == int(result.remote.file_id)
                ),
                None,
            )
        remote_file = remote_file or remote_mod.default_file()
        if remote_file is None:
            raise LibraryModUpdateInstallError(
                "GameBanana stellt für dieses Update keine herunterladbare Datei bereit."
            )

        revision = self._revision_from_file(remote_file)
        operation_result = replace(
            result,
            remote=revision,
            profile_url=remote_mod.profile_url,
            remote_mod_name=remote_mod.name,
        )

        with tempfile.TemporaryDirectory(prefix="gmm-mod-update-") as temp_text:
            temp_root = Path(temp_text)
            download_root = temp_root / "download"
            extraction_root = temp_root / "extracted"
            extraction_root.mkdir(parents=True, exist_ok=True)

            downloader = GameBananaDownloader(timeout=45.0)

            def download_progress(current: int, total: int) -> None:
                self._emit(progress_callback, current, total, "download")

            try:
                download = downloader.download(
                    file=remote_file,
                    destination_directory=download_root,
                    progress_callback=download_progress,
                    cancel_callback=cancel_callback,
                    overwrite=True,
                )
            except GameBananaDownloadCancelled as error:
                raise LibraryModUpdateInstallCancelled(str(error)) from error

            self._check_cancelled(cancel_callback)
            if not is_supported_archive(download.path):
                raise LibraryModUpdateInstallError(
                    f"Das Update-Archiv wird nicht unterstützt: {download.path.name}"
                )

            self._emit(progress_callback, 0, 0, "extract")
            try:
                extract_archive_securely(
                    source=download.path,
                    destination=extraction_root,
                    cancel_callback=cancel_callback,
                )
            except ArchiveExtractionCancelled as error:
                raise LibraryModUpdateInstallCancelled(str(error)) from error

            self._check_cancelled(cancel_callback)
            extracted_mod_root = self._select_extracted_root(extraction_root)
            if not extracted_mod_root.is_dir():
                raise LibraryModUpdateInstallError(
                    "Das entpackte Update enthält keinen gültigen Mod-Ordner."
                )

            self._emit(progress_callback, 0, 0, "stage")
            stage_root = temp_root / "staged-mod"
            shutil.copytree(
                extracted_mod_root,
                stage_root,
                symlinks=False,
                copy_function=shutil.copy2,
            )

            # Preserve GMM-owned root metadata across a GameBanana archive
            # replacement.  Archive-owned metadata.json remains untouched.
            old_root = Path(mod.path)
            for metadata_file in old_root.iterdir():
                if not metadata_file.is_file():
                    continue
                lower_name = metadata_file.name.casefold()
                if not (
                    lower_name.startswith(".gmm")
                    or lower_name.startswith(".xxmi")
                ):
                    continue
                if lower_name in {
                    ".gmm-managed.json",
                    ".xxmimm-managed.json",
                }:
                    continue
                shutil.copy2(
                    metadata_file,
                    stage_root / metadata_file.name,
                )

            set_gamebanana_mod_id(
                stage_root,
                game_id=result.game_id,
                mod_id=int(result.gamebanana_mod_id),
            )

            self._check_cancelled(cancel_callback)
            library_replaced = False
            try:
                self._emit(progress_callback, 0, 0, "replace")
                self._replace_library_directory(
                    source=stage_root,
                    destination=Path(mod.path),
                )
                library_replaced = True

                if managed_path is not None:
                    self._emit(progress_callback, 0, 0, "sync")
                    mod_manager.refresh_from_library(mod.path)

                self._emit(progress_callback, 0, 0, "tracking")
                updated = self.update_service.set_installed_revision(
                    operation_result,
                    revision,
                )

            except Exception:
                if library_replaced:
                    try:
                        self.backup_service.restore_library(
                            record=backup,
                            destination=mod.path,
                        )
                        if backup.has_managed_copy and backup.managed_path.is_dir():
                            mod_manager.restore_managed_copy(
                                mod.path,
                                backup.managed_path,
                                backup.managed_state or managed_state.value,
                            )
                    except Exception:
                        pass
                raise

        self._emit(progress_callback, 1, 1, "finished")
        return ModUpdateInstallResult(
            update_result=updated,
            backup_record=backup,
            downloaded_file=remote_file.name,
            bytes_written=download.bytes_written,
        )

    def restore_backup(
        self,
        *,
        result: ModUpdateResult,
        mod: ModInfo,
        record: ModBackupRecord,
        mod_manager: ModManager,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> ModUpdateRestoreResult:
        self._check_cancelled(cancel_callback)
        managed_path, managed_state = self._managed_snapshot(
            mod=mod,
            mod_manager=mod_manager,
        )

        self._emit(progress_callback, 0, 0, "backup")
        safety = self.backup_service.create_backup(
            game_id=result.game_id,
            mod_key=result.mod_key,
            mod_name=result.mod_name,
            library_path=mod.path,
            installed_revision=result.installed,
            managed_state=managed_state.value,
            managed_path=managed_path,
            prune=False,
        )

        try:
            self._check_cancelled(cancel_callback)
            self._emit(progress_callback, 0, 0, "restore")
            self.backup_service.restore_library(
                record=record,
                destination=mod.path,
            )

            if record.has_managed_copy and record.managed_path.is_dir():
                self._emit(progress_callback, 0, 0, "sync")
                mod_manager.restore_managed_copy(
                    mod.path,
                    record.managed_path,
                    record.managed_state or ModState.DISABLED.value,
                )
            elif managed_path is not None:
                mod_manager.refresh_from_library(mod.path)

            updated = self.update_service.set_installed_revision(
                result,
                record.installed_revision,
            )

        except Exception:
            try:
                self.backup_service.restore_library(
                    record=safety,
                    destination=mod.path,
                )
                if safety.has_managed_copy and safety.managed_path.is_dir():
                    mod_manager.restore_managed_copy(
                        mod.path,
                        safety.managed_path,
                        safety.managed_state or managed_state.value,
                    )
                self.update_service.set_installed_revision(
                    result,
                    safety.installed_revision,
                )
            except Exception:
                pass
            raise

        self.backup_service.prune_backups(
            game_id=result.game_id,
            mod_key=result.mod_key,
            mod_name=result.mod_name,
        )
        self._emit(progress_callback, 1, 1, "finished")
        return ModUpdateRestoreResult(
            update_result=updated,
            restored_backup=record,
            safety_backup=safety,
        )


__all__ = [
    "LibraryModUpdateInstallCancelled",
    "LibraryModUpdateInstallError",
    "LibraryModUpdateInstaller",
    "ModUpdateInstallResult",
    "ModUpdateRestoreResult",
]
