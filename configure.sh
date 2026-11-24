#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 && $# -eq 2 ]] || { echo 'Usage: sudo bash configure.sh DOMAIN EMAIL'; exit 2; }
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd /opt/makia-vps-manager
.venv/bin/python "$ROOT/scripts/configure-fresh.py" "$1" "$2"
/usr/local/sbin/makia-install-outline --hostname "$1" --keys-port 49852
.venv/bin/python - <<'PY'
from app import integration_ops,network_services,protocol_ops
from app.main import _unified_xray_targets,UNIFIED_SS_PORTS
assert integration_ops.outline_status()['api_ok'], 'Outline manager not ready'
assert len(_unified_xray_targets())==5, 'Xray profile inventory incomplete'
assert network_services.dns_status()['query_ok'], 'DNS resolver failed'
assert protocol_ops.openvpn_policy_status()['ready'], 'OpenVPN policy not ready'
print('All 12 access method prerequisites are configured; perform a real external connection test before delivery.')
PY
if command -v ufw >/dev/null && ufw status | grep -qi '^Status: active'; then
  for p in 80 443 11443 2053 13001 13002 13003 8443 49852 2083 2096 1080; do ufw allow "$p/tcp"; done
  for p in 51820 1194 49852 2083 2096 1080; do ufw allow "$p/udp"; done
fi
systemctl restart makia-vps-manager makia-policy-enforcer makia-protocol-traffic
curl -fsS http://127.0.0.1:8787/healthz >/dev/null
echo "Makia setup completed: https://$1/ ; credentials: /root/makia-install-credentials.txt"
