from __future__ import annotations

import logging
import sys

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

from app.config import AppConfig

from app.dialogs.update_dialog import (
    UpdateDialog,
)

from app.i18n import tr

from app.services.appimage_updater import (
    cleanup_previous_update_backup,
    is_appimage_runtime,
    stage_update_and_launch_helper,
)

from app.services.update_service import (
    ReleaseAsset,
    UpdateChannel,
    UpdateInfo,
)

from app.services.windows_installer_updater import (
    is_windows_installer_runtime,
    launch_windows_installer_update,
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
            QThreadPool.globalInstance()
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

    # ==================================================
    # Start
    # ==================================================

    def start_auto_check(
        self,
    ) -> None:
        if (
            sys.platform
            .casefold()
            .startswith(
                "linux"
            )
        ):
            QTimer.singleShot(
                30_000,
                cleanup_previous_update_backup,
            )

        if not getattr(
            self.config,
            "auto_check_updates",
            True,
        ):
            return

        QTimer.singleShot(
            3_000,
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

    # ==================================================
    # Prüfen
    # ==================================================

    def check_for_updates(
        self,
        *,
        manual: bool,
    ) -> None:
        if self._check_worker is not None:
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
            else:
                logger.warning(
                    (
                        "Auto-Update deaktiviert: "
                        "GitHub Repository nicht "
                        "konfiguriert."
                    )
                )

            return

        channel_value = getattr(
            self.config,
            "update_channel",
            "prerelease",
        )

        try:
            channel = UpdateChannel(
                channel_value
            )
        except ValueError:
            channel = (
                UpdateChannel.PRERELEASE
            )

        self._manual_check = manual

        worker = UpdateCheckWorker(
            owner=GITHUB_OWNER,
            repository=(
                GITHUB_REPOSITORY
            ),
            current_version=(
                APP_VERSION
            ),
            channel=channel,
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

    def _on_check_finished(
        self,
        update: object,
    ) -> None:
        manual = (
            self._manual_check
        )

        self._check_worker = None

        if update is None:
            if manual:
                QMessageBox.information(
                    self.parent_window,
                    tr(
                        "updates.check.title"
                    ),
                    tr(
                        "updates.check.up_to_date",
                        version=APP_VERSION,
                    ),
                )

            return

        if not isinstance(
            update,
            UpdateInfo,
        ):
            return

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

        self._check_worker = None

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
        else:
            logger.warning(
                (
                    "Automatische Update-Prüfung "
                    "fehlgeschlagen: %s"
                ),
                message,
            )

    # ==================================================
    # Plattform
    # ==================================================

    @staticmethod
    def _is_windows(
    ) -> bool:
        return (
            sys.platform
            .casefold()
            .startswith(
                "win"
            )
        )

    @staticmethod
    def _is_linux(
    ) -> bool:
        return (
            sys.platform
            .casefold()
            .startswith(
                "linux"
            )
        )

    def _asset_for_update(
        self,
        update: UpdateInfo,
    ) -> ReleaseAsset | None:
        if self._is_windows():
            return (
                update
                .find_windows_installer_asset()
            )

        if self._is_linux():
            return (
                update
                .find_appimage_asset()
            )

        return None

    def _automatic_install_supported(
        self,
        asset: ReleaseAsset | None,
    ) -> bool:
        if asset is None:
            return False

        if not asset.digest:
            return False

        if self._is_windows():
            return (
                is_windows_installer_runtime()
            )

        if self._is_linux():
            return (
                is_appimage_runtime()
            )

        return False

    # ==================================================
    # Dialog
    # ==================================================

    def _show_update(
        self,
        update: UpdateInfo,
    ) -> None:
        asset = (
            self._asset_for_update(
                update
            )
        )

        install_supported = (
            self._automatic_install_supported(
                asset
            )
        )

        self._current_update = update
        self._current_asset = asset

        dialog = UpdateDialog(
            update=update,
            install_supported=(
                install_supported
            ),
            parent=self.parent_window,
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

    # ==================================================
    # Download
    # ==================================================

    def _start_download(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            return

        asset = (
            self._current_asset
        )

        dialog = self._dialog

        if (
            asset is None
            or dialog is None
        ):
            return

        if not asset.digest:
            dialog.show_error(
                tr(
                    "updates.error.no_digest"
                )
            )

            return

        worker = UpdateDownloadWorker(
            asset=asset
        )

        self._download_worker = worker

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

    def _on_download_finished(
        self,
        downloaded_file: object,
    ) -> None:
        self._download_worker = None

        dialog = self._dialog

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

        dialog.show_installing()

        try:
            if (
                self._is_linux()
                and is_appimage_runtime()
            ):
                stage_update_and_launch_helper(
                    downloaded_file
                )

            elif (
                self._is_windows()
                and
                is_windows_installer_runtime()
            ):
                launch_windows_installer_update(
                    downloaded_file
                )

            else:
                raise RuntimeError(
                    tr(
                        "updates.error.install_unsupported"
                    )
                )

        except Exception as error:
            logger.exception(
                (
                    "Automatische Installation "
                    "konnte nicht vorbereitet werden."
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
            # Beide Updater laufen außerhalb des
            # Mod-Managers weiter:
            #
            # Linux:
            #   Shell-Helper wartet auf diesen Prozess,
            #   ersetzt das AppImage und startet es neu.
            #
            # Windows:
            #   Inno Setup wird detached gestartet.
            #   Setup darf die installierte EXE ersetzen
            #   und startet sie nach erfolgreichem
            #   Silent-Update neu.
            QTimer.singleShot(
                250,
                application.quit,
            )

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self._download_worker = None

        if self._dialog is not None:
            self._dialog.show_error(
                message
            )

    def _on_download_cancelled(
        self,
    ) -> None:
        self._download_worker = None

        if self._dialog is not None:
            self._dialog.show_error(
                tr(
                    "updates.status.cancelled"
                )
            )

    # ==================================================
    # Shutdown
    # ==================================================

    def shutdown(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
        ):
            self._download_worker.cancel()
