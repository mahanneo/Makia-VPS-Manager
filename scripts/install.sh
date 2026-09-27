#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install.sh"
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Unsupported system: /etc/os-release not found"
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Unsupported OS: ${ID:-unknown}. Supported: Ubuntu 22.04/24.04."
  exit 1
fi
case "${VERSION_ID:-}" in
  22.04|24.04) ;;
  *) echo "Unsupported Ubuntu version: ${VERSION_ID:-unknown}. Supported: 22.04/24.04."; exit 1 ;;
esac

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP=/opt/makia-vps-manager
OLD_APP=/opt/dragon-vps-manager-ng
DATA="$APP/data"
ADMIN_PASSWORD="${MAKIA_INITIAL_ADMIN_PASSWORD:-${DRAGON_INITIAL_ADMIN_PASSWORD:-}}"

if [[ -z "$ADMIN_PASSWORD" ]]; then
  ADMIN_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
fi
if [[ ${#ADMIN_PASSWORD} -lt 16 ]]; then
  echo "MAKIA_INITIAL_ADMIN_PASSWORD must be at least 16 characters."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx curl ca-certificates tar fail2ban wireguard openvpn easy-rsa iptables stunnel4 certbot python3-certbot-nginx strongswan-swanctl charon-systemd strongswan-pki libcharon-extra-plugins

install -d -m 0750 "$APP"
if [[ ! -d "$DATA" && -d "$OLD_APP/data" ]]; then
  echo "Migrating existing Dragon data into Makia..."
  cp -a "$OLD_APP/data" "$DATA"
fi
install -d -m 0750 "$DATA"
install -d -m 0700 /var/backups/makia-vps-manager
install -d -m 0700 /etc/makia-vps-manager
if [[ ! -f /etc/makia-vps-manager/makia.env ]]; then
  cat >/etc/makia-vps-manager/makia.env <<EOF
# Makia owner/distribution configuration. Keep root-only.
MAKIA_SUPPORT_TELEGRAM=${MAKIA_SUPPORT_TELEGRAM:-}
MAKIA_SUPPORT_WEBHOOK_URL=${MAKIA_SUPPORT_WEBHOOK_URL:-}
MAKIA_SUPPORT_WEBHOOK_TOKEN=${MAKIA_SUPPORT_WEBHOOK_TOKEN:-}
MAKIA_RELEASE_ARCHIVE_URL=${MAKIA_RELEASE_ARCHIVE_URL:-}
MAKIA_RELEASE_BEARER_TOKEN=${MAKIA_RELEASE_BEARER_TOKEN:-}
MAKIA_ADMIN_ALLOWED_CIDRS=${MAKIA_ADMIN_ALLOWED_CIDRS:-}
EOF
  chmod 0600 /etc/makia-vps-manager/makia.env
fi

cp -a "$SOURCE_DIR/app" "$SOURCE_DIR/requirements.txt" "$SOURCE_DIR/VERSION" "$APP/"
chown -R root:root "$APP/app"
find "$APP/app" -type d -exec chmod 0750 {} +
find "$APP/app" -type f -exec chmod 0640 {} +
chmod 0640 "$APP/requirements.txt" "$APP/VERSION"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip
"$APP/.venv/bin/pip" install -r "$APP/requirements.txt"

(
  cd "$APP"
  MAKIA_INITIAL_ADMIN_PASSWORD="$ADMIN_PASSWORD"   MAKIA_DATA_DIR="$DATA"   "$APP/.venv/bin/python" -c 'from app.db import init_db; init_db()'
)

systemctl disable --now dragon-vps-manager 2>/dev/null || true
rm -f /etc/systemd/system/dragon-vps-manager.service

install -m 0644 "$SOURCE_DIR/systemd/makia-vps-manager.service" /etc/systemd/system/makia-vps-manager.service
install -m 0644 "$SOURCE_DIR/systemd/makia-policy-enforcer.service" /etc/systemd/system/makia-policy-enforcer.service
install -m 0644 "$SOURCE_DIR/systemd/makia-metrics-sampler.service" /etc/systemd/system/makia-metrics-sampler.service
install -m 0644 "$SOURCE_DIR/systemd/makia-protocol-traffic.service" /etc/systemd/system/makia-protocol-traffic.service
install -m 0644 "$SOURCE_DIR/systemd/makia-ikev2-firewall.service" /etc/systemd/system/makia-ikev2-firewall.service
install -m 0644 "$SOURCE_DIR/systemd/makia-stealth.service" /etc/systemd/system/makia-stealth.service
install -m 0644 "$SOURCE_DIR/systemd/makia-wstunnel.service" /etc/systemd/system/makia-wstunnel.service
install -m 0644 "$SOURCE_DIR/nginx/makia-vps-manager.conf" /etc/nginx/sites-available/makia-vps-manager
ln -sfn /etc/nginx/sites-available/makia-vps-manager /etc/nginx/sites-enabled/makia-vps-manager
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/dragon-vps-manager /etc/nginx/sites-available/dragon-vps-manager

install -m 0755 "$SOURCE_DIR/scripts/update.sh" /usr/local/sbin/makia-update
install -m 0755 "$SOURCE_DIR/scripts/backup.sh" /usr/local/sbin/makia-backup
install -m 0755 "$SOURCE_DIR/scripts/uninstall.sh" /usr/local/sbin/makia-uninstall
install -m 0755 "$SOURCE_DIR/scripts/doctor.sh" /usr/local/sbin/makia-doctor
install -m 0755 "$SOURCE_DIR/scripts/uat-smoke.sh" /usr/local/sbin/makia-uat-smoke
install -m 0755 "$SOURCE_DIR/scripts/restore-portable.py" /usr/local/sbin/makia-restore-portable
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
install -m 0755 "$SOURCE_DIR/scripts/xray-cert-sync.sh" /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync
install -m 0755 "$SOURCE_DIR/scripts/reset-admin.sh" /usr/local/sbin/makia-reset-admin
install -m 0755 "$SOURCE_DIR/scripts/configure-owner.py" /usr/local/sbin/makia-owner-config
install -d -m 0755 /usr/local/lib/makia-vps-manager
install -m 0755 "$SOURCE_DIR/scripts/ikev2-firewall.sh" /usr/local/lib/makia-vps-manager/ikev2-firewall.sh
bash "$SOURCE_DIR/scripts/install-wstunnel.sh"
install -m 0755 "$SOURCE_DIR/upgrade.sh" /usr/local/sbin/makia-upgrade
ln -sfn /usr/local/sbin/makia-update /usr/local/sbin/dragon-update
ln -sfn /usr/local/sbin/makia-backup /usr/local/sbin/dragon-backup
ln -sfn /usr/local/sbin/makia-uninstall /usr/local/sbin/dragon-uninstall

systemctl daemon-reload
systemctl enable --now makia-vps-manager
systemctl enable --now makia-policy-enforcer
systemctl enable --now makia-metrics-sampler
systemctl enable --now makia-protocol-traffic

# Baseline SSH brute-force protection. We do not enable/modify UFW automatically
# because doing so without knowing the operator's SSH path can lock them out.
install -d -m 0755 /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/makia-sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban

echo "Provisioning Makia full protocol stack (Xray, WireGuard, OpenVPN, Stunnel)..."
(
  cd "$APP"
  MAKIA_DATA_DIR="$DATA" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
from app.db import set_setting

result=protocol_ops.ensure_full_protocol_stack()
wg=result["wireguard"]
ov=result["openvpn"]
if wg.get("port"):
    set_setting("default_wireguard_port",int(wg["port"]))
if ov.get("port"):
    set_setting("default_openvpn_port",int(ov["port"]))
if ov.get("proto"):
    set_setting("default_openvpn_proto","tcp" if str(ov["proto"]).startswith("tcp") else "udp")
print("Full protocol stack READY")
print("  Xray: active")
print("  WireGuard: UDP/%s" % (wg.get("port") or "?"))
print("  OpenVPN: %s/%s" % (str(ov.get("proto") or "udp").upper(), ov.get("port") or "?"))
print("  Stunnel: installed")
PY
)

nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "Running full-stack installation smoke gate..."
/usr/local/sbin/makia-uat-smoke

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
printf '\nMakia VPS Manager installed successfully.\n'
printf 'Panel: http://%s/\n' "${SERVER_IP:-SERVER_IP}"
printf 'Username: admin\n'
printf 'Bootstrap password: %s\n' "$ADMIN_PASSWORD"
printf '\nIMPORTANT: change the administrator password immediately.\n'
printf 'For public exposure, enable HTTPS and review Security Center first.\n'
printf 'Protocol stack: Xray + WireGuard + OpenVPN are preinstalled and bootstrapped.\n'
printf 'You can create users immediately after login.\n'
printf 'Run makia-doctor for host diagnostics.\n\n'
