#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run as root."; exit 1; }
export DEBIAN_FRONTEND=noninteractive
FORCE_MAIN="${MAKIA_FORCE_MAIN:-0}"

ENV_FILE=/etc/makia-vps-manager/makia.env
if [[ -r "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    case "$key" in
      MAKIA_SUPPORT_TELEGRAM|MAKIA_SUPPORT_WEBHOOK_URL|MAKIA_SUPPORT_WEBHOOK_TOKEN|MAKIA_RELEASE_ARCHIVE_URL|MAKIA_RELEASE_BEARER_TOKEN|MAKIA_ADMIN_ALLOWED_CIDRS)
        printf -v "$key" '%s' "$value"
        export "$key"
        ;;
    esac
  done <"$ENV_FILE"
fi

REPO="mahanneo/Makia-VPS-Manager"
REF="${MAKIA_REF:-${DRAGON_REF:-main}}"
APP=/opt/makia-vps-manager
OLD_APP=/opt/dragon-vps-manager-ng
TMP="$(mktemp -d)"
ROLLBACK_ARMED=0
RELEASE_BACKUP=""

MTPROXY_ENV_PATH=/etc/makia-vps-manager/mtproxy.env
MTPROXY_CONFIG_PATH=/etc/makia-vps-manager/mtproxy.toml
DNS_STATE_PATH=/etc/makia-vps-manager/dns.json
DNS_CONFIG_PATH=/etc/unbound/unbound.conf.d/makia.conf

file_sha256(){
  local path="$1"
  [[ -f "$path" ]] || return 0
  sha256sum "$path" | awk '{print $1}'
}

MTPROXY_ENV_PRE_SHA="$(file_sha256 "$MTPROXY_ENV_PATH")"
MTPROXY_CONFIG_PRE_SHA="$(file_sha256 "$MTPROXY_CONFIG_PATH")"
DNS_STATE_PRE_SHA="$(file_sha256 "$DNS_STATE_PATH")"
DNS_CONFIG_PRE_SHA="$(file_sha256 "$DNS_CONFIG_PATH")"
MTPROXY_ENV_ACCEPTED_SHA="$MTPROXY_ENV_PRE_SHA"
MTPROXY_CONFIG_ACCEPTED_SHA="$MTPROXY_CONFIG_PRE_SHA"
DNS_STATE_ACCEPTED_SHA="$DNS_STATE_PRE_SHA"
DNS_CONFIG_ACCEPTED_SHA="$DNS_CONFIG_PRE_SHA"
MTPROXY_WAS_ACTIVE=0
DNS_WAS_ACTIVE=0
DNS_WAS_QUERY_OK=0
systemctl is-active --quiet makia-mtproxy 2>/dev/null && MTPROXY_WAS_ACTIVE=1 || true
systemctl is-active --quiet unbound 2>/dev/null && DNS_WAS_ACTIVE=1 || true
if [[ "$DNS_WAS_ACTIVE" -eq 1 ]] && command -v dig >/dev/null 2>&1; then
  DNS_PRECHECK="$(dig @127.0.0.1 example.com A +short +time=2 +tries=1 2>/dev/null || true)"
  if [[ -n "$DNS_PRECHECK" ]]; then
    DNS_WAS_QUERY_OK=1
  fi
fi

assert_preserved_file(){
  local path="$1" before="$2" label="$3"
  [[ -n "$before" ]] || return 0
  if [[ ! -f "$path" ]]; then
    echo "ERROR: $label disappeared during update: $path" >&2
    return 1
  fi
  local after
  after="$(file_sha256 "$path")"
  if [[ "$after" != "$before" ]]; then
    echo "ERROR: $label changed unexpectedly during update: $path" >&2
    return 1
  fi
}

on_exit(){
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 && "$ROLLBACK_ARMED" -eq 1 && -n "$RELEASE_BACKUP" && -f "$RELEASE_BACKUP" ]]; then
    echo
    echo "Update failed. Restoring previous Makia runtime..."
    set +e
    systemctl stop makia-vps-manager 2>/dev/null
    rm -rf "$APP/app"
    tar -xzf "$RELEASE_BACKUP" -C /
    if [[ -f "$APP/requirements.txt" && -x "$APP/.venv/bin/pip" ]]; then
      "$APP/.venv/bin/pip" install -r "$APP/requirements.txt" >/dev/null 2>&1
    fi
    systemctl daemon-reload
    nginx -t >/dev/null 2>&1 && systemctl reload nginx
    systemctl restart makia-vps-manager
    systemctl restart makia-policy-enforcer 2>/dev/null
    systemctl restart makia-metrics-sampler 2>/dev/null
    systemctl restart makia-protocol-traffic 2>/dev/null
    if [[ "${XRAY_WAS_ACTIVE:-0}" -eq 1 ]]; then
      systemctl restart xray 2>/dev/null
    fi
    if [[ "${WG_WAS_ACTIVE:-0}" -eq 1 ]]; then
      systemctl restart wg-quick@wg0 2>/dev/null
    fi
    if [[ "${OVPN_WAS_ACTIVE:-0}" -eq 1 ]]; then
      systemctl restart openvpn-server@server 2>/dev/null
    fi
    if [[ "${STUNNEL_WAS_ACTIVE:-0}" -eq 1 && -n "${STUNNEL_RUNTIME_SERVICE:-}" ]]; then
      systemctl enable --now "$STUNNEL_RUNTIME_SERVICE" 2>/dev/null
      systemctl restart "$STUNNEL_RUNTIME_SERVICE" 2>/dev/null
    fi
    if [[ "${WSTUNNEL_WAS_ACTIVE:-0}" -eq 1 ]]; then
      systemctl enable --now makia-wstunnel 2>/dev/null
      systemctl restart makia-wstunnel 2>/dev/null
    fi
    if [[ "${OVPN_WSTUNNEL_WAS_ACTIVE:-0}" -eq 1 ]]; then
      systemctl enable --now openvpn-server@makia-ws 2>/dev/null
      systemctl restart openvpn-server@makia-ws 2>/dev/null
      systemctl enable --now makia-openvpn-wstunnel 2>/dev/null
      systemctl restart makia-openvpn-wstunnel 2>/dev/null
    fi
    if [[ -s "$MTPROXY_ENV_PATH" && -s "$MTPROXY_CONFIG_PATH" && -x /opt/makia-mtproxy/mtg ]]; then
      systemctl enable --now makia-mtproxy 2>/dev/null
      systemctl restart makia-mtproxy 2>/dev/null
    fi
    if [[ -s "$DNS_CONFIG_PATH" ]] && command -v unbound >/dev/null 2>&1; then
      systemctl enable --now unbound 2>/dev/null
      systemctl restart unbound 2>/dev/null
    fi
    restored=0
    for _ in {1..12}; do
      if curl -fsS --max-time 3 http://127.0.0.1:8787/healthz >/dev/null 2>&1; then
        restored=1; break
      fi
      sleep 1
    done
    if [[ "$restored" -eq 1 ]]; then
      echo "Rollback successful. Previous backend is healthy again."
      echo "Runtime backup: $RELEASE_BACKUP"
    else
      echo "Rollback attempted, but backend is still unhealthy."
      echo "Run: sudo journalctl -u makia-vps-manager -n 120 --no-pager"
    fi
    set -e
  fi
  rm -rf "$TMP"
  exit "$rc"
}
trap on_exit EXIT

