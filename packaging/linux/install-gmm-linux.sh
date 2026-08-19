#!/usr/bin/env bash
set -euo pipefail

OWNER="Poppey2001"
REPOSITORY="genshin-mod-manager_v1"
CHANNEL="${GMM_UPDATE_CHANNEL:-prerelease}"
INSTALL_DIR="${GMM_INSTALL_DIR:-$HOME/.local/opt/genshin-mod-manager}"
APPIMAGE_TARGET="$INSTALL_DIR/GenshinModManager.AppImage"
AGENT_TARGET="$INSTALL_DIR/GMMUpdateAgent"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/genshin-mod-manager.desktop"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/genshin-mod-manager"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR=""
VERSION=""
LOCAL_APPIMAGE=""
LOCAL_AGENT=""
LOCAL_ICON=""

cleanup() {
    if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
        rm -rf -- "$TMP_DIR"
    fi
}
trap cleanup EXIT

log() { printf '[GMM Installer] %s\n' "$*"; }
warn() { printf '[GMM Installer] WARN: %s\n' "$*" >&2; }
die() { printf '[GMM Installer] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<EOF
Usage: $0 [--stable|--prerelease] [--install-dir PATH] [--local-appimage FILE] [--local-agent FILE]
EOF
}

while (($#)); do
    case "$1" in
        --stable) CHANNEL="stable"; shift ;;
        --prerelease) CHANNEL="prerelease"; shift ;;
        --install-dir) (($# >= 2)) || die "Missing path after --install-dir"; INSTALL_DIR="$2"; APPIMAGE_TARGET="$INSTALL_DIR/GenshinModManager.AppImage"; AGENT_TARGET="$INSTALL_DIR/GMMUpdateAgent"; shift 2 ;;
        --local-appimage) (($# >= 2)) || die "Missing file after --local-appimage"; LOCAL_APPIMAGE="$2"; shift 2 ;;
        --local-agent) (($# >= 2)) || die "Missing file after --local-agent"; LOCAL_AGENT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done

[[ ${EUID:-$(id -u)} -ne 0 ]] || die "Do not run this installer as root. GMM is installed for the current user."
[[ "$(uname -s)" == "Linux" ]] || die "This installer is for Linux only."
[[ "$(uname -m)" == "x86_64" || "$(uname -m)" == "amd64" ]] || die "Currently only x86_64/amd64 is supported."
command -v python3 >/dev/null 2>&1 || die "python3 is required."
command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required."
command -v curl >/dev/null 2>&1 || die "curl is required."

find_local_payload() {
    if [[ -z "$LOCAL_APPIMAGE" ]]; then
        LOCAL_APPIMAGE="$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name 'Genshin-Mod-Manager-*-x86_64.AppImage' -print -quit 2>/dev/null || true)"
        [[ -n "$LOCAL_APPIMAGE" ]] || LOCAL_APPIMAGE="$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name 'GenshinModManager.AppImage' -print -quit 2>/dev/null || true)"
    fi
    if [[ -z "$LOCAL_AGENT" ]]; then
        LOCAL_AGENT="$(find "$SCRIPT_DIR" -maxdepth 1 -type f \( -name 'GMMUpdateAgent-Linux-*-x86_64' -o -name 'GMMUpdateAgent-*-x86_64' \) -print -quit 2>/dev/null || true)"
        [[ -n "$LOCAL_AGENT" ]] || LOCAL_AGENT="$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name 'GMMUpdateAgent' -print -quit 2>/dev/null || true)"
    fi
    [[ -f "$SCRIPT_DIR/gmm.png" ]] && LOCAL_ICON="$SCRIPT_DIR/gmm.png" || true
}

verify_with_sidecar() {
    local file="$1"
    local sidecar="$2"
    [[ -f "$sidecar" ]] || return 1
    local expected actual
    expected="$(grep -Eo '[0-9a-fA-F]{64}' "$sidecar" | head -n1 | tr 'A-F' 'a-f')"
    [[ -n "$expected" ]] || return 1
    actual="$(sha256sum "$file" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]]
}

download_release() {
    TMP_DIR="$(mktemp -d -t gmm-linux-installer.XXXXXX)"
    local api="$TMP_DIR/releases.json"
    log "Loading GitHub releases …"
    curl --fail --location --retry 3 --silent --show-error \
        -H 'Accept: application/vnd.github+json' \
        -H 'X-GitHub-Api-Version: 2026-03-10' \
        -H 'User-Agent: GMM-Linux-Installer' \
        "https://api.github.com/repos/$OWNER/$REPOSITORY/releases?per_page=20" \
        -o "$api"

    mapfile -t META < <(python3 - "$api" "$CHANNEL" <<'PY'
import json, sys
from pathlib import Path
releases = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
channel = sys.argv[2]
for release in releases:
    if release.get("draft"):
        continue
    if channel == "stable" and release.get("prerelease"):
        continue
    assets = release.get("assets") or []
    app = next((a for a in assets if str(a.get("name", "")).lower().endswith(".appimage") and any(x in str(a.get("name", "")).lower() for x in ("x86_64", "amd64"))), None)
    agent = next((a for a in assets if str(a.get("name", "")).lower().startswith("gmmupdateagent-") and not str(a.get("name", "")).lower().endswith((".sha256", ".exe")) and any(x in str(a.get("name", "")).lower() for x in ("x86_64", "amd64")) and ("linux" in str(a.get("name", "")).lower() or "." not in Path(str(a.get("name", ""))).suffix)), None)
    if not app or not agent:
        continue
    by_name = {str(a.get("name", "")): a for a in assets}
    app_sum = by_name.get(str(app.get("name")) + ".sha256")
    agent_sum = by_name.get(str(agent.get("name")) + ".sha256")
    if not app_sum or not agent_sum:
        continue
    tag = str(release.get("tag_name") or "").lstrip("vV")
    print(tag)
    print(app["browser_download_url"])
    print(app_sum["browser_download_url"])
    print(agent["browser_download_url"])
    print(agent_sum["browser_download_url"])
    raise SystemExit(0)
raise SystemExit("No compatible Linux release with AppImage, Update Agent and SHA256 files found")
PY
    )

    [[ ${#META[@]} -eq 5 ]] || die "No compatible Linux release found."
    VERSION="${META[0]}"
    local app_url="${META[1]}" app_sum_url="${META[2]}" agent_url="${META[3]}" agent_sum_url="${META[4]}"
    LOCAL_APPIMAGE="$TMP_DIR/GenshinModManager.AppImage"
    LOCAL_AGENT="$TMP_DIR/GMMUpdateAgent"
    local app_sum="$TMP_DIR/app.sha256" agent_sum="$TMP_DIR/agent.sha256"

    log "Downloading GMM $VERSION …"
    curl --fail --location --retry 3 --show-error "$app_url" -o "$LOCAL_APPIMAGE"
    curl --fail --location --retry 3 --silent --show-error "$app_sum_url" -o "$app_sum"
    log "Downloading Update Agent …"
    curl --fail --location --retry 3 --show-error "$agent_url" -o "$LOCAL_AGENT"
    curl --fail --location --retry 3 --silent --show-error "$agent_sum_url" -o "$agent_sum"

    verify_with_sidecar "$LOCAL_APPIMAGE" "$app_sum" || die "AppImage SHA-256 verification failed."
    verify_with_sidecar "$LOCAL_AGENT" "$agent_sum" || die "Update Agent SHA-256 verification failed."
}

read_bundle_version() {
    if [[ -f "$SCRIPT_DIR/VERSION" ]]; then
        VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION")"
    fi
    if [[ -z "$VERSION" && -n "$LOCAL_APPIMAGE" ]]; then
        local base
        base="$(basename "$LOCAL_APPIMAGE")"
        VERSION="$(sed -nE 's/^Genshin-Mod-Manager-(.+)-x86_64\.AppImage$/\1/p' <<<"$base")"
    fi
    VERSION="${VERSION:-0.0.0}"
}

install_payload() {
    mkdir -p "$INSTALL_DIR" "$APPLICATIONS_DIR" "$BIN_DIR"
    install -m 0755 "$LOCAL_APPIMAGE" "$APPIMAGE_TARGET.new"
    mv -f "$APPIMAGE_TARGET.new" "$APPIMAGE_TARGET"
    install -m 0755 "$LOCAL_AGENT" "$AGENT_TARGET.new"
    mv -f "$AGENT_TARGET.new" "$AGENT_TARGET"

    cat > "$LAUNCHER" <<EOF
#!/bin/sh
exec "$APPIMAGE_TARGET" "\$@"
EOF
    chmod 0755 "$LAUNCHER"

    local icon_line="Icon=applications-games"
    if [[ -n "$LOCAL_ICON" && -f "$LOCAL_ICON" ]]; then
        install -m 0644 "$LOCAL_ICON" "$INSTALL_DIR/gmm.png"
        icon_line="Icon=$INSTALL_DIR/gmm.png"
    fi

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Genshin Mod Manager
Comment=Manage Genshin Impact mods
Exec=$LAUNCHER
$icon_line
Terminal=false
Categories=Game;Utility;
StartupNotify=true
EOF
    chmod 0644 "$DESKTOP_FILE"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
    fi
}

configure_agent() {
    local agent_config_file="${XDG_CONFIG_HOME:-$HOME/.config}/genshin-mod-manager/update-agent.json"

    if [[ -f "$agent_config_file" ]]; then
        # Reinstall/update: preserve the user's previous autostart and
        # automatic-check decision. Only installation paths/version/channel
        # are refreshed before showing the configuration dialog.
        "$AGENT_TARGET" --write-config \
            --appimage "$APPIMAGE_TARGET" \
            --agent-path "$AGENT_TARGET" \
            --installed-version "$VERSION" \
            --channel "$CHANNEL"
    else
        # Fresh install: defaults are enabled, but the installer immediately
        # asks the user and can turn either option off.
        "$AGENT_TARGET" --write-config \
            --appimage "$APPIMAGE_TARGET" \
            --agent-path "$AGENT_TARGET" \
            --installed-version "$VERSION" \
            --channel "$CHANNEL" \
            --autostart yes \
            --auto-check yes \
            --interval 20
    fi

    if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        if "$AGENT_TARGET" --configure-install \
            --appimage "$APPIMAGE_TARGET" \
            --agent-path "$AGENT_TARGET" \
            --installed-version "$VERSION" \
            --channel "$CHANNEL"; then
            return
        fi
        warn "Graphical configuration was cancelled or unavailable; falling back to terminal questions."
    fi

    local autostart="yes" auto_check="yes" interval="20" answer=""
    if [[ -t 0 ]]; then
        read -r -p "Start GMM Update Agent automatically at login? [Y/n]: " answer || true
        [[ "$answer" =~ ^[Nn] ]] && autostart="no"
        answer=""
        read -r -p "Automatically check for updates every 20 minutes? [Y/n]: " answer || true
        [[ "$answer" =~ ^[Nn] ]] && auto_check="no"
        if [[ "$auto_check" == "yes" ]]; then
            answer=""
            read -r -p "Check interval in minutes [20]: " answer || true
            if [[ "$answer" =~ ^[0-9]+$ ]] && (( answer >= 15 )); then interval="$answer"; fi
        fi
    fi

    "$AGENT_TARGET" --write-config \
        --appimage "$APPIMAGE_TARGET" \
        --agent-path "$AGENT_TARGET" \
        --installed-version "$VERSION" \
        --channel "$CHANNEL" \
        --autostart "$autostart" \
        --auto-check "$auto_check" \
        --interval "$interval"
}

find_local_payload
if [[ ! -f "$LOCAL_APPIMAGE" || ! -f "$LOCAL_AGENT" ]]; then
    download_release
else
    read_bundle_version
    APP_SUM_LOCAL="$LOCAL_APPIMAGE.sha256"
    AGENT_SUM_LOCAL="$LOCAL_AGENT.sha256"
    if [[ -f "$APP_SUM_LOCAL" ]]; then
        verify_with_sidecar "$LOCAL_APPIMAGE" "$APP_SUM_LOCAL" || die "Local AppImage SHA-256 verification failed."
    else
        warn "No local AppImage SHA256 sidecar found; continuing with the local payload."
    fi
    if [[ -f "$AGENT_SUM_LOCAL" ]]; then
        verify_with_sidecar "$LOCAL_AGENT" "$AGENT_SUM_LOCAL" || die "Local Update Agent SHA-256 verification failed."
    else
        warn "No local Update Agent SHA256 sidecar found; continuing with the local payload."
    fi
fi

[[ -f "$LOCAL_APPIMAGE" ]] || die "AppImage payload missing."
[[ -f "$LOCAL_AGENT" ]] || die "Update Agent payload missing."

log "Installing to: $INSTALL_DIR"
install_payload
configure_agent

if "$AGENT_TARGET" --autostart-enabled; then
    nohup "$AGENT_TARGET" --background >/dev/null 2>&1 &
fi

log "Installation complete."
log "GMM: $APPIMAGE_TARGET"
log "Update Agent: $AGENT_TARGET"
log "Desktop entry: $DESKTOP_FILE"
