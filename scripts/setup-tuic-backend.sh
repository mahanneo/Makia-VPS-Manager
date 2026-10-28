#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install a pinned, official sing-box runtime and isolate Makia TUIC on UDP/8445.
# Does not change Nginx/443, WireGuard/443, SSTP/14443 or existing VPN services.
if (( $# > 0 )); then DOMAIN="$1"; else DOMAIN="p.mahinet.shop"; fi
PINNED_VERSION="$(printenv SING_BOX_VERSION 2>/dev/null || true)"
if [[ -z "$PINNED_VERSION" ]]; then PINNED_VERSION="1.14.4"; fi
PORT="$(printenv MAKIA_TUIC_PORT 2>/dev/null || true)"
if [[ -z "$PORT" ]]; then PORT="8445"; fi
[[ $EUID -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1024 && PORT <= 65535 )) || { echo "Invalid TUIC UDP port." >&2; exit 1; }
python3 - "$DOMAIN" <<'PY'
import ipaddress,re,sys
v=sys.argv[1].strip().rstrip(".")
try:
 ipaddress.ip_address(v)
 raise SystemExit("TUIC requires a DNS name with a matching TLS certificate, not a bare IP.")
except ValueError: pass
try: v=v.encode("idna").decode("ascii")
except Exception: raise SystemExit("Invalid TUIC domain.")
if len(v)>253 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",x) for x in v.split(".")):
 raise SystemExit("Invalid TUIC domain.")
PY

CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
[[ -r "$CERT" && -r "$KEY" ]] || { echo "Missing Let's Encrypt certificate/key for $DOMAIN." >&2; exit 1; }
openssl x509 -in "$CERT" -noout -checkend 0 >/dev/null
openssl x509 -in "$CERT" -noout -checkhost "$DOMAIN" >/dev/null
cert_pub="$(openssl x509 -in "$CERT" -pubkey -noout)"
key_pub="$(openssl pkey -in "$KEY" -pubout)"
[[ "$cert_pub" == "$key_pub" ]] || { echo "Certificate and private key do not match." >&2; exit 1; }

if ss -H -lun 2>/dev/null | awk '{print $5}' | grep -Eq ":$PORT$"; then
  echo "UDP/$PORT is already bound. No changes made." >&2
  exit 1
fi
if systemctl is-active --quiet sing-box.service 2>/dev/null || systemctl is-enabled --quiet sing-box.service 2>/dev/null; then
  echo "An existing sing-box.service is active or enabled; refusing to replace its runtime." >&2
  exit 1
fi
if [[ -e /etc/sing-box/makia-tuic.json || -e /etc/systemd/system/makia-tuic.service || -e /etc/makia-vps-manager/tuic-state.json ]] || systemctl is-active --quiet makia-tuic.service 2>/dev/null; then
  echo "Makia TUIC already has a config/service; refusing to overwrite users or runtime state." >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/makia-vps-manager/tuic-bootstrap-$STAMP"
install -d -m 0700 "$BACKUP"
for f in /etc/apt/keyrings/sagernet.asc /etc/apt/sources.list.d/sagernet.sources /etc/sing-box/makia-tuic.json /etc/sing-box/tls/fullchain.pem /etc/sing-box/tls/privkey.pem /etc/systemd/system/makia-tuic.service /etc/makia-vps-manager/tuic-state.json /etc/letsencrypt/renewal-hooks/deploy/50-makia-tuic-certificate.sh; do
  if [[ -e "$f" ]]; then
    install -d -m 0700 "$BACKUP$(dirname "$f")"
    cp -a "$f" "$BACKUP$f"
  fi
done
rollback_setup() {
  local rc=$?
  trap - ERR
  systemctl disable --now makia-tuic.service 2>/dev/null || true
  systemctl disable --now sing-box.service 2>/dev/null || true
  for f in /etc/apt/keyrings/sagernet.asc /etc/apt/sources.list.d/sagernet.sources /etc/sing-box/makia-tuic.json /etc/sing-box/tls/fullchain.pem /etc/sing-box/tls/privkey.pem /etc/systemd/system/makia-tuic.service /etc/makia-vps-manager/tuic-state.json /etc/letsencrypt/renewal-hooks/deploy/50-makia-tuic-certificate.sh; do
    if [[ -e "$BACKUP$f" ]]; then
      rm -f "$f"
      install -d -m 0755 "$(dirname "$f")"
      cp -a "$BACKUP$f" "$f"
    else
      rm -f "$f"
    fi
  done
  systemctl daemon-reload 2>/dev/null || true
  echo "TUIC setup failed; previous files restored from $BACKUP" >&2
  exit "$rc"
}
trap rollback_setup ERR

install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error --location --retry 3 https://sing-box.app/gpg.key -o /etc/apt/keyrings/sagernet.asc
chmod 0644 /etc/apt/keyrings/sagernet.asc
cat > /etc/apt/sources.list.d/sagernet.sources <<'EOF'
Types: deb
URIs: https://deb.sagernet.org/
Suites: *
Components: *
Enabled: yes
Signed-By: /etc/apt/keyrings/sagernet.asc
EOF
chmod 0644 /etc/apt/sources.list.d/sagernet.sources
apt-get update
PKG_VERSION="$(apt-cache madison sing-box | awk -v want="$PINNED_VERSION" '$3 == want || index($3,want "-")==1 {print $3; exit}')"
[[ -n "$PKG_VERSION" ]] || {
  echo "Pinned sing-box $PINNED_VERSION is not present in the signed official repository; refusing an unpinned install." >&2
  apt-cache madison sing-box >&2 || true
  exit 1
}
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "sing-box=$PKG_VERSION"
# The package may ship a generic sing-box.service; this host uses the isolated Makia unit below.
systemctl disable --now sing-box.service 2>/dev/null || true
if systemctl is-active --quiet sing-box.service 2>/dev/null; then echo "Generic sing-box.service is still active; aborting." >&2; exit 1; fi
BINARY="$(command -v sing-box || true)"
[[ -x "$BINARY" ]] || { echo "sing-box binary missing after package installation." >&2; exit 1; }
ACTUAL_VERSION="$("$BINARY" version | head -n1)"
[[ "$ACTUAL_VERSION" == *"$PINNED_VERSION"* ]] || { echo "Installed version does not match pin: $ACTUAL_VERSION" >&2; exit 1; }

if ! getent group sing-box >/dev/null; then groupadd --system sing-box; fi
if ! id -u sing-box >/dev/null 2>&1; then useradd --system --gid sing-box --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin sing-box; fi
install -d -o root -g sing-box -m 0750 /etc/sing-box /etc/sing-box/tls
install -o root -g sing-box -m 0640 "$CERT" /etc/sing-box/tls/fullchain.pem
install -o root -g sing-box -m 0640 "$KEY" /etc/sing-box/tls/privkey.pem

if [[ -e /etc/sing-box/makia-tuic.json ]]; then
  cp -a /etc/sing-box/makia-tuic.json "$BACKUP/makia-tuic.json.pre-install"
fi
cat > /etc/sing-box/makia-tuic.json <<EOF
{
  "log": {"level": "warn", "timestamp": true},
  "inbounds": [
    {
      "type": "tuic",
      "tag": "makia-tuic-in",
      "listen": "0.0.0.0",
      "listen_port": $PORT,
      "users": [],
      "congestion_control": "bbr",
      "auth_timeout": "3s",
      "zero_rtt_handshake": false,
      "heartbeat": "10s",
      "tls": {
        "enabled": true,
        "alpn": ["h3"],
        "certificate_path": "/etc/sing-box/tls/fullchain.pem",
        "key_path": "/etc/sing-box/tls/privkey.pem"
      }
    }
  ],
  "outbounds": [
    {"type": "direct", "tag": "direct"}
  ]
}
EOF
chown root:sing-box /etc/sing-box/makia-tuic.json
chmod 0640 /etc/sing-box/makia-tuic.json

install -m 0644 "$ROOT_DIR/systemd/makia-tuic.service" /etc/systemd/system/makia-tuic.service
if [[ "$BINARY" != "/usr/bin/sing-box" ]]; then
  echo "Unexpected sing-box binary path: $BINARY" >&2
  exit 1
fi

install -d -m 0700 /etc/makia-vps-manager
python3 - "$DOMAIN" "$PORT" "$PINNED_VERSION" <<'PY'
import json,os,sys,tempfile
from datetime import datetime,timezone
p="/etc/makia-vps-manager/tuic-state.json"
data={"domain":sys.argv[1],"port":int(sys.argv[2]),"version":sys.argv[3],"installed_at":datetime.now(timezone.utc).isoformat()}
fd,tmp=tempfile.mkstemp(prefix=".tuic-state-",dir="/etc/makia-vps-manager")
with os.fdopen(fd,"w") as f: json.dump(data,f); f.write("\n"); f.flush(); os.fsync(f.fileno())
os.chmod(tmp,0o600); os.replace(tmp,p); os.chown(p,0,0)
PY

HOOK="/etc/letsencrypt/renewal-hooks/deploy/50-makia-tuic-certificate.sh"
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > "$HOOK" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ -z "\$RENEWED_LINEAGE" || "\$RENEWED_LINEAGE" != "/etc/letsencrypt/live/$DOMAIN" ]]; then exit 0; fi
install -o root -g sing-box -m 0640 "\$RENEWED_LINEAGE/fullchain.pem" /etc/sing-box/tls/fullchain.pem
install -o root -g sing-box -m 0640 "\$RENEWED_LINEAGE/privkey.pem" /etc/sing-box/tls/privkey.pem
systemctl try-restart makia-tuic.service
EOF
chmod 0750 "$HOOK"
chown root:root "$HOOK"

"$BINARY" check -c /etc/sing-box/makia-tuic.json
systemctl daemon-reload
# No listener is started until the first authenticated user is created through Makia.
systemctl disable --now makia-tuic.service 2>/dev/null || true
trap - ERR
echo "TUIC backend prepared: $DOMAIN UDP/$PORT; $ACTUAL_VERSION"
echo "No users were created and no TUIC listener is active yet. Create the first user from Makia to start the service."
echo "Verify upstream/cloud firewall allows UDP/$PORT before client tests."
echo "Backup: $BACKUP"
