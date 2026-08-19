from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


COMPONENTS = (
    {
        "id": "qss-library",
        "kind": "qss",
        "source": "app/styles/library.qss",
        "target": "styles/library.qss",
    },
    {
        "id": "qss-gamebanana",
        "kind": "qss",
        "source": "app/styles/gamebanana.qss",
        "target": "styles/gamebanana.qss",
    },
    {
        "id": "qss-profiles",
        "kind": "qss",
        "source": "app/styles/profiles.qss",
        "target": "styles/profiles.qss",
    },
    {
        "id": "qss-conflicts",
        "kind": "qss",
        "source": "app/styles/conflicts.qss",
        "target": "styles/conflicts.qss",
    },
    {
        "id": "qss-update-agent",
        "kind": "qss",
        "source": "updater/styles/update_agent.qss",
        "target": "styles/update_agent.qss",
        "restart_required": False,
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_qss(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit(f"QSS is empty: {path}")
    if text.count("{") != text.count("}"):
        raise SystemExit(f"QSS braces are unbalanced: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GMM small-component update feed")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="component-feed")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    manifest_components: list[dict[str, object]] = []

    for definition in COMPONENTS:
        component_id = str(definition["id"])
        source = root / str(definition["source"])
        if not source.is_file():
            raise SystemExit(f"Missing component source: {source}")
        if definition["kind"] == "qss":
            validate_qss(source)

        target_rel = Path("files") / str(definition["target"])
        target = output / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

        digest = sha256(target)
        version = "sha256-" + digest[:16]

        manifest_components.append(
            {
                "id": component_id,
                "version": version,
                "kind": definition["kind"],
                "source": target_rel.as_posix(),
                "target": definition["target"],
                "sha256": digest,
                "size": target.stat().st_size,
                "platforms": ["windows", "linux"],
                "min_app_version": "0",
                "restart_required": bool(
                    definition.get(
                        "restart_required",
                        True,
                    )
                ),
            }
        )

    manifest = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": manifest_components,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Component feed written to: {output}")
    for item in manifest_components:
        print(f"  {item['id']} -> {item['version']} ({item['target']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
