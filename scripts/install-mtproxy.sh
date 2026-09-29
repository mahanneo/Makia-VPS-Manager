#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }

MTPROXY_COMMIT="f36d8af769ffaeac36978d38c2c0f6d1104c2137"
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
apt-get install -y git curl ca-certificates build-essential libssl-dev zlib1g-dev xxd

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -c advice.detachedHead=false clone --quiet https://github.com/TelegramMessenger/MTProxy.git "$tmp/src"
git -C "$tmp/src" checkout --quiet "$MTPROXY_COMMIT"
actual="$(git -C "$tmp/src" rev-parse HEAD)"
[[ "$actual" == "$MTPROXY_COMMIT" ]] || { echo "Pinned MTProxy commit mismatch." >&2; exit 3; }

make -C "$tmp/src" -j"$(nproc)"
test -x "$tmp/src/objs/bin/mtproto-proxy"

install -d -m 0755 "$ROOT"
install -m 0755 "$tmp/src/objs/bin/mtproto-proxy" "$ROOT/mtproto-proxy"

curl -fsSL --retry 3 https://core.telegram.org/getProxySecret -o "$ROOT/proxy-secret"
curl -fsSL --retry 3 https://core.telegram.org/getProxyConfig -o "$ROOT/proxy-multi.conf"
test -s "$ROOT/proxy-secret"
test -s "$ROOT/proxy-multi.conf"
chmod 0644 "$ROOT/proxy-secret" "$ROOT/proxy-multi.conf"

install -d -m 0700 /etc/makia-vps-manager
if [[ ! -s "$ENV_FILE" ]]; then
  if [[ -z "$HOST" ]]; then
    HOST="$(hostname -f 2>/dev/null || true)"
    [[ "$HOST" == *.* ]] || HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  [[ -n "$HOST" ]] || { echo "Unable to determine public host. Re-run with --host." >&2; exit 4; }

  selected="$(python3 - "$PORT" <<'PY'
import socket,sys
requested=int(sys.argv[1] or 0)
candidates=[requested,443,8443,9443,10443,11443,12443,2053,2087,13010]
seen=[]
for p in candidates:
    if not p or p in seen: continue
    seen.append(p)
    s=socket.socket()
    try:
        s.bind(("0.0.0.0",p))
    except OSError:
        s.close(); continue
    s.close()
    print(p);raise SystemExit
raise SystemExit("No free TCP MTProxy port found")
PY
)"
  stats="$(python3 - <<'PY'
import socket
for p in (8888,8889,8890,8891,18888):
    s=socket.socket()
    try:s.bind(("0.0.0.0",p))
    except OSError:s.close();continue
    s.close();print(p);break
else:raise SystemExit("No free MTProxy stats port")
PY
)"
  secret="$(openssl rand -hex 16)"
  cat >"$ENV_FILE" <<EOF
MTPROXY_PUBLIC_HOST=$HOST
MTPROXY_PORT=$selected
MTPROXY_STATS_PORT=$stats
MTPROXY_SECRET=$secret
EOF
  chmod 0600 "$ENV_FILE"
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$source_dir/systemd/makia-mtproxy.service" ]]; then
  install -m 0644 "$source_dir/systemd/makia-mtproxy.service" /etc/systemd/system/makia-mtproxy.service
elif [[ -f /etc/systemd/system/makia-mtproxy.service ]]; then
  : # Installed by makia-install/makia-update before this optional component.
elif [[ -f /opt/makia-vps-manager/systemd/makia-mtproxy.service ]]; then
  install -m 0644 /opt/makia-vps-manager/systemd/makia-mtproxy.service /etc/systemd/system/makia-mtproxy.service
else
  echo "Makia MTProxy service unit not found. Run sudo makia-upgrade first." >&2; exit 5
fi

systemctl daemon-reload
systemctl enable --now makia-mtproxy
systemctl restart makia-mtproxy
sleep 1
systemctl is-active --quiet makia-mtproxy || { systemctl status makia-mtproxy --no-pager --lines=30; exit 6; }

# shellcheck disable=SC1090
source "$ENV_FILE"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
  ufw allow "${MTPROXY_PORT}/tcp" comment 'Makia Telegram MTProxy' >/dev/null
fi

client_secret="dd${MTPROXY_SECRET}"
echo "MTProxy installed from pinned official commit: $MTPROXY_COMMIT"
echo "Service: makia-mtproxy"
echo "tg://proxy?server=${MTPROXY_PUBLIC_HOST}&port=${MTPROXY_PORT}&secret=${client_secret}"
echo "https://t.me/proxy?server=${MTPROXY_PUBLIC_HOST}&port=${MTPROXY_PORT}&secret=${client_secret}"
