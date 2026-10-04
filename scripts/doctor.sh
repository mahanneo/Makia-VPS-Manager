#!/usr/bin/env bash
set -uo pipefail

APP=/opt/makia-vps-manager

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
    fail "Xray" "binary installed, config not found"
  fi
else
  fail "Xray" "not installed; run makia-upgrade to provision full stack"
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
    fail "WireGuard" "tooling installed but wg0 is not bootstrapped"
  else
    fail "WireGuard" "installed but no readable interface/config"
  fi
else
  fail "WireGuard" "not installed; run makia-upgrade to provision full stack"
fi

if command -v openvpn >/dev/null 2>&1; then
  ok "OpenVPN tooling" "$(openvpn --version 2>/dev/null | head -n1)"
  if [[ -f /etc/openvpn/server/server.conf ]] && systemctl is-active --quiet openvpn-server@server; then
    OVPN_PORT="$(awk '$1=="port"{print $2; exit}' /etc/openvpn/server/server.conf 2>/dev/null || true)"
    if [[ -n "$OVPN_PORT" ]] && ss -H -lntu 2>/dev/null | grep -Eq ":${OVPN_PORT}([[:space:]]|$)"; then
      ok "OpenVPN runtime" "active + listener :$OVPN_PORT"
    else
      fail "OpenVPN runtime" "service active but listener missing"
    fi
  else
    fail "OpenVPN runtime" "server config/service missing"
  fi
else
  fail "OpenVPN" "not installed; run makia-upgrade to provision full stack"
fi

if command -v stunnel4 >/dev/null 2>&1 || command -v stunnel >/dev/null 2>&1; then
  ok "Stunnel tooling" "installed"
  if [[ -f /etc/stunnel/makia-openvpn.conf ]]; then
    if systemctl is-active --quiet stunnel4; then
      ok "Stealth TLS/Stunnel" "active"
    elif grep -Eq '^[[:space:]]*ENABLED[[:space:]]*=[[:space:]]*1[[:space:]]*
else
  fail "Stunnel tooling" "not installed"
fi

if command -v ipsec >/dev/null 2>&1; then
  ok "IKEv2 tooling" "strongSwan installed"
  if grep -q '# BEGIN MAKIA IKEV2' /etc/ipsec.conf 2>/dev/null; then
    if systemctl is-active --quiet strongswan-starter || systemctl is-active --quiet strongswan; then ok "IKEv2 runtime" "active"; else fail "IKEv2 runtime" "configured but inactive"; fi
    if ss -H -lun 2>/dev/null | grep -Eq ':(500|4500)([[:space:]]|$)'; then ok "IKEv2 listeners" "UDP/500 or UDP/4500 active"; else fail "IKEv2 listeners" "missing UDP/500 and UDP/4500"; fi
  else
    warn "IKEv2 runtime" "tooling ready, not configured"
  fi
else
  fail "IKEv2 tooling" "strongSwan missing; run makia-upgrade"
fi

if command -v wstunnel >/dev/null 2>&1; then
  ok "WStunnel tooling" "$(wstunnel --version 2>/dev/null | head -n1)"
  if [[ -f /etc/makia-vps-manager/wstunnel.env ]]; then check_service makia-wstunnel "WStunnel runtime" yes; else warn "WStunnel runtime" "tooling ready, not configured"; fi
else
  fail "WStunnel tooling" "missing; run makia-upgrade"
fi

if [[ -f /etc/makia-vps-manager/mtproxy.env ]]; then
  if [[ -x /opt/makia-mtproxy/mtg ]]; then
    MTG_VERSION="$(/opt/makia-mtproxy/mtg --version 2>/dev/null | head -n1 || true)"
    ok "Telegram MTProxy tooling" "${MTG_VERSION:-installed}"
    check_service makia-mtproxy "Telegram MTProxy runtime" yes
  else
    fail "Telegram MTProxy" "configured but /opt/makia-mtproxy/mtg is missing"
  fi
else
  warn "Telegram MTProxy" "optional; not configured"
fi

