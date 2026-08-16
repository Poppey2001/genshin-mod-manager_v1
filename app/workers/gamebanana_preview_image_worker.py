from __future__ import annotations

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import (
    urlsplit,
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


class GameBananaPreviewImageSignals(
    QObject
):
    loaded = Signal(
        str,
        object,
        int,
    )

    failed = Signal(
        str,
        str,
        int,
    )


class GameBananaPreviewImageWorker(
    QRunnable
):
    """
    Lädt genau ein Preview-Bild außerhalb des UI-Threads.

    Jede URL wird VOR urllib.Request validiert. Selbst wenn ein
    API-Parser später einmal fehlerhafte Daten durchreichen sollte,
    darf ein ungültiger Preview-Wert niemals aus QRunnable.run()
    herausfallen und den globalen Crash-Handler auslösen.
    """

    MAX_IMAGE_BYTES = (
        32
        * 1024
        * 1024
    )

    def __init__(
        self,
        *,
        url: str,
        generation: int,
        timeout: float = 20.0,
    ) -> None:
        super().__init__()

        self.url = str(url).strip()
        self.generation = int(generation)
        self.timeout = float(timeout)

        self.signals = (
            GameBananaPreviewImageSignals()
        )

        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            validated_url = self._validated_url(
                self.url
            )

            request = Request(
                validated_url,
                headers={
                    "Accept": "image/*,*/*;q=0.8",
                    "User-Agent": (
                        "XXMI-Mod-Manager/0.4"
                    ),
                },
            )

            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                content_length = (
                    response.headers.get(
                        "Content-Length"
                    )
                )

                if content_length:
                    try:
                        declared_size = int(
                            content_length
                        )
                    except ValueError:
                        declared_size = 0

                    if (
                        declared_size
                        > self.MAX_IMAGE_BYTES
                    ):
                        raise ValueError(
                            "image_too_large"
                        )

                data = response.read(
                    self.MAX_IMAGE_BYTES + 1
                )

                if len(data) > self.MAX_IMAGE_BYTES:
                    raise ValueError(
                        "image_too_large"
                    )

                if not data:
                    raise ValueError(
                        "empty_image"
                    )

        except HTTPError as error:
            message = f"HTTP {error.code}"

        except URLError as error:
            message = str(error)

        except TimeoutError:
            message = "timeout"

        except ValueError as error:
            message = str(error)

        except Exception as error:
            # Letzte Sicherheitsbarriere: kein Preview-Fehler darf
            # ungefangen aus dem QRunnable herauslaufen.
            message = (
                f"{type(error).__name__}: "
                f"{error}"
            )

        else:
            self.signals.loaded.emit(
                self.url,
                data,
                self.generation,
            )
            return

        self.signals.failed.emit(
            self.url,
            message,
            self.generation,
        )

    @staticmethod
    def _validated_url(
        value: str,
    ) -> str:
        text = str(value).strip()

        if not text:
            raise ValueError(
                "invalid_preview_url"
            )

        if text[0] in "{[\"'":
            raise ValueError(
                "invalid_preview_url"
            )

        try:
            parsed = urlsplit(text)
        except ValueError as error:
            raise ValueError(
                "invalid_preview_url"
            ) from error

        if parsed.scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                "invalid_preview_url"
            )

        if not parsed.netloc:
            raise ValueError(
                "invalid_preview_url"
            )

        try:
            hostname = parsed.hostname
        except ValueError as error:
            raise ValueError(
                "invalid_preview_url"
            ) from error

        if not hostname:
            raise ValueError(
                "invalid_preview_url"
            )

        return text


__all__ = [
    "GameBananaPreviewImageWorker",
]
