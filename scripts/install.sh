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
CREDENTIAL_FILE=/root/makia-install-credentials.txt
ADMIN_PASSWORD="${MAKIA_INITIAL_ADMIN_PASSWORD:-${DRAGON_INITIAL_ADMIN_PASSWORD:-}}"
NEW_ADMIN_BOOTSTRAP=0

if ! command -v systemctl >/dev/null 2>&1 || [[ ! -d /run/systemd/system ]]; then
  echo "Unsupported environment: Makia requires an Ubuntu VPS booted with systemd." >&2
  echo "Use a normal Ubuntu 22.04/24.04 VPS, not a minimal container without systemd." >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64|amd64|aarch64|arm64) ;;
  *) echo "Unsupported CPU architecture: $(uname -m). Supported: amd64/arm64." >&2; exit 1 ;;
esac

FREE_KB="$(df -Pk / | awk 'NR==2 {print $4}')"
if [[ ! "$FREE_KB" =~ ^[0-9]+$ ]] || (( FREE_KB < 1048576 )); then
  echo "At least 1 GiB of free disk space is required for a clean Makia install." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if apt-get -o DPkg::Lock::Timeout=180 "$@"; then
      return 0
    fi
    echo "[MAKIA] apt-get $* failed (attempt $attempt/3); retrying..." >&2
    sleep $((attempt * 5))
  done
  return 1
}

echo "[MAKIA] Installing required Ubuntu packages..."
apt_retry update
apt_retry install -y --no-install-recommends \
  python3 python3-venv python3-pip nginx curl ca-certificates tar gzip unzip \
  iproute2 openssl fail2ban \
  wireguard-tools openvpn easy-rsa iptables stunnel4 \
  certbot python3-certbot-nginx strongswan strongswan-pki libcharon-extra-plugins

# A failed/partial install can already contain the administrator row. Never
# generate or advertise a new password in that case: init_db intentionally
# preserves the existing admin credential.
ADMIN_EXISTS=0
if [[ -s "$DATA/makia.db" ]]; then
  ADMIN_EXISTS="$(python3 - "$DATA/makia.db" <<'PY'
import sqlite3, sys
db=sys.argv[1]
try:
    con=sqlite3.connect(db)
    row=con.execute("SELECT 1 FROM admins LIMIT 1").fetchone()
    print("1" if row else "0")
except Exception:
    print("0")
PY
)"
fi

if [[ "$ADMIN_EXISTS" == "1" ]]; then
  if [[ -n "$ADMIN_PASSWORD" ]]; then
    echo "[MAKIA] Existing administrator detected; MAKIA_INITIAL_ADMIN_PASSWORD will not overwrite it." >&2
    echo "[MAKIA] Use 'sudo makia-reset-admin' after installation if the password must be changed." >&2
  fi
  ADMIN_PASSWORD=""
else
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
  NEW_ADMIN_BOOTSTRAP=1
  umask 077
  cat >"$CREDENTIAL_FILE" <<EOF
Makia VPS Manager
Username: admin
Bootstrap password: $ADMIN_PASSWORD
Panel: pending until installation completes
EOF
  chmod 0600 "$CREDENTIAL_FILE"
fi

install_failure_hint() {
  rc=$?
  printf '\n[MAKIA] Installation stopped before the final success screen (exit %s).\n' "$rc" >&2
  if [[ "$NEW_ADMIN_BOOTSTRAP" == "1" ]]; then
    printf '[MAKIA] The generated admin credential is preserved at: %s\n' "$CREDENTIAL_FILE" >&2
  else
    printf '[MAKIA] Existing administrator credentials were preserved and were not rotated.\n' >&2
  fi
  printf '[MAKIA] Fix the reported error and re-run the installer; existing Makia data is not intentionally deleted.\n\n' >&2
  exit "$rc"
}
trap install_failure_hint ERR

if [[ "${MAKIA_ENABLE_OUTLINE:-0}" == "1" ]]; then
  apt_retry install -y docker.io
  systemctl enable --now docker
fi

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
MAKIA_CLIENT_PORTAL_ENABLED=${MAKIA_CLIENT_PORTAL_ENABLED:-auto}
MAKIA_PUBLIC_BASE_URL=${MAKIA_PUBLIC_BASE_URL:-}
MAKIA_ANDROID_CONNECTOR_URL=${MAKIA_ANDROID_CONNECTOR_URL:-}
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
  MAKIA_INITIAL_ADMIN_PASSWORD="$ADMIN_PASSWORD"   MAKIA_DATA_DIR="$DATA"   "$APP/.venv/bin/python" -c 'from app.db import init_db; from app.security import ensure_secret; init_db(); ensure_secret()'
)

systemctl disable --now dragon-vps-manager 2>/dev/null || true
rm -f /etc/systemd/system/dragon-vps-manager.service