if [[ -f /etc/unbound/unbound.conf.d/makia.conf ]]; then
  if command -v unbound-checkconf >/dev/null 2>&1 && unbound-checkconf >/tmp/makia-unbound-check.log 2>&1; then
    ok "Makia DNS config" "valid"
  else
    fail "Makia DNS config" "$(tail -n 2 /tmp/makia-unbound-check.log 2>/dev/null | tr '\n' ' ')"
  fi
  check_service unbound "Makia DNS resolver" yes
  if command -v dig >/dev/null 2>&1 && dig @127.0.0.1 example.com +short +time=2 +tries=1 | grep -q .; then
    ok "Makia DNS query" "localhost resolver answered"
  else
    fail "Makia DNS query" "local resolver did not answer"
  fi
else
  warn "Makia DNS" "optional; not configured"
fi

printf '\nSummary: %d PASS · %d WARN · %d FAIL\n\n' "$PASS" "$WARN" "$FAIL"
[[ "$FAIL" -eq 0 ]]
 /etc/default/stunnel4 2>/dev/null; then
      warn "Stealth TLS/Stunnel" "optional config is ENABLED=1 but service is inactive; core VPNs are unaffected"
    else
      warn "Stealth TLS/Stunnel" "optional config retained but service is disabled/inactive"
    fi
  else
    warn "Stealth TLS/Stunnel" "not configured"
  fi
else
  fail "Stunnel tooling" "not installed"
fi

if command -v ipsec >/dev/null 2>&1; then
  ok "IKEv2 tooling" "strongSwan installed"
  if grep -q '# BEGIN MAKIA IKEV2' /etc/ipsec.conf 2>/dev/null; then
    if systemctl is-active --quiet strongswan-starter || systemctl is-active --quiet strongswan; then ok "IKEv2 runtime" "active"; else fail "IKEv2 runtime" "configured but inactive"; fi
    if ss -H -lun 2>/dev/null | grep -Eq ':(500|4500)([[:space:]]|$)'; then ok "IKEv2 listeners" "UDP/500 or UDP/4500 active"; else fail "IKEv2 listeners" "missing UDP/500 and UDP/4500"; fi
  else
    warn "IKEv2 runtime" "tooling ready, not configured"
  fi
else
  fail "IKEv2 tooling" "strongSwan missing; run makia-upgrade"
fi

if command -v wstunnel >/dev/null 2>&1; then
  ok "WStunnel tooling" "$(wstunnel --version 2>/dev/null | head -n1)"
  if [[ -f /etc/makia-vps-manager/wstunnel.env ]]; then check_service makia-wstunnel "WStunnel runtime" yes; else warn "WStunnel runtime" "tooling ready, not configured"; fi
else
  fail "WStunnel tooling" "missing; run makia-upgrade"
fi

if [[ -f /etc/makia-vps-manager/mtproxy.env ]]; then
  if [[ -x /opt/makia-mtproxy/mtg ]]; then
    MTG_VERSION="$(/opt/makia-mtproxy/mtg --version 2>/dev/null | head -n1 || true)"
    ok "Telegram MTProxy tooling" "${MTG_VERSION:-installed}"
    check_service makia-mtproxy "Telegram MTProxy runtime" yes
  else
    fail "Telegram MTProxy" "configured but /opt/makia-mtproxy/mtg is missing"
  fi
else
  warn "Telegram MTProxy" "optional; not configured"
fi

if [[ -f /etc/unbound/unbound.conf.d/makia.conf ]]; then
  if command -v unbound-checkconf >/dev/null 2>&1 && unbound-checkconf >/tmp/makia-unbound-check.log 2>&1; then
    ok "Makia DNS config" "valid"
  else
    fail "Makia DNS config" "$(tail -n 2 /tmp/makia-unbound-check.log 2>/dev/null | tr '\n' ' ')"
  fi
  check_service unbound "Makia DNS resolver" yes
  if command -v dig >/dev/null 2>&1 && dig @127.0.0.1 example.com +short +time=2 +tries=1 | grep -q .; then
    ok "Makia DNS query" "localhost resolver answered"
  else
    fail "Makia DNS query" "local resolver did not answer"
  fi
else
  warn "Makia DNS" "optional; not configured"
fi

printf '\nSummary: %d PASS · %d WARN · %d FAIL\n\n' "$PASS" "$WARN" "$FAIL"
[[ "$FAIL" -eq 0 ]]
