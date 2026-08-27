from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.models.mod import ModInfo
from app.services.library_mod_backup_service import ModBackupRecord
from app.services.library_mod_update_installer import (
    LibraryModUpdateInstallCancelled,
    LibraryModUpdateInstaller,
)
from app.services.library_mod_update_service import ModUpdateResult
from app.services.mod_manager import ModManager


class ModUpdateOperationSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class _BaseModUpdateWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = ModUpdateOperationSignals()
        self._cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _progress(self, current: int, total: int, stage: str) -> None:
        self.signals.progress.emit(int(current), int(total), str(stage))


class ModUpdateInstallWorker(_BaseModUpdateWorker):
    def __init__(
        self,
        *,
        installer: LibraryModUpdateInstaller,
        result: ModUpdateResult,
        mod: ModInfo,
        mod_manager: ModManager,
    ) -> None:
        super().__init__()
        self.installer = installer
        self.result = result
        self.mod = mod
        self.mod_manager = mod_manager

    @Slot()
    def run(self) -> None:
        try:
            payload = self.installer.install(
                result=self.result,
                mod=self.mod,
                mod_manager=self.mod_manager,
                progress_callback=self._progress,
                cancel_callback=self.is_cancelled,
            )
        except LibraryModUpdateInstallCancelled:
            self.signals.cancelled.emit()
            return
        except Exception as error:
            self.signals.failed.emit(f"{type(error).__name__}: {error}")
            return
        self.signals.finished.emit(payload)


class ModUpdateRestoreWorker(_BaseModUpdateWorker):
    def __init__(
        self,
        *,
        installer: LibraryModUpdateInstaller,
        result: ModUpdateResult,
        mod: ModInfo,
        record: ModBackupRecord,
        mod_manager: ModManager,
    ) -> None:
        super().__init__()
        self.installer = installer
        self.result = result
        self.mod = mod
        self.record = record
        self.mod_manager = mod_manager

    @Slot()
    def run(self) -> None:
        try:
            payload = self.installer.restore_backup(
                result=self.result,
                mod=self.mod,
                record=self.record,
                mod_manager=self.mod_manager,
                progress_callback=self._progress,
                cancel_callback=self.is_cancelled,
            )
        except LibraryModUpdateInstallCancelled:
            self.signals.cancelled.emit()
            return
        except Exception as error:
            self.signals.failed.emit(f"{type(error).__name__}: {error}")
            return
        self.signals.finished.emit(payload)


__all__ = [
    "ModUpdateInstallWorker",
    "ModUpdateOperationSignals",
    "ModUpdateRestoreWorker",
]
