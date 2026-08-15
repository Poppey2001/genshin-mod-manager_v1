from __future__ import annotations

import hashlib
import hmac
import threading

from pathlib import Path

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.request import (
    Request,
    urlopen,
)

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
    ReleaseAsset,
    UpdateChannel,
    UpdateService,
)

from app.update_config import (
    UPDATE_DOWNLOAD_TIMEOUT,
)


# ============================================================
# Check
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


class UpdateCheckWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        current_version: str,
        channel: UpdateChannel,
    ) -> None:
        super().__init__()

        self.owner = owner

        self.repository = (
            repository
        )

        self.current_version = (
            current_version
        )

        self.channel = channel

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
                UpdateService(
                    owner=self.owner,
                    repository=(
                        self.repository
                    ),
                    current_version=(
                        self.current_version
                    ),
                    channel=(
                        self.channel
                    ),
                )
            )

            result = (
                service
                .check_for_update()
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
            result
        )


# ============================================================
# Download
# ============================================================

class UpdateDownloadSignals(
    QObject
):
    progress = Signal(
        int,
        int,
    )

    finished = Signal(
        object
    )

    failed = Signal(
        str
    )

    cancelled = Signal()


class UpdateDownloadWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        asset: ReleaseAsset,
    ) -> None:
        super().__init__()

        self.asset = asset

        self.signals = (
            UpdateDownloadSignals()
        )

        self._cancel_event = (
            threading.Event()
        )

        self.setAutoDelete(
            True
        )

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

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            result = (
                self._download()
            )

        except Exception as error:
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
            result.unlink(
                missing_ok=True
            )

            self.signals.cancelled.emit()

            return

        self.signals.finished.emit(
            result
        )

    def _download(
        self,
    ) -> Path:
        expected_hash = (
            self.asset.sha256
        )

        if not expected_hash:
            raise RuntimeError(
                (
                    "Das GitHub Release "
                    "besitzt keinen gültigen "
                    "SHA-256-Digest."
                )
            )

        update_directory = (
            CACHE_DIR
            / "updates"
        )

        update_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            update_directory
            / self.asset.name
        )

        partial = (
            destination.with_name(
                destination.name
                + ".part"
            )
        )

        partial.unlink(
            missing_ok=True
        )

        request = Request(
            self.asset.download_url,
            headers={
                "User-Agent": (
                    "XXMI-Mod-Manager-Updater"
                ),
            },
        )

        hasher = (
            hashlib.sha256()
        )

        received = 0

        try:
            with urlopen(
                request,
                timeout=(
                    UPDATE_DOWNLOAD_TIMEOUT
                ),
            ) as response:
                content_length = (
                    response.headers
                    .get(
                        "Content-Length"
                    )
                )

                try:
                    total = int(
                        content_length
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    total = (
                        self.asset.size
                        if self.asset.size > 0
                        else 0
                    )

                with partial.open(
                    "wb"
                ) as output:
                    while True:
                        if self.is_cancelled():
                            raise RuntimeError(
                                "Download abgebrochen."
                            )

                        chunk = response.read(
                            1024
                            * 1024
                        )

                        if not chunk:
                            break

                        output.write(
                            chunk
                        )

                        hasher.update(
                            chunk
                        )

                        received += len(
                            chunk
                        )

                        self.signals.progress.emit(
                            received,
                            total,
                        )

        except (
            HTTPError,
            URLError,
            TimeoutError,
        ):
            partial.unlink(
                missing_ok=True
            )

            raise

        actual_hash = (
            hasher
            .hexdigest()
            .casefold()
        )

        if not hmac.compare_digest(
            actual_hash,
            expected_hash,
        ):
            partial.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                (
                    "SHA-256-Prüfung "
                    "des Updates ist "
                    "fehlgeschlagen."
                )
            )

        partial.replace(
            destination
        )

        destination.chmod(
            destination.stat().st_mode
            | 0o111
        )

        return destination


__all__ = [
    "UpdateCheckWorker",
    "UpdateDownloadWorker",
]