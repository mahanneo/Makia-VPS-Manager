#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }

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

export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io ca-certificates curl
fi
systemctl enable --now docker

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

OUTLINE_TAG="server-v1.12.0"
OUTLINE_INSTALL_URL="https://raw.githubusercontent.com/OutlineFoundation/outline-server/${OUTLINE_TAG}/src/server_manager/install_scripts/install_server.sh"
curl --fail --show-error --silent --location "$OUTLINE_INSTALL_URL" -o "$TMP"
chmod 0700 "$TMP"

args=()
[[ -n "$HOSTNAME_ARG" ]] && args+=(--hostname "$HOSTNAME_ARG")
(( KEYS_PORT > 0 )) && args+=(--keys-port "$KEYS_PORT")

bash "$TMP" "${args[@]}"

if [[ ! -s /opt/outline/access.txt ]]; then
  echo "Outline installer completed but /opt/outline/access.txt is missing." >&2
  exit 1
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
echo "Pinned installer release: ${OUTLINE_TAG}"