install -m 0644 "$SOURCE_DIR/systemd/makia-vps-manager.service" /etc/systemd/system/makia-vps-manager.service
install -m 0644 "$SOURCE_DIR/systemd/makia-policy-enforcer.service" /etc/systemd/system/makia-policy-enforcer.service
install -m 0644 "$SOURCE_DIR/systemd/makia-metrics-sampler.service" /etc/systemd/system/makia-metrics-sampler.service
install -m 0644 "$SOURCE_DIR/systemd/makia-protocol-traffic.service" /etc/systemd/system/makia-protocol-traffic.service
install -m 0644 "$SOURCE_DIR/systemd/makia-browser-gateway.service" /etc/systemd/system/makia-browser-gateway.service
install -m 0644 "$SOURCE_DIR/systemd/makia-wstunnel.service" /etc/systemd/system/makia-wstunnel.service
install -m 0644 "$SOURCE_DIR/systemd/makia-openvpn-wstunnel.service" /etc/systemd/system/makia-openvpn-wstunnel.service
install -m 0644 "$SOURCE_DIR/systemd/makia-ikev2-network.service" /etc/systemd/system/makia-ikev2-network.service
install -m 0644 "$SOURCE_DIR/systemd/makia-migration-restore@.service" /etc/systemd/system/makia-migration-restore@.service
install -m 0644 "$SOURCE_DIR/systemd/makia-scheduled-backup.service" /etc/systemd/system/makia-scheduled-backup.service
install -m 0644 "$SOURCE_DIR/systemd/makia-scheduled-backup.timer" /etc/systemd/system/makia-scheduled-backup.timer
install -m 0644 "$SOURCE_DIR/systemd/makia-ops-monitor.service" /etc/systemd/system/makia-ops-monitor.service
install -m 0644 "$SOURCE_DIR/systemd/makia-ops-monitor.timer" /etc/systemd/system/makia-ops-monitor.timer
install -m 0644 "$SOURCE_DIR/systemd/makia-mtproxy.service" /etc/systemd/system/makia-mtproxy.service
install -m 0644 "$SOURCE_DIR/nginx/makia-vps-manager.conf" /etc/nginx/sites-available/makia-vps-manager
ln -sfn /etc/nginx/sites-available/makia-vps-manager /etc/nginx/sites-enabled/makia-vps-manager
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/dragon-vps-manager /etc/nginx/sites-available/dragon-vps-manager

install -m 0755 "$SOURCE_DIR/scripts/update.sh" /usr/local/sbin/makia-update
install -m 0755 "$SOURCE_DIR/scripts/backup.sh" /usr/local/sbin/makia-backup
install -m 0755 "$SOURCE_DIR/scripts/uninstall.sh" /usr/local/sbin/makia-uninstall
install -m 0755 "$SOURCE_DIR/scripts/doctor.sh" /usr/local/sbin/makia-doctor
install -m 0755 "$SOURCE_DIR/scripts/uat-smoke.sh" /usr/local/sbin/makia-uat-smoke
install -m 0755 "$SOURCE_DIR/scripts/restore-portable.py" /usr/local/sbin/makia-restore-portable
install -m 0755 "$SOURCE_DIR/scripts/run-migration-restore.py" /usr/local/sbin/makia-run-migration-restore
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
install -m 0755 "$SOURCE_DIR/scripts/xray-cert-sync.sh" /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync
install -m 0755 "$SOURCE_DIR/scripts/makia-vpn-tls-sync.sh" /etc/letsencrypt/renewal-hooks/deploy/makia-vpn-tls-sync
install -m 0755 "$SOURCE_DIR/scripts/reset-admin.sh" /usr/local/sbin/makia-reset-admin
install -m 0755 "$SOURCE_DIR/scripts/configure-owner.py" /usr/local/sbin/makia-owner-config
install -m 0755 "$SOURCE_DIR/scripts/ikev2-network.sh" /usr/local/sbin/makia-ikev2-network
install -m 0755 "$SOURCE_DIR/scripts/install-wstunnel.sh" /usr/local/sbin/makia-install-wstunnel
install -m 0755 "$SOURCE_DIR/scripts/install-outline.sh" /usr/local/sbin/makia-install-outline
install -m 0755 "$SOURCE_DIR/scripts/install-mtproxy.sh" /usr/local/sbin/makia-install-mtproxy
install -m 0755 "$SOURCE_DIR/scripts/refresh-mtproxy.sh" /usr/local/sbin/makia-refresh-mtproxy
install -m 0755 "$SOURCE_DIR/scripts/install-dns.sh" /usr/local/sbin/makia-install-dns
echo "Preparing optional Telegram/DNS tooling for panel-managed configuration..."
if ! /usr/local/sbin/makia-install-mtproxy --install-only; then
  echo "WARNING: MTProxy tooling preparation failed; panel will show the root repair/install command."
