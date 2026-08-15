from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.services.mod_duplicate_service import (
    ModDuplicateService,
)


class ModDuplicateWorkerSignals(
    QObject
):
    progress = Signal(
        str,
        int,
        int,
        str,
    )

    finished = Signal(
        object,
        object,
    )

    failed = Signal(
        object,
        str,
        str,
    )


class ModDuplicateWorker(
    QRunnable
):
    def __init__(
        self,
        *,
        source: Path,
        library_paths: tuple[
            Path,
            ...,
        ],
        game_id: str,
        service: ModDuplicateService,
    ) -> None:
        super().__init__()

        self.source = (
            Path(
                source
            )
        )

        self.library_paths = (
            library_paths
        )

        self.game_id = (
            game_id
        )

        self.service = service

        self.source_key = str(
            self.source
            .expanduser()
            .absolute()
        )

        self.signals = (
            ModDuplicateWorkerSignals()
        )

        self.setAutoDelete(
            True
        )

    @Slot()
    def run(
        self,
    ) -> None:
        try:
            result = (
                self.service
                .find_duplicate(
                    source=(
                        self.source
                    ),
                    library_paths=(
                        self.library_paths
                    ),
                    game_id=(
                        self.game_id
                    ),
                    progress_callback=(
                        self._progress
                    ),
                )
            )

        except Exception as error:
            self.signals.failed.emit(
                self,
                self.source_key,
                (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            )

            return

        self.signals.finished.emit(
            self,
            result,
        )

    def _progress(
        self,
        current: int,
        total: int,
        name: str,
    ) -> None:
        self.signals.progress.emit(
            self.source_key,
            current,
            total,
            name,
        )


__all__ = [
    "ModDuplicateWorker",
]