#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
ROOT=/opt/makia-mtproxy
STATE_FILE=/etc/makia-vps-manager/mtproxy.env
CONFIG_FILE=/etc/makia-vps-manager/mtproxy.toml

test -x "$ROOT/mtg" || { echo "mtg is not installed; run sudo makia-install-mtproxy first." >&2; exit 2; }
test -s "$STATE_FILE" || { echo "MTProxy state is missing." >&2; exit 3; }
test -s "$CONFIG_FILE" || { echo "MTProxy config is missing." >&2; exit 3; }

"$ROOT/mtg" doctor "$CONFIG_FILE"
systemctl restart makia-mtproxy
systemctl is-active --quiet makia-mtproxy

# shellcheck disable=SC1090
source "$STATE_FILE"
[[ "${MTPROXY_PORT:-}" =~ ^[0-9]+$ ]] || { echo "Invalid MTProxy port." >&2; exit 4; }
ss -H -ltn | grep -Eq ":${MTPROXY_PORT}([[:space:]]|$)"
echo "Telegram MTProxy doctor PASS; runtime restarted."
