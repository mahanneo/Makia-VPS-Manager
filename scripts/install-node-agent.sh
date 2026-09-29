#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }
CONTROLLER_URL="${MAKIA_CONTROLLER_URL:-${1:-}}"
NODE_TOKEN="${MAKIA_NODE_TOKEN:-${2:-}}"
[[ "$CONTROLLER_URL" =~ ^https?:// ]] || { echo "Usage: MAKIA_CONTROLLER_URL=https://panel.example.com MAKIA_NODE_TOKEN=mn_xxx bash install-node-agent.sh"; exit 1; }
[[ -n "$NODE_TOKEN" ]] || { echo "Missing MAKIA_NODE_TOKEN"; exit 1; }
install -d -m 0755 /opt/makia-node-agent
curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/agent/makia_node_agent.py -o /opt/makia-node-agent/agent.py
chmod 0755 /opt/makia-node-agent/agent.py
cat >/etc/makia-node-agent.env <<EOF
MAKIA_CONTROLLER_URL=$CONTROLLER_URL
MAKIA_NODE_TOKEN=$NODE_TOKEN
MAKIA_NODE_INTERVAL=30
EOF
chmod 0600 /etc/makia-node-agent.env
curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/systemd/makia-node-agent.service -o /etc/systemd/system/makia-node-agent.service
systemctl daemon-reload
systemctl enable --now makia-node-agent
echo "Makia node agent installed and started."
