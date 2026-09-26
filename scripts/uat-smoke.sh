#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/makia-vps-manager
FAIL=0

ok(){ printf '✓ %s\n' "$1"; }
bad(){ printf '✗ %s\n' "$1"; FAIL=1; }
xray_bad(){
  if [[ "${MAKIA_ALLOW_PREEXISTING_XRAY_FAILURE:-0}" == "1" ]]; then
    printf '! %s (pre-existing Xray failure; panel diagnostics update allowed)\n' "$1"
  else
    bad "$1"
  fi
}
ovpn_bad(){
  if [[ "${MAKIA_ALLOW_PREEXISTING_OPENVPN_FAILURE:-0}" == "1" ]]; then
    printf '! %s (pre-existing OpenVPN failure; panel diagnostics update allowed)\n' "$1"
  else
    bad "$1"
  fi
}
wg_bad(){
  if [[ "${MAKIA_ALLOW_PREEXISTING_WIREGUARD_FAILURE:-0}" == "1" ]]; then
    printf '! %s (pre-existing WireGuard failure; panel diagnostics/repair update allowed)\n' "$1"
  else
    bad "$1"
  fi
}

[[ -d "$APP" ]] || { bad "Makia runtime missing at $APP"; exit 1; }

printf '\nMakia host smoke / protocol runtime gate\n'
printf '%s\n' '---------------------'

VERSION="$(cat "$APP/VERSION" 2>/dev/null || true)"
[[ -n "$VERSION" ]] && ok "Version: $VERSION" || bad "VERSION missing"

if curl -fsS --max-time 4 http://127.0.0.1:8787/healthz >/tmp/makia-health.json; then
  ok "Backend health endpoint"
else
  bad "Backend health endpoint"
fi

if nginx -t >/dev/null 2>&1; then ok "Nginx config"; else bad "Nginx config"; fi

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
  fi
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
fi

if [[ -f /etc/wireguard/wg0.conf ]]; then
  if ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops.wireguard_diagnostics("wg0")
print("WireGuard diagnostics:",
      "service="+str(d.get("service_active")),
      "interface="+str(d.get("interface_active")),
      "listener="+str(d.get("listener")),
      "ip_forward="+str(d.get("ip_forward")),
      "nat="+str(d.get("nat_rule")),
      "forward="+str(bool(d.get("forward_in_rule") and d.get("forward_out_rule"))),
      "port="+str(d.get("port")))
if not d.get("runtime_ok"):
    raise SystemExit("; ".join(d.get("warnings") or ["WireGuard runtime unhealthy"]))
PY
  ); then
    ok "WireGuard listener + forwarding + NAT"
  else
    wg_bad "WireGuard listener / forwarding / NAT runtime"
  fi
fi

if ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
from app.db import get_setting
endpoint=(get_setting("panel_domain","") or "").strip()
if not endpoint:
    candidates=protocol_ops._local_ipv4_candidates()
    endpoint=candidates[0] if candidates else ""
if not endpoint:
    print("No public endpoint configured; connectivity matrix skipped")
else:
    d=protocol_ops.endpoint_connectivity_matrix(endpoint)
    print("Protocol endpoint matrix:", endpoint, f"{d.get('passed')}/{d.get('checked')} server-side ready")
    for name in ("ssh","wireguard","openvpn","xray"):
        row=d.get(name)
        if isinstance(row,dict):
            print(" -",name, "PASS" if row.get("ok") else "CHECK", "; ".join(row.get("warnings") or []))
PY
); then
  ok "Protocol IP/domain readiness probe"
else
  bad "Protocol IP/domain readiness probe"
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
