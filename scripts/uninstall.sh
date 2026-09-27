#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }
APP=/opt/makia-vps-manager
if [[ -d "$APP/data" ]]; then
  BACKUP="$(/usr/local/sbin/makia-backup 2>/dev/null || true)"
  [[ -n "$BACKUP" ]] && echo "Backup created: $BACKUP"
fi
systemctl disable --now makia-vps-manager 2>/dev/null || true
systemctl disable --now makia-policy-enforcer 2>/dev/null || true
systemctl disable --now makia-metrics-sampler 2>/dev/null || true
systemctl disable --now makia-protocol-traffic 2>/dev/null || true
systemctl disable --now makia-ikev2-firewall 2>/dev/null || true
systemctl disable --now makia-stealth 2>/dev/null || true
systemctl disable --now makia-wstunnel 2>/dev/null || true
rm -f /etc/systemd/system/makia-vps-manager.service /etc/systemd/system/makia-policy-enforcer.service /etc/systemd/system/makia-metrics-sampler.service /etc/systemd/system/makia-protocol-traffic.service
rm -f /etc/systemd/system/makia-ikev2-firewall.service /etc/systemd/system/makia-stealth.service /etc/systemd/system/makia-wstunnel.service
rm -f /etc/nginx/sites-enabled/makia-vps-manager /etc/nginx/sites-available/makia-vps-manager
rm -f /usr/local/sbin/makia-update /usr/local/sbin/makia-backup /usr/local/sbin/makia-uninstall /usr/local/sbin/makia-doctor /usr/local/sbin/makia-uat-smoke /usr/local/sbin/makia-reset-admin /usr/local/sbin/makia-upgrade
rm -f /usr/local/sbin/dragon-update /usr/local/sbin/dragon-backup /usr/local/sbin/dragon-uninstall
rm -f /usr/local/lib/makia-vps-manager/ikev2-firewall.sh
rmdir /usr/local/lib/makia-vps-manager 2>/dev/null || true
systemctl daemon-reload
nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
rm -rf "$APP"
echo "Makia VPS Manager removed. Backups under /var/backups/makia-vps-manager are preserved."

rm -f /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync
