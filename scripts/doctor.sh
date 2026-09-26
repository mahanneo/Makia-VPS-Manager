#!/usr/bin/env bash
set -uo pipefail

PASS=0
WARN=0
FAIL=0

ok(){ PASS=$((PASS+1)); printf '✓ %-30s %s\n' "$1" "${2:-OK}"; }
warn(){ WARN=$((WARN+1)); printf '! %-30s %s\n' "$1" "$2"; }
fail(){ FAIL=$((FAIL+1)); printf '✗ %-30s %s\n' "$1" "$2"; }

check_service(){
  local service="$1" label="$2" required="${3:-yes}"
  if systemctl is-active --quiet "$service" 2>/dev/null; then
    ok "$label" "active"
  elif [[ "$required" == "yes" ]]; then
    fail "$label" "$(systemctl is-active "$service" 2>/dev/null || true)"
  else
    warn "$label" "$(systemctl is-active "$service" 2>/dev/null || echo not-installed)"
  fi
}

printf '\nMakia VPS Manager Doctor\n'
printf '========================\n'
if [[ -r /opt/makia-vps-manager/VERSION ]]; then
  ok "Version" "$(cat /opt/makia-vps-manager/VERSION)"
else
  fail "Version" "/opt/makia-vps-manager/VERSION missing"
fi

check_service makia-vps-manager "Makia backend"
check_service nginx "Nginx"
check_service makia-policy-enforcer "SSH policy enforcer"
check_service makia-metrics-sampler "Metrics sampler"
check_service makia-protocol-traffic "Protocol traffic collector"
check_service fail2ban "Fail2ban"

TMP_HEALTH="$(mktemp)"
if curl -fsS --max-time 5 http://127.0.0.1:8787/healthz >"$TMP_HEALTH" 2>/dev/null; then
  ok "Backend health" "$(cat "$TMP_HEALTH")"
else
  fail "Backend health" "http://127.0.0.1:8787/healthz failed"
fi
rm -f "$TMP_HEALTH"

TMP_NGINX="$(mktemp)"
if nginx -t >"$TMP_NGINX" 2>&1; then
  ok "Nginx config" "valid"
else
  fail "Nginx config" "$(tail -n 2 "$TMP_NGINX" | tr '\n' ' ')"
fi
rm -f "$TMP_NGINX"

DB=/opt/makia-vps-manager/data/makia.db
if [[ -f "$DB" ]]; then
  PERM="$(stat -c '%a' "$DB" 2>/dev/null || echo unknown)"
  if [[ "$PERM" == "600" ]]; then ok "Database permissions" "0600"; else warn "Database permissions" "$PERM (expected 600 after next DB access)"; fi
else
  warn "Database" "not found yet"
fi

XRAY="$(command -v xray 2>/dev/null || true)"
if [[ -n "$XRAY" ]]; then
  CONF=""
  [[ -f /usr/local/etc/xray/config.json ]] && CONF=/usr/local/etc/xray/config.json
  [[ -z "$CONF" && -f /etc/xray/config.json ]] && CONF=/etc/xray/config.json
  if [[ -n "$CONF" ]]; then
    TMP_XRAY="$(mktemp)"
    XRAY_VERSION="$("$XRAY" version 2>/dev/null | head -n1 || true)"
    if [[ "$XRAY_VERSION" == *"26.3.27"* ]]; then
      ok "Xray version" "$XRAY_VERSION"
    else
      warn "Xray version" "${XRAY_VERSION:-unknown} (CI target: 26.3.27)"
    fi
    if "$XRAY" run -test -format=json -config "$CONF" >"$TMP_XRAY" 2>&1; then
      ok "Xray config (root)" "valid"
    else
      fail "Xray config (root)" "$(tail -n 2 "$TMP_XRAY" | tr '\n' ' ')"
    fi
    XRAY_USER="$(systemctl show xray -p User --value 2>/dev/null || true)"
    XRAY_USER="${XRAY_USER:-root}"
    if [[ "$XRAY_USER" == "root" ]]; then
      XRAY_USER_TEST=( "$XRAY" run -test -format=json -config "$CONF" )
    else
      XRAY_USER_TEST=( runuser -u "$XRAY_USER" -- "$XRAY" run -test -format=json -config "$CONF" )
    fi
    if "${XRAY_USER_TEST[@]}" >>"$TMP_XRAY" 2>&1; then
      ok "Xray config ($XRAY_USER)" "readable + valid"
    else
      fail "Xray config ($XRAY_USER)" "$(tail -n 3 "$TMP_XRAY" | tr '\n' ' ')"
    fi
    rm -f "$TMP_XRAY"
    check_service xray "Xray service" yes
  else
    warn "Xray" "binary installed, config not found"
  fi
