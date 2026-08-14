from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.gamebanana.client import (
    GameBananaClient,
)

from app.games import (
    get_game,
)

from app.services.library_preview_service import (
    LibraryPreviewResult,
    find_local_preview_images,
)

from app.services.mod_metadata import (
    load_mod_metadata,
)


class LibraryPreviewSignals(
    QObject
):
    finished = Signal(
        object,
        object,
    )

    failed = Signal(
        object,
        str,
    )


class LibraryPreviewWorker(
    QRunnable
):
    """
    Priorität:

    1. lokale Preview
    2. GameBanana über gespeicherte ID
    3. keine Preview
    """

    def __init__(
        self,
        *,
        mod_path,
    ) -> None:
        super().__init__()

        self.mod_path = mod_path

        self.signals = (
            LibraryPreviewSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            metadata = (
                load_mod_metadata(
                    self.mod_path
                )
            )

            local_images = (
                find_local_preview_images(
                    self.mod_path,
                    configured_preview=(
                        metadata.preview_file
                    ),
                )
            )

            # ------------------------------------------------
            # Lokal gewinnt immer.
            # ------------------------------------------------

            if local_images:
                result = (
                    LibraryPreviewResult(
                        local_images=(
                            local_images
                        ),
                        gamebanana_mod_id=(
                            metadata
                            .gamebanana_mod_id
                        ),
                    )
                )

                self.signals.finished.emit(
                    self.mod_path,
                    result,
                )

                return

            # ------------------------------------------------
            # Kein GameBanana-Link vorhanden
            # ------------------------------------------------

            if (
                metadata.gamebanana_mod_id
                is None
            ):
                result = (
                    LibraryPreviewResult()
                )

                self.signals.finished.emit(
                    self.mod_path,
                    result,
                )

                return

            expected_game = None

            if metadata.game_id:
                try:
                    expected_game = get_game(
                        metadata.game_id
                    )

                except (
                    KeyError,
                    ValueError,
                ):
                    expected_game = None

            client = (
                GameBananaClient()
            )

            mod = client.fetch_mod(
                metadata.gamebanana_mod_id,
                expected_game=(
                    expected_game
                ),
            )

            remote_images = list(
                getattr(
                    mod,
                    "image_urls",
                    (),
                )
            )

            if (
                not remote_images
                and mod.preview_url
            ):
                remote_images.append(
                    mod.preview_url
                )

            result = (
                LibraryPreviewResult(
                    remote_images=tuple(
                        remote_images
                    ),
                    gamebanana_mod_id=(
                        metadata
                        .gamebanana_mod_id
                    ),
                )
            )

        except Exception as error:
            self.signals.failed.emit(
                self.mod_path,
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            )

            return

        self.signals.finished.emit(
            self.mod_path,
            result,
        )


__all__ = [
    "LibraryPreviewWorker",
]