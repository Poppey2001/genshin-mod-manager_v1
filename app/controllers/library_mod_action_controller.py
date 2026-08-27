from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from app.models.mod import ModInfo
from app.services.mod_manager import (
    ModManager,
    ModState,
)


class ModActionStatus(Enum):
    SUCCESS = auto()
    NOT_CONFIGURED = auto()
    CONFLICT = auto()
    NOT_CONFLICT = auto()


@dataclass(
    frozen=True,
    slots=True,
)
class ModActionResult:
    status: ModActionStatus
    state: ModState
    message: str


class LibraryModActionController:
    def __init__(
        self,
        *,
        mod_manager: ModManager,
    ) -> None:
        self._mod_manager = mod_manager

    def get_state(
        self,
        mod: ModInfo,
    ) -> ModState:
        return self._mod_manager.get_state(
            mod.path
        )
    
    def get_state_for_path(
        self,
        path: Path,
    ) -> ModState:
        return self._mod_manager.get_state(
            path
        )
        
    def toggle(
        self,
        mod: ModInfo,
    ) -> ModActionResult:
        state = self.get_state(
            mod
        )

        if state == ModState.DISABLED:
            destination = (
                self._mod_manager.enable(
                    mod.path
                )
            )

            resulting_state = self.get_state(
                mod
            )

            mode = getattr(
                self._mod_manager,
                "last_enable_mode",
                None,
            )
            if mode in {"rename_exact", "rename_discovered"}:
                action_text = "reaktiviert (nur umbenannt, nicht kopiert)"
            elif mode == "copy_first_activation":
                action_text = "erstmals aktiviert (einmalig kopiert)"
            elif mode in {"already_enabled", "already_enabled_discovered", "already_enabled_symlink"}:
                action_text = "war bereits aktiviert"
            else:
                action_text = "aktiviert"

            return ModActionResult(
                status=ModActionStatus.SUCCESS,
                state=resulting_state,
                message=(
                    f"„{mod.name}“ wurde {action_text}: {destination}"
                ),
            )

        if state in {
            ModState.ENABLED,
            ModState.BROKEN,
        }:
            self._mod_manager.disable(
                mod.path
            )

            resulting_state = self.get_state(
                mod
            )

            return ModActionResult(
                status=ModActionStatus.SUCCESS,
                state=resulting_state,
                message=(
                    f"„{mod.name}“ wurde "
                    "deaktiviert und die "
                    "reparierte Version wurde "
                    "gespeichert."
                ),
            )

        if state == ModState.NOT_CONFIGURED:
            return ModActionResult(
                status=(
                    ModActionStatus.NOT_CONFIGURED
                ),
                state=state,
                message=(
                    "Wähle unter Einstellungen "
                    "zuerst den aktiven "
                    "Mods-Ordner aus."
                ),
            )

        return ModActionResult(
            status=ModActionStatus.CONFLICT,
            state=state,
            message=(
                "Am Ziel befindet sich bereits "
                "ein fremder Ordner oder eine "
                "fremde Verknüpfung.\n\n"
                "Der Manager überschreibt "
                "diese Daten nicht."
            ),
        )

    def adopt(
        self,
        mod: ModInfo,
    ) -> ModActionResult:
        state = self.get_state(
            mod
        )

        if state != ModState.CONFLICT:
            return ModActionResult(
                status=(
                    ModActionStatus.NOT_CONFLICT
                ),
                state=state,
                message=(
                    "Der ausgewählte Mod besitzt "
                    "aktuell keinen Konflikt."
                ),
            )

        resulting_state = (
            self._mod_manager.adopt_existing(
                mod.path
            )
        )

        if resulting_state == ModState.ENABLED:
            state_text = "aktiviert"
        else:
            state_text = "deaktiviert"

        return ModActionResult(
            status=ModActionStatus.SUCCESS,
            state=resulting_state,
            message=(
                f"„{mod.name}“ wurde als "
                f"vorhandener {state_text}er "
                "Mod übernommen."
            ),
        )
        
    def validate_adopt(
        self,
        mod: ModInfo,
    ) -> ModActionResult | None:
        state = self.get_state(
            mod
        )

        if state == ModState.CONFLICT:
            return None

        return ModActionResult(
            status=(
                ModActionStatus.NOT_CONFLICT
            ),
            state=state,
            message=(
                "Der ausgewählte Mod besitzt "
                "aktuell keinen Konflikt."
            ),
        )