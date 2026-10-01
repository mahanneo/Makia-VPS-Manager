#!/usr/bin/env bash
set -Eeuo pipefail

REPO="mahanneo/Makia-VPS-Manager"
REF="${MAKIA_REF:-${DRAGON_REF:-main}}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

if [[ ! "$REF" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid MAKIA_REF: $REF" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
missing=()
for cmd in curl tar; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if (( ${#missing[@]} > 0 )); then
  apt-get -o DPkg::Lock::Timeout=120 update
  apt-get -o DPkg::Lock::Timeout=120 install -y curl ca-certificates tar gzip
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# codeload accepts branches (including names with /), tags and exact commit SHAs.
# This is required by the frozen-UAT workflow where MAKIA_REF is a commit SHA.
ARCHIVE_URL="https://codeload.github.com/${REPO}/tar.gz/${REF}"
echo "[MAKIA] Downloading ${REPO}@${REF} ..."
curl -fL \
  --retry 5 --retry-all-errors --retry-delay 2 \
  --connect-timeout 20 --max-time 300 \
  "$ARCHIVE_URL" -o "$TMP/source.tar.gz"

tar -tzf "$TMP/source.tar.gz" >/dev/null
tar -xzf "$TMP/source.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d -name 'Makia-VPS-Manager-*' | head -n1)"
[[ -n "$SRC" && -r "$SRC/scripts/install.sh" ]] || {
  echo "Unable to locate a valid Makia source archive for ref: $REF" >&2
  exit 3
}

MAKIA_INSTALL_SOURCE_REF="$REF" bash "$SRC/scripts/install.sh"
