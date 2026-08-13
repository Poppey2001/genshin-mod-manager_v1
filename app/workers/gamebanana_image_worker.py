from __future__ import annotations

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

from app.services.gamebanana_image_cache import (
    GameBananaImageCache,
)


MAX_PREVIEW_SIZE = (
    16
    * 1024
    * 1024
)

CHUNK_SIZE = (
    256
    * 1024
)


class GameBananaImageSignals(
    QObject
):
    finished = Signal(
        str,
        object,
    )

    failed = Signal(
        str,
        str,
    )


class GameBananaImageWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        url: str,
    ) -> None:
        super().__init__()

        self.url = (
            url.strip()
        )

        self.signals = (
            GameBananaImageSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        cache = (
            GameBananaImageCache()
        )

        # ====================================================
        # Disk Cache
        # ====================================================

        cached_data = cache.read(
            self.url
        )

        if cached_data is not None:
            self.signals.finished.emit(
                self.url,
                cached_data,
            )

            return

        # ====================================================
        # Download
        # ====================================================

        request = Request(
            self.url,
            headers={
                "Accept": (
                    "image/avif,"
                    "image/webp,"
                    "image/png,"
                    "image/jpeg,"
                    "image/*"
                ),
                "User-Agent": (
                    "XXMI-Mod-Manager/0.5"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=20.0,
            ) as response:
                content_type = (
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                    .casefold()
                )

                if (
                    content_type
                    and "image/"
                    not in content_type
                ):
                    raise RuntimeError(
                        (
                            "Die URL hat keine "
                            "Bilddatei geliefert."
                        )
                    )

                content_length = (
                    response.headers.get(
                        "Content-Length"
                    )
                )

                if content_length:
                    try:
                        expected_size = int(
                            content_length
                        )

                    except ValueError:
                        expected_size = 0

                    if (
                        expected_size
                        > MAX_PREVIEW_SIZE
                    ):
                        raise RuntimeError(
                            (
                                "Das Vorschaubild "
                                "ist zu groß."
                            )
                        )

                data = bytearray()

                while True:
                    chunk = response.read(
                        CHUNK_SIZE
                    )

                    if not chunk:
                        break

                    data.extend(
                        chunk
                    )

                    if (
                        len(
                            data
                        )
                        > MAX_PREVIEW_SIZE
                    ):
                        raise RuntimeError(
                            (
                                "Das Vorschaubild "
                                "überschreitet das "
                                "Größenlimit."
                            )
                        )

        except HTTPError as error:
            self.signals.failed.emit(
                self.url,
                f"HTTP {error.code}",
            )

            return

        except URLError as error:
            self.signals.failed.emit(
                self.url,
                str(
                    error
                ),
            )

            return

        except Exception as error:
            self.signals.failed.emit(
                self.url,
                str(
                    error
                ),
            )

            return

        image_data = bytes(
            data
        )

        if not image_data:
            self.signals.failed.emit(
                self.url,
                "Leeres Bild erhalten.",
            )

            return

        cache.write(
            self.url,
            image_data,
        )

        self.signals.finished.emit(
            self.url,
            image_data,
        )


__all__ = [
    "GameBananaImageWorker",
]