if [[ ! -d "$APP" && -d "$OLD_APP" ]]; then
  echo "Legacy installation detected. Run the latest installer once to migrate to /opt/makia-vps-manager."
  exit 2
fi
[[ -d "$APP" ]] || { echo "Makia VPS Manager is not installed."; exit 1; }
install -d -m 0700 /var/backups/makia-vps-manager

XRAY_WAS_PRESENT=0
XRAY_WAS_ACTIVE=0
if command -v xray >/dev/null 2>&1 && { [[ -f /usr/local/etc/xray/config.json ]] || [[ -f /etc/xray/config.json ]]; }; then
  XRAY_WAS_PRESENT=1
  systemctl is-active --quiet xray 2>/dev/null && XRAY_WAS_ACTIVE=1 || true
fi

openvpn_primary_listener_present(){
  local conf=/etc/openvpn/server/server.conf port proto flag
  [[ -f "$conf" ]] || return 1
  port="$(awk '$1=="port"{print $2; exit}' "$conf" 2>/dev/null || true)"
  proto="$(awk '$1=="proto"{print tolower($2); exit}' "$conf" 2>/dev/null || true)"
  [[ "$port" =~ ^[0-9]+$ ]] || return 1
  if [[ "$proto" == tcp* ]]; then flag=-ltn; else flag=-lun; fi
  ss -H "$flag" 2>/dev/null | grep -Eq ":${port}([[:space:]]|$)"
}

OVPN_WAS_PRESENT=0
OVPN_WAS_ACTIVE=0
OVPN_WAS_LISTENING=0
if [[ -f /etc/openvpn/server/server.conf ]]; then
  OVPN_WAS_PRESENT=1
  systemctl is-active --quiet openvpn-server@server 2>/dev/null && OVPN_WAS_ACTIVE=1 || true
  if [[ "$OVPN_WAS_ACTIVE" -eq 1 ]] && openvpn_primary_listener_present; then
    OVPN_WAS_LISTENING=1
  fi
fi

WG_WAS_PRESENT=0
WG_WAS_ACTIVE=0
if [[ -f /etc/wireguard/wg0.conf ]]; then
  WG_WAS_PRESENT=1
  systemctl is-active --quiet wg-quick@wg0 2>/dev/null && WG_WAS_ACTIVE=1 || true
fi

STUNNEL_WAS_CONFIGURED=0
STUNNEL_WAS_ACTIVE=0
STUNNEL_RUNTIME_SERVICE=""
if [[ -f /etc/makia-vps-manager/stunnel-openvpn.conf ]]; then
  STUNNEL_WAS_CONFIGURED=1
  STUNNEL_RUNTIME_SERVICE="makia-stealth"
  systemctl is-active --quiet makia-stealth 2>/dev/null && STUNNEL_WAS_ACTIVE=1 || true
elif [[ -f /etc/stunnel/makia-openvpn.conf ]]; then
  STUNNEL_WAS_CONFIGURED=1
  STUNNEL_RUNTIME_SERVICE="stunnel4"
  systemctl is-active --quiet stunnel4 2>/dev/null && STUNNEL_WAS_ACTIVE=1 || true
fi

WSTUNNEL_WAS_CONFIGURED=0
WSTUNNEL_WAS_ACTIVE=0
if [[ -f /etc/makia-vps-manager/wstunnel.env ]]; then
  WSTUNNEL_WAS_CONFIGURED=1
  systemctl is-active --quiet makia-wstunnel 2>/dev/null && WSTUNNEL_WAS_ACTIVE=1 || true
fi

OVPN_WSTUNNEL_WAS_CONFIGURED=0
OVPN_WSTUNNEL_WAS_ACTIVE=0
if [[ -f /etc/makia-vps-manager/openvpn-wstunnel.env ]]; then
  OVPN_WSTUNNEL_WAS_CONFIGURED=1
  systemctl is-active --quiet makia-openvpn-wstunnel 2>/dev/null && OVPN_WSTUNNEL_WAS_ACTIVE=1 || true
