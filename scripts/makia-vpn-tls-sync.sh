#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-${RENEWED_DOMAINS%% *}}"
LINEAGE="${RENEWED_LINEAGE:-}"
[[ -n "$DOMAIN" && "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || exit 0
[[ -n "$LINEAGE" ]] || LINEAGE="/etc/letsencrypt/live/$DOMAIN"
[[ -f "$LINEAGE/fullchain.pem" && -f "$LINEAGE/privkey.pem" ]] || exit 0

# strongSwan uses managed copies so refresh them atomically after renewal.
if grep -q '# BEGIN MAKIA IKEV2' /etc/ipsec.conf 2>/dev/null && grep -q "leftid=$DOMAIN" /etc/ipsec.conf 2>/dev/null; then
  install -m 0644 "$LINEAGE/cert.pem" /etc/ipsec.d/certs/makia-ikev2.pem
  install -m 0600 "$LINEAGE/privkey.pem" /etc/ipsec.d/private/makia-ikev2.key
  install -m 0644 "$LINEAGE/chain.pem" /etc/ipsec.d/cacerts/makia-ikev2-chain.pem
  if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
    systemctl restart strongswan-starter
  elif systemctl is-active --quiet strongswan 2>/dev/null; then
    systemctl restart strongswan
  fi
fi

# Stunnel and WStunnel reference the Let's Encrypt lineage directly; restart
# only managed services that actually use this domain/lineage.
if grep -q "$LINEAGE/" /etc/stunnel/makia-openvpn.conf 2>/dev/null && systemctl is-active --quiet stunnel4 2>/dev/null; then
  systemctl restart stunnel4
fi

if grep -q "WSTUNNEL_CERT=$LINEAGE/fullchain.pem" /etc/makia-vps-manager/wstunnel.env 2>/dev/null && systemctl is-active --quiet makia-wstunnel 2>/dev/null; then
  systemctl restart makia-wstunnel
fi

# Browser Gateway reads the Let's Encrypt lineage directly. A restart makes the
# renewed certificate effective for new secure-proxy connections.
if systemctl is-active --quiet makia-browser-gateway 2>/dev/null; then
  systemctl restart makia-browser-gateway
fi

echo "Makia VPN TLS sync: renewed services for $DOMAIN."
