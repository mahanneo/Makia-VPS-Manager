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
  [[ -s "$CERT" ]] && ok "HTTPS certificate present for $PANEL_DOMAIN" || bad "HTTPS certificate missing for configured domain $PANEL_DOMAIN"
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
assert result["ok"] and result["sample_size"]==15
print("storage/crypto PASS")
PY
); then
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
    [[ -f "$candidate" ]] && { XRAY_CONFIG="$candidate"; break; }
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
    systemctl is-active --quiet xray && ok "Xray runtime active" || xray_bad "Xray runtime inactive"
  else
    xray_bad "Xray config missing"
  fi
else
  xray_bad "Xray binary missing"
fi

[[ -x /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync ]] && ok "Xray Certbot deploy hook" || bad "Xray Certbot deploy hook missing"

if [[ -f /etc/openvpn/server/server.conf ]]; then
  OVPN_PROTO="$(awk '$1=="proto"{print $2; exit}' /etc/openvpn/server/server.conf 2>/dev/null || true)"
  OVPN_PORT="$(awk '$1=="port"{print $2; exit}' /etc/openvpn/server/server.conf 2>/dev/null || true)"
  [[ "$OVPN_PROTO" == "udp4" || "$OVPN_PROTO" == "tcp4-server" ]] && ok "OpenVPN IPv4 transport ($OVPN_PROTO)" || ovpn_bad "OpenVPN transport is not normalized to udp4/tcp4-server ($OVPN_PROTO)"
  systemctl is-active --quiet openvpn-server@server && ok "OpenVPN runtime active" || ovpn_bad "OpenVPN runtime inactive"
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
  fi
else
  wg_bad "WireGuard wg0 config missing"
fi

if command -v stunnel4 >/dev/null 2>&1 || command -v stunnel >/dev/null 2>&1; then ok "Stunnel tooling installed"; else bad "Stunnel tooling missing"; fi
command -v swanctl >/dev/null 2>&1 && ok "StrongSwan swanctl tooling installed" || bad "StrongSwan swanctl tooling missing"
command -v wstunnel >/dev/null 2>&1 && ok "WStunnel tooling installed" || bad "WStunnel tooling missing"
[[ -f /etc/systemd/system/makia-ikev2-firewall.service ]] && ok "IKEv2 firewall unit installed" || bad "IKEv2 firewall unit missing"
[[ -f /etc/systemd/system/makia-stealth.service ]] && ok "Stealth service unit installed" || bad "Stealth service unit missing"
[[ -f /etc/systemd/system/makia-wstunnel.service ]] && ok "WStunnel service unit installed" || bad "WStunnel service unit missing"

if [[ -f /etc/swanctl/conf.d/makia.conf ]]; then
  if systemctl is-active --quiet strongswan && \
     ss -H -lun 2>/dev/null | grep -Eq ':500([[:space:]]|$)' && \
     ss -H -lun 2>/dev/null | grep -Eq ':4500([[:space:]]|$)'; then
    ok "IKEv2 configured runtime active"
  else
    bad "IKEv2 configured but StrongSwan/listeners unhealthy"
  fi
fi
if [[ -f /etc/stunnel/makia-openvpn.conf ]]; then
  systemctl is-active --quiet makia-stealth && ok "Stealth configured runtime active" || bad "Stealth configured but service inactive"
fi
if [[ -f /etc/makia-vps-manager/wstunnel.env ]]; then
  systemctl is-active --quiet makia-wstunnel && ok "WStunnel configured runtime active" || bad "WStunnel configured but service inactive"
fi

command -v makia-restore-portable >/dev/null 2>&1 && ok "Portable restore command" || bad "Portable restore command missing"
if command -v makia-doctor >/dev/null 2>&1; then makia-doctor || true; else bad "makia-doctor command missing"; fi

printf '\n'
if [[ "$FAIL" -eq 0 ]]; then
  printf 'HOST SMOKE: PASS\n'
else
  printf 'HOST SMOKE: FAIL\n'
fi
exit "$FAIL"
