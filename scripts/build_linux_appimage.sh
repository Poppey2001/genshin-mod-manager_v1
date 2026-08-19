#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"

if [[ -z "$VERSION" ]]; then
    VERSION="$(
        python3 - <<'PY'
from pathlib import Path
import re

text = Path("app/version.py").read_text(encoding="utf-8")

match = re.search(
    r'(?m)^APP_VERSION\s*=\s*["\']([^"\']+)["\']',
    text,
)

if not match:
    raise SystemExit("APP_VERSION not found in app/version.py")

print(match.group(1))
PY
    )"
fi

VERSION="${VERSION#v}"

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
