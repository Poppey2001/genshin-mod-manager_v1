from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request

from app.services.network_tls import verified_urlopen

from .component_manifest import (
    ComponentEntry,
    ComponentManifest,
    ComponentManifestError,
    is_newer_component_version,
)
from .component_store import ComponentStore, ComponentStoreError


class ComponentUpdateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ComponentUpdateResult:
    checked: int
    updated: tuple[str, ...]
    restart_required: bool


class ComponentUpdateService:
    """Checks and installs small resource updates independently of the main app."""

    def __init__(
        self,
        *,
        manifest_url: str,
        component_root: Path,
        platform_name: str,
        app_version: str,
        user_agent: str,
        timeout: int = 25,
    ) -> None:
        self.manifest_url = manifest_url
        self.store = ComponentStore(component_root)
        self.platform_name = platform_name.casefold()
        self.app_version = app_version
        self.user_agent = user_agent
        self.timeout = timeout

    def _request(self, url: str) -> bytes:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Cache-Control": "no-cache",
            },
        )
        with verified_urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _manifest(self) -> ComponentManifest:
        try:
            return ComponentManifest.from_bytes(self._request(self.manifest_url))
        except (OSError, ComponentManifestError) as error:
            raise ComponentUpdateError(str(error)) from error

    def _eligible(self, entry: ComponentEntry, installed: dict[str, str]) -> bool:
        if not entry.supports_platform(self.platform_name):
            return False
        if not entry.supports_app_version(self.app_version):
            return False
        return is_newer_component_version(
            entry.version,
            installed.get(entry.component_id, ""),
        )

    def check_and_install(self) -> ComponentUpdateResult:
        manifest = self._manifest()
        installed = self.store.load_versions()
        candidates = [
            entry
            for entry in manifest.components
            if self._eligible(entry, installed)
        ]

        updated: list[str] = []
        restart_required = False

        for entry in candidates:
            try:
                payload = self._request(entry.source_url(self.manifest_url))
                self.store.install(entry, payload)
            except (OSError, ComponentStoreError) as error:
                raise ComponentUpdateError(
                    f"Component {entry.component_id} could not be updated: {error}"
                ) from error
            logging.info(
                "Component updated: %s -> %s (%s)",
                entry.component_id,
                entry.version,
                entry.target,
            )
            updated.append(entry.component_id)
            restart_required = restart_required or entry.restart_required

        return ComponentUpdateResult(
            checked=len(manifest.components),
            updated=tuple(updated),
            restart_required=restart_required,
        )
