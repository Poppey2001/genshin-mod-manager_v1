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

from app.config import CACHE_DIR
from app.i18n import tr

from app.services.update_service import (
    ReleaseAsset,
    UpdateChannel,
    UpdateService,
)


class UpdateCheckSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class UpdateCheckWorker(QRunnable):
    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        current_version: str,
        channel: UpdateChannel,
    ) -> None:
        super().__init__()

        self.signals = (
            UpdateCheckSignals()
        )

        self.owner = owner
        self.repository = repository

        self.current_version = (
            current_version
        )

        self.channel = channel

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            service = UpdateService(
                owner=self.owner,
                repository=(
                    self.repository
                ),
                current_version=(
                    self.current_version
                ),
                channel=self.channel,
            )

            update = (
                service.check_for_update()
            )

        except Exception as error:
            self.signals.failed.emit(
                str(
                    error
                )
            )

            return

        self.signals.finished.emit(
            update
        )


class UpdateDownloadSignals(QObject):
    progress = Signal(
        int,
        int,
    )

    finished = Signal(object)

    failed = Signal(str)

    cancelled = Signal()


class UpdateDownloadWorker(QRunnable):
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
            self._cancel_event.is_set()
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
                str(
                    error
                )
            )

            return

        if self.is_cancelled():
            try:
                result.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            self.signals.cancelled.emit()
            return

        self.signals.finished.emit(
            result
        )

    def _download(
        self,
    ) -> Path:
        digest = self.asset.digest

        if not digest:
            raise RuntimeError(
                tr(
                    "updates.error.no_digest"
                )
            )

        algorithm, separator, expected_hash = (
            digest.partition(":")
        )

        if (
            separator != ":"
            or algorithm.casefold()
            != "sha256"
            or not expected_hash
        ):
            raise RuntimeError(
                tr(
                    "updates.error.download.unsupported_digest"
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

        partial_file = (
            destination.with_suffix(
                destination.suffix
                + ".part"
            )
        )

        partial_file.unlink(
            missing_ok=True
        )

        request = Request(
            self.asset.download_url,
            headers={
                "User-Agent": (
                    "Genshin-Mod-Manager-Updater"
                ),
            },
        )

        hasher = hashlib.sha256()

        received = 0

        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:
                content_length = (
                    response.headers.get(
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

                with partial_file.open(
                    "wb"
                ) as output:
                    while True:
                        if self.is_cancelled():
                            raise RuntimeError(
                                tr(
                                    "updates.error.download.cancelled"
                                )
                            )

                        chunk = response.read(
                            1024 * 1024
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

        except HTTPError as error:
            partial_file.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                tr(
                    "updates.error.download.http",
                    code=error.code,
                )
            ) from error

        except URLError as error:
            partial_file.unlink(
                missing_ok=True
            )

            reason = getattr(
                error,
                "reason",
                error,
            )

            raise RuntimeError(
                tr(
                    "updates.error.download.network",
                    reason=reason,
                )
            ) from error

        except TimeoutError as error:
            partial_file.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                tr(
                    "updates.error.download.timeout"
                )
            ) from error

        actual_hash = (
            hasher.hexdigest()
        )

        if not hmac.compare_digest(
            actual_hash.casefold(),
            expected_hash.casefold(),
        ):
            partial_file.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                tr(
                    "updates.error.download.hash_mismatch"
                )
            )

        partial_file.replace(
            destination
        )

        destination.chmod(
            destination.stat().st_mode
            | 0o111
        )

        return destination