#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${GMM_INSTALL_DIR:-$HOME/.local/opt/genshin-mod-manager}"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
AGENT="$INSTALL_DIR/GMMUpdateAgent"

if [[ -x "$AGENT" ]]; then
    "$AGENT" --write-config --autostart no >/dev/null 2>&1 || true
    "$AGENT" --shutdown >/dev/null 2>&1 || true
    sleep 1
fi

rm -f -- "$CONFIG_HOME/autostart/gmm-update-agent.desktop"
rm -f -- "$APPLICATIONS_DIR/genshin-mod-manager.desktop"
rm -f -- "$HOME/.local/bin/genshin-mod-manager"

pkill -u "$(id -u)" -f "$INSTALL_DIR/GMMUpdateAgent" 2>/dev/null || true
rm -rf -- "$INSTALL_DIR"
rm -rf -- "$CACHE_HOME/genshin-mod-manager/update-agent"

printf 'Genshin Mod Manager and the Linux Update Agent were removed.\n'
printf 'User settings were kept in: %s\n' "$CONFIG_HOME/genshin-mod-manager"
printf 'Delete that directory manually if you also want to remove settings.\n'
