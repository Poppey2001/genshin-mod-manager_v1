from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from app.models.mod import ModInfo
from app.services.mod_manager import (
    ModManager,
    ModState,
)
from app.i18n import tr

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

            return ModActionResult(
                status=ModActionStatus.SUCCESS,
                state=resulting_state,
                message=tr(
                    "library.mod_action.enabled",
                    mod_name=mod.name,
                    destination=destination,
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
                message=tr(
                    "library.mod_action.disabled",
                    mod_name=mod.name,
                ),
            )

        if state == ModState.NOT_CONFIGURED:
            return ModActionResult(
                status=(
                    ModActionStatus.NOT_CONFIGURED
                ),
                state=state,
                message=tr(
                    "library.mod_action.not_configured"
                ),
            )

        return ModActionResult(
            status=ModActionStatus.CONFLICT,
            state=state,
            message=tr(
                "library.mod_action.conflict"
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
                message=tr(
                    "library.mod_action.not_conflict"
                ),
            )

        resulting_state = (
            self._mod_manager.adopt_existing(
                mod.path
            )
        )

        if resulting_state == ModState.ENABLED:
            message_key = (
                "library.mod_action."
                "adopted_enabled"
            )
        else:
            message_key = (
                "library.mod_action."
                "adopted_disabled"
            )

        return ModActionResult(
            status=ModActionStatus.SUCCESS,
            state=resulting_state,
            message=tr(
                message_key,
                mod_name=mod.name,
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
            message=tr(
                "library.mod_action.not_conflict"
            ),
        )