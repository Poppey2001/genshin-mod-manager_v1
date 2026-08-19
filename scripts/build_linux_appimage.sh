#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUESTED_VERSION="${1:-}"

VERSION="$(
    python3 - <<'PY'
from pathlib import Path
import ast

path = Path("app/version.py")
source = path.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(path))

for node in tree.body:
    if isinstance(node, ast.Assign):
        if any(
            isinstance(target, ast.Name)
            and target.id == "APP_VERSION"
            for target in node.targets
        ):
            if (
                isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                print(node.value.value.strip())
                raise SystemExit(0)

    if isinstance(node, ast.AnnAssign):
        if (
            isinstance(node.target, ast.Name)
            and node.target.id == "APP_VERSION"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            print(node.value.value.strip())
            raise SystemExit(0)

raise SystemExit("APP_VERSION not found in app/version.py")
PY
)"

VERSION="${VERSION#v}"

if [[ -n "$REQUESTED_VERSION" ]]; then
    REQUESTED_VERSION="${REQUESTED_VERSION#v}"

    if [[ "$REQUESTED_VERSION" != "$VERSION" ]]; then
        echo "ERROR: Build version does not match app/version.py." >&2
        echo "Requested: $REQUESTED_VERSION" >&2
        echo "version.py: $VERSION" >&2
        exit 1
    fi
fi

echo "Version source: app/version.py"
echo "Building Linux AppImage version: $VERSION"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt

rm -rf build dist AppDir release
mkdir -p release

python3 -m PyInstaller \
    --noconfirm \
    --clean \
    packaging/GenshinModManager.spec

APPDIR="$ROOT/AppDir"

mkdir -p \
    "$APPDIR/usr/bin/GenshinModManager"

cp -a \
    "$ROOT/dist/GenshinModManager/." \
    "$APPDIR/usr/bin/GenshinModManager/"

cp \
    "$ROOT/packaging/linux/AppRun" \
    "$APPDIR/AppRun"

chmod +x \
    "$APPDIR/AppRun"

cp \
    "$ROOT/packaging/linux/genshin-mod-manager.desktop" \
    "$APPDIR/genshin-mod-manager.desktop"

ICON_SOURCE="$ROOT/assets/icons/app.png"

if [[ ! -f "$ICON_SOURCE" ]]; then
    echo "Missing application icon: $ICON_SOURCE" >&2
    exit 1
fi

cp \
    "$ICON_SOURCE" \
    "$APPDIR/gmm.png"

ln -sfn \
    "gmm.png" \
    "$APPDIR/.DirIcon"

TOOLS_DIR="$ROOT/.build-tools"
mkdir -p "$TOOLS_DIR"

APPIMAGETOOL="$TOOLS_DIR/appimagetool-x86_64.AppImage"

if [[ ! -x "$APPIMAGETOOL" ]]; then
    curl \
        --fail \
        --location \
        --retry 3 \
        --output "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

    chmod +x "$APPIMAGETOOL"
fi

OUTPUT="$ROOT/release/Genshin-Mod-Manager-${VERSION}-x86_64.AppImage"

ARCH=x86_64 \
APPIMAGE_EXTRACT_AND_RUN=1 \
"$APPIMAGETOOL" \
    "$APPDIR" \
    "$OUTPUT"

chmod +x "$OUTPUT"

(
    cd "$ROOT/release"
    sha256sum \
        "$(basename "$OUTPUT")" \
        > "$(basename "$OUTPUT").sha256"
)

echo
echo "Built:"
echo "  $OUTPUT"
echo "  $OUTPUT.sha256"
