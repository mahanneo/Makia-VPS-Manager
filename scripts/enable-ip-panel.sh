#!/usr/bin/env bash
# Optional, guarded migration for legacy Makia Nginx sites.
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run as root: sudo makia-enable-ip-panel" >&2; exit 1; }
command -v nginx >/dev/null || { echo "nginx is not installed" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
DOMAIN=/etc/nginx/sites-available/makia-vps-manager
FALLBACK=/etc/nginx/sites-available/makia-ip-fallback
LINK=/etc/nginx/sites-enabled/makia-ip-fallback
[[ -f "$DOMAIN" ]] || { echo "Makia Nginx domain site is missing" >&2; exit 1; }
[[ -f "$FALLBACK" && -L "$LINK" ]] && {
    nginx -t
    echo "Makia IP fallback is already installed; no changes made."
    exit 0
}
umask 077
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="/var/backups/makia-vps-manager/nginx-before-ip-panel-$stamp"
mkdir -p "$backup"
cp -a "$DOMAIN" "$backup/makia-vps-manager"
had_fallback=0
had_link=0
if [[ -e "$FALLBACK" ]]; then cp -a "$FALLBACK" "$backup/makia-ip-fallback"; had_fallback=1; fi
if [[ -L "$LINK" ]]; then cp -aP "$LINK" "$backup/makia-ip-fallback.link"; had_link=1; fi
restore(){
    local rc=$?
    cp -a "$backup/makia-vps-manager" "$DOMAIN"
    if [[ "$had_fallback" -eq 1 ]]; then cp -a "$backup/makia-ip-fallback" "$FALLBACK"; else rm -f "$FALLBACK"; fi
    if [[ "$had_link" -eq 1 ]]; then cp -aP "$backup/makia-ip-fallback.link" "$LINK"; else rm -f "$LINK"; fi
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    echo "IP fallback validation failed; original Nginx site restored. Backup: $backup" >&2
    exit "$rc"
}
trap restore ERR
# Modify ONLY HTTP listen directives of this site's configuration.
python3 - "$DOMAIN" <<'PY'
from pathlib import Path
import re, sys
site=Path(sys.argv[1])
old=site.read_text(encoding="utf-8")
new=re.sub(r"(?m)^(\s*listen\s+(?:80|\[::\]:80))\s+default_server(\s*;)",r"\1\2",old)
site.write_text(new,encoding="utf-8")
PY
cat > "$FALLBACK" <<'CONF'
# Dedicated HTTP bootstrap endpoint for IP-based setup.
# This must stay separate from Certbot-managed HTTPS hostname redirects.
# WARNING: HTTP admin login is not encrypted. Restrict by firewall during bootstrap.
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;
    client_max_body_size 2m;

    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
CONF
chmod 0644 "$FALLBACK"
ln -sfn "$FALLBACK" "$LINK"
nginx -t
systemctl reload nginx
# A test-only Host header verifies that IP/default traffic is NOT redirected.
status="$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' -H 'Host: 203.0.113.99' http://127.0.0.1/healthz)"
[[ "$status" == "200" ]] || { echo "IP HTTP fallback returned $status, expected 200" >&2; false; }
trap - ERR
echo "IP bootstrap fallback is active on HTTP/80; domain HTTPS and VPNs unchanged."
echo "Backup: $backup"
echo "SECURITY: HTTP is unencrypted. Restrict public administration until HTTPS is configured."
