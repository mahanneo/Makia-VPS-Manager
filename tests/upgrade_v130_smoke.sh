#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_SHA="${1:?candidate SHA required}"
BASELINE_DIR="${2:?baseline directory required}"
CONTAINER="makia-upgrade-v130"
IMAGE="makia-upgrade-v130"

cleanup(){
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cat >/tmp/MakiaUpgradeDockerfile <<'EOF'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive container=docker
RUN apt-get update \
 && apt-get install -y systemd systemd-sysv dbus curl ca-certificates \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
EOF

docker build -t "$IMAGE" -f /tmp/MakiaUpgradeDockerfile /tmp >/dev/null
extra=()
if [[ -e /dev/net/tun ]]; then extra+=(--device /dev/net/tun); fi
docker run -d --name "$CONTAINER" \
  --privileged --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  -v /lib/modules:/lib/modules:ro \
  --tmpfs /run --tmpfs /run/lock \
  "${extra[@]}" "$IMAGE" >/dev/null

for _ in {1..30}; do
  if docker exec "$CONTAINER" systemctl list-units >/dev/null 2>&1; then break; fi
  sleep 2
done

docker cp "$BASELINE_DIR" "$CONTAINER":/tmp/makia-v130
docker cp tests/upgrade_identity_probe.py "$CONTAINER":/tmp/upgrade_identity_probe.py
set +e
docker exec -e MAKIA_INITIAL_ADMIN_PASSWORD="UpgradeBaselineOnly-130" \
  "$CONTAINER" bash -lc 'bash /tmp/makia-v130/scripts/install.sh'
baseline_rc=$?
set -e
echo "baseline installer exit=$baseline_rc"

docker exec "$CONTAINER" bash -lc '
  set -Eeuo pipefail
  test "$(cat /opt/makia-vps-manager/VERSION)" = "1.3.0"
  systemctl enable --now nginx
  cd /opt/makia-vps-manager
  MAKIA_DATA_DIR=/opt/makia-vps-manager/data .venv/bin/python -c "from app.security import ensure_secret; ensure_secret()"
  systemctl restart makia-vps-manager
  healthy=0
  for _ in {1..20}; do
    if curl -fsS --max-time 2 http://127.0.0.1:8787/healthz | grep -q "1.3.0"; then healthy=1; break; fi
    sleep 1
  done
  test "$healthy" = "1"
  systemctl is-active --quiet xray
  systemctl is-active --quiet wg-quick@wg0
  systemctl is-active --quiet openvpn-server@server
'

docker exec "$CONTAINER" bash -lc '
  set -Eeuo pipefail
  install -d -m 0755 /etc/stunnel
  printf "%s\n" "pid = /run/stunnel4/makia-openvpn.pid" "[makia-openvpn]" "accept = 9443" "connect = 127.0.0.1:8443" >/etc/stunnel/makia-openvpn.conf
  touch /etc/default/stunnel4
  sed -i "/^[[:space:]]*ENABLED=/d" /etc/default/stunnel4
  echo "ENABLED=0" >> /etc/default/stunnel4
  systemctl stop stunnel4 2>/dev/null || true
  ! systemctl is-active --quiet stunnel4
'

docker exec -e MAKIA_DATA_DIR=/opt/makia-vps-manager/data "$CONTAINER" \
  /opt/makia-vps-manager/.venv/bin/python /tmp/upgrade_identity_probe.py >/tmp/makia-pre-identity.json

docker exec -e MAKIA_REF="$CANDIDATE_SHA" -e MAKIA_FORCE_MAIN=0 \
  "$CONTAINER" bash -lc 'makia-upgrade'

docker exec "$CONTAINER" bash -lc '
  set -Eeuo pipefail
  test "$(cat /opt/makia-vps-manager/VERSION)" = "1.5.0"
  curl -fsS http://127.0.0.1:8787/healthz | grep -q "1.5.0"
  systemctl is-active --quiet makia-vps-manager
  systemctl is-active --quiet nginx
  systemctl is-active --quiet xray
  systemctl is-active --quiet wg-quick@wg0
  systemctl is-active --quiet openvpn-server@server
  ! systemctl is-active --quiet stunnel4
  grep -Eq "^[[:space:]]*ENABLED[[:space:]]*=[[:space:]]*0[[:space:]]*$" /etc/default/stunnel4
  makia-doctor
  makia-uat-smoke
'

docker exec -e MAKIA_DATA_DIR=/opt/makia-vps-manager/data "$CONTAINER" \
  /opt/makia-vps-manager/.venv/bin/python /tmp/upgrade_identity_probe.py >/tmp/makia-post-identity.json
cmp -s /tmp/makia-pre-identity.json /tmp/makia-post-identity.json

echo "UPGRADE 1.3.0 -> 1.5.0 SMOKE: PASS"
