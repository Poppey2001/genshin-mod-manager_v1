from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from packaging.version import InvalidVersion, Version


class ComponentManifestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ComponentEntry:
    component_id: str
    version: str
    kind: str
    source: str
    target: str
    sha256: str
    size: int = 0
    platforms: tuple[str, ...] = ("windows", "linux")
    min_app_version: str = "0"
    restart_required: bool = True

    def source_url(self, manifest_url: str) -> str:
        return urljoin(manifest_url, self.source)

    def supports_platform(self, platform_name: str) -> bool:
        normalized = platform_name.casefold()
        values = {value.casefold() for value in self.platforms}
        return "all" in values or normalized in values

    def supports_app_version(self, app_version: str) -> bool:
        try:
            current = Version(app_version.lstrip("vV"))
            minimum = Version(self.min_app_version.lstrip("vV"))
        except InvalidVersion:
            return True
        return current >= minimum


@dataclass(frozen=True, slots=True)
class ComponentManifest:
    schema: int
    components: tuple[ComponentEntry, ...]

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ComponentManifest":
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ComponentManifestError(
                "The component manifest is not valid UTF-8 JSON."
            ) from error

        if not isinstance(data, dict):
            raise ComponentManifestError("The component manifest root must be an object.")

        schema = int(data.get("schema", 0))
        if schema != 1:
            raise ComponentManifestError(f"Unsupported component manifest schema: {schema}")

        raw_components = data.get("components")
        if not isinstance(raw_components, list):
            raise ComponentManifestError("The component manifest has no components list.")

        components: list[ComponentEntry] = []
        seen_ids: set[str] = set()

        for item in raw_components:
            if not isinstance(item, dict):
                raise ComponentManifestError("A component entry is not an object.")

            component_id = str(item.get("id", "")).strip()
            version = str(item.get("version", "")).strip()
            kind = str(item.get("kind", "file")).strip().casefold()
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            sha256 = str(item.get("sha256", "")).strip().lower()

            if not component_id or component_id in seen_ids:
                raise ComponentManifestError(f"Invalid or duplicate component id: {component_id!r}")
            if not version:
                raise ComponentManifestError(f"Component {component_id} has no version.")
            if not source or "://" in source:
                raise ComponentManifestError(
                    f"Component {component_id} must use a relative source path."
                )
            if source.startswith(("/", "\\")) or ".." in source.replace("\\", "/").split("/"):
                raise ComponentManifestError(f"Unsafe source path for component {component_id}.")
            if not target or target.startswith(("/", "\\")):
                raise ComponentManifestError(f"Unsafe target path for component {component_id}.")
            if ".." in target.replace("\\", "/").split("/"):
                raise ComponentManifestError(f"Unsafe target path for component {component_id}.")
            if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
                raise ComponentManifestError(f"Component {component_id} has an invalid SHA-256.")
            if kind not in {"file", "qss", "json"}:
                raise ComponentManifestError(f"Unsupported component kind {kind!r}.")

            platforms_value = item.get("platforms", ["windows", "linux"])
            if isinstance(platforms_value, str):
                platforms = (platforms_value,)
            elif isinstance(platforms_value, list):
                platforms = tuple(str(value) for value in platforms_value if str(value).strip())
            else:
                raise ComponentManifestError(f"Invalid platforms for component {component_id}.")

            components.append(
                ComponentEntry(
                    component_id=component_id,
                    version=version,
                    kind=kind,
                    source=source,
                    target=target.replace("\\", "/"),
                    sha256=sha256,
                    size=max(0, int(item.get("size", 0) or 0)),
                    platforms=platforms or ("windows", "linux"),
                    min_app_version=str(item.get("min_app_version", "0") or "0"),
                    restart_required=bool(item.get("restart_required", True)),
                )
            )
            seen_ids.add(component_id)

        return cls(schema=schema, components=tuple(components))


def is_newer_component_version(remote: str, installed: str) -> bool:
    if not installed:
        return True
    try:
        return Version(remote.lstrip("vV")) > Version(installed.lstrip("vV"))
    except InvalidVersion:
        return remote != installed
