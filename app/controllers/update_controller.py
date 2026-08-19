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

from app.services.update_agent_client import (
    is_update_agent_installed,
    request_update_agent_check,
    sync_update_agent_settings,
)

from app.services.windows_installer_updater import (
    is_windows_installer_runtime,
    launch_windows_installer_update,
)

from app.services.windows_source_builder import (
    local_windows_build_available,
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
    WindowsSourceBuildWorker,
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

        self._source_build_worker: (
            WindowsSourceBuildWorker
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

        # Release-first / source-build fallback state.
        self._release_failure_message: (
            str
            | None
        ) = None

        self._source_fallback_started = False

    # ==================================================
    # Start
    # ==================================================

    def start_auto_check(
        self,
    ) -> None:
        if self._is_linux():
            QTimer.singleShot(
                30_000,
                cleanup_previous_update_backup,
            )

        # Installed Windows and Linux builds delegate update checks to
        # the independent GMM Update Agent. GMM itself therefore no
        # longer owns the update lifecycle or installer handover.
        if is_update_agent_installed():
            self.sync_external_agent_settings()
            return

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
        if is_update_agent_installed():
            if request_update_agent_check():
                return

            QMessageBox.warning(
                self.parent_window,
                tr("updates.check.failed_title"),
                tr(
                    "updates.check.failed",
                    error=tr(
                        "updates.error.agent_start_failed"
                    ),
                ),
            )
            return

        self.check_for_updates(
            manual=True
        )

    def sync_external_agent_settings(
        self,
    ) -> None:
        if not is_update_agent_installed():
            return

        sync_update_agent_settings(
            auto_check=bool(
                getattr(
                    self.config,
                    "auto_check_updates",
                    True,
                )
            ),
            channel=str(
                getattr(
                    self.config,
                    "update_channel",
                    "prerelease",
                )
            ),
            language=str(
                getattr(
                    self.config,
                    "language",
                    "en",
                )
            ),
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
        update: UpdateInfo,
        asset: ReleaseAsset | None,
    ) -> bool:
        if self._is_windows():
            if not (
                is_windows_installer_runtime()
            ):
                return False

            release_available = bool(
                asset is not None
                and asset.digest
            )

            source_fallback_available = bool(
                update.source_commit
                and local_windows_build_available()
            )

            return bool(
                release_available
                or source_fallback_available
            )

        if self._is_linux():
            return bool(
                asset is not None
                and asset.digest
                and is_appimage_runtime()
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
                update,
                asset,
            )
        )

        self._current_update = update
        self._current_asset = asset

        self._release_failure_message = None
        self._source_fallback_started = False

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
            or self._source_build_worker
            is not None
        ):
            return

        self._dialog = None
        self._current_update = None
        self._current_asset = None
        self._release_failure_message = None
        self._source_fallback_started = False

    # ==================================================
    # Download / fallback chain
    # ==================================================

    def _start_download(
        self,
    ) -> None:
        if (
            self._download_worker
            is not None
            or self._source_build_worker
            is not None
        ):
            return

        update = (
            self._current_update
        )

        asset = (
            self._current_asset
        )

        dialog = self._dialog

        if (
            update is None
            or dialog is None
        ):
            return

        self._release_failure_message = None
        self._source_fallback_started = False

        # --------------------------------------------------
        # Preferred path:
        # published Release / Prerelease asset
        # --------------------------------------------------

        if (
            asset is not None
            and asset.digest
        ):
            self._start_release_asset_download(
                asset
            )

            return

        # --------------------------------------------------
        # Windows fallback:
        # no usable published installer -> exact source build
        # --------------------------------------------------

        if self._is_windows():
            if asset is None:
                reason = tr(
                    "updates.error.fallback.no_release_asset"
                )
            else:
                reason = tr(
                    "updates.error.fallback.no_digest"
                )

            if self._start_windows_source_fallback(
                reason=reason
            ):
                return

            dialog.show_error(
                self._release_failure_message
                or reason
            )

            return

        # Linux currently requires a published AppImage asset.
        if asset is None:
            dialog.show_error(
                tr(
                    "updates.error.install_unsupported"
                )
            )

            return

        dialog.show_error(
            tr(
                "updates.error.no_digest"
            )
        )

    def _start_release_asset_download(
        self,
        asset: ReleaseAsset,
    ) -> None:
        dialog = self._dialog

        if dialog is None:
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

    def _can_start_windows_source_fallback(
        self,
    ) -> bool:
        update = (
            self._current_update
        )

        if update is None:
            return False

        return bool(
            self._is_windows()
            and is_windows_installer_runtime()
            and update.source_commit
            and local_windows_build_available()
            and self._source_build_worker
            is None
        )

    def _start_windows_source_fallback(
        self,
        *,
        reason: str,
    ) -> bool:
        dialog = self._dialog
        update = self._current_update

        if (
            dialog is None
            or update is None
        ):
            return False

        reason = str(
            reason
        ).strip()

        if reason:
            self._release_failure_message = (
                reason
            )

        if self._source_fallback_started:
            return False

        if not (
            self._can_start_windows_source_fallback()
        ):
            if self._release_failure_message:
                self._release_failure_message = (
                    tr(
                        "updates.error.fallback.unavailable",
                        release_error=(
                            self._release_failure_message
                        ),
                    )
                )

            return False

        self._source_fallback_started = True

        worker = WindowsSourceBuildWorker(
            owner=GITHUB_OWNER,
            repository=(
                GITHUB_REPOSITORY
            ),
            version=str(
                update.version
            ),
            source_commit=(
                update.source_commit
            ),
        )

        self._source_build_worker = worker

        worker.signals.status.connect(
            dialog.update_local_build_stage
        )

        worker.signals.progress.connect(
            dialog.update_progress
        )

        worker.signals.finished.connect(
            self._on_source_build_finished
        )

        worker.signals.failed.connect(
            self._on_source_build_failed
        )

        worker.signals.cancelled.connect(
            self._on_source_build_cancelled
        )

        dialog.start_local_build(
            fallback_reason=(
                self._release_failure_message
            )
        )

        self.thread_pool.start(
            worker
        )

        return True

    def _combined_fallback_error(
        self,
        source_error: str,
    ) -> str:
        release_error = (
            self._release_failure_message
        )

        if release_error:
            return tr(
                "updates.error.fallback.both_failed",
                release_error=release_error,
                source_error=source_error,
            )

        return source_error

    def _quit_for_windows_update(
        self,
    ) -> None:
        """
        Close the UI immediately after the detached handoff process exists.

        The helper process owns the remainder of the update. It waits for this
        PID to disappear before starting Inno Setup, so there is no installer /
        running-app deadlock.
        """

        try:
            self.parent_window.close()

        except Exception:
            logger.exception(
                "Hauptfenster konnte für Windows-Update nicht geschlossen werden."
            )

        application = (
            QApplication.instance()
        )

        if application is not None:
            application.quit()

    def _on_source_build_finished(
        self,
        installer_file: object,
    ) -> None:
        self._source_build_worker = None

        dialog = self._dialog

        if dialog is None:
            return

        if not isinstance(
            installer_file,
            Path,
        ):
            dialog.show_error(
                self._combined_fallback_error(
                    tr(
                        "updates.error.invalid_download"
                    )
                )
            )

            return

        dialog.show_installing()

        try:
            launch_windows_installer_update(
                installer_file
            )

        except Exception as error:
            logger.exception(
                (
                    "Lokaler Windows-Source-Build "
                    "konnte nicht installiert werden."
                )
            )

            dialog.show_error(
                self._combined_fallback_error(
                    str(
                        error
                    )
                )
            )

            return

        self._quit_for_windows_update()

    def _on_source_build_failed(
        self,
        message: str,
    ) -> None:
        self._source_build_worker = None

        if self._dialog is not None:
            self._dialog.show_error(
                self._combined_fallback_error(
                    message
                )
            )

    def _on_source_build_cancelled(
        self,
    ) -> None:
        self._source_build_worker = None

        if self._dialog is not None:
            self._dialog.show_error(
                tr(
                    "updates.status.cancelled"
                )
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
            reason = tr(
                "updates.error.invalid_download"
            )

            if self._is_windows() and (
                self._start_windows_source_fallback(
                    reason=reason
                )
            ):
                return

            dialog.show_error(
                reason
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
                and is_windows_installer_runtime()
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
                    "Release-Update konnte nicht "
                    "installiert werden."
                )
            )

            reason = str(
                error
            )

            if self._is_windows() and (
                self._start_windows_source_fallback(
                    reason=reason
                )
            ):
                return

            dialog.show_error(
                reason
            )

            return

        if self._is_windows():
            self._quit_for_windows_update()

        else:
            application = (
                QApplication.instance()
            )

            if application is not None:
                QTimer.singleShot(
                    250,
                    application.quit,
                )

    def _on_download_failed(
        self,
        message: str,
    ) -> None:
        self._download_worker = None

        dialog = self._dialog

        if dialog is None:
            return

        if self._is_windows() and (
            self._start_windows_source_fallback(
                reason=message
            )
        ):
            return

        dialog.show_error(
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

        if (
            self._source_build_worker
            is not None
        ):
            self._source_build_worker.cancel()