else
  warn "Xray" "not installed (optional)"
fi

if [[ -f /etc/wireguard/wg0.conf ]]; then
  WG_DIAG="$(cd /opt/makia-vps-manager && MAKIA_DATA_DIR=/opt/makia-vps-manager/data ./.venv/bin/python - <<'PY' 2>&1
from app import protocol_ops
d=protocol_ops.wireguard_diagnostics("wg0")
print("port="+str(d.get("port"))+
      " listener="+str(d.get("listener"))+
      " forward="+str(d.get("ip_forward"))+
      " nat="+str(d.get("nat_rule"))+
      " rules="+str(bool(d.get("forward_in_rule") and d.get("forward_out_rule"))) +
      " peers="+str(d.get("peer_count")))
if not d.get("runtime_ok"):
    raise SystemExit("; ".join(d.get("warnings") or ["unhealthy"]))
PY
)"
  if [[ "$?" -eq 0 ]]; then
    ok "WireGuard runtime" "$WG_DIAG"
  else
    fail "WireGuard runtime" "$WG_DIAG"
  fi
elif command -v wg >/dev/null 2>&1; then
  warn "WireGuard" "tooling installed, wg0 not configured"
else
  warn "WireGuard" "not installed (optional)"
fi

if [[ -f /etc/openvpn/server/server.conf ]]; then
  OVPN_DIAG="$(cd /opt/makia-vps-manager && MAKIA_DATA_DIR=/opt/makia-vps-manager/data ./.venv/bin/python - <<'PY' 2>&1
from app import protocol_ops
d=protocol_ops._openvpn_server_runtime()
print("proto="+str(d.get("proto"))+" port="+str(d.get("port"))+" listener="+str(d.get("listener")))
if str(d.get("proto") or "") not in {"udp4","tcp4-server"} or not d.get("service_active") or not d.get("listener"):
    raise SystemExit("OpenVPN runtime is not healthy")
PY
)"
  if [[ "$?" -eq 0 ]]; then
    ok "OpenVPN runtime" "$OVPN_DIAG"
  else
    fail "OpenVPN runtime" "$OVPN_DIAG"
  fi
elif command -v openvpn >/dev/null 2>&1; then
  warn "OpenVPN" "tooling installed, server not configured"
else
  warn "OpenVPN" "not installed (optional)"
fi

ENDPOINT_DIAG="$(cd /opt/makia-vps-manager && MAKIA_DATA_DIR=/opt/makia-vps-manager/data ./.venv/bin/python - <<'PY' 2>&1
from app import protocol_ops
from app.db import get_setting
endpoint=(get_setting("panel_domain","") or "").strip()
if not endpoint:
    ips=protocol_ops._local_ipv4_candidates()
    endpoint=ips[0] if ips else ""
if not endpoint:
    print("no public endpoint configured")
    raise SystemExit(2)
d=protocol_ops.endpoint_connectivity_matrix(endpoint)
parts=[]
for name in ("ssh","wireguard","openvpn","xray"):
    row=d.get(name)
    if isinstance(row,dict):
        parts.append(name+"="+("PASS" if row.get("ok") else "CHECK"))
print(endpoint+" · "+", ".join(parts))
PY
)"
ENDPOINT_RC=$?
if [[ "$ENDPOINT_RC" -eq 0 ]]; then
  ok "Protocol endpoint matrix" "$ENDPOINT_DIAG"
elif [[ "$ENDPOINT_RC" -eq 2 ]]; then
  warn "Protocol endpoint matrix" "$ENDPOINT_DIAG"
else
  warn "Protocol endpoint matrix" "$ENDPOINT_DIAG"
fi

printf '\nSummary: %d PASS · %d WARN · %d FAIL\n\n' "$PASS" "$WARN" "$FAIL"
[[ "$FAIL" -eq 0 ]]
