#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }
[[ $# -ge 2 ]] || { echo "Usage: makia-node-connect CONTROLLER_URL NODE_TOKEN [PUBLIC_URL]"; exit 2; }
install -d -m 0700 /etc/makia-vps-manager
umask 077
cat >/etc/makia-vps-manager/node.env <<EOF
MAKIA_NODE_CONTROLLER=$1
MAKIA_NODE_TOKEN=$2
MAKIA_NODE_PUBLIC_URL=${3:-}
EOF
chmod 0600 /etc/makia-vps-manager/node.env
systemctl daemon-reload
systemctl enable --now makia-node-agent.timer
systemctl start makia-node-agent.service || true
echo "Makia node agent configured."
