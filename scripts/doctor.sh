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

if command -v wg >/dev/null 2>&1; then
  if [[ -f /etc/wireguard/wg0.conf ]]; then
    if ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops.wireguard_endpoint_diagnostics("")
assert d.get("runtime_ok"), "; ".join(d.get("warnings") or [])
print("wg0", d.get("port"), d.get("network"), d.get("uplink"))
PY
    ); then
      ok "WireGuard runtime" "forwarding + NAT + listener ready"
    else
      fail "WireGuard runtime" "run Protocols → WireGuard → Repair Runtime"
    fi
  elif wg show >/dev/null 2>&1; then
    ok "WireGuard tooling" "installed; wg0 not bootstrapped"
  else
    warn "WireGuard tooling" "installed but no readable interface"
  fi
else
  warn "WireGuard" "not installed (optional)"
fi

if command -v openvpn >/dev/null 2>&1; then
  ok "OpenVPN tooling" "$(openvpn --version 2>/dev/null | head -n1)"
else
  warn "OpenVPN" "not installed (optional)"
fi

printf '\nSummary: %d PASS · %d WARN · %d FAIL\n\n' "$PASS" "$WARN" "$FAIL"
[[ "$FAIL" -eq 0 ]]
