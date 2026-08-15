from __future__ import annotations

import logging

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

from app.services.update_service import (
    UpdateInfo,
    StagedUpdate,
)

from app.services.windows_script_updater import (
    cleanup_successful_update_cache,
    external_scripts_available,
    is_windows,
    launch_script_update_helper,
)

from app.update_config import (
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

        self._manual_check = False

    # ========================================================
    # Startup
    # ========================================================

    def start_auto_check(
        self,
    ) -> None:
        # ----------------------------------------------------
        # Alten erfolgreichen Update-Cache löschen.
        # Etwas verzögert, damit der PowerShell Helper
        # sicher beendet ist.
        # ----------------------------------------------------

        QTimer.singleShot(
            3000,
            cleanup_successful_update_cache,
        )

        # ----------------------------------------------------
        # Auto Update nur Windows
        # ----------------------------------------------------

        if not is_windows():
            return

        if not getattr(
            self.config,
            "auto_check_updates",
            True,
        ):
            return

        QTimer.singleShot(
            5000,
            self._run_auto_check,
        )

    def _run_auto_check(
        self,
    ) -> None:
        self.check_for_updates(
            manual=False
        )

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
        if (
            self._check_worker
            is not None
        ):
            return

        if not (
            github_repository_configured()
        ):
            if manual:
                QMessageBox.warning(
                    self.parent_window,
                    tr(
                        "updates.check.title"
                    ),
                    tr(
                        "updates.error.repo_not_configured"
                    ),
                )

            return

        channel = getattr(
            self.config,
            "update_channel",
            "prerelease",
        )

        allow_prerelease = (
            channel
            != "stable"
        )

        self._manual_check = (
            manual
        )

        worker = (
            UpdateCheckWorker(
                allow_prerelease=(
                    allow_prerelease
                )
            )
        )

        self._check_worker = worker

        worker.signals.finished.connect(
            self._on_check_finished
        )

        worker.signals.failed.connect(
            self._on_check_failed
        )

        self.thread_pool.start(
            worker
        )

    # ========================================================
    # Check Result
    # ========================================================

    def _on_check_finished(
        self,
        result: object,
    ) -> None:
        manual = (
            self._manual_check
        )

        self._check_worker = None

        if result is None:
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
            result,
            UpdateInfo,
        ):
            return

        self._current_update = (
            result
        )

        install_supported = (
            is_windows()
            and external_scripts_available()
        )

        dialog = (
            UpdateDialog(
                update=result,
                install_supported=(
                    install_supported
                ),
                parent=(
                    self.parent_window
                ),
            )
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

    def _on_check_failed(
        self,
        message: str,
    ) -> None:
        manual = (
            self._manual_check
        )

        self._check_worker = None

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

        if (
            self._current_update
            is None
            or self._dialog
            is None
        ):
            return

        worker = (
            UpdateDownloadWorker(
                info=(
                    self._current_update
                )
            )
        )

        self._download_worker = worker

        worker.signals.progress.connect(
            self._dialog
            .update_progress
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

        self._dialog.start_download()

        self.thread_pool.start(
            worker
        )

    # ========================================================
    # Download Finished
    # ========================================================

    def _on_download_finished(
        self,
        result: object,
    ) -> None:
        self._download_worker = None

        dialog = (
            self._dialog
        )

        if dialog is None:
            return

        if not isinstance(
            result,
            StagedUpdate,
        ):
            dialog.show_error(
                tr(
                    "updates.error.invalid_download"
                )
            )

            return

        dialog.show_installing()

        try:
            launch_script_update_helper(
                result
            )

        except Exception as error:
            logger.exception(
                (
                    "Windows Script Update "
                    "konnte nicht gestartet werden."
                )
            )

            dialog.show_error(
                str(
                    error
                )
            )

            return

        application = (
            QApplication.instance()
        )

        if application is not None:
            QTimer.singleShot(
                300,
                application.quit,
            )

    # ========================================================
    # Errors
    # ========================================================

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self._download_worker = None

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
        self._download_worker = None

        if (
            self._dialog
            is not None
        ):
            self._dialog.show_error(
                tr(
                    "updates.status.cancelled"
                )
            )

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