#!/usr/bin/env bash
set -Eeuo pipefail

REPO="mahanneo/Makia-VPS-Manager"
REF="${MAKIA_REF:-main}"
APP_VERSION_FILE=/opt/makia-vps-manager/VERSION
ENV_FILE=/etc/makia-vps-manager/makia.env

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo makia-upgrade" >&2
  exit 1
fi

CURRENT_VERSION="$(tr -d '[:space:]' < "$APP_VERSION_FILE" 2>/dev/null || true)"
[[ "$CURRENT_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "Unable to verify the installed Makia version; refusing an unverified upgrade." >&2
  exit 2
}

ARCHIVE_CONFIGURED=0
if [[ -r "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" == "MAKIA_RELEASE_ARCHIVE_URL" ]] || continue
    value="${value%$'\r'}"
    value="${value#\"}"
    value="${value%\"}"
    value="${value#\'}"
    value="${value%\'}"
    [[ -n "${value//[[:space:]]/}" ]] && ARCHIVE_CONFIGURED=1
  done < "$ENV_FILE"
fi

if [[ "$ARCHIVE_CONFIGURED" != "1" && "${MAKIA_FORCE_MAIN:-0}" != "1" ]]; then
  REMOTE_VERSION="$(curl -fsSL --retry 2 --max-time 10 "https://raw.githubusercontent.com/${REPO}/${REF}/VERSION" | tr -d '[:space:]')" || {
    echo "Unable to verify the published VERSION from GitHub; refusing an unverified upgrade." >&2
    exit 2
  }
  [[ "$REMOTE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "The published VERSION is invalid; refusing an unverified upgrade." >&2
    exit 2
  }
  if [[ "$REMOTE_VERSION" == "$CURRENT_VERSION" ]]; then
    echo "Makia $CURRENT_VERSION is already installed; no newer public release is available. No changes made."
    exit 0
  fi
  SORTED_NEWEST="$(printf '%s\n%s\n' "$CURRENT_VERSION" "$REMOTE_VERSION" | sort -V | tail -n1)"
  if [[ "$SORTED_NEWEST" != "$REMOTE_VERSION" ]]; then
    echo "Refusing downgrade: installed=$CURRENT_VERSION published=$REMOTE_VERSION." >&2
    echo "The public release is behind this local maintenance build. Publish a newer release or configure the intended release archive before upgrading. No changes made." >&2
    exit 3
  fi
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "Fetching the latest Makia updater from ${REPO}@${REF}..."
curl -fL --retry 3 --max-time 30 "https://raw.githubusercontent.com/${REPO}/${REF}/scripts/update.sh" -o "$TMP"
chmod 0700 "$TMP"
bash "$TMP"
