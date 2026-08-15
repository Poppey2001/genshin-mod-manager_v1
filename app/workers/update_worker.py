from __future__ import annotations

import shutil
import threading

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.config import (
    CACHE_DIR,
)

from app.services.update_service import (
    StagedUpdate,
    UpdateInfo,
    UpdateService,
)


# ============================================================
# Check Signals
# ============================================================

class UpdateCheckSignals(
    QObject
):
    finished = Signal(
        object
    )

    failed = Signal(
        str
    )


# ============================================================
# Check Worker
# ============================================================

class UpdateCheckWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        allow_prerelease: bool = True,
    ) -> None:
        super().__init__()

        self.allow_prerelease = bool(
            allow_prerelease
        )

        self.signals = (
            UpdateCheckSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            service = (
                UpdateService()
            )

            update = (
                service.check_for_update(
                    allow_prerelease=(
                        self.allow_prerelease
                    )
                )
            )

        except Exception as error:
            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        self.signals.finished.emit(
            update
        )


# ============================================================
# Download Signals
# ============================================================

class UpdateDownloadSignals(
    QObject
):
    # Bytes können größer als Qt int werden.
    progress = Signal(
        object,
        object,
        str,
    )

    finished = Signal(
        object
    )

    failed = Signal(
        str
    )

    cancelled = Signal()


# ============================================================
# Download Worker
# ============================================================

class UpdateDownloadWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        info: UpdateInfo,
    ) -> None:
        super().__init__()

        self.info = info

        self.signals = (
            UpdateDownloadSignals()
        )

        self._cancel_event = (
            threading.Event()
        )

        self.setAutoDelete(
            True
        )

    # ========================================================
    # Cancel
    # ========================================================

    def cancel(
        self,
    ) -> None:
        self._cancel_event.set()

    def is_cancelled(
        self,
    ) -> bool:
        return (
            self._cancel_event
            .is_set()
        )

    # ========================================================
    # Cache
    # ========================================================

    def cache_root(
        self,
    ) -> Path:
        safe_version = (
            str(
                self.info.version
            )
            .replace(
                "/",
                "_",
            )
            .replace(
                "\\",
                "_",
            )
        )

        return (
            CACHE_DIR
            / "updates"
            / (
                "source-"
                + safe_version
            )
        )

    # ========================================================
    # Run
    # ========================================================

    @Slot()
    def run(
        self,
    ) -> None:
        cache_root = (
            self.cache_root()
        )

        try:
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            if self.is_cancelled():
                self.signals.cancelled.emit()

                return

            service = (
                UpdateService()
            )

            staged = (
                service.download_update(
                    info=(
                        self.info
                    ),
                    cache_root=(
                        cache_root
                    ),
                    progress_callback=(
                        self._on_progress
                    ),
                    cancel_callback=(
                        self.is_cancelled
                    ),
                )
            )

        except Exception as error:
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            if self.is_cancelled():
                self.signals.cancelled.emit()

                return

            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        if self.is_cancelled():
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            self.signals.cancelled.emit()

            return

        if not isinstance(
            staged,
            StagedUpdate,
        ):
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

            self.signals.failed.emit(
                (
                    "Ungültiges "
                    "Update-Ergebnis."
                )
            )

            return

        self.signals.finished.emit(
            staged
        )

    # ========================================================
    # Progress
    # ========================================================

    def _on_progress(
        self,
        current: int,
        total: int,
        name: str,
    ) -> None:
        self.signals.progress.emit(
            current,
            total,
            name,
        )


__all__ = [
    "UpdateCheckSignals",
    "UpdateCheckWorker",
    "UpdateDownloadSignals",
    "UpdateDownloadWorker",
]