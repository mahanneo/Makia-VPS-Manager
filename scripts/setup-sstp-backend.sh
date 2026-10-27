#!/usr/bin/env bash
# Reproducible, fail-closed SSTP provisioning. No Nginx/HTTPS port mutation.
set -Eeuo pipefail
umask 077
test "$(id -u)" -eq 0
: "$MAKIA_SSTP_PUBLIC_IP" "$MAKIA_SSTP_DOMAIN" "$MAKIA_SSTP_PORT"
python3 - "$MAKIA_SSTP_PUBLIC_IP" "$MAKIA_SSTP_DOMAIN" "$MAKIA_SSTP_PORT" <<'PY'
import ipaddress,re,sys
assert ipaddress.IPv4Address(sys.argv[1]).is_global
assert re.fullmatch(r"[a-zA-Z0-9.-]{3,253}",sys.argv[2])
assert 1<=int(sys.argv[3])<=65535
PY
cert="/etc/letsencrypt/live/$MAKIA_SSTP_DOMAIN/fullchain.pem"
key="/etc/letsencrypt/live/$MAKIA_SSTP_DOMAIN/privkey.pem"
test -r "$cert" && test -r "$key"
openssl x509 -in "$cert" -checkend 86400 -noout
openssl x509 -in "$cert" -checkhost "$MAKIA_SSTP_DOMAIN" -noout | grep -qi 'does match certificate'
# Refuse to steal an occupied port even if a previous daemon instance exists.
if ss -lntH "( sport = :$MAKIA_SSTP_PORT )" | grep -q .; then
  echo "The desired SSTP TCP port is occupied; aborting" >&2; exit 1
fi
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
apt-get update -qq
apt-get install -yq --no-install-recommends build-essential cmake git libssl-dev libpcre2-dev
src=/opt/makia-sstp/accel-src
prefix=/opt/makia-sstp/runtime
mkdir -p /opt/makia-sstp /etc/accel-ppp /var/log/makia-sstp
chmod 0700 /var/log/makia-sstp
test -d "$src/.git" || git clone --depth 1 --branch 1.14.0 https://github.com/accel-ppp/accel-ppp.git "$src"
test "$(git -C "$src" rev-parse HEAD)" = "048d31cb446879e0d1a1471b4ab99135a92bf289"
cmake -S "$src" -B /opt/makia-sstp/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DRADIUS=FALSE -DSHAPER=FALSE -DNETSNMP=FALSE -DLUA=FALSE -DBUILD_IPOE_DRIVER=FALSE -DBUILD_VLAN_MON_DRIVER=FALSE -DBUILD_PPPOSEQ_DRIVER=FALSE
nice -n 15 cmake --build /opt/makia-sstp/build -j 1
cmake --install /opt/makia-sstp/build
cred=/etc/makia-vps-manager/sstp-chap-secrets
test -f "$cred" || install -o root -g root -m 0600 /dev/null "$cred"
chmod 0600 "$cred"
cat > /etc/accel-ppp/makia-sstp.conf <<CONFIG
[modules]
log_syslog
sstp
auth_mschap_v2
chap-secrets
ippool
[core]
log-error=/var/log/makia-sstp/error.log
[ppp]
verbose=0
min-mtu=1280
mtu=1452
mru=1452
mppe=prefer
ipv4=require
ipv6=deny
[client-ip-range]
0.0.0.0/0
[sstp]
bind=$MAKIA_SSTP_PUBLIC_IP
port=$MAKIA_SSTP_PORT
host-name=$MAKIA_SSTP_DOMAIN
accept=ssl
ssl-pemfile=$cert
ssl-keyfile=$key
http-error=deny
ip-pool=sstp
ifname=sstp%d
[chap-secrets]
chap-secrets=$cred
[ip-pool]
gw-ip-address=10.79.0.1
tunnel=10.79.0.2-254,name=sstp
[dns]
dns1=1.1.1.1
dns2=8.8.8.8
[log]
level=3
CONFIG
chmod 0600 /etc/accel-ppp/makia-sstp.conf
install -m 0644 "$(dirname "$0")/../systemd/makia-sstp-backend.service" /etc/systemd/system/makia-sstp-backend.service
systemctl daemon-reload
systemctl enable --now makia-sstp-backend.service
systemctl is-active --quiet makia-sstp-backend.service
echo "SSTP backend installed. Complete NAT, off-host Windows PPP client test and certificate validation before declaring production-ready."