fi

STAMP_DATA="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/makia-vps-manager/makia-data-${STAMP_DATA}.tar.gz"
BACKUP_TMP="$(mktemp -d)"
mkdir -p "$BACKUP_TMP/data"

# Bootstrap-safe live backup: do not depend on an older installed makia-backup
# because the currently installed copy may itself be the reason the upgrade fails.
tar -C "$APP" -cf - \
  --exclude='data/makia.db' \
  --exclude='data/makia.db-wal' \
  --exclude='data/makia.db-shm' \
  data | tar -C "$BACKUP_TMP" -xf -

if [[ -f "$APP/data/makia.db" ]]; then
  SRC_DB="$APP/data/makia.db" DST_DB="$BACKUP_TMP/data/makia.db" python3 - <<'PY'
import os, sqlite3
src=os.environ["SRC_DB"]
dst=os.environ["DST_DB"]
source=sqlite3.connect(f"file:{src}?mode=ro", uri=True)
target=sqlite3.connect(dst)
try:
    source.backup(target)
    target.commit()
finally:
    target.close()
    source.close()
PY
  chmod 0600 "$BACKUP_TMP/data/makia.db"
fi

tar -C "$BACKUP_TMP" -czf "$BACKUP" data
chmod 0600 "$BACKUP"
rm -rf "$BACKUP_TMP"
echo "Data backup created: $BACKUP"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_BACKUP="/var/backups/makia-vps-manager/makia-runtime-${STAMP}.tar.gz"
SNAPSHOT=("opt/makia-vps-manager/app" "opt/makia-vps-manager/requirements.txt" "opt/makia-vps-manager/VERSION")
for item in \
  "etc/systemd/system/makia-vps-manager.service" \
  "etc/systemd/system/makia-policy-enforcer.service" \
  "etc/systemd/system/makia-metrics-sampler.service" \
  "etc/systemd/system/makia-protocol-traffic.service" \
  "etc/systemd/system/makia-browser-gateway.service" \
  "etc/systemd/system/makia-stealth.service" \
  "etc/systemd/system/makia-scheduled-backup.service" \
  "etc/systemd/system/makia-scheduled-backup.timer" \
  "etc/systemd/system/makia-ops-monitor.service" \
  "etc/systemd/system/makia-ops-monitor.timer" \
  "etc/systemd/system/makia-mtproxy.service" \
  "etc/systemd/system/makia-wstunnel.service" \
  "etc/systemd/system/makia-openvpn-wstunnel.service" \
  "etc/systemd/system/makia-ikev2-network.service" \
  "usr/local/sbin/makia-update" \
  "usr/local/sbin/makia-upgrade" \
  "usr/local/sbin/makia-backup" \
  "usr/local/sbin/makia-uninstall" \
  "usr/local/sbin/makia-doctor" \
  "usr/local/sbin/makia-uat-smoke" \
  "usr/local/sbin/makia-restore-portable" \
  "usr/local/sbin/makia-run-migration-restore" \
  "usr/local/sbin/makia-reset-admin" \
  "usr/local/sbin/makia-owner-config" \
  "usr/local/sbin/makia-ikev2-network" \
  "usr/local/sbin/makia-install-wstunnel" \
  "usr/local/sbin/makia-install-outline" \
  "usr/local/sbin/makia-install-mtproxy" \
  "usr/local/sbin/makia-refresh-mtproxy" \
  "usr/local/sbin/makia-install-dns" \
  "etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync" \
  "etc/letsencrypt/renewal-hooks/deploy/makia-vpn-tls-sync" \
  "usr/local/etc/xray/config.json" \
  "etc/xray/config.json" \
  "etc/wireguard/wg0.conf" \
  "etc/openvpn/server" \
  "etc/stunnel/makia-openvpn.conf" \
  "etc/makia-vps-manager/stunnel-openvpn.conf" \
  "etc/default/stunnel4" \
  "etc/ipsec.conf" \
  "etc/ipsec.secrets" \
  "etc/makia-vps-manager/wstunnel.env" \
  "etc/makia-vps-manager/openvpn-wstunnel.env" \
  "etc/openvpn/server/makia-ws.conf" \
  "etc/makia-vps-manager/mtproxy.env" \
  "etc/makia-vps-manager/mtproxy.toml" \
  "etc/makia-vps-manager/dns.json" \
  "etc/unbound/unbound.conf.d/makia.conf" \
  "opt/makia-mtproxy" \
  "etc/nginx/sites-available/makia-vps-manager"; do
  [[ -e "/$item" ]] && SNAPSHOT+=("$item")
done
tar -C / -czf "$RELEASE_BACKUP" "${SNAPSHOT[@]}"
chmod 0600 "$RELEASE_BACKUP"
echo "Runtime rollback point: $RELEASE_BACKUP"

CURL_AUTH=()
if [[ -n "${MAKIA_RELEASE_BEARER_TOKEN:-}" ]]; then
  CURL_AUTH=(-H "Authorization: Bearer ${MAKIA_RELEASE_BEARER_TOKEN}")
fi

resolve_github_commit(){
  local ref="$1" api json sha
  api="https://api.github.com/repos/${REPO}/commits/${ref}"
  json="$(curl -fsSL --retry 3 "${CURL_AUTH[@]}" -H "Accept: application/vnd.github+json" "$api")"
  sha="$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha",""))')"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "Unable to resolve immutable GitHub commit for ref: $ref" >&2; return 1; }
  printf '%s' "$sha"
}

SOURCE_COMMIT=""
if [[ "$FORCE_MAIN" == "1" ]]; then
  REF="main"
  SOURCE_COMMIT="$(resolve_github_commit "$REF")"
  ARCHIVE_URL="https://codeload.github.com/${REPO}/tar.gz/${SOURCE_COMMIT}"
  echo "Force-main update enabled; pinned immutable source commit: $SOURCE_COMMIT"
