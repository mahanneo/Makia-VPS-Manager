#!/usr/bin/env bash
set -Eeuo pipefail

NS=makia-wg-ci
HOST_VETH=mkwghost
CLIENT_VETH=mkwgcli
SERVER_WG=mkwgsrv
CLIENT_WG=mkwgclt
PORT=51888
TMP="$(mktemp -d)"

cleanup(){
  set +e
  sudo ip link del "$SERVER_WG" 2>/dev/null || true
  sudo ip link del "$HOST_VETH" 2>/dev/null || true
  sudo ip netns del "$NS" 2>/dev/null || true
  sudo sed -i '/# makia-wg-ci$/d' /etc/hosts 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

command -v wg >/dev/null
sudo modprobe wireguard 2>/dev/null || true

umask 077
wg genkey >"$TMP/server.key"
wg pubkey <"$TMP/server.key" >"$TMP/server.pub"
wg genkey >"$TMP/client.key"
wg pubkey <"$TMP/client.key" >"$TMP/client.pub"
SERVER_PUB="$(cat "$TMP/server.pub")"
CLIENT_PUB="$(cat "$TMP/client.pub")"

sudo ip netns add "$NS"
sudo ip link add "$HOST_VETH" type veth peer name "$CLIENT_VETH"
sudo ip link set "$CLIENT_VETH" netns "$NS"
sudo ip addr add 192.0.2.1/24 dev "$HOST_VETH"
sudo ip link set "$HOST_VETH" up
sudo ip netns exec "$NS" ip link set lo up
sudo ip netns exec "$NS" ip addr add 192.0.2.2/24 dev "$CLIENT_VETH"
sudo ip netns exec "$NS" ip link set "$CLIENT_VETH" up

sudo ip link add "$SERVER_WG" type wireguard
sudo ip addr add 10.250.0.1/24 dev "$SERVER_WG"
sudo wg set "$SERVER_WG" private-key "$TMP/server.key" listen-port "$PORT" peer "$CLIENT_PUB" allowed-ips 10.250.0.2/32
sudo ip link set "$SERVER_WG" up

sudo ip netns exec "$NS" ip link add "$CLIENT_WG" type wireguard
sudo ip netns exec "$NS" ip addr add 10.250.0.2/24 dev "$CLIENT_WG"
sudo ip netns exec "$NS" wg set "$CLIENT_WG" private-key "$TMP/client.key" peer "$SERVER_PUB" allowed-ips 10.250.0.1/32 endpoint 192.0.2.1:"$PORT" persistent-keepalive 5
sudo ip netns exec "$NS" ip link set "$CLIENT_WG" up

echo "Testing WireGuard direct IPv4 endpoint..."
sudo ip netns exec "$NS" ping -c 2 -W 2 10.250.0.1
IP_HANDSHAKE="$(sudo wg show "$SERVER_WG" latest-handshakes | awk '{print $2}' | head -n1)"
[[ "$IP_HANDSHAKE" =~ ^[1-9][0-9]*$ ]] || { echo "No direct-IP WireGuard handshake"; exit 1; }

echo "192.0.2.1 wg-ci.test # makia-wg-ci" | sudo tee -a /etc/hosts >/dev/null
sudo ip netns exec "$NS" wg set "$CLIENT_WG" peer "$SERVER_PUB" endpoint wg-ci.test:"$PORT"
sleep 1
echo "Testing WireGuard domain endpoint..."
sudo ip netns exec "$NS" ping -c 2 -W 2 10.250.0.1
DOMAIN_ENDPOINT="$(sudo ip netns exec "$NS" wg show "$CLIENT_WG" endpoints | awk '{print $2}')"
[[ "$DOMAIN_ENDPOINT" == 192.0.2.1:* ]] || { echo "Domain did not resolve to expected IPv4 endpoint: $DOMAIN_ENDPOINT"; exit 1; }
DOMAIN_HANDSHAKE="$(sudo wg show "$SERVER_WG" latest-handshakes | awk '{print $2}' | head -n1)"
[[ "$DOMAIN_HANDSHAKE" =~ ^[1-9][0-9]*$ ]] || { echo "No domain WireGuard handshake"; exit 1; }

echo "WireGuard network-namespace handshake PASS: direct IPv4 + domain"