fi
if ! /usr/local/sbin/makia-install-dns --install-only; then
  echo "WARNING: DNS tooling preparation failed; panel will show the root repair/install command."
fi
# Enforce the shared config-directory contract after all optional installers.
# DNS must never revoke the MTProxy service group's traverse permission.
if getent group makia-mtproxy >/dev/null 2>&1; then
  chown root:makia-mtproxy /etc/makia-vps-manager
  chmod 0710 /etc/makia-vps-manager
else
  chown root:root /etc/makia-vps-manager
  chmod 0700 /etc/makia-vps-manager
fi
[[ -f /etc/makia-vps-manager/makia.env ]] && { chown root:root /etc/makia-vps-manager/makia.env; chmod 0600 /etc/makia-vps-manager/makia.env; }
[[ -f /etc/makia-vps-manager/dns.json ]] && { chown root:root /etc/makia-vps-manager/dns.json; chmod 0600 /etc/makia-vps-manager/dns.json; }
[[ -f /etc/makia-vps-manager/mtproxy.env ]] && { chown root:root /etc/makia-vps-manager/mtproxy.env; chmod 0600 /etc/makia-vps-manager/mtproxy.env; }
if [[ -f /etc/makia-vps-manager/mtproxy.toml ]] && getent group makia-mtproxy >/dev/null 2>&1; then
  chown root:makia-mtproxy /etc/makia-vps-manager/mtproxy.toml
  chmod 0640 /etc/makia-vps-manager/mtproxy.toml
fi
/usr/local/sbin/makia-install-wstunnel
install -m 0755 "$SOURCE_DIR/upgrade.sh" /usr/local/sbin/makia-upgrade
ln -sfn /usr/local/sbin/makia-update /usr/local/sbin/dragon-update
ln -sfn /usr/local/sbin/makia-backup /usr/local/sbin/dragon-backup
ln -sfn /usr/local/sbin/makia-uninstall /usr/local/sbin/dragon-uninstall

systemctl daemon-reload
systemctl enable --now makia-vps-manager
systemctl enable --now makia-policy-enforcer
systemctl enable --now makia-metrics-sampler
systemctl enable --now makia-protocol-traffic
systemctl enable --now makia-browser-gateway
BROWSER_GATEWAY_PORT="${MAKIA_BROWSER_GATEWAY_PORT:-9444}"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  ufw allow "${BROWSER_GATEWAY_PORT}/tcp" comment 'Makia Browser Gateway' >/dev/null 2>&1 || true
fi
systemctl enable --now makia-scheduled-backup.timer
systemctl enable --now makia-ops-monitor.timer

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

echo "Provisioning Makia full protocol stack (Xray, WireGuard, OpenVPN, Stunnel; IKEv2/WStunnel tooling ready)..."
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
PANEL_URL="http://${SERVER_IP:-SERVER_IP}/"
if [[ "$NEW_ADMIN_BOOTSTRAP" == "1" ]]; then
  cat >"$CREDENTIAL_FILE" <<EOF
Makia VPS Manager
Panel: $PANEL_URL
Username: admin
Bootstrap password: $ADMIN_PASSWORD
Credential file: $CREDENTIAL_FILE
EOF
  chmod 0600 "$CREDENTIAL_FILE"
fi
trap - ERR

printf '\n'
printf '+------------------------------------------------------------------+\n'
printf '|                 MAKIA VPS MANAGER - INSTALL READY                |\n'
printf '+------------------------------------------------------------------+\n'
printf '| Panel    : %-53s |\n' "$PANEL_URL"
printf '| Username : %-53s |\n' "admin"
if [[ "$NEW_ADMIN_BOOTSTRAP" == "1" ]]; then
  printf '| Password : %-53s |\n' "$ADMIN_PASSWORD"
  printf '+------------------------------------------------------------------+\n'
  printf '| Credentials saved (root-only): %-32s |\n' "$CREDENTIAL_FILE"
  printf '+------------------------------------------------------------------+\n'
  printf '\nIMPORTANT: save the password now, then change it after first login.\n'
else
  printf '| Password : %-53s |\n' "existing credential preserved"
  printf '+------------------------------------------------------------------+\n'
  printf '\nExisting administrator detected; its password was not changed.\n'
  printf 'If needed, reset it explicitly with: sudo makia-reset-admin\n'
fi
printf 'For public exposure, configure Domain + HTTPS and review Security Center.\n'
printf 'Protocol stack: Xray + WireGuard + OpenVPN are preinstalled and bootstrapped.\n'
printf 'Run: makia-doctor   for host diagnostics.\n\n'