elif [[ -n "${MAKIA_RELEASE_ARCHIVE_URL:-}" ]]; then
  ARCHIVE_URL="$MAKIA_RELEASE_ARCHIVE_URL"
  echo "Using explicitly configured release archive URL."
else
  SOURCE_COMMIT="$(resolve_github_commit "$REF")"
  ARCHIVE_URL="https://codeload.github.com/${REPO}/tar.gz/${SOURCE_COMMIT}"
  echo "Resolved release ref '$REF' to immutable commit: $SOURCE_COMMIT"
fi

curl -fL --retry 3 --retry-all-errors "${CURL_AUTH[@]}" "$ARCHIVE_URL" -o "$TMP/source.tar.gz"
tar -tzf "$TMP/source.tar.gz" >/dev/null
tar -xzf "$TMP/source.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d -name 'Makia-VPS-Manager-*' | head -n1)"
[[ -n "$SRC" ]] || { echo "Unable to locate extracted source."; exit 1; }

if [[ -n "$SOURCE_COMMIT" ]]; then
  EXPECTED_PREFIX="Makia-VPS-Manager-${SOURCE_COMMIT}"
  [[ "$(basename "$SRC")" == "$EXPECTED_PREFIX" ]] || {
    echo "Immutable archive root mismatch: expected $EXPECTED_PREFIX, got $(basename "$SRC")" >&2
    exit 1
  }
fi

