#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
ROOT=/opt/makia-mtproxy
ENV_FILE=/etc/makia-vps-manager/mtproxy.env

test -x "$ROOT/mtg" || { echo "mtg is not installed; run sudo makia-install-mtproxy first." >&2; exit 2; }
test -s "$ENV_FILE" || { echo "MTProxy configuration is missing." >&2; exit 3; }

# shellcheck disable=SC1090
source "$ENV_FILE"
[[ "${MTPROXY_SECRET:-}" =~ ^ee[0-9a-fA-F]+$ ]] || { echo "Invalid mtg FakeTLS secret." >&2; exit 4; }
[[ "${MTPROXY_PORT:-}" =~ ^[0-9]+$ ]] || { echo "Invalid MTProxy port." >&2; exit 4; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
cat >"$tmp" <<EOF
secret = "${MTPROXY_SECRET}"
bind-to = "0.0.0.0:${MTPROXY_PORT}"

[network]
dns = "https://1.1.1.1"
EOF

"$ROOT/mtg" doctor "$tmp"
systemctl restart makia-mtproxy
systemctl is-active --quiet makia-mtproxy
ss -H -ltn | grep -Eq ":${MTPROXY_PORT}([[:space:]]|$)"
echo "Telegram MTProxy doctor PASS; runtime restarted."
