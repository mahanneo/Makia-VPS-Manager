#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root: sudo bash install.sh DOMAIN EMAIL'; exit 1; }
[[ $# -eq 2 ]] || { echo 'Usage: sudo bash install.sh vpn.example.org admin@example.org'; exit 2; }
[[ ! -e /opt/makia-vps-manager/data/makia.db && ! -e /etc/wireguard/wg0.conf && ! -e /etc/openvpn/server/server.conf && ! -e /opt/outline/access.txt ]] || { echo 'Existing VPN or Makia installation found. Use a fresh VPS; do not overwrite existing state.'; exit 3; }
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[[ $1 =~ ^[A-Za-z0-9.-]+$ ]] || { echo 'Invalid domain'; exit 2; }
[[ $2 == *@* ]] || { echo 'Email required'; exit 2; }
export MAKIA_ENABLE_OUTLINE=1 MAKIA_CLIENT_PORTAL_ENABLED=1
bash "$ROOT/scripts/install.sh"
bash "$ROOT/configure.sh" "$1" "$2"
