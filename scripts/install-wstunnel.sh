#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="11.0.0"
case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Unsupported wstunnel architecture: $(uname -m)" >&2; exit 2 ;;
esac
if command -v wstunnel >/dev/null 2>&1 && wstunnel --version 2>/dev/null | grep -q "11.0.0"; then exit 0; fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
BASE="https://github.com/erebe/wstunnel/releases/download/v${VERSION}"
ASSET="wstunnel_${VERSION}_linux_${ARCH}.tar.gz"
curl -fsSL --retry 3 "$BASE/$ASSET" -o "$TMP/$ASSET"
curl -fsSL --retry 3 "$BASE/checksums.txt" -o "$TMP/checksums.txt"
(
  cd "$TMP"
  grep "  $ASSET$" checksums.txt | sha256sum -c -
)
tar -xzf "$TMP/$ASSET" -C "$TMP"
BIN="$(find "$TMP" -maxdepth 2 -type f -name wstunnel | head -n1)"
[[ -n "$BIN" ]] || { echo "wstunnel binary missing from release asset" >&2; exit 3; }
install -m 0755 "$BIN" /usr/local/bin/wstunnel
/usr/local/bin/wstunnel --version
