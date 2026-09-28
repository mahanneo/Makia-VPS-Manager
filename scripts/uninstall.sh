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
systemctl disable --now makia-wstunnel 2>/dev/null || true
systemctl disable --now makia-ikev2-network 2>/dev/null || true
rm -f /etc/systemd/system/makia-vps-manager.service /etc/systemd/system/makia-policy-enforcer.service /etc/systemd/system/makia-metrics-sampler.service /etc/systemd/system/makia-protocol-traffic.service /etc/systemd/system/makia-wstunnel.service /etc/systemd/system/makia-ikev2-network.service
rm -f /etc/nginx/sites-enabled/makia-vps-manager /etc/nginx/sites-available/makia-vps-manager
rm -f /usr/local/sbin/makia-update /usr/local/sbin/makia-backup /usr/local/sbin/makia-uninstall /usr/local/sbin/makia-doctor /usr/local/sbin/makia-uat-smoke /usr/local/sbin/makia-reset-admin /usr/local/sbin/makia-upgrade /usr/local/sbin/makia-ikev2-network /usr/local/sbin/makia-install-wstunnel
rm -f /usr/local/sbin/dragon-update /usr/local/sbin/dragon-backup /usr/local/sbin/dragon-uninstall
systemctl daemon-reload
nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
rm -rf "$APP"
echo "Makia VPS Manager removed. Backups and protocol credentials/configs are preserved."
echo "IKEv2 / Stunnel / WStunnel protocol configs under /etc are intentionally not purged."

rm -f /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync
rm -f /etc/letsencrypt/renewal-hooks/deploy/makia-vpn-tls-sync

# Migration restore runner/unit are code/runtime artifacts; encrypted backup history is preserved.
systemctl stop 'makia-migration-restore@*.service' 2>/dev/null || true
rm -f /etc/systemd/system/makia-migration-restore@.service
rm -f /usr/local/sbin/makia-run-migration-restore
