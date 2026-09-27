#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-${RENEWED_DOMAINS%% *}}"
LINEAGE="${RENEWED_LINEAGE:-}"
if [[ -z "$DOMAIN" || ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "Makia certificate deploy hook: no safe renewed domain supplied; nothing to do."
  exit 0
fi
if [[ -z "$LINEAGE" ]]; then LINEAGE="/etc/letsencrypt/live/$DOMAIN"; fi
[[ -f "$LINEAGE/fullchain.pem" && -f "$LINEAGE/privkey.pem" ]] || exit 0

CHANGED=0
XRAY_BIN="$(command -v xray 2>/dev/null || true)"
CONFIG=""
for candidate in /usr/local/etc/xray/config.json /etc/xray/config.json; do
  if [[ -f "$candidate" ]]; then CONFIG="$candidate"; break; fi
done
TARGET="/usr/local/etc/xray/tls/$DOMAIN"
if [[ -n "$XRAY_BIN" && -n "$CONFIG" && -d "$TARGET" ]]; then
  XRAY_USER="$(systemctl show xray -p User --value 2>/dev/null || true)"
  XRAY_USER="${XRAY_USER:-root}"
  if ! id "$XRAY_USER" >/dev/null 2>&1; then
    echo "Makia certificate deploy hook: Xray systemd user $XRAY_USER does not exist."
    exit 1
  fi
  XRAY_GROUP="$(id -gn "$XRAY_USER")"
  install -d -m 0700 -o "$XRAY_USER" -g "$XRAY_GROUP" "$TARGET"
  TMP_CERT="$TARGET/.fullchain.pem.makia.$$"
  TMP_KEY="$TARGET/.privkey.pem.makia.$$"
  trap 'rm -f "$TMP_CERT" "$TMP_KEY"' EXIT
  install -m 0600 -o "$XRAY_USER" -g "$XRAY_GROUP" "$LINEAGE/fullchain.pem" "$TMP_CERT"
  install -m 0600 -o "$XRAY_USER" -g "$XRAY_GROUP" "$LINEAGE/privkey.pem" "$TMP_KEY"
  mv -f "$TMP_CERT" "$TARGET/fullchain.pem"
  mv -f "$TMP_KEY" "$TARGET/privkey.pem"
  chown "$XRAY_USER:$XRAY_GROUP" "$TARGET/fullchain.pem" "$TARGET/privkey.pem"
  chmod 0600 "$TARGET/fullchain.pem" "$TARGET/privkey.pem"
  if [[ "$XRAY_USER" == "root" ]]; then
    "$XRAY_BIN" run -test -format=json -config "$CONFIG"
  else
    runuser -u "$XRAY_USER" -- "$XRAY_BIN" run -test -format=json -config "$CONFIG"
  fi
  if systemctl is-active --quiet xray; then
    systemctl restart xray
    systemctl is-active --quiet xray
  fi
  CHANGED=1
  echo "Makia certificate deploy hook: Xray TLS material refreshed for $DOMAIN."
fi

if [[ -f /etc/ipsec.conf ]] && grep -q "# BEGIN MAKIA IKEV2" /etc/ipsec.conf && grep -Eq "^[[:space:]]*leftid=@${DOMAIN//./\.}[[:space:]]*$" /etc/ipsec.conf; then
  if systemctl is-active --quiet strongswan-starter; then
    systemctl restart strongswan-starter
    systemctl is-active --quiet strongswan-starter
    ipsec statusall >/dev/null
    CHANGED=1
    echo "Makia certificate deploy hook: IKEv2 certificate reloaded for $DOMAIN."
  fi
fi

if [[ "$CHANGED" -eq 0 ]]; then
  echo "Makia certificate deploy hook: renewed domain $DOMAIN is not used by a managed TLS runtime."
fi
