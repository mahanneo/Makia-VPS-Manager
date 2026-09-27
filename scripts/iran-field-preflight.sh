#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-}"
if [[ -z "$HOST" ]]; then
  echo "Usage: $0 <host>"
  echo "Optional env: PANEL_URL SSH_PORT XRAY_PORTS WG_PORT OVPN_PORT OVPN_PROTO"
  exit 2
fi

SSH_PORT="${SSH_PORT:-22}"
XRAY_PORTS="${XRAY_PORTS:-}"
WG_PORT="${WG_PORT:-443}"
OVPN_PORT="${OVPN_PORT:-1194}"
OVPN_PROTO="${OVPN_PROTO:-udp}"
PANEL_URL="${PANEL_URL:-}"

fail=0
say(){ printf '%-28s %s\n' "$1" "$2"; }

if getent ahostsv4 "$HOST" >/tmp/makia-iran-resolve.$$ 2>/dev/null; then
  ip="$(awk 'NR==1{print $1}' /tmp/makia-iran-resolve.$$)"
  say "DNS/IPv4" "PASS -> $ip"
else
  say "DNS/IPv4" "FAIL"
  fail=1
fi
rm -f /tmp/makia-iran-resolve.$$ || true

tcp_probe(){
  local label="$1" port="$2"
  if python3 - "$HOST" "$port" <<'PY' >/dev/null 2>&1
import socket,sys
host=sys.argv[1]; port=int(sys.argv[2])
with socket.create_connection((host,port),timeout=5):
    pass
PY
  then say "$label TCP/$port" "PASS"
  else say "$label TCP/$port" "FAIL"; fail=1
  fi
}

tcp_probe "SSH" "$SSH_PORT"

IFS=',' read -ra XP <<< "$XRAY_PORTS"
for port in "${XP[@]}"; do
  [[ -z "$port" ]] && continue
  tcp_probe "Xray transport" "$port"
done

if [[ "$OVPN_PROTO" == tcp* ]]; then
  tcp_probe "OpenVPN" "$OVPN_PORT"
else
  if command -v nc >/dev/null 2>&1; then
    if nc -z -u -w3 "$HOST" "$OVPN_PORT" >/dev/null 2>&1; then
      say "OpenVPN UDP/$OVPN_PORT" "PROBE SENT (not handshake proof)"
    else
      say "OpenVPN UDP/$OVPN_PORT" "NO UDP RESPONSE (inconclusive)"
    fi
  else
    say "OpenVPN UDP/$OVPN_PORT" "SKIP: nc missing"
  fi
fi

if command -v nc >/dev/null 2>&1; then
  if nc -z -u -w3 "$HOST" "$WG_PORT" >/dev/null 2>&1; then
    say "WireGuard UDP/$WG_PORT" "PROBE SENT (not handshake proof)"
  else
    say "WireGuard UDP/$WG_PORT" "NO UDP RESPONSE (inconclusive)"
  fi
else
  say "WireGuard UDP/$WG_PORT" "SKIP: nc missing"
fi

if [[ -n "$PANEL_URL" ]]; then
  if curl -fsS --max-time 8 "$PANEL_URL/healthz" >/dev/null; then
    say "Panel healthz" "PASS"
  else
    say "Panel healthz" "FAIL"
    fail=1
  fi
fi

echo
echo "Important: this is transport preflight only."
echo "Real SSH/Xray/WireGuard/OpenVPN handshake and traffic must be tested with actual client configs inside Iran."
exit "$fail"
