#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REQUESTED_VERSION="${1:-}"

VERSION="$(python3 - <<'PY'
from pathlib import Path
import ast
path = Path('app/version.py')
tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
for node in tree.body:
    value = None
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in node.targets):
        value = node.value
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'APP_VERSION':
        value = node.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        print(value.value.strip().lstrip('vV'))
        raise SystemExit(0)
raise SystemExit('APP_VERSION not found')
PY
)"

if [[ -n "$REQUESTED_VERSION" && "${REQUESTED_VERSION#v}" != "$VERSION" ]]; then
    echo "ERROR: Requested version $REQUESTED_VERSION does not match app/version.py ($VERSION)." >&2
    exit 1
fi

echo "Building Linux AppImage + standalone Update Agent for $VERSION"

bash scripts/build_linux_appimage.sh "$VERSION"

python3 -m PyInstaller --noconfirm --clean packaging/GMMUpdateAgent.spec
AGENT_BUILD="$ROOT/dist/GMMUpdateAgent"
[[ -x "$AGENT_BUILD" ]] || { echo "ERROR: Update Agent build missing: $AGENT_BUILD" >&2; exit 1; }

AGENT_RELEASE="$ROOT/release/GMMUpdateAgent-Linux-${VERSION}-x86_64"
cp "$AGENT_BUILD" "$AGENT_RELEASE"
chmod +x "$AGENT_RELEASE"
(
    cd "$ROOT/release"
    sha256sum "$(basename "$AGENT_RELEASE")" > "$(basename "$AGENT_RELEASE").sha256"
)

cp packaging/linux/install-gmm-linux.sh release/install-gmm-linux.sh
cp packaging/linux/uninstall-gmm-linux.sh release/uninstall-gmm-linux.sh
chmod +x release/install-gmm-linux.sh release/uninstall-gmm-linux.sh

APPIMAGE="$ROOT/release/Genshin-Mod-Manager-${VERSION}-x86_64.AppImage"
[[ -f "$APPIMAGE" ]] || { echo "ERROR: AppImage missing after build: $APPIMAGE" >&2; exit 1; }

STAGING="$ROOT/release/.linux-bundle-${VERSION}"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp "$APPIMAGE" "$STAGING/Genshin-Mod-Manager-${VERSION}-x86_64.AppImage"
cp "$APPIMAGE.sha256" "$STAGING/Genshin-Mod-Manager-${VERSION}-x86_64.AppImage.sha256"
cp "$AGENT_RELEASE" "$STAGING/GMMUpdateAgent-Linux-${VERSION}-x86_64"
cp "$AGENT_RELEASE.sha256" "$STAGING/GMMUpdateAgent-Linux-${VERSION}-x86_64.sha256"
cp packaging/linux/install-gmm-linux.sh "$STAGING/install.sh"
cp packaging/linux/uninstall-gmm-linux.sh "$STAGING/uninstall.sh"
printf '%s\n' "$VERSION" > "$STAGING/VERSION"

ICON=""
for candidate in assets/icons/app.png assets/icons/games/genshin-impact.png; do
    if [[ -f "$candidate" ]]; then ICON="$candidate"; break; fi
done
if [[ -n "$ICON" ]]; then cp "$ICON" "$STAGING/gmm.png"; fi

BUNDLE="$ROOT/release/Genshin-Mod-Manager-${VERSION}-Linux-x86_64.tar.gz"
tar -C "$STAGING" -czf "$BUNDLE" .
rm -rf "$STAGING"
(
    cd "$ROOT/release"
    sha256sum "$(basename "$BUNDLE")" > "$(basename "$BUNDLE").sha256"
)

echo
printf 'Built Linux release assets:\n'
printf '  %s\n' "$APPIMAGE" "$APPIMAGE.sha256" "$AGENT_RELEASE" "$AGENT_RELEASE.sha256" "$BUNDLE" "$BUNDLE.sha256"
