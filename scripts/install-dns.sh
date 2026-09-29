#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root." >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y unbound dnsutils ca-certificates

install -d -m 0755 /etc/unbound/unbound.conf.d
install -d -m 0700 /etc/makia-vps-manager

cat >/etc/unbound/unbound.conf.d/makia.conf <<'EOF'
server:
    verbosity: 1
    interface: 127.0.0.1
    port: 53
    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes
    hide-identity: yes
    hide-version: yes
    qname-minimisation: yes
    harden-glue: yes
    harden-dnssec-stripped: yes
    prefetch: yes
    serve-expired: yes
    cache-min-ttl: 30
    cache-max-ttl: 86400
    access-control: 0.0.0.0/0 refuse
    access-control: 127.0.0.0/8 allow

forward-zone:
    name: "."
    forward-tls-upstream: yes
    forward-addr: 1.1.1.1@853#cloudflare-dns.com
    forward-addr: 1.0.0.1@853#cloudflare-dns.com
EOF
chmod 0600 /etc/unbound/unbound.conf.d/makia.conf
cat >/etc/makia-vps-manager/dns.json <<'EOF'
{
  "mode": "private",
  "upstream": "cloudflare",
  "bind_addresses": ["127.0.0.1"],
  "allowed_cidrs": [],
  "public_address": "",
  "wireguard_address": ""
}
EOF
chmod 0600 /etc/makia-vps-manager/dns.json

unbound-checkconf
systemctl enable --now unbound
systemctl restart unbound
systemctl is-active --quiet unbound
dig @127.0.0.1 example.com +short +time=2 +tries=1 | grep -q .
echo "Makia private DNS resolver installed. Public access remains disabled until an explicit CIDR allowlist is configured."
