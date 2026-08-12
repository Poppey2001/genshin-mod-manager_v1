from __future__ import annotations

import hashlib
import re

from dataclasses import dataclass

from pathlib import Path

from collections.abc import (
    Callable,
)

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    urlparse,
)

from urllib.request import (
    Request,
    urlopen,
)

from app.gamebanana.models import (
    GameBananaFile,
)


ProgressCallback = Callable[
    [
        int,
        int,
    ],
    None,
]

CancelCallback = Callable[
    [],
    bool,
]


class GameBananaDownloadError(
    RuntimeError
):
    """GameBanana-Datei konnte nicht geladen werden."""


class GameBananaDownloadCancelled(
    GameBananaDownloadError
):
    """Download wurde abgebrochen."""


@dataclass(
    frozen=True,
    slots=True,
)
class GameBananaDownloadResult:
    file: GameBananaFile

    path: Path

    bytes_written: int

    sha256: str


class GameBananaDownloader:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        chunk_size: int = (
            1024
            * 1024
        ),
        max_download_bytes: (
            int
            | None
        ) = (
            8
            * 1024
            * 1024
            * 1024
        ),
    ) -> None:
        self.timeout = timeout
        self.chunk_size = chunk_size

        self.max_download_bytes = (
            max_download_bytes
        )

    def download(
        self,
        *,
        file: GameBananaFile,
        destination_directory: Path,
        progress_callback: (
            ProgressCallback
            | None
        ) = None,
        cancel_callback: (
            CancelCallback
            | None
        ) = None,
        overwrite: bool = True,
    ) -> GameBananaDownloadResult:
        self._validate_download_url(
            file.download_url
        )

        destination_directory = (
            Path(
                destination_directory
            )
            .expanduser()
            .absolute()
        )

        try:
            destination_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as error:
            raise GameBananaDownloadError(
                (
                    "Das Download-Verzeichnis konnte "
                    "nicht erstellt werden.\n\n"
                    f"{error}"
                )
            ) from error

        safe_name = (
            self._safe_filename(
                file.name,
                file.id,
            )
        )

        destination = (
            destination_directory
            / safe_name
        )

        temporary_file = (
            destination.with_name(
                f"{destination.name}.part"
            )
        )

        if (
            destination.exists()
            and not overwrite
        ):
            raise GameBananaDownloadError(
                (
                    "Die Download-Datei existiert bereits:\n"
                    f"{destination}"
                )
            )

        self._remove_file(
            temporary_file
        )

        request = Request(
            file.download_url,
            headers={
                "User-Agent": (
                    "XXMI-Mod-Manager/0.4"
                ),
                "Accept": (
                    "application/octet-stream,*/*"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                total_bytes = (
                    self._content_length(
                        response
                    )
                )

                if (
                    total_bytes <= 0
                    and file.size
                    is not None
                ):
                    total_bytes = (
                        file.size
                    )

                self._check_max_size(
                    total_bytes
                )

                sha256 = hashlib.sha256()

                bytes_written = 0

                with temporary_file.open(
                    "wb"
                ) as output_file:
                    while True:
                        if (
                            cancel_callback
                            is not None
                            and cancel_callback()
                        ):
                            raise (
                                GameBananaDownloadCancelled(
                                    "Download wurde abgebrochen."
                                )
                            )

                        chunk = response.read(
                            self.chunk_size
                        )

                        if not chunk:
                            break

                        bytes_written += (
                            len(chunk)
                        )

                        self._check_max_size(
                            bytes_written
                        )

                        output_file.write(
                            chunk
                        )

                        sha256.update(
                            chunk
                        )

                        if (
                            progress_callback
                            is not None
                        ):
                            progress_callback(
                                bytes_written,
                                total_bytes,
                            )

                if (
                    total_bytes > 0
                    and bytes_written
                    != total_bytes
                ):
                    raise GameBananaDownloadError(
                        (
                            "Der Download ist unvollständig.\n\n"
                            f"Erwartet: {total_bytes} Bytes\n"
                            f"Empfangen: {bytes_written} Bytes"
                        )
                    )

                if destination.exists():
                    destination.unlink()

                temporary_file.replace(
                    destination
                )

                return (
                    GameBananaDownloadResult(
                        file=file,
                        path=destination,
                        bytes_written=(
                            bytes_written
                        ),
                        sha256=(
                            sha256.hexdigest()
                        ),
                    )
                )

        except GameBananaDownloadCancelled:
            self._remove_file(
                temporary_file
            )

            raise

        except HTTPError as error:
            self._remove_file(
                temporary_file
            )

            raise GameBananaDownloadError(
                (
                    "GameBanana-Download fehlgeschlagen: "
                    f"HTTP {error.code}"
                )
            ) from error

        except URLError as error:
            self._remove_file(
                temporary_file
            )

            raise GameBananaDownloadError(
                (
                    "GameBanana-Download fehlgeschlagen.\n\n"
                    f"{error}"
                )
            ) from error

        except TimeoutError as error:
            self._remove_file(
                temporary_file
            )

            raise GameBananaDownloadError(
                "Der GameBanana-Download hat zu lange gedauert."
            ) from error

        except OSError as error:
            self._remove_file(
                temporary_file
            )

            raise GameBananaDownloadError(
                (
                    "Die heruntergeladene Datei konnte "
                    "nicht gespeichert werden.\n\n"
                    f"{error}"
                )
            ) from error

        except GameBananaDownloadError:
            self._remove_file(
                temporary_file
            )

            raise

    def _check_max_size(
        self,
        size: int,
    ) -> None:
        if (
            self.max_download_bytes
            is None
        ):
            return

        if size <= 0:
            return

        if (
            size
            > self.max_download_bytes
        ):
            raise GameBananaDownloadError(
                (
                    "Die Datei überschreitet das "
                    "konfigurierte Download-Limit."
                )
            )

    @staticmethod
    def _validate_download_url(
        url: str,
    ) -> None:
        parsed = urlparse(
            url
        )

        if (
            parsed.scheme.casefold()
            not in {
                "http",
                "https",
            }
        ):
            raise GameBananaDownloadError(
                "Die Download-URL verwendet kein HTTP oder HTTPS."
            )

        if not parsed.hostname:
            raise GameBananaDownloadError(
                "Die Download-URL besitzt keinen gültigen Host."
            )

    @staticmethod
    def _safe_filename(
        filename: str,
        file_id: int | None,
    ) -> str:
        filename = (
            Path(filename)
            .name
            .strip()
        )

        filename = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]',
            "_",
            filename,
        )

        filename = (
            filename
            .rstrip(
                ". "
            )
        )

        if not filename:
            filename = (
                "gamebanana-file"
                f"-{file_id or 'download'}"
            )

        return filename

    @staticmethod
    def _content_length(
        response,
    ) -> int:
        value = (
            response.headers.get(
                "Content-Length"
            )
        )

        if not value:
            return 0

        try:
            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _remove_file(
        path: Path,
    ) -> None:
        try:
            path.unlink(
                missing_ok=True
            )

        except OSError:
            pass