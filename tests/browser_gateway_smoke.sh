#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/makia-vps-manager
DOMAIN=localhost
CERT_DIR=/etc/letsencrypt/live/$DOMAIN
PORT="${MAKIA_BROWSER_GATEWAY_PORT:-9444}"

cleanup(){
  (
    cd "$APP"
    MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app.db import set_setting
set_setting("panel_domain","")
PY
  ) || true
  systemctl restart makia-browser-gateway 2>/dev/null || true
  rm -rf "$CERT_DIR"
}
trap cleanup EXIT

install -d -m 0755 "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 1   -subj "/CN=$DOMAIN"   -keyout "$CERT_DIR/privkey.pem"   -out "$CERT_DIR/fullchain.pem" >/dev/null 2>&1
chmod 0600 "$CERT_DIR/privkey.pem"
chmod 0644 "$CERT_DIR/fullchain.pem"

CREDS="$(
  cd "$APP"
  MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import client_store
from app.db import set_setting

set_setting("panel_domain","localhost")
client_store.init_client_db()
try:
    account_id=client_store.create_account(
        "browser-smoke","BrowserSmokePass!150",
        display_name="Browser Smoke",quota_bytes=10*1024*1024,
        device_limit=1,concurrent_device_limit=1,
    )
except Exception:
    account_id=client_store.account_by_username("browser-smoke")["id"]
device,device_key=client_store.register_or_get_device(
    account_id,label="Browser Smoke",platform="browser-extension",ip="127.0.0.1",
)
session_token,expires=client_store.create_session(account_id,device["id"],"127.0.0.1",3600)
session=client_store.session_by_token(session_token,"127.0.0.1")
proxy=client_store.issue_browser_proxy_token(session,3600)
print(proxy["username"])
print(proxy["password"])
print(session_token)
print(account_id)
PY
)"
mapfile -t PARTS <<<"$CREDS"
USER="${PARTS[0]}"
PASS="${PARTS[1]}"
SESSION="${PARTS[2]}"
ACCOUNT="${PARTS[3]}"

systemctl restart makia-browser-gateway
for _ in {1..20}; do
  if ss -H -ltn | awk '{print $4}' | grep -Eq "(^|:|\])${PORT}$"; then break; fi
  sleep 1
done
ss -H -ltn | awk '{print $4}' | grep -Eq "(^|:|\])${PORT}$"

curl --fail --silent --show-error --max-time 20   --proxy-insecure   --proxy "https://127.0.0.1:$PORT"   --proxy-user "$USER:$PASS"   "https://example.com/" >/tmp/makia-browser-gateway-example.html
grep -qi '<html' /tmp/makia-browser-gateway-example.html

USAGE="$(
  cd "$APP"
  MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - "$ACCOUNT" <<'PY'
import sys
from app import client_store
print(client_store.browser_usage_bytes(int(sys.argv[1])))
PY
)"
test "$USAGE" -gt 0

(
  cd "$APP"
  MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - "$SESSION" <<'PY'
import sys
from app import client_store
client_store.revoke_session(sys.argv[1])
PY
)

set +e
curl --silent --show-error --max-time 10   --proxy-insecure   --proxy "https://127.0.0.1:$PORT"   --proxy-user "$USER:$PASS"   "https://example.com/" >/tmp/makia-browser-revoked.out 2>/tmp/makia-browser-revoked.err
RC=$?
set -e
test "$RC" -ne 0

echo "PURE BROWSER GATEWAY SMOKE: PASS (usage=$USAGE bytes, revoked credential rejected)"
