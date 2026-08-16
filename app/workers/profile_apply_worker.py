from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from app.models.mod import ModInfo
from app.models.profile import (
    ModProfile,
    ProfileApplyItem,
    ProfileApplyResult,
    ProfileApplyStatus,
)
from app.services.mod_manager import (
    ModManager,
    ModManagerError,
    ModState,
)


class ProfileApplySignals(
    QObject
):
    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(
        object
    )

    failed = Signal(
        str
    )

    cancelled = Signal()


class ProfileApplyWorker(
    QRunnable
):
    """
    Wendet ein Profil außerhalb des UI-Threads an.

    Sicherheitsregeln:
    - Konflikte werden niemals automatisch übernommen.
    - Nicht konfigurierte Mods werden nicht verändert.
    - Mods, die seit dem Speichern aus der Library verschwunden sind,
      werden als fehlend gemeldet.
    - Neue Mods, die nicht im Profil enthalten sind, bleiben unverändert.
    """

    def __init__(
        self,
        *,
        profile: ModProfile,
        mods: tuple[ModInfo, ...],
        mod_manager: ModManager,
    ) -> None:
        super().__init__()

        self.profile = profile
        self.mods = mods
        self.mod_manager = mod_manager

        self.signals = (
            ProfileApplySignals()
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
        return self._cancel_event.is_set()

    @Slot()
    def run(
        self,
    ) -> None:
        started_at = time.monotonic()

        try:
            result = self._apply(
                started_at=started_at
            )
        except Exception as error:
            self.signals.failed.emit(
                f"{type(error).__name__}: {error}"
            )
            return

        if result.cancelled:
            self.signals.cancelled.emit()

        self.signals.finished.emit(
            result
        )

    def _apply(
        self,
        *,
        started_at: float,
    ) -> ProfileApplyResult:
        mods_by_key = {
            self._mod_key(mod): mod
            for mod in self.mods
        }

        results: list[ProfileApplyItem] = []
        total = len(
            self.profile.mods
        )

        cancelled = False

        for index, entry in enumerate(
            self.profile.mods,
            start=1,
        ):
            if self.is_cancelled():
                cancelled = True
                break

            self.signals.progress.emit(
                index - 1,
                total,
                entry.name,
            )

            mod = mods_by_key.get(
                self._normalize_key(
                    entry.relative_path
                )
            )

            if mod is None:
                results.append(
                    ProfileApplyItem(
                        relative_path=entry.relative_path,
                        name=entry.name,
                        desired_enabled=entry.enabled,
                        status=ProfileApplyStatus.MISSING,
                        message="Mod ist nicht mehr in der Library vorhanden.",
                    )
                )

                self.signals.progress.emit(
                    index,
                    total,
                    entry.name,
                )
                continue

            result = self._apply_entry(
                mod=mod,
                relative_path=entry.relative_path,
                desired_enabled=entry.enabled,
            )

            results.append(
                result
            )

            self.signals.progress.emit(
                index,
                total,
                entry.name,
            )

        return ProfileApplyResult(
            profile_name=self.profile.name,
            game_id=self.profile.game_id,
            items=tuple(results),
            duration_seconds=(
                time.monotonic()
                - started_at
            ),
            cancelled=cancelled,
        )

    def _apply_entry(
        self,
        *,
        mod: ModInfo,
        relative_path: str,
        desired_enabled: bool,
    ) -> ProfileApplyItem:
        try:
            state = self.mod_manager.get_state(
                mod.path
            )

            if state == ModState.NOT_CONFIGURED:
                return self._blocked(
                    mod=mod,
                    relative_path=relative_path,
                    desired_enabled=desired_enabled,
                    message="Aktiver Mods-Ordner ist nicht konfiguriert.",
                )

            if state == ModState.CONFLICT:
                return self._blocked(
                    mod=mod,
                    relative_path=relative_path,
                    desired_enabled=desired_enabled,
                    message="Konflikt: fremde Daten werden nicht automatisch übernommen.",
                )

            if desired_enabled:
                if state == ModState.ENABLED:
                    return self._unchanged(
                        mod=mod,
                        relative_path=relative_path,
                        desired_enabled=True,
                    )

                if state == ModState.BROKEN:
                    # Ein kaputter verwalteter Zustand wird erst sauber
                    # deaktiviert/repariert und anschließend aktiviert.
                    self.mod_manager.disable(
                        mod.path
                    )

                self.mod_manager.enable(
                    mod.path
                )

            else:
                if state == ModState.DISABLED:
                    return self._unchanged(
                        mod=mod,
                        relative_path=relative_path,
                        desired_enabled=False,
                    )

                if state in {
                    ModState.ENABLED,
                    ModState.BROKEN,
                }:
                    self.mod_manager.disable(
                        mod.path
                    )
                else:
                    return self._blocked(
                        mod=mod,
                        relative_path=relative_path,
                        desired_enabled=False,
                        message=f"Zustand kann nicht deaktiviert werden: {state.value}",
                    )

            final_state = self.mod_manager.get_state(
                mod.path
            )

            expected = (
                ModState.ENABLED
                if desired_enabled
                else ModState.DISABLED
            )

            if final_state != expected:
                return ProfileApplyItem(
                    relative_path=relative_path,
                    name=str(
                        getattr(
                            mod,
                            "name",
                            Path(mod.path).name,
                        )
                    ),
                    desired_enabled=desired_enabled,
                    status=ProfileApplyStatus.FAILED,
                    message=(
                        "Unerwarteter Endzustand: "
                        f"{final_state.value}"
                    ),
                )

            return ProfileApplyItem(
                relative_path=relative_path,
                name=str(
                    getattr(
                        mod,
                        "name",
                        Path(mod.path).name,
                    )
                ),
                desired_enabled=desired_enabled,
                status=ProfileApplyStatus.CHANGED,
            )

        except ModManagerError as error:
            return ProfileApplyItem(
                relative_path=relative_path,
                name=str(
                    getattr(
                        mod,
                        "name",
                        Path(mod.path).name,
                    )
                ),
                desired_enabled=desired_enabled,
                status=ProfileApplyStatus.FAILED,
                message=str(error),
            )
        except OSError as error:
            return ProfileApplyItem(
                relative_path=relative_path,
                name=str(
                    getattr(
                        mod,
                        "name",
                        Path(mod.path).name,
                    )
                ),
                desired_enabled=desired_enabled,
                status=ProfileApplyStatus.FAILED,
                message=str(error),
            )

    @classmethod
    def _mod_key(
        cls,
        mod: ModInfo,
    ) -> str:
        relative_path = getattr(
            mod,
            "relative_path",
            None,
        )

        if not relative_path:
            relative_path = Path(
                mod.path
            ).name

        return cls._normalize_key(
            str(relative_path)
        )

    @staticmethod
    def _normalize_key(
        value: str,
    ) -> str:
        return (
            str(value)
            .replace("\\", "/")
            .strip("/")
            .casefold()
        )

    @staticmethod
    def _unchanged(
        *,
        mod: ModInfo,
        relative_path: str,
        desired_enabled: bool,
    ) -> ProfileApplyItem:
        return ProfileApplyItem(
            relative_path=relative_path,
            name=str(
                getattr(
                    mod,
                    "name",
                    Path(mod.path).name,
                )
            ),
            desired_enabled=desired_enabled,
            status=ProfileApplyStatus.UNCHANGED,
        )

    @staticmethod
    def _blocked(
        *,
        mod: ModInfo,
        relative_path: str,
        desired_enabled: bool,
        message: str,
    ) -> ProfileApplyItem:
        return ProfileApplyItem(
            relative_path=relative_path,
            name=str(
                getattr(
                    mod,
                    "name",
                    Path(mod.path).name,
                )
            ),
            desired_enabled=desired_enabled,
            status=ProfileApplyStatus.BLOCKED,
            message=message,
        )


__all__ = [
    "ProfileApplySignals",
    "ProfileApplyWorker",
]
