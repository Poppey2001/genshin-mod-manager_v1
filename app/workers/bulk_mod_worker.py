from __future__ import annotations

import threading
import time

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.models.mod import ModInfo
from app.services.mod_manager import (
    ModManager,
    ModManagerError,
    ModState,
)


class BulkAction(str, Enum):
    """Verfügbare Sammelaktionen."""

    ENABLE = "enable"
    DISABLE = "disable"
    ADOPT = "adopt"


class BulkItemStatus(str, Enum):
    """Ergebnis einer einzelnen Mod-Aktion."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    CONFLICT = "conflict"
    FAILED = "failed"


@dataclass(slots=True, frozen=True)
class BulkItemResult:
    """Ergebnis für einen einzelnen Mod."""

    mod_name: str
    mod_path: Path
    status: BulkItemStatus
    message: str


@dataclass(slots=True, frozen=True)
class BulkBatchResult:
    """Gesamtergebnis einer Sammelaktion."""

    action: BulkAction
    items: tuple[BulkItemResult, ...]
    cancelled: bool
    duration_seconds: float

    @property
    def success_count(self) -> int:
        return sum(
            item.status == BulkItemStatus.SUCCESS
            for item in self.items
        )

    @property
    def skipped_count(self) -> int:
        return sum(
            item.status == BulkItemStatus.SKIPPED
            for item in self.items
        )

    @property
    def conflict_count(self) -> int:
        return sum(
            item.status == BulkItemStatus.CONFLICT
            for item in self.items
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status == BulkItemStatus.FAILED
            for item in self.items
        )


class BulkModWorkerSignals(QObject):
    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(object)
    failed = Signal(str)


class BulkModWorker(QRunnable):
    """
    Führt Aktivieren, Deaktivieren und Übernehmen
    außerhalb des UI-Threads aus.
    """

    def __init__(
        self,
        mods: list[ModInfo],
        action: BulkAction,
        mod_manager: ModManager,
    ) -> None:
        super().__init__()

        self.mods = list(mods)
        self.action = action
        self.mod_manager = mod_manager

        self.signals = BulkModWorkerSignals()

        self._cancel_event = threading.Event()

        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        started_at = time.monotonic()

        results: list[BulkItemResult] = []
        total = len(self.mods)
        cancelled = False

        try:
            for index, mod in enumerate(
                self.mods,
                start=1,
            ):
                if self.is_cancelled():
                    cancelled = True
                    break

                self.signals.progress.emit(
                    index - 1,
                    total,
                    mod.name,
                )

                result = self._process_mod(
                    mod
                )

                results.append(result)

                self.signals.progress.emit(
                    index,
                    total,
                    mod.name,
                )

            if self.is_cancelled():
                cancelled = True

            batch_result = BulkBatchResult(
                action=self.action,
                items=tuple(results),
                cancelled=cancelled,
                duration_seconds=(
                    time.monotonic() - started_at
                ),
            )

            self.signals.finished.emit(
                batch_result
            )

        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: {error}"
            )

    def _process_mod(
        self,
        mod: ModInfo,
    ) -> BulkItemResult:
        try:
            state = self.mod_manager.get_state(
                mod.path
            )

            if self.action == BulkAction.ENABLE:
                return self._enable_mod(
                    mod=mod,
                    state=state,
                )

            if self.action == BulkAction.DISABLE:
                return self._disable_mod(
                    mod=mod,
                    state=state,
                )

            if self.action == BulkAction.ADOPT:
                return self._adopt_mod(
                    mod=mod,
                    state=state,
                )

            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message="Unbekannte Sammelaktion.",
            )

        except ModManagerError as error:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=str(error),
            )

        except OSError as error:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=f"Dateisystemfehler: {error}",
            )

        except Exception as error:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=(
                    f"{type(error).__name__}: {error}"
                ),
            )

    def _enable_mod(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> BulkItemResult:
        if state == ModState.ENABLED:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.SKIPPED,
                message="Der Mod ist bereits aktiviert.",
            )

        if state == ModState.CONFLICT:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.CONFLICT,
                message=(
                    "Der vorhandene Zielordner wird noch nicht "
                    "vom Manager verwaltet."
                ),
            )

        if state == ModState.NOT_CONFIGURED:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=(
                    "Der aktive Mods-Ordner ist nicht konfiguriert."
                ),
            )

        if state == ModState.BROKEN:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=(
                    "Der Mod besitzt einen defekten verwalteten Pfad."
                ),
            )

        self.mod_manager.enable(
            mod.path
        )

        return BulkItemResult(
            mod_name=mod.name,
            mod_path=mod.path,
            status=BulkItemStatus.SUCCESS,
            message="Mod wurde aktiviert.",
        )

    def _disable_mod(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> BulkItemResult:
        if state == ModState.DISABLED:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.SKIPPED,
                message="Der Mod ist bereits deaktiviert.",
            )

        if state == ModState.CONFLICT:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.CONFLICT,
                message=(
                    "Der vorhandene Zielordner wird noch nicht "
                    "vom Manager verwaltet."
                ),
            )

        if state == ModState.NOT_CONFIGURED:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=(
                    "Der aktive Mods-Ordner ist nicht konfiguriert."
                ),
            )

        if state == ModState.BROKEN:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.FAILED,
                message=(
                    "Der Mod besitzt einen defekten verwalteten Pfad."
                ),
            )

        self.mod_manager.disable(
            mod.path
        )

        return BulkItemResult(
            mod_name=mod.name,
            mod_path=mod.path,
            status=BulkItemStatus.SUCCESS,
            message="Mod wurde deaktiviert.",
        )

    def _adopt_mod(
        self,
        mod: ModInfo,
        state: ModState,
    ) -> BulkItemResult:
        if state != ModState.CONFLICT:
            return BulkItemResult(
                mod_name=mod.name,
                mod_path=mod.path,
                status=BulkItemStatus.SKIPPED,
                message=(
                    "Der Mod besitzt keinen übernehmbaren Konflikt."
                ),
            )

        resulting_state = (
            self.mod_manager.adopt_existing(
                mod.path
            )
        )

        if resulting_state == ModState.ENABLED:
            state_text = "aktivierter"
        else:
            state_text = "deaktivierter"

        return BulkItemResult(
            mod_name=mod.name,
            mod_path=mod.path,
            status=BulkItemStatus.SUCCESS,
            message=(
                f"Mod wurde als vorhandener {state_text} "
                "Mod übernommen."
            ),
        )