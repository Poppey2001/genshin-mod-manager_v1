from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .component_manifest import ComponentEntry


class ComponentStoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InstalledComponent:
    component_id: str
    version: str
    target: str
    sha256: str


class ComponentStore:
    """Atomic storage for hot-updateable non-code GMM components."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.state_file = self.root / "component-state.json"
        self.backup_root = self.root / ".backups"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def load_versions(self) -> dict[str, str]:
        if not self.state_file.is_file():
            return {}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        raw = data.get("components", {})
        if not isinstance(raw, dict):
            return {}
        result: dict[str, str] = {}
        for component_id, entry in raw.items():
            if isinstance(entry, dict):
                result[str(component_id)] = str(entry.get("version", "") or "")
        return result

    def _load_state(self) -> dict[str, object]:
        if not self.state_file.is_file():
            return {"schema": 1, "components": {}}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema": 1, "components": {}}
        if not isinstance(data, dict):
            return {"schema": 1, "components": {}}
        if not isinstance(data.get("components"), dict):
            data["components"] = {}
        data["schema"] = 1
        return data

    def _save_state(self, state: dict[str, object]) -> None:
        self.ensure()
        temporary = self.state_file.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_file)

    def target_path(self, entry: ComponentEntry) -> Path:
        target = (self.root / entry.target).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as error:
            raise ComponentStoreError(f"Unsafe component target: {entry.target}") from error
        return target

    @staticmethod
    def verify_payload(entry: ComponentEntry, payload: bytes) -> None:
        if not payload:
            raise ComponentStoreError(f"Component {entry.component_id} is empty.")
        if len(payload) > 8 * 1024 * 1024:
            raise ComponentStoreError(f"Component {entry.component_id} is unexpectedly large.")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != entry.sha256:
            raise ComponentStoreError(
                f"SHA-256 mismatch for component {entry.component_id}: {digest} != {entry.sha256}"
            )
        if entry.size and len(payload) != entry.size:
            raise ComponentStoreError(
                f"Size mismatch for component {entry.component_id}: {len(payload)} != {entry.size}"
            )
        if entry.kind == "qss":
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ComponentStoreError(f"QSS component {entry.component_id} is not UTF-8.") from error
            if text.count("{") != text.count("}"):
                raise ComponentStoreError(
                    f"QSS component {entry.component_id} has unbalanced braces."
                )
        elif entry.kind == "json":
            try:
                json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ComponentStoreError(f"JSON component {entry.component_id} is invalid.") from error

    def install(self, entry: ComponentEntry, payload: bytes) -> InstalledComponent:
        self.ensure()
        self.verify_payload(entry, payload)
        target = self.target_path(entry)
        target.parent.mkdir(parents=True, exist_ok=True)

        backup = self.backup_root / f"{entry.component_id}.previous"
        backup.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".new")
        temporary.write_bytes(payload)

        try:
            if target.is_file():
                shutil.copy2(target, backup)
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            if backup.is_file() and not target.is_file():
                shutil.copy2(backup, target)
            raise

        state = self._load_state()
        components = state.setdefault("components", {})
        assert isinstance(components, dict)
        components[entry.component_id] = {
            "version": entry.version,
            "target": entry.target,
            "sha256": entry.sha256,
        }
        self._save_state(state)

        return InstalledComponent(
            component_id=entry.component_id,
            version=entry.version,
            target=entry.target,
            sha256=entry.sha256,
        )
