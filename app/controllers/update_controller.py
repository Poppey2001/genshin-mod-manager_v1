from __future__ import annotations

import logging

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    QTimer,
)

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)

from app.config import (
    AppConfig,
)

from app.dialogs.update_dialog import (
    UpdateDialog,
)

from app.i18n import (
    tr,
)

from app.services.runtime_platform import (
    is_windows,
)

from app.services.windows_updater import (
    stage_windows_update,
)

from app.services.update_service import (
    ReleaseAsset,
    UpdateChannel,
    UpdateInfo,
)

from app.update_config import (
    GITHUB_OWNER,
    GITHUB_REPOSITORY,
    github_repository_configured,
)

from app.version import (
    APP_VERSION,
)

from app.workers.update_worker import (
    UpdateCheckWorker,
    UpdateDownloadWorker,
)


logger = logging.getLogger(
    __name__
)


class UpdateController(
    QObject
):
    def __init__(
        self,
        *,
        config: AppConfig,
        parent_window: QWidget,
    ) -> None:
        super().__init__(
            parent_window
        )

        self.config = config

        self.parent_window = (
            parent_window
        )

        self.thread_pool = (
            QThreadPool
            .globalInstance()
        )

        self._check_worker: (
            UpdateCheckWorker
            | None
        ) = None

        self._download_worker: (
            UpdateDownloadWorker
            | None
        ) = None

        self._dialog: (
            UpdateDialog
            | None
        ) = None

        self._current_update: (
            UpdateInfo
            | None
        ) = None

        self._current_asset: (
            ReleaseAsset
            | None
        ) = None

        self._manual_check = False

    # ========================================================
    # Startup
    # ========================================================

    def start_auto_check(
        self,
    ) -> None:
        # ====================================================
        # Automatischer Install-Updater aktuell nur Windows.
        # ====================================================

        if not is_windows():
            logger.info(
                (
                    "Automatischer Update-Check "
                    "übersprungen: Kein Windows."
                )
            )

            return

        if not getattr(
            self.config,
            "auto_check_updates",
            True,
        ):
            return

        QTimer.singleShot(
            3000,
            self._run_auto_check,
        )
    def _run_auto_check(
        self,
    ) -> None:
        self.check_for_updates(
            manual=False
        )

    # ========================================================
    # Manual
    # ========================================================

    def check_now(
        self,
    ) -> None:
        self.check_for_updates(
            manual=True
        )

    # ========================================================
    # Check
    # ========================================================

    def check_for_updates(
        self,
        *,
        manual: bool,
    ) -> None:
        # ----------------------------------------------------
        # Bereits aktiv
        # ----------------------------------------------------

        if (
            self._check_worker
            is not None
        ):
            if manual:
                QMessageBox.information(
                    self.parent_window,
                    tr(
                        "updates.check.title"
                    ),
                    tr(
                        "updates.check.already_running"
                    ),
                )

            return

        # ----------------------------------------------------
        # Repository
        # ----------------------------------------------------

        if not (
            github_repository_configured()
        ):
            message = (
                "GitHub Repository ist "
                "nicht konfiguriert. "
                "Trage GITHUB_OWNER in "
                "app/update_config.py ein."
            )

            if manual:
                QMessageBox.warning(
                    self.parent_window,
                    tr(
                        "updates.check.title"
                    ),
                    message,
                )

            else:
                logger.warning(
                    message
                )

            return

        # ----------------------------------------------------
        # Dialog existiert bereits
        # ----------------------------------------------------

        if (
            self._dialog
            is not None
        ):
            try:
                self._dialog.raise_()
                self._dialog.activateWindow()

                return

            except RuntimeError:
                self._dialog = None

        # ----------------------------------------------------
        # Channel
        # ----------------------------------------------------

        channel_value = getattr(
            self.config,
            "update_channel",
            "prerelease",
        )

        try:
            channel = (
                UpdateChannel(
                    channel_value
                )
            )

        except ValueError:
            channel = (
                UpdateChannel.PRERELEASE
            )

        self._manual_check = (
            manual
        )

        # ----------------------------------------------------
        # Worker
        # ----------------------------------------------------

        worker = (
            UpdateCheckWorker(
                owner=(
                    GITHUB_OWNER
                ),
                repository=(
                    GITHUB_REPOSITORY
                ),
                current_version=(
                    APP_VERSION
                ),
                channel=channel,
            )
        )

        self._check_worker = (
            worker
        )

        worker.signals.finished.connect(
            self._on_check_finished
        )

        worker.signals.failed.connect(
            self._on_check_failed
        )

        logger.info(
            (
                "Prüfe GitHub auf Updates: "
                "%s/%s – lokal %s – Kanal %s"
            ),
            GITHUB_OWNER,
            GITHUB_REPOSITORY,
            APP_VERSION,
            channel.value,
        )

        self.thread_pool.start(
            worker
        )

    # ========================================================
    # Check Ergebnis
    # ========================================================

    def _on_check_finished(
        self,
        update: object,
    ) -> None:
        manual = (
            self._manual_check
        )

        self._check_worker = (
            None
        )

        if update is None:
            logger.info(
                (
                    "Kein Update verfügbar. "
                    "Lokale Version: %s"
                ),
                APP_VERSION,
            )

            if manual:
                QMessageBox.information(
                    self.parent_window,
                    tr(
                        "updates.check.title"
                    ),
                    tr(
                        "updates.check.up_to_date",
                        version=(
                            APP_VERSION
                        ),
                    ),
                )

            return

        if not isinstance(
            update,
            UpdateInfo,
        ):
            logger.warning(
                (
                    "Ungültiges Update-Ergebnis: %r"
                ),
                update,
            )

            return

        logger.info(
            (
                "Update gefunden: "
                "%s -> %s"
            ),
            update.current_version,
            update.version,
        )

        self._show_update(
            update
        )

    def _on_check_failed(
        self,
        message: str,
    ) -> None:
        manual = (
            self._manual_check
        )

        self._check_worker = (
            None
        )

        logger.warning(
            (
                "Update-Prüfung "
                "fehlgeschlagen: %s"
            ),
            message,
        )

        if manual:
            QMessageBox.warning(
                self.parent_window,
                tr(
                    "updates.check.failed_title"
                ),
                tr(
                    "updates.check.failed",
                    error=message,
                ),
            )

    # ========================================================
    # Dialog
    # ========================================================

    def _show_update(
        self,
        update: UpdateInfo,
    ) -> None:
        asset: (
            ReleaseAsset
            | None
        ) = None

        install_supported = False

        # ====================================================
        # Windows
        # ====================================================

        if is_windows():
            asset = (
                update
                .find_windows_asset()
            )

            install_supported = (
                asset is not None
                and asset.sha256
                is not None
            )

        self._current_update = (
            update
        )

        self._current_asset = (
            asset
        )

        dialog = UpdateDialog(
            update=update,
            install_supported=(
                install_supported
            ),
            parent=(
                self.parent_window
            ),
        )

        self._dialog = dialog

        dialog.install_requested.connect(
            self._start_download
        )

        dialog.finished.connect(
            self._on_dialog_finished
        )

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_dialog_finished(
        self,
        _result: int,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            return

        self._dialog = None

        self._current_update = None

        self._current_asset = None

    # ========================================================
    # Download
    # ========================================================

    def _start_download(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            return

        dialog = (
            self._dialog
        )

        asset = (
            self._current_asset
        )

        if (
            dialog is None
            or asset is None
        ):
            return

        if asset.sha256 is None:
            dialog.show_error(
                tr(
                    "updates.error.no_digest"
                )
            )

            return

        worker = (
            UpdateDownloadWorker(
                asset=asset
            )
        )

        self._download_worker = (
            worker
        )

        worker.signals.progress.connect(
            dialog.update_progress
        )

        worker.signals.finished.connect(
            self._on_download_finished
        )

        worker.signals.failed.connect(
            self._on_download_failed
        )

        worker.signals.cancelled.connect(
            self._on_download_cancelled
        )

        dialog.start_download()

        self.thread_pool.start(
            worker
        )

    # ========================================================
    # Download abgeschlossen
    # ========================================================

    def _on_download_finished(
        self,
        downloaded_file: object,
    ) -> None:
        self._download_worker = (
            None
        )

        dialog = (
            self._dialog
        )

        if dialog is None:
            return

        if not isinstance(
            downloaded_file,
            Path,
        ):
            dialog.show_error(
                tr(
                    "updates.error.invalid_download"
                )
            )

            return

        # ====================================================
        # Windows
        # ====================================================

        if not is_windows():
            dialog.show_error(
                tr(
                    "updates.error.unsupported_platform"
                )
            )

            return

        dialog.show_installing()

        try:
            stage_windows_update(
                archive_path=(
                    downloaded_file
                )
            )

        except Exception as error:
            logger.exception(
                (
                    "Windows-Update konnte "
                    "nicht vorbereitet werden."
                )
            )

            dialog.show_error(
                str(
                    error
                )
            )

            return

        # ====================================================
        # Hauptanwendung beenden.
        #
        # Der PowerShell-Helper wartet auf genau diesen
        # Prozess und tauscht danach die Dateien aus.
        # ====================================================

        application = (
            QApplication.instance()
        )

        if application is not None:
            QTimer.singleShot(
                250,
                application.quit,
            )

    # ========================================================
    # Download Fehler
    # ========================================================

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self._download_worker = (
            None
        )

        logger.warning(
            (
                "Update Download "
                "fehlgeschlagen: %s"
            ),
            message,
        )

        if (
            self._dialog
            is not None
        ):
            self._dialog.show_error(
                message
            )

    def _on_download_cancelled(
        self,
    ) -> None:
        self._download_worker = (
            None
        )

        if (
            self._dialog
            is not None
        ):
            self._dialog.show_error(
                tr(
                    "updates.status.cancelled"
                )
            )

    # ========================================================
    # Shutdown
    # ========================================================

    def shutdown(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            self._download_worker.cancel()


__all__ = [
    "UpdateController",
]