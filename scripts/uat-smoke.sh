#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/makia-vps-manager
FAIL=0

ok(){ printf '✓ %s\n' "$1"; }
bad(){ printf '✗ %s\n' "$1"; FAIL=1; }
xray_bad(){ bad "$1"; }
ovpn_bad(){ bad "$1"; }
wg_bad(){ bad "$1"; }

[[ -d "$APP" ]] || { bad "Makia runtime missing at $APP"; exit 1; }

printf '\nMakia host smoke\n'
printf '%s\n' '---------------------'

VERSION="$(cat "$APP/VERSION" 2>/dev/null || true)"
[[ -n "$VERSION" ]] && ok "Version: $VERSION" || bad "VERSION missing"

if curl -fsS --max-time 4 http://127.0.0.1:8787/healthz >/tmp/makia-health.json; then
  ok "Backend health endpoint"
else
  bad "Backend health endpoint"
fi

if nginx -t >/dev/null 2>&1; then ok "Nginx config"; else bad "Nginx config"; fi

PANEL_DOMAIN="$(
  cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app.db import get_setting
print((get_setting("panel_domain","") or "").strip())
PY
)"
if [[ -n "$PANEL_DOMAIN" ]]; then
  CERT="/etc/letsencrypt/live/$PANEL_DOMAIN/fullchain.pem"
  if [[ -s "$CERT" ]]; then
    ok "HTTPS certificate present for $PANEL_DOMAIN"
  else
    bad "HTTPS certificate missing for configured domain $PANEL_DOMAIN"
  fi
  if ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:|\])443$'; then
    ok "HTTPS listener TCP/443"
  else
    bad "HTTPS listener TCP/443 missing"
  fi
  if curl -fsS --max-time 8 --resolve "$PANEL_DOMAIN:443:127.0.0.1" "https://$PANEL_DOMAIN/healthz" >/tmp/makia-https-health.json; then
    ok "HTTPS domain health ($PANEL_DOMAIN)"
  else
    bad "HTTPS domain health failed for $PANEL_DOMAIN"
  fi
else
  ok "Panel domain not configured; HTTPS domain gate skipped (IP mode)"
fi

for svc in makia-vps-manager makia-policy-enforcer makia-metrics-sampler makia-protocol-traffic nginx fail2ban; do
  if systemctl is-active --quiet "$svc"; then ok "Service $svc"; else bad "Service $svc"; fi
done

for timer in makia-scheduled-backup.timer makia-ops-monitor.timer; do
  if systemctl is-enabled --quiet "$timer" && systemctl is-active --quiet "$timer"; then
    ok "Timer $timer"
  else
    bad "Timer $timer is not enabled/active"
  fi
done

if [[ -s /opt/outline/access.txt ]]; then
  if command -v docker >/dev/null 2>&1 && docker inspect -f '{{.State.Running}}' shadowbox 2>/dev/null | grep -qx true; then
    ok "Outline shadowbox container"
  else
    bad "Outline configured but shadowbox container is not running"
  fi
  if ( cd "$APP" && "$APP/.venv/bin/python" - <<'PY'
from app import integration_ops
state=integration_ops.outline_status()
assert state.get("api_ok"), state.get("error") or state
print(state.get("key_count",0))
PY
  ) >/tmp/makia-outline-health.txt 2>&1; then
    ok "Outline Management API + certificate fingerprint"
  else
    bad "Outline Management API/fingerprint check"
    sed -n '1,8p' /tmp/makia-outline-health.txt || true
  fi
else
  ok "Outline not installed; live Outline gate skipped"
fi

if ( cd "$APP" && "$APP/.venv/bin/python" - <<'PY'
from app import access_ops
from app.db import connect
from app.config import SECRET_PATH
import os, stat

with connect() as con:
    result=con.execute("PRAGMA integrity_check").fetchone()[0]
assert str(result).lower()=="ok", result

assert SECRET_PATH.exists(), "server secret missing"
mode=stat.S_IMODE(os.stat(SECRET_PATH).st_mode)
assert mode==0o600, oct(mode)

blob=access_ops.protected_zip({"probe.txt":b"makia-self-test"},"582941")
result=access_ops.verify_protected_zip(blob,"582941","probe.txt")
assert result["ok"]
assert result["sample_size"]==15
print("storage/crypto PASS")
PY
)
then
  ok "SQLite integrity + secret permission + AES ZIP"
