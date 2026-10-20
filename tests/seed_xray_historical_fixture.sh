#!/usr/bin/env bash
# Historical v1.3/v1.5 fixtures are immutable and fetch mutable XTLS/main.
# Seed the exact compatible Xray engine on isolated CI Docker guests BEFORE
# baseline install, then exercise real baseline->target update as before.
set -Eeuo pipefail
if [[ ! -f /run/.containerenv && ! -f /.dockerenv ]]; then
  echo "CI fixture must run inside a disposable container" >&2
  exit 2
fi
tmp="$(mktemp /tmp/makia-xray-fixture-XXXXXX.sh)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL --retry 3 --output "$tmp"   https://raw.githubusercontent.com/XTLS/Xray-install/e741a4f56d368afbb9e5be3361b40c4552d3710d/install-release.sh
bash -n "$tmp"
bash "$tmp" install --version v26.3.27 -u nobody
test -x /usr/local/bin/xray
systemctl is-active --quiet xray
