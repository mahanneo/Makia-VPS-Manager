#!/usr/bin/env bash
# Provision only the dedicated SSTP IPv4 egress CIDR. Must be run as root
# during a reviewed maintenance window; this does not change Nginx listeners.
set -Eeuo pipefail
test "$(id -u)" -eq 0
cidr="10.79.0.0/24"
uplink="$(ip -4 route show default | awk 'NR==1 {for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
test -n "$uplink"
test -f /etc/accel-ppp/makia-sstp.conf
systemctl is-active --quiet makia-sstp-backend
# Existing Makia network services use state-match forwarding rules.
sysctl -q -w net.ipv4.ip_forward=1
iptables -C FORWARD -s "$cidr" -j ACCEPT 2>/dev/null ||
    iptables -I FORWARD -s "$cidr" -j ACCEPT
iptables -C FORWARD -d "$cidr" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null ||
    iptables -I FORWARD -d "$cidr" -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -C POSTROUTING -s "$cidr" -o "$uplink" -j MASQUERADE 2>/dev/null ||
    iptables -t nat -A POSTROUTING -s "$cidr" -o "$uplink" -j MASQUERADE
iptables -C FORWARD -s "$cidr" -j ACCEPT
iptables -C FORWARD -d "$cidr" -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -C POSTROUTING -s "$cidr" -o "$uplink" -j MASQUERADE
echo "Makia SSTP $cidr network forwarding and NAT installed on $uplink"
