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
    UpdateChannel,
    UpdateInfo,
    UpdateService,
)


# ============================================================
# Update Check Signals
# ============================================================

class UpdateCheckSignals(
    QObject
):
    """
    Signale für die Versionsprüfung.

    finished:
        UpdateInfo
        oder None

    failed:
        Fehlermeldung
    """

    finished = Signal(
        object
    )

    failed = Signal(
        str
    )


# ============================================================
# Update Check Worker
# ============================================================

class UpdateCheckWorker(
    QRunnable
):
    """
    Prüft GitHub auf eine neuere Version.

    Die lokale Version wird vom UpdateService
    direkt aus app/version.py übernommen.

    GitHub Owner, Repository und Branch werden
    ebenfalls vom UpdateService über update_config.py
    geladen.
    """

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
# Update Download Signals
# ============================================================

class UpdateDownloadSignals(
    QObject
):
    """
    Signale für den Script-Download.

    progress:
        current
        total
        remote_path

    finished:
        StagedUpdate

    failed:
        Fehlermeldung

    cancelled:
        Benutzerabbruch
    """

    progress = Signal(
        int,
        int,
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
# Update Download Worker
# ============================================================

class UpdateDownloadWorker(
    QRunnable
):
    """
    Lädt alle Python-Dateien des Update-Commits
    in den lokalen Update-Cache.

    Beispiel:

        CACHE_DIR/
            updates/
                script-abcdef123456/
                    manifest.json
                    payload/
                        main.py
                        app/
                            version.py
                            main_window.py
                            ...

    Der Worker installiert das Update NICHT.

    Installation übernimmt später der
    Windows-Update-Helper.
    """

    def __init__(
        self,
        *,
        info: UpdateInfo,
    ) -> None:
        super().__init__()

        self.info = (
            info
        )

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
        """
        Jeder Commit erhält seinen eigenen Cache.

        Dadurch kollidieren zwei verschiedene
        Update-Versionen nicht miteinander.
        """

        short_commit = (
            self.info
            .commit_sha[
                :12
            ]
        )

        return (
            CACHE_DIR
            / "updates"
            / (
                "script-"
                f"{short_commit}"
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
            # ================================================
            # Schon vor Start abgebrochen
            # ================================================

            if self.is_cancelled():
                self._cleanup_cache(
                    cache_root
                )

                self.signals.cancelled.emit()

                return

            # ================================================
            # Alten Cache desselben Commits entfernen
            # ================================================

            self._cleanup_cache(
                cache_root
            )

            # ================================================
            # Service
            # ================================================

            service = (
                UpdateService()
            )

            staged_update = (
                service
                .download_update(
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
            # ================================================
            # Benutzerabbruch
            # ================================================

            if self.is_cancelled():
                self._cleanup_cache(
                    cache_root
                )

                self.signals.cancelled.emit()

                return

            # ================================================
            # Fehler
            #
            # Ein unvollständiger Update-Cache darf nicht
            # liegen bleiben.
            # ================================================

            self._cleanup_cache(
                cache_root
            )

            self.signals.failed.emit(
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            )

            return

        # ====================================================
        # Nach dem Download erneut Cancel prüfen
        # ====================================================

        if self.is_cancelled():
            self._cleanup_cache(
                cache_root
            )

            self.signals.cancelled.emit()

            return

        # ====================================================
        # Ergebnis prüfen
        # ====================================================

        if not isinstance(
            staged_update,
            StagedUpdate,
        ):
            self._cleanup_cache(
                cache_root
            )

            self.signals.failed.emit(
                (
                    "UpdateService hat kein "
                    "gültiges StagedUpdate "
                    "zurückgegeben."
                )
            )

            return

        if not (
            staged_update
            .manifest_path
            .is_file()
        ):
            self._cleanup_cache(
                cache_root
            )

            self.signals.failed.emit(
                (
                    "Der Update-Download wurde "
                    "abgeschlossen, aber das "
                    "Manifest fehlt."
                )
            )

            return

        if not (
            staged_update
            .payload_root
            .is_dir()
        ):
            self._cleanup_cache(
                cache_root
            )

            self.signals.failed.emit(
                (
                    "Der Update-Download wurde "
                    "abgeschlossen, aber der "
                    "Payload-Ordner fehlt."
                )
            )

            return

        # ====================================================
        # Fertig
        # ====================================================

        self.signals.finished.emit(
            staged_update
        )

    # ========================================================
    # Progress
    # ========================================================

    def _on_progress(
        self,
        current: int,
        total: int,
        remote_path: str,
    ) -> None:
        """
        Wird vom UpdateService für jede Datei aufgerufen.
        """

        if self.is_cancelled():
            return

        self.signals.progress.emit(
            int(
                current
            ),
            int(
                total
            ),
            str(
                remote_path
            ),
        )

    # ========================================================
    # Cleanup
    # ========================================================

    @staticmethod
    def _cleanup_cache(
        cache_root: Path,
    ) -> None:
        """
        Löscht einen unvollständigen Update-Cache.

        Erfolgreich heruntergeladene Updates werden hier
        NICHT gelöscht. Diese braucht anschließend der
        Windows-Installer.
        """

        try:
            shutil.rmtree(
                cache_root,
                ignore_errors=True,
            )

        except OSError:
            # ignore_errors=True sollte das normalerweise
            # bereits abfangen.
            pass


__all__ = [
    "UpdateCheckSignals",
    "UpdateCheckWorker",
    "UpdateDownloadSignals",
    "UpdateDownloadWorker",
]