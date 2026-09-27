#!/usr/bin/env bash
set -Eeuo pipefail
ENV=/etc/makia-vps-manager/ikev2.env
[[ -r "$ENV" ]] && source "$ENV"
POOL="${MAKIA_IKEV2_POOL:-10.99.0.0/24}"
UPLINK="${MAKIA_IKEV2_UPLINK:-$(ip -4 route show default | awk '/default/{print $5; exit}')}"
[[ -n "$UPLINK" ]] || { echo "IKEv2 uplink not found" >&2; exit 1; }
add_rule(){ local table="$1"; shift; if ! iptables -t "$table" -C "$@" 2>/dev/null; then iptables -t "$table" -A "$@"; fi; }
del_rule(){ local table="$1"; shift; while iptables -t "$table" -C "$@" 2>/dev/null; do iptables -t "$table" -D "$@" || break; done; }
case "${1:-start}" in
  start)
    sysctl -w net.ipv4.ip_forward=1 >/dev/null
    add_rule filter FORWARD -s "$POOL" -j ACCEPT
    add_rule filter FORWARD -d "$POOL" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    add_rule nat POSTROUTING -s "$POOL" -o "$UPLINK" -j MASQUERADE
    ;;
  stop)
    del_rule filter FORWARD -s "$POOL" -j ACCEPT
    del_rule filter FORWARD -d "$POOL" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    del_rule nat POSTROUTING -s "$POOL" -o "$UPLINK" -j MASQUERADE
    ;;
  *) echo "usage: $0 start|stop" >&2; exit 2 ;;
esac
