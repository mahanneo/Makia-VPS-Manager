#!/usr/bin/env bash
set -Eeuo pipefail
CIDR="${MAKIA_IKEV2_CIDR:-10.77.0.0/24}"
IFACE="$(ip -4 route show default | awk '/default/ {for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')"
[[ -n "$IFACE" ]] || { echo "Unable to determine default interface" >&2; exit 1; }
sysctl -w net.ipv4.ip_forward=1 >/dev/null
iptables -C FORWARD -s "$CIDR" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s "$CIDR" -j ACCEPT
iptables -C FORWARD -d "$CIDR" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -d "$CIDR" -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -C POSTROUTING -s "$CIDR" -o "$IFACE" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "$CIDR" -o "$IFACE" -j MASQUERADE
