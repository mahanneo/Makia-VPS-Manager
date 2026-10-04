#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/makia-vps-manager
ENV_FILE=/etc/makia-vps-manager/makia.env
SERVICE=makia-browser-gateway

if [[ -r "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    case "$key" in
      MAKIA_BROWSER_GATEWAY_ENABLED|MAKIA_BROWSER_GATEWAY_HOST|MAKIA_BROWSER_GATEWAY_PORT|MAKIA_BROWSER_GATEWAY_BIND|MAKIA_BROWSER_GATEWAY_CERT|MAKIA_BROWSER_GATEWAY_KEY|MAKIA_BROWSER_GATEWAY_MAX_CONNECTIONS)
        printf -v "$key" '%s' "$value"
        export "$key"
        ;;
    esac
  done <"$ENV_FILE"
fi

[[ -x "$APP/.venv/bin/python" ]] || { echo "Makia Python runtime not ready."; exit 2; }

CFG="$(
  cd "$APP"
  MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
import json
from app.browser_gateway import gateway_config
print(json.dumps(gateway_config(),separators=(",",":")))
PY
)"

readarray -t PARTS < <(python3 - "$CFG" <<'PY'
import json,sys
cfg=json.loads(sys.argv[1])
print("1" if cfg.get("enabled") else "0")
print(cfg.get("host") or "")
print(int(cfg.get("port") or 0))
print(cfg.get("cert") or "")
print(cfg.get("key") or "")
PY
)
ENABLED="${PARTS[0]:-0}"
HOST="${PARTS[1]:-}"
PORT="${PARTS[2]:-0}"
CERT="${PARTS[3]:-}"
KEY="${PARTS[4]:-}"

if [[ "$ENABLED" != "1" ]]; then
  systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
  echo "Makia Browser Gateway disabled by configuration."
  exit 0
fi

if [[ -z "$HOST" || "$PORT" -lt 1 || ! -s "$CERT" || ! -s "$KEY" ]]; then
  systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
  echo "Makia Browser Gateway not activated: public HTTPS domain/certificate is not ready."
  echo "Host=${HOST:-unset} Port=${PORT:-unset} Cert=${CERT:-unset}"
  exit 0
fi

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  ufw allow "${PORT}/tcp" comment 'Makia Browser Gateway' >/dev/null || true
fi

systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

for _ in {1..15}; do
  if systemctl is-active --quiet "$SERVICE" && ss -H -ltn 2>/dev/null | grep -Eq ":${PORT}([[:space:]]|$)"; then
    echo "Makia Browser Gateway READY: https://${HOST}:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "Makia Browser Gateway failed to become ready." >&2
systemctl status "$SERVICE" --no-pager -l >&2 || true
journalctl -u "$SERVICE" -n 40 --no-pager >&2 || true
exit 3
