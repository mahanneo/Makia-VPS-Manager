#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }

OUTLINE_VERSION="server-v1.12.0"
OUTLINE_INSTALL_URL="https://raw.githubusercontent.com/OutlineFoundation/outline-server/${OUTLINE_VERSION}/src/server_manager/install_scripts/install_server.sh"
# Git blob SHA for the exact official installer bytes above. Update only together with OUTLINE_VERSION.
OUTLINE_GIT_BLOB_SHA="39ba2b0d4ed6cb60ef94bc6015fcc619f092633b"

HOSTNAME_ARG=""
KEYS_PORT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname)
      HOSTNAME_ARG="${2:-}"
      shift 2
      ;;
    --keys-port)
      KEYS_PORT="${2:-0}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$HOSTNAME_ARG" ]] && [[ ! "$HOSTNAME_ARG" =~ ^[A-Za-z0-9.:-]{1,255}$ ]]; then
  echo "Invalid hostname." >&2
  exit 2
fi
if [[ "$KEYS_PORT" != "0" ]] && { ! [[ "$KEYS_PORT" =~ ^[0-9]+$ ]] || (( KEYS_PORT < 1 || KEYS_PORT > 65535 )); }; then
  echo "Invalid keys port." >&2
  exit 2
fi

if [[ -s /opt/outline/access.txt ]]; then
  chmod 0700 /opt/outline || true
  chmod 0600 /opt/outline/access.txt || true
  echo "Outline is already configured at /opt/outline/access.txt"
  exit 0
fi
if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Fxq shadowbox; then
  echo "A shadowbox container exists but /opt/outline/access.txt is missing. Resolve or import the existing Outline state before setup." >&2
  exit 3
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io ca-certificates curl
fi
systemctl enable --now docker

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
curl --fail --show-error --silent --location --retry 3 "$OUTLINE_INSTALL_URL" -o "$TMP"

ACTUAL_GIT_BLOB_SHA="$(python3 - "$TMP" <<'PY'
import hashlib
import sys
data=open(sys.argv[1],"rb").read()
print(hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest())
PY
)"
if [[ "$ACTUAL_GIT_BLOB_SHA" != "$OUTLINE_GIT_BLOB_SHA" ]]; then
  echo "Pinned Outline installer integrity check failed." >&2
  echo "Expected git blob: $OUTLINE_GIT_BLOB_SHA" >&2
  echo "Actual git blob:   $ACTUAL_GIT_BLOB_SHA" >&2
  exit 4
fi
chmod 0700 "$TMP"

args=()
[[ -n "$HOSTNAME_ARG" ]] && args+=(--hostname "$HOSTNAME_ARG")
(( KEYS_PORT > 0 )) && args+=(--keys-port "$KEYS_PORT")

bash "$TMP" "${args[@]}"

if [[ ! -s /opt/outline/access.txt ]]; then
  echo "Outline installer completed but /opt/outline/access.txt is missing." >&2
  exit 5
fi
chmod 0700 /opt/outline || true
chmod 0600 /opt/outline/access.txt || true

if (( KEYS_PORT > 0 )) && command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
  ufw allow "${KEYS_PORT}/tcp" comment 'Makia Outline' >/dev/null
  ufw allow "${KEYS_PORT}/udp" comment 'Makia Outline' >/dev/null
fi

echo
echo "Outline Server is installed and connected to Makia."
echo "State: /opt/outline"
echo "Access config: /opt/outline/access.txt"
echo "Pinned installer release: ${OUTLINE_VERSION}"
echo "Pinned installer git blob: ${OUTLINE_GIT_BLOB_SHA}"