[[ -s "$SRC/VERSION" ]] || { echo "Downloaded release is missing VERSION." >&2; exit 1; }
RELEASE_VERSION="$(tr -d '[:space:]' < "$SRC/VERSION")"
[[ "$RELEASE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "Downloaded release has an invalid VERSION: $RELEASE_VERSION" >&2
  exit 1
}
echo "Downloaded immutable Makia release: version=$RELEASE_VERSION commit=${SOURCE_COMMIT:-custom-archive}"

install_verified_shell(){
  local src="$1" dest="$2" mode="${3:-0755}" tmp src_sha tmp_sha dest_sha
  [[ -f "$src" ]] || { echo "Missing shell source: $src" >&2; return 1; }
  bash -n "$src" || { echo "Source shell syntax failed: $src" >&2; return 1; }
  mkdir -p "$(dirname "$dest")"
  tmp="$(mktemp "$(dirname "$dest")/.makia-script.XXXXXX")"
  if ! install -m "$mode" "$src" "$tmp"; then
    rm -f "$tmp"
    return 1
  fi
  if ! bash -n "$tmp"; then
    echo "Staged shell syntax failed: $src" >&2
    rm -f "$tmp"
    return 1
  fi
  src_sha="$(sha256sum "$src" | awk '{print $1}')"
  tmp_sha="$(sha256sum "$tmp" | awk '{print $1}')"
  if [[ "$src_sha" != "$tmp_sha" ]]; then
    echo "Staged shell hash mismatch: $src -> $dest" >&2
    rm -f "$tmp"
    return 1
  fi
  chown root:root "$tmp"
  chmod "$mode" "$tmp"
  mv -f "$tmp" "$dest"
  bash -n "$dest" || { echo "Installed shell syntax failed: $dest" >&2; return 1; }
  dest_sha="$(sha256sum "$dest" | awk '{print $1}')"
  [[ "$dest_sha" == "$src_sha" ]] || { echo "Installed shell hash mismatch: $dest" >&2; return 1; }
}

ensure_installed_shell_integrity(){
  local src="$1" dest="$2" src_sha dest_sha
  src_sha="$(sha256sum "$src" | awk '{print $1}')"
  dest_sha="$(sha256sum "$dest" 2>/dev/null | awk '{print $1}')"
  if ! bash -n "$dest" >/dev/null 2>&1 || [[ "$dest_sha" != "$src_sha" ]]; then
    echo "Repairing installed shell artifact: $dest"
    install_verified_shell "$src" "$dest"
  fi
  bash -n "$dest"
  dest_sha="$(sha256sum "$dest" | awk '{print $1}')"
  [[ "$dest_sha" == "$src_sha" ]] || { echo "Critical shell artifact still differs from source: $dest" >&2; return 1; }
}

echo "Preflighting critical release shell scripts..."
for script in   "$SRC/scripts/update.sh"   "$SRC/scripts/doctor.sh"   "$SRC/scripts/uat-smoke.sh"   "$SRC/scripts/backup.sh"   "$SRC/scripts/install-mtproxy.sh"   "$SRC/scripts/install-dns.sh"   "$SRC/upgrade.sh"; do
  bash -n "$script"
done

# Package managers must run from this root updater, before the hardened
# makia-vps-manager service is stopped. Running APT from the web service is
# incompatible with RestrictSUIDSGID/NoNewPrivileges because APT drops to
# the _apt user (UID 42).
NEED_HOST_PACKAGES=0
command -v fail2ban-client >/dev/null 2>&1 || NEED_HOST_PACKAGES=1
command -v certbot >/dev/null 2>&1 || NEED_HOST_PACKAGES=1
dpkg-query -W -f='${Status}' python3-certbot-nginx 2>/dev/null | grep -q 'install ok installed' || NEED_HOST_PACKAGES=1
dpkg-query -W -f='${Status}' strongswan 2>/dev/null | grep -q 'install ok installed' || NEED_HOST_PACKAGES=1
dpkg-query -W -f='${Status}' libcharon-extra-plugins 2>/dev/null | grep -q 'install ok installed' || NEED_HOST_PACKAGES=1
OUTLINE_HOST_PACKAGES=()
if [[ "${MAKIA_ENABLE_OUTLINE:-0}" == "1" || -s /opt/outline/access.txt ]]; then
  dpkg-query -W -f='${Status}' docker.io 2>/dev/null | grep -q 'install ok installed' || OUTLINE_HOST_PACKAGES+=(docker.io)
fi
if [[ "$NEED_HOST_PACKAGES" -eq 1 || "${#OUTLINE_HOST_PACKAGES[@]}" -gt 0 ]]; then
  echo "Ensuring host security/TLS/VPN/Outline packages outside the hardened web-service sandbox..."
  apt-get update
  apt-get install -y fail2ban certbot python3-certbot-nginx strongswan strongswan-pki libcharon-extra-plugins "${OUTLINE_HOST_PACKAGES[@]}"
fi
if command -v docker >/dev/null 2>&1 && [[ "${MAKIA_ENABLE_OUTLINE:-0}" == "1" || -s /opt/outline/access.txt ]]; then
  systemctl enable --now docker
fi

PROTOCOL_RUNTIME_CHANGED=1
if [[ -f "$APP/app/protocol_ops.py" && -f "$SRC/app/protocol_ops.py" ]] && cmp -s "$APP/app/protocol_ops.py" "$SRC/app/protocol_ops.py"; then
  PROTOCOL_RUNTIME_CHANGED=0
  echo "Protocol runtime code is unchanged; active VPN runtimes will be preserved without repair/restart."
else
  echo "Protocol runtime code changed; protocol readiness/repair gates remain enabled."
fi

ROLLBACK_ARMED=1
systemctl stop makia-vps-manager
rm -rf "$APP/app"
cp -a "$SRC/app" "$APP/app"
install -m 0640 "$SRC/requirements.txt" "$APP/requirements.txt"
install -m 0640 "$SRC/VERSION" "$APP/VERSION"
chown -R root:root "$APP/app"
find "$APP/app" -type d -exec chmod 0750 {} +
find "$APP/app" -type f -exec chmod 0640 {} +
"$APP/.venv/bin/pip" install -r "$APP/requirements.txt"

install -d -m 0755 /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/makia-sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
EOF

install -m 0644 "$SRC/systemd/makia-vps-manager.service" /etc/systemd/system/makia-vps-manager.service
install -m 0644 "$SRC/systemd/makia-policy-enforcer.service" /etc/systemd/system/makia-policy-enforcer.service
install -m 0644 "$SRC/systemd/makia-metrics-sampler.service" /etc/systemd/system/makia-metrics-sampler.service
install -m 0644 "$SRC/systemd/makia-protocol-traffic.service" /etc/systemd/system/makia-protocol-traffic.service
install -m 0644 "$SRC/systemd/makia-browser-gateway.service" /etc/systemd/system/makia-browser-gateway.service
install -m 0644 "$SRC/systemd/makia-stealth.service" /etc/systemd/system/makia-stealth.service
install -m 0644 "$SRC/systemd/makia-wstunnel.service" /etc/systemd/system/makia-wstunnel.service
install -m 0644 "$SRC/systemd/makia-openvpn-wstunnel.service" /etc/systemd/system/makia-openvpn-wstunnel.service
install -m 0644 "$SRC/systemd/makia-ikev2-network.service" /etc/systemd/system/makia-ikev2-network.service
install -m 0644 "$SRC/systemd/makia-migration-restore@.service" /etc/systemd/system/makia-migration-restore@.service
install -m 0644 "$SRC/systemd/makia-scheduled-backup.service" /etc/systemd/system/makia-scheduled-backup.service
install -m 0644 "$SRC/systemd/makia-scheduled-backup.timer" /etc/systemd/system/makia-scheduled-backup.timer
install -m 0644 "$SRC/systemd/makia-ops-monitor.service" /etc/systemd/system/makia-ops-monitor.service
install -m 0644 "$SRC/systemd/makia-ops-monitor.timer" /etc/systemd/system/makia-ops-monitor.timer
install -m 0644 "$SRC/systemd/makia-mtproxy.service" /etc/systemd/system/makia-mtproxy.service
if [[ ! -f /etc/nginx/sites-available/makia-vps-manager ]]; then
  install -m 0644 "$SRC/nginx/makia-vps-manager.conf" /etc/nginx/sites-available/makia-vps-manager
else
  echo "Preserving active Makia Nginx/Certbot configuration."
fi
ln -sfn /etc/nginx/sites-available/makia-vps-manager /etc/nginx/sites-enabled/makia-vps-manager
install_verified_shell "$SRC/scripts/update.sh" /usr/local/sbin/makia-update
install_verified_shell "$SRC/scripts/backup.sh" /usr/local/sbin/makia-backup
install_verified_shell "$SRC/scripts/uninstall.sh" /usr/local/sbin/makia-uninstall
install_verified_shell "$SRC/scripts/doctor.sh" /usr/local/sbin/makia-doctor
install_verified_shell "$SRC/scripts/uat-smoke.sh" /usr/local/sbin/makia-uat-smoke
install -m 0755 "$SRC/scripts/restore-portable.py" /usr/local/sbin/makia-restore-portable
install -m 0755 "$SRC/scripts/run-migration-restore.py" /usr/local/sbin/makia-run-migration-restore
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
install_verified_shell "$SRC/scripts/xray-cert-sync.sh" /etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync
install_verified_shell "$SRC/scripts/makia-vpn-tls-sync.sh" /etc/letsencrypt/renewal-hooks/deploy/makia-vpn-tls-sync
install -m 0755 "$SRC/scripts/reset-admin.sh" /usr/local/sbin/makia-reset-admin
install -m 0755 "$SRC/scripts/configure-owner.py" /usr/local/sbin/makia-owner-config
install_verified_shell "$SRC/scripts/ikev2-network.sh" /usr/local/sbin/makia-ikev2-network
install_verified_shell "$SRC/scripts/install-wstunnel.sh" /usr/local/sbin/makia-install-wstunnel
install_verified_shell "$SRC/scripts/install-outline.sh" /usr/local/sbin/makia-install-outline
install_verified_shell "$SRC/scripts/install-mtproxy.sh" /usr/local/sbin/makia-install-mtproxy
install_verified_shell "$SRC/scripts/refresh-mtproxy.sh" /usr/local/sbin/makia-refresh-mtproxy
install_verified_shell "$SRC/scripts/install-dns.sh" /usr/local/sbin/makia-install-dns
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

echo "Verifying optional installers did not mutate persistent network state..."
assert_preserved_file "$MTPROXY_ENV_PATH" "$MTPROXY_ENV_PRE_SHA" "MTProxy state" || exit 8
assert_preserved_file "$MTPROXY_CONFIG_PATH" "$MTPROXY_CONFIG_PRE_SHA" "MTProxy config" || exit 8
assert_preserved_file "$DNS_STATE_PATH" "$DNS_STATE_PRE_SHA" "DNS state" || exit 8
assert_preserved_file "$DNS_CONFIG_PATH" "$DNS_CONFIG_PRE_SHA" "DNS config" || exit 8

# A broken optional MTProxy from an older release must not prevent the release
# containing its repair from being installed. Only repair if it was inactive
# before the update; a healthy active proxy is preserved byte-for-byte.
if [[ "$MTPROXY_WAS_ACTIVE" -eq 0 && -s "$MTPROXY_ENV_PATH" && -s "$MTPROXY_CONFIG_PATH" && -x /opt/makia-mtproxy/mtg ]]; then
  echo "Repairing existing Telegram MTProxy with the new runtime contract..."
  if (
    cd "$APP"
    MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import network_services
state=network_services.mtproxy_status()
host=str(state.get("host") or "").strip()
if not host:
    raise SystemExit("MTProxy state exists but public host is missing")
result=network_services.configure_mtproxy(host,0,False)
print("Telegram MTProxy repair:", result.get("host"), result.get("port"), "active="+str(result.get("service_active")), "listener="+str(result.get("listener")))
if not result.get("service_active") or not result.get("listener"):
    raise SystemExit("MTProxy repair did not produce an active listener")
PY
  ); then
    MTPROXY_ENV_ACCEPTED_SHA="$(file_sha256 "$MTPROXY_ENV_PATH")"
    MTPROXY_CONFIG_ACCEPTED_SHA="$(file_sha256 "$MTPROXY_CONFIG_PATH")"
    echo "Accepted repaired MTProxy state for the remainder of this update transaction."
  else
    echo "WARNING: pre-existing Telegram MTProxy remains unhealthy; core update will continue so the repaired panel/runtime code is retained."
    # configure_mtproxy restores the previous state on failed reconfiguration.
    # Keep the original hashes as the accepted transaction state.
    assert_preserved_file "$MTPROXY_ENV_PATH" "$MTPROXY_ENV_PRE_SHA" "MTProxy state after failed repair" || exit 8
    assert_preserved_file "$MTPROXY_CONFIG_PATH" "$MTPROXY_CONFIG_PRE_SHA" "MTProxy config after failed repair" || exit 8
  fi
fi

# Repair a pre-existing resolver that could not answer before the update.
# A successful repair is an intentional config mutation, so its hashes become
# the accepted baseline for the rest of this update transaction.
if [[ "$DNS_WAS_QUERY_OK" -eq 0 && -s "$DNS_STATE_PATH" && -s "$DNS_CONFIG_PATH" ]] && command -v unbound >/dev/null 2>&1; then
  echo "Repairing existing Makia DNS resolver with the current DoT contract..."
  if (
    cd "$APP"
    MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import network_services
state=network_services.dns_status()
result=network_services.configure_dns(
    state.get("mode") or "private",
    state.get("upstream") or "cloudflare",
    state.get("allowed_cidrs") or [],
    state.get("public_address") or "",
)
print("Makia DNS repair:", result.get("mode"), result.get("upstream"), "query_ok="+str(result.get("query_ok")))
if not result.get("service_active") or not result.get("query_ok"):
    raise SystemExit("DNS repair did not produce a working localhost query")
PY
  ); then
    DNS_STATE_ACCEPTED_SHA="$(file_sha256 "$DNS_STATE_PATH")"
    DNS_CONFIG_ACCEPTED_SHA="$(file_sha256 "$DNS_CONFIG_PATH")"
    echo "Accepted repaired DNS state for the remainder of this update transaction."
  else
    echo "WARNING: pre-existing Makia DNS remains unhealthy; core update will continue so the repaired resolver code is retained."
    assert_preserved_file "$DNS_STATE_PATH" "$DNS_STATE_PRE_SHA" "DNS state after failed repair" || exit 8
    assert_preserved_file "$DNS_CONFIG_PATH" "$DNS_CONFIG_PRE_SHA" "DNS config after failed repair" || exit 8
  fi
fi

echo "Verifying accepted Telegram/DNS state after optional repair..."
assert_preserved_file "$MTPROXY_ENV_PATH" "$MTPROXY_ENV_ACCEPTED_SHA" "MTProxy accepted state" || exit 8
assert_preserved_file "$MTPROXY_CONFIG_PATH" "$MTPROXY_CONFIG_ACCEPTED_SHA" "MTProxy accepted config" || exit 8
assert_preserved_file "$DNS_STATE_PATH" "$DNS_STATE_ACCEPTED_SHA" "DNS accepted state" || exit 8
assert_preserved_file "$DNS_CONFIG_PATH" "$DNS_CONFIG_ACCEPTED_SHA" "DNS accepted config" || exit 8
if [[ "$MTPROXY_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet makia-mtproxy; then
  echo "ERROR: MTProxy was active before update but is not active after tooling refresh." >&2
  exit 8
fi
if [[ "$DNS_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet unbound; then
  echo "ERROR: DNS resolver was active before update but is not active after tooling refresh." >&2
  exit 8
fi

/usr/local/sbin/makia-install-wstunnel
install_verified_shell "$SRC/upgrade.sh" /usr/local/sbin/makia-upgrade

systemctl daemon-reload

if [[ "$PROTOCOL_RUNTIME_CHANGED" -eq 1 ]]; then
  echo "Protocol runtime changed; ensuring the complete Makia protocol stack is installed and ready..."
  (
    cd "$APP"
  MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
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
print("Protocol stack READY: Xray, WireGuard UDP/%s, OpenVPN %s/%s" % (
    wg.get("port") or "?",
    str(ov.get("proto") or "udp").upper(),
    ov.get("port") or "?",
))
PY
)

# Repair the historical root-only Xray config/TLS permission mismatch before
# the post-update UAT gate. This preserves credentials and rolls back the
# Xray config internally if the repair itself cannot validate.
if command -v xray >/dev/null 2>&1 && { [[ -f /usr/local/etc/xray/config.json ]] || [[ -f /etc/xray/config.json ]]; }; then
  echo "Checking Xray runtime permissions as the real systemd user..."
  if ! ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops.xray_diagnostics()
print("Xray:", d.get("version") or "unknown", "user="+str(d.get("service_user") or "root"))
if not d.get("service_validation") or not d.get("service_active"):
    result=protocol_ops.repair_xray_runtime()
    d=result["diagnostics"]
if not d.get("service_validation") or not d.get("service_active"):
    raise SystemExit("Xray runtime remains unhealthy after repair")
print("Xray runtime validation PASS")
PY
  ); then
    if [[ "$XRAY_WAS_ACTIVE" -eq 1 ]]; then
      echo "Xray was healthy before this update but is unhealthy now; updater will roll back."
      exit 5
    fi
    echo "WARNING: Xray was already unhealthy before the update and automatic repair could not fix it."
    echo "The panel update will continue so the new Diagnose/Repair UI is available."
  fi
fi

# Normalize legacy OpenVPN server transports to an explicit IPv4 runtime.
# This fixes domain profiles that may otherwise be diverted by AAAA/IPv6,
# while preserving the EasyRSA PKI and all existing client certificates.
if [[ "$OVPN_WAS_PRESENT" -eq 1 ]]; then
  echo "Checking OpenVPN IPv4 runtime..."
  if ! ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops._openvpn_server_runtime()
proto=str(d.get("proto") or "")
needs=proto not in {"udp4","tcp4-server"} or not d.get("service_active") or not d.get("listener")
up=protocol_ops.OVPN_DIR/"makia-up.sh"
if up.exists() and "iptables -I FORWARD" not in up.read_text(encoding="utf-8",errors="ignore"):
    needs=True
if needs:
    result=protocol_ops.repair_openvpn_ipv4_runtime()
    d=result["runtime"]
if str(d.get("proto") or "") not in {"udp4","tcp4-server"} or not d.get("service_active") or not d.get("listener"):
    raise SystemExit("OpenVPN runtime remains unhealthy after IPv4 normalization")
print("OpenVPN runtime validation PASS:", d.get("proto"), d.get("port"))
PY
  ); then
    if [[ "$OVPN_WAS_ACTIVE" -eq 1 && "$OVPN_WAS_LISTENING" -eq 1 ]]; then
      echo "OpenVPN listener was healthy before this update but is unhealthy now; updater will roll back."
      exit 6
    fi
    echo "WARNING: OpenVPN primary listener was already unhealthy before the update and automatic normalization could not fix it."
    echo "The panel update will continue so Domain Diagnostics and Repair are available."
  fi
fi

# Repair legacy WireGuard forwarding/NAT rules and restart wg0.
# The old bootstrap appended FORWARD rules behind some firewall chains; v0.17
# normalizes them to idempotent top-priority rules and source-scoped NAT.
if [[ "$WG_WAS_PRESENT" -eq 1 ]]; then
  echo "Checking WireGuard forwarding/NAT runtime..."
  if ! ( cd "$APP" && MAKIA_DATA_DIR="$APP/data" "$APP/.venv/bin/python" - <<'PY'
from app import protocol_ops
d=protocol_ops.wireguard_endpoint_diagnostics("")
if not d.get("runtime_ok"):
    result=protocol_ops.repair_wireguard_runtime()
    d=result["diagnostics"]
if not d.get("runtime_ok"):
    raise SystemExit("WireGuard runtime remains unhealthy after repair: "+"; ".join(d.get("warnings") or []))
print("WireGuard runtime validation PASS:", d.get("interface"), d.get("port"), d.get("uplink"))
PY
  ); then
    if [[ "$WG_WAS_ACTIVE" -eq 1 ]]; then
      echo "WireGuard was active before this update but is unhealthy now; updater will roll back."
      exit 7
    fi
    echo "WARNING: WireGuard was already unhealthy before the update and automatic repair could not fix it."
    echo "The panel update will continue so WireGuard Diagnostics and Repair are available."
  fi
fi
else
  echo "Protocol runtime code unchanged; skipping automatic Xray/WireGuard/OpenVPN provisioning and repair."
  if [[ "$XRAY_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet xray; then
    echo "Xray was active before update but is no longer active; updater will roll back." >&2
    exit 5
  fi
  if [[ "$OVPN_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet openvpn-server@server; then
    echo "OpenVPN was active before update but is no longer active; updater will roll back." >&2
    exit 6
  fi
  if [[ "$WG_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet wg-quick@wg0; then
    echo "WireGuard was active before update but is no longer active; updater will roll back." >&2
    exit 7
  fi
  if [[ "$STUNNEL_WAS_ACTIVE" -eq 1 && -n "$STUNNEL_RUNTIME_SERVICE" ]] && ! systemctl is-active --quiet "$STUNNEL_RUNTIME_SERVICE"; then
    echo "Stealth/Stunnel was active before update but is no longer active; updater will roll back." >&2
    exit 9
  fi
  if [[ "$WSTUNNEL_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet makia-wstunnel; then
    echo "WireGuard WStunnel was active before update but is no longer active; updater will roll back." >&2
    exit 10
  fi
  if [[ "$OVPN_WSTUNNEL_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet makia-openvpn-wstunnel; then
    echo "OpenVPN WStunnel 443 was active before update but is no longer active; updater will roll back." >&2
    exit 11
  fi
  echo "Existing protocol runtime state preserved."
fi

nginx -t
systemctl restart makia-vps-manager
systemctl enable --now makia-policy-enforcer
systemctl restart makia-policy-enforcer
systemctl enable --now makia-metrics-sampler
systemctl enable --now makia-protocol-traffic
systemctl enable --now makia-browser-gateway
systemctl enable --now makia-scheduled-backup.timer
systemctl enable --now makia-ops-monitor.timer
systemctl restart makia-metrics-sampler
systemctl restart makia-protocol-traffic
systemctl restart makia-browser-gateway
BROWSER_GATEWAY_PORT="${MAKIA_BROWSER_GATEWAY_PORT:-9444}"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  ufw allow "${BROWSER_GATEWAY_PORT}/tcp" comment 'Makia Browser Gateway' >/dev/null 2>&1 || true
fi
systemctl enable --now fail2ban
systemctl restart fail2ban
systemctl reload nginx

healthy=0
for _ in {1..20}; do
  if curl -fsS --max-time 3 http://127.0.0.1:8787/healthz >/dev/null; then
    healthy=1; break
  fi
  sleep 1
done
if [[ "$healthy" -ne 1 ]]; then
  echo "Health check failed after update."
  echo "The updater will restore the previous runtime automatically."
  exit 3
fi

EXPECTED_VERSION="$(tr -d '[:space:]' < "$APP/VERSION")"
RUNNING_VERSION="$(curl -fsS --max-time 3 http://127.0.0.1:8787/healthz | "$APP/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin).get("version",""))')"
if [[ -z "$EXPECTED_VERSION" || "$RUNNING_VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "Running backend version mismatch after update: expected=$EXPECTED_VERSION running=$RUNNING_VERSION" >&2
  exit 3
fi
echo "Running backend version verified: $RUNNING_VERSION"

echo
echo "Re-checking persistent network-service state before final acceptance..."
assert_preserved_file "$MTPROXY_ENV_PATH" "$MTPROXY_ENV_ACCEPTED_SHA" "MTProxy accepted state" || exit 8
assert_preserved_file "$MTPROXY_CONFIG_PATH" "$MTPROXY_CONFIG_ACCEPTED_SHA" "MTProxy accepted config" || exit 8
assert_preserved_file "$DNS_STATE_PATH" "$DNS_STATE_ACCEPTED_SHA" "DNS accepted state" || exit 8
assert_preserved_file "$DNS_CONFIG_PATH" "$DNS_CONFIG_ACCEPTED_SHA" "DNS accepted config" || exit 8

echo "Verifying installed critical shell artifacts before host smoke..."
ensure_installed_shell_integrity "$SRC/scripts/update.sh" /usr/local/sbin/makia-update
ensure_installed_shell_integrity "$SRC/scripts/doctor.sh" /usr/local/sbin/makia-doctor
ensure_installed_shell_integrity "$SRC/scripts/uat-smoke.sh" /usr/local/sbin/makia-uat-smoke

echo "Running post-update Makia host smoke gate..."
UAT_ENV=(env)
if [[ "$MTPROXY_WAS_ACTIVE" -eq 0 ]]; then
  UAT_ENV+=(MAKIA_UAT_OPTIONAL_NETWORK_SOFTFAIL=1)
fi
if [[ "$DNS_WAS_QUERY_OK" -eq 0 ]]; then
  UAT_ENV+=(MAKIA_UAT_DNS_SOFTFAIL=1)
fi
if [[ "$STUNNEL_WAS_CONFIGURED" -eq 1 && "$STUNNEL_WAS_ACTIVE" -eq 0 ]]; then
  UAT_ENV+=(MAKIA_UAT_STEALTH_SOFTFAIL=1)
fi
if [[ "$OVPN_WAS_PRESENT" -eq 1 && "$OVPN_WAS_ACTIVE" -eq 1 && "$OVPN_WAS_LISTENING" -eq 0 ]]; then
  echo "OpenVPN primary listener was already missing before this update; retaining it as a warning so unrelated panel/WStunnel fixes can be accepted."
  UAT_ENV+=(MAKIA_UAT_OPENVPN_LISTENER_SOFTFAIL=1)
fi
UAT_CMD=("${UAT_ENV[@]}" /usr/local/sbin/makia-uat-smoke)
if ! "${UAT_CMD[@]}"; then
  echo "Post-update host smoke failed."
  echo "The updater will restore the previous runtime automatically."
  exit 4
fi

ROLLBACK_ARMED=0
printf 'Update complete. Installed version: '
cat "$APP/VERSION"
echo
/usr/local/sbin/makia-doctor || true
