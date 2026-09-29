#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }

MTG_VERSION="2.2.8"
ROOT="/opt/makia-mtproxy"
ENV_FILE="/etc/makia-vps-manager/mtproxy.env"
HOST=""
PORT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --port) PORT="${2:-0}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$HOST" ]] && [[ ! "$HOST" =~ ^[A-Za-z0-9.:-]{1,253}$ ]]; then
  echo "Invalid MTProxy host." >&2; exit 2
fi
if [[ "$PORT" != "0" ]] && { ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); }; then
  echo "Invalid MTProxy port." >&2; exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl ca-certificates

case "$(uname -m)" in
  x86_64|amd64)
    ARCH="amd64"
    EXPECTED="7ef19d079d85f4e00d4f8334ec1f3f3c8718e3d0ed1f3109ea9a8673138a2102"
    ;;
  aarch64|arm64)
    ARCH="arm64"
    EXPECTED="562a94dd4cafcb8f179b76cfeafb76da12747c8e230bc76235bf8746cc189644"
    ;;
  *)
    echo "Unsupported mtg architecture: $(uname -m)" >&2
    exit 3
    ;;
esac

NAME="mtg-${MTG_VERSION}-linux-${ARCH}.tar.gz"
URL="https://github.com/9seconds/mtg/releases/download/v${MTG_VERSION}/${NAME}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 "$URL" -o "$tmp/$NAME"
actual="$(sha256sum "$tmp/$NAME" | awk '{print $1}')"
[[ "$actual" == "$EXPECTED" ]] || {
  echo "mtg release checksum mismatch." >&2
  echo "Expected: $EXPECTED" >&2
  echo "Actual:   $actual" >&2
  exit 4
}
tar -xzf "$tmp/$NAME" -C "$tmp"
bin="$(find "$tmp" -type f -name mtg -perm -u+x | head -n1)"
[[ -n "$bin" ]] || { echo "mtg binary not found in verified release." >&2; exit 5; }

install -d -m 0755 "$ROOT"
install -m 0755 "$bin" "$ROOT/mtg"
"$ROOT/mtg" --version | grep -F "2.2.8" >/dev/null

install -d -m 0700 /etc/makia-vps-manager
if [[ ! -s "$ENV_FILE" ]]; then
  if [[ -z "$HOST" ]]; then
    HOST="$(hostname -f 2>/dev/null || true)"
    [[ "$HOST" == *.* ]] || HOST=""
  fi
  [[ -n "$HOST" ]] || {
    echo "A DNS hostname pointing to this VPS is required for the initial FakeTLS secret." >&2
    echo "Re-run with: sudo makia-install-mtproxy --host proxy.example.com" >&2
    exit 6
  }

  selected="$(python3 - "$PORT" <<'PY'
import socket,sys
requested=int(sys.argv[1] or 0)
candidates=[requested,443,8443,9443,10443,11443,12443,2053,2087,13010]
seen=[]
for p in candidates:
    if not p or p in seen: continue
    seen.append(p)
    s=socket.socket()
    try:s.bind(("0.0.0.0",p))
    except OSError:s.close();continue
    s.close();print(p);raise SystemExit
raise SystemExit("No free TCP Telegram proxy port found")
PY
)"
  secret="$("$ROOT/mtg" generate-secret --hex "$HOST")"
  [[ "$secret" =~ ^ee[0-9a-fA-F]+$ ]] || { echo "mtg returned an invalid FakeTLS secret." >&2; exit 7; }

  cat >"$ENV_FILE" <<EOF
MTPROXY_PUBLIC_HOST=$HOST
MTPROXY_PORT=$selected
MTPROXY_FRONT_DOMAIN=$HOST
MTPROXY_SECRET=$secret
EOF
  chmod 0600 "$ENV_FILE"
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$source_dir/systemd/makia-mtproxy.service" ]]; then
  install -m 0644 "$source_dir/systemd/makia-mtproxy.service" /etc/systemd/system/makia-mtproxy.service
elif [[ -f /etc/systemd/system/makia-mtproxy.service ]]; then
  :
elif [[ -f /opt/makia-vps-manager/systemd/makia-mtproxy.service ]]; then
  install -m 0644 /opt/makia-vps-manager/systemd/makia-mtproxy.service /etc/systemd/system/makia-mtproxy.service
else
  echo "Makia MTProxy service unit not found. Run sudo makia-upgrade first." >&2; exit 8
fi

systemctl daemon-reload
systemctl enable --now makia-mtproxy
systemctl restart makia-mtproxy
sleep 1
systemctl is-active --quiet makia-mtproxy || {
  systemctl status makia-mtproxy --no-pager --lines=30
  exit 9
}

# shellcheck disable=SC1090
source "$ENV_FILE"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
  ufw allow "${MTPROXY_PORT}/tcp" comment 'Makia Telegram MTProxy' >/dev/null
fi

echo "Telegram MTProxy installed with mtg v${MTG_VERSION}."
echo "https://t.me/proxy?server=${MTPROXY_PUBLIC_HOST}&port=${MTPROXY_PORT}&secret=${MTPROXY_SECRET}"
