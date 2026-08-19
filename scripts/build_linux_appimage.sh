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
    value = None

    if isinstance(node, ast.Assign):
        if any(
            isinstance(target, ast.Name)
            and target.id == "APP_VERSION"
            for target in node.targets
        ):
            value = node.value

    elif isinstance(node, ast.AnnAssign):
        if (
            isinstance(node.target, ast.Name)
            and node.target.id == "APP_VERSION"
        ):
            value = node.value

    if (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
    ):
        print(value.value.strip())
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

# ------------------------------------------------------------
# Build dependencies
# ------------------------------------------------------------

python3 -m pip install --upgrade pip

if [[ -f "$ROOT/requirements-build.txt" ]]; then
    python3 -m pip install \
        -r "$ROOT/requirements-build.txt"
else
    if [[ -f "$ROOT/requirements.txt" ]]; then
        python3 -m pip install \
            -r "$ROOT/requirements.txt"
    fi

    python3 -m pip install \
        "pyinstaller>=6.10,<7"
fi

rm -rf \
    "$ROOT/build" \
    "$ROOT/dist" \
    "$ROOT/AppDir" \
    "$ROOT/release"

mkdir -p \
    "$ROOT/release"

# ------------------------------------------------------------
# PyInstaller
# ------------------------------------------------------------

python3 -m PyInstaller \
    --noconfirm \
    --clean \
    "$ROOT/packaging/GenshinModManager.spec"

BINARY="$ROOT/dist/GenshinModManager/GenshinModManager"

if [[ ! -x "$BINARY" ]]; then
    echo "ERROR: PyInstaller output is missing: $BINARY" >&2
    exit 1
fi

# ------------------------------------------------------------
# AppDir
# ------------------------------------------------------------

APPDIR="$ROOT/AppDir"
PAYLOAD="$APPDIR/usr/bin/GenshinModManager"

mkdir -p \
    "$PAYLOAD"

cp -a \
    "$ROOT/dist/GenshinModManager/." \
    "$PAYLOAD/"

cp \
    "$ROOT/packaging/linux/AppRun" \
    "$APPDIR/AppRun"

chmod +x \
    "$APPDIR/AppRun"

cp \
    "$ROOT/packaging/linux/genshin-mod-manager.desktop" \
    "$APPDIR/genshin-mod-manager.desktop"

# ------------------------------------------------------------
# AppImage icon
# ------------------------------------------------------------
# Prefer the dedicated app icon, then Genshin's game icon, then
# any PNG below assets/icons. If none exists, generate a valid
# 256x256 fallback so the AppDir remains packageable.

ICON_SOURCE=""

ICON_CANDIDATES=(
    "$ROOT/assets/icons/app.png"
    "$ROOT/assets/icons/games/genshin-impact.png"
)

for candidate in "${ICON_CANDIDATES[@]}"; do
    if [[ -f "$candidate" ]]; then
        ICON_SOURCE="$candidate"
        break
    fi
done

if [[ -z "$ICON_SOURCE" && -d "$ROOT/assets/icons" ]]; then
    ICON_SOURCE="$(
        find "$ROOT/assets/icons" \
            -type f \
            -iname '*.png' \
            -print \
            -quit \
            2>/dev/null || true
    )"
fi

if [[ -n "$ICON_SOURCE" ]]; then
    echo "AppImage icon: $ICON_SOURCE"

    cp \
        "$ICON_SOURCE" \
        "$APPDIR/gmm.png"
else
    echo \
        "WARNING: No PNG application icon found. Generating fallback icon." \
        >&2

    APPDIR_PATH="$APPDIR" python3 - <<'PY'
from pathlib import Path
import os
import struct
import zlib

appdir = Path(
    os.environ["APPDIR_PATH"]
)

output = (
    appdir
    / "gmm.png"
)

width = 256
height = 256

rows = []

for y in range(height):
    row = bytearray(
        [0]
    )

    for x in range(width):
        cx = x - width / 2
        cy = y - height / 2

        radius = (
            cx * cx
            + cy * cy
        ) ** 0.5

        if radius < 92:
            pixel = (
                245,
                178,
                35,
                255,
            )
        else:
            pixel = (
                24,
                28,
                36,
                255,
            )

        row.extend(
            pixel
        )

    rows.append(
        bytes(
            row
        )
    )

raw = b"".join(
    rows
)

def chunk(
    kind: bytes,
    payload: bytes,
) -> bytes:
    crc = zlib.crc32(
        kind
    )

    crc = zlib.crc32(
        payload,
        crc,
    ) & 0xFFFFFFFF

    return (
        struct.pack(
            ">I",
            len(
                payload
            ),
        )
        + kind
        + payload
        + struct.pack(
            ">I",
            crc,
        )
    )

png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(
        b"IHDR",
        struct.pack(
            ">IIBBBBB",
            width,
            height,
            8,
            6,
            0,
            0,
            0,
        ),
    )
    + chunk(
        b"IDAT",
        zlib.compress(
            raw,
            9,
        ),
    )
    + chunk(
        b"IEND",
        b"",
    )
)

output.write_bytes(
    png
)

print(
    f"Generated fallback icon: {output}"
)
PY
fi

ln -sfn \
    "gmm.png" \
    "$APPDIR/.DirIcon"

# ------------------------------------------------------------
# AppDir validation
# ------------------------------------------------------------

for required in \
    "$APPDIR/AppRun" \
    "$APPDIR/genshin-mod-manager.desktop" \
    "$APPDIR/gmm.png" \
    "$PAYLOAD/GenshinModManager"; do

    if [[ ! -e "$required" ]]; then
        echo "ERROR: AppDir file missing: $required" >&2
        exit 1
    fi
done

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate \
        "$APPDIR/genshin-mod-manager.desktop"
fi

# ------------------------------------------------------------
# appimagetool
# ------------------------------------------------------------

TOOLS_DIR="$ROOT/.build-tools"

mkdir -p \
    "$TOOLS_DIR"

APPIMAGETOOL="$TOOLS_DIR/appimagetool-x86_64.AppImage"

if [[ ! -x "$APPIMAGETOOL" ]]; then
    curl \
        --fail \
        --location \
        --retry 3 \
        --output "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

    chmod +x \
        "$APPIMAGETOOL"
fi

OUTPUT="$ROOT/release/Genshin-Mod-Manager-${VERSION}-x86_64.AppImage"

ARCH=x86_64 \
APPIMAGE_EXTRACT_AND_RUN=1 \
"$APPIMAGETOOL" \
    "$APPDIR" \
    "$OUTPUT"

if [[ ! -f "$OUTPUT" ]]; then
    echo "ERROR: AppImage was not created: $OUTPUT" >&2
    exit 1
fi

chmod +x \
    "$OUTPUT"

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
