#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="${WSTUNNEL_VERSION:-11.0.0}"
DEST="${WSTUNNEL_DEST:-/usr/local/bin/wstunnel}"
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64|amd64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  i386|i686) ARCH=386 ;;
  *) echo "Unsupported wstunnel architecture: $ARCH_RAW" >&2; exit 2 ;;
esac

NAME="wstunnel_${VERSION}_linux_${ARCH}.tar.gz"
BASE="https://github.com/erebe/wstunnel/releases/download/v${VERSION}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL --retry 3 "$BASE/$NAME" -o "$TMP/$NAME"
curl -fsSL --retry 3 "$BASE/checksums.txt" -o "$TMP/checksums.txt"
EXPECTED="$(awk -v n="$NAME" '$2==n || $2=="*"n {print $1; exit}' "$TMP/checksums.txt")"
[[ -n "$EXPECTED" ]] || { echo "Checksum for $NAME not found" >&2; exit 3; }
ACTUAL="$(sha256sum "$TMP/$NAME" | awk '{print $1}')"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "wstunnel checksum mismatch" >&2; exit 4; }

tar -xzf "$TMP/$NAME" -C "$TMP"
BIN="$(find "$TMP" -type f -name wstunnel | head -n1)"
[[ -n "$BIN" ]] || { echo "wstunnel binary not found in release archive" >&2; exit 5; }
install -m 0755 "$BIN" "$DEST"
"$DEST" --version
