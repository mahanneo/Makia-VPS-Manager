#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
ROOT=/opt/makia-mtproxy
test -x "$ROOT/mtproto-proxy"
tmp_secret="$(mktemp)"
tmp_config="$(mktemp)"
trap 'rm -f "$tmp_secret" "$tmp_config"' EXIT
curl -fsSL --retry 3 https://core.telegram.org/getProxySecret -o "$tmp_secret"
curl -fsSL --retry 3 https://core.telegram.org/getProxyConfig -o "$tmp_config"
test -s "$tmp_secret"; test -s "$tmp_config"
install -m 0644 "$tmp_secret" "$ROOT/proxy-secret"
install -m 0644 "$tmp_config" "$ROOT/proxy-multi.conf"
systemctl restart makia-mtproxy
systemctl is-active --quiet makia-mtproxy
