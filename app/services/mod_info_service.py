from __future__ import annotations

from typing import Any

from app.models.mod import ModInfo
from app.services.ini_analyzer import (
    analyze_mod_ini,
)
from app.services.mod_manager import (
    ModManager,
)


class ModInfoService:
    """
    Bereitet die INI-Analyse eines Mods vor.

    Diese Klasse enthält keine UI-Logik.
    """

    def __init__(
        self,
        *,
        mod_manager: ModManager,
    ) -> None:
        self._mod_manager = mod_manager

    def analyze(
        self,
        mod: ModInfo,
    ) -> Any:
        inspection_path = (
            self._mod_manager.inspection_path_for(
                mod.path
            )
        )

        return analyze_mod_ini(
            inspection_path
        )