else
  bad "SQLite integrity / crypto smoke"
fi

if ( cd "$APP" && "$APP/.venv/bin/python" -c 'import app.main; print(app.main.APP_NAME, app.main.VERSION)' ) >/tmp/makia-import.txt; then
  ok "Application import"
else
  bad "Application import"
fi

if command -v xray >/dev/null 2>&1; then
  XRAY_CONFIG=""
  for candidate in /usr/local/etc/xray/config.json /etc/xray/config.json; do
    if [[ -f "$candidate" ]]; then XRAY_CONFIG="$candidate"; break; fi
  done
  if [[ -n "$XRAY_CONFIG" ]]; then
    if xray run -test -format=json -config "$XRAY_CONFIG" >/tmp/makia-xray-test.log 2>&1; then
      ok "Xray active config syntax (root)"
    else
      xray_bad "Xray active config syntax (root)"
      sed -n '1,12p' /tmp/makia-xray-test.log || true
    fi
    XRAY_USER="$(systemctl show xray -p User --value 2>/dev/null || true)"
    XRAY_USER="${XRAY_USER:-root}"
    if [[ "$XRAY_USER" == "root" ]]; then
      XRAY_USER_TEST=( xray run -test -format=json -config "$XRAY_CONFIG" )
    else
      XRAY_USER_TEST=( runuser -u "$XRAY_USER" -- xray run -test -format=json -config "$XRAY_CONFIG" )
    fi
    if "${XRAY_USER_TEST[@]}" >/tmp/makia-xray-user-test.log 2>&1; then
      ok "Xray config readable by systemd user ($XRAY_USER)"
    else
      xray_bad "Xray config unreadable/invalid for systemd user ($XRAY_USER)"
      sed -n '1,12p' /tmp/makia-xray-user-test.log || true
    fi
    if systemctl is-active --quiet xray; then
      ok "Xray runtime active"
    else
      xray_bad "Xray runtime inactive"
      journalctl -u xray -n 12 --no-pager || true
    fi
  else
    xray_bad "Xray config missing"
  fi
else
  xray_bad "Xray binary missing"
fi

if [[ -x /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync ]]; then
  ok "Xray Certbot deploy hook"
else
  bad "Xray Certbot deploy hook missing"
fi

if [[ -f /etc/openvpn/server/server.conf ]]; then
  OVPN_PROTO="$(awk '$1=="proto"{print $2; exit}' /etc/openvpn/server/server.conf 2>/dev/null || true)"
  OVPN_PORT="$(awk '$1=="port"{print $2; exit}' /etc/openvpn/server/server.conf 2>/dev/null || true)"
  if [[ "$OVPN_PROTO" == "udp4" || "$OVPN_PROTO" == "tcp4-server" ]]; then
    ok "OpenVPN IPv4 transport ($OVPN_PROTO)"
  else
    ovpn_bad "OpenVPN transport is not normalized to udp4/tcp4-server ($OVPN_PROTO)"
  fi
  if systemctl is-active --quiet openvpn-server@server; then
    ok "OpenVPN runtime active"
  else
    ovpn_bad "OpenVPN runtime inactive"
    journalctl -u openvpn-server@server -n 12 --no-pager || true
  fi
  if [[ -n "$OVPN_PORT" ]] && ss -H -lntu 2>/dev/null | grep -Eq ":${OVPN_PORT}([[:space:]]|$)"; then
    ok "OpenVPN listener on port $OVPN_PORT"
  else
    ovpn_bad "OpenVPN listener missing"
  fi
else
  ovpn_bad "OpenVPN server config missing"
fi

if [[ -f /etc/wireguard/wg0.conf ]]; then
  if ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops.wireguard_endpoint_diagnostics("")
assert d.get("service_active"), d.get("warnings")
assert d.get("interface_present"), d.get("warnings")
assert d.get("listener"), d.get("warnings")
assert d.get("ip_forward"), d.get("warnings")
assert d.get("forward_in") is not False, d.get("warnings")
assert d.get("forward_out") is not False, d.get("warnings")
assert d.get("nat") is not False, d.get("warnings")
print("wg0", d.get("port"), d.get("network"), d.get("uplink"))
PY
  ); then
    ok "WireGuard forwarding + NAT + listener"
  else
    wg_bad "WireGuard runtime/forwarding/NAT unhealthy"
    systemctl status wg-quick@wg0 --no-pager -l || true
    wg show wg0 || true
  fi
else
  wg_bad "WireGuard wg0 config missing"
fi

if command -v stunnel4 >/dev/null 2>&1 || command -v stunnel >/dev/null 2>&1; then
  ok "Stunnel tooling installed"
else
  bad "Stunnel tooling missing"
fi

if command -v ipsec >/dev/null 2>&1; then
  ok "IKEv2/strongSwan tooling installed"
  if grep -q '# BEGIN MAKIA IKEV2' /etc/ipsec.conf 2>/dev/null; then
    if systemctl is-active --quiet strongswan-starter || systemctl is-active --quiet strongswan; then
      ok "IKEv2 runtime active"
    else
      bad "IKEv2 configured but strongSwan inactive"
    fi
    if ss -H -lun 2>/dev/null | grep -Eq ':(500|4500)([[:space:]]|$)'; then
      ok "IKEv2 UDP/500 or UDP/4500 listener"
    else
      bad "IKEv2 configured but UDP/500/4500 listener missing"
    fi
  else
    ok "IKEv2 tooling ready; mode not configured"
  fi
else
  bad "IKEv2/strongSwan tooling missing"
fi

if command -v wstunnel >/dev/null 2>&1; then
  ok "WStunnel tooling installed"
  if [[ -f /etc/makia-vps-manager/wstunnel.env ]]; then
    if systemctl is-active --quiet makia-wstunnel; then
      ok "WStunnel runtime active"
    else
      bad "WStunnel configured but service inactive"
    fi
  else
    ok "WStunnel tooling ready; mode not configured"
  fi
else
  bad "WStunnel tooling missing"
fi

if [[ -f /etc/openvpn/server/makia-tcp.conf ]]; then
  OVPN_TCP_PORT="$(awk '$1=="port"{print $2; exit}' /etc/openvpn/server/makia-tcp.conf 2>/dev/null || true)"
  if systemctl is-active --quiet openvpn-server@makia-tcp; then
    ok "OpenVPN parallel TCP fallback runtime active"
  else
    bad "OpenVPN TCP fallback configured but service inactive"
  fi
  if [[ -n "$OVPN_TCP_PORT" ]] && ss -H -ltn 2>/dev/null | grep -Eq ":${OVPN_TCP_PORT}([[:space:]]|$)"; then
    ok "OpenVPN TCP fallback listener on port $OVPN_TCP_PORT"
  else
    bad "OpenVPN TCP fallback listener missing"
  fi
else
  ok "OpenVPN TCP fallback not configured"
fi
if [[ -f /etc/stunnel/makia-openvpn.conf ]]; then
  if systemctl is-active --quiet stunnel4; then
    ok "Stealth TLS/Stunnel runtime active"
  else
    bad "Stealth configured but stunnel4 inactive"
  fi
else
  ok "Stealth mode not configured"
fi

if command -v makia-restore-portable >/dev/null 2>&1; then
  ok "Portable restore command"
else
  bad "Portable restore command missing"
fi

if command -v makia-doctor >/dev/null 2>&1; then
  makia-doctor || true
else
  bad "makia-doctor command missing"
fi

printf '\n'
if [[ "$FAIL" -eq 0 ]]; then
  printf 'HOST SMOKE: PASS\n'
else
  printf 'HOST SMOKE: FAIL\n'
fi
exit "$FAIL"
