#!/usr/bin/env bash
set -euo pipefail

OUTLINE_VERSION="server-v1.12.0"
OUTLINE_SCRIPT_URL="https://raw.githubusercontent.com/OutlineFoundation/outline-server/${OUTLINE_VERSION}/src/server_manager/install_scripts/install_server.sh"
OUTLINE_GIT_BLOB_SHA="39ba2b0d4ed6cb60ef94bc6015fcc619f092633b"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Run: sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade" >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  systemctl enable --now docker
fi
if [[ -s /opt/outline/access.txt ]]; then
  echo "Outline is already configured at /opt/outline/access.txt"
  exit 0
fi
if docker ps -a --format '{{.Names}}' | grep -Fxq shadowbox; then
  echo "A shadowbox container already exists but Makia has no Outline access.txt. Resolve/import it manually before setup." >&2
  exit 3
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL --retry 3 "$OUTLINE_SCRIPT_URL" -o "$tmp"
actual="$(python3 - "$tmp" <<'PY'
import hashlib,sys
data=open(sys.argv[1],"rb").read()
print(hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest())
PY
)"
if [[ "$actual" != "$OUTLINE_GIT_BLOB_SHA" ]]; then
  echo "Pinned Outline installer integrity check failed." >&2
  echo "Expected git blob: $OUTLINE_GIT_BLOB_SHA" >&2
  echo "Actual git blob:   $actual" >&2
  exit 4
fi
chmod 0700 "$tmp"
mkdir -p /opt/outline
chmod 0770 /opt/outline

"$tmp" "$@"

if [[ ! -s /opt/outline/access.txt ]]; then
  echo "Outline installation did not produce /opt/outline/access.txt" >&2
  exit 5
fi
chmod 0660 /opt/outline/access.txt || true
echo "Outline installation completed. Makia can now manage access keys."
