#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_SHA="${1:?candidate SHA required}"
BASELINE_DIR="${2:?baseline directory required}"
CONTAINER="makia-upgrade-v151"
IMAGE="makia-upgrade-v151"

cleanup(){
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cat >/tmp/MakiaUpgrade151Dockerfile <<'EOF'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive container=docker
RUN apt-get update \
 && apt-get install -y systemd systemd-sysv dbus curl ca-certificates \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
EOF

docker build -t "$IMAGE" -f /tmp/MakiaUpgrade151Dockerfile /tmp >/dev/null
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

docker cp "$BASELINE_DIR" "$CONTAINER":/tmp/makia-v151
docker cp tests/upgrade_identity_probe.py "$CONTAINER":/tmp/upgrade_identity_probe.py

docker exec -e MAKIA_INITIAL_ADMIN_PASSWORD="UpgradeBaselineOnly-151" \
  "$CONTAINER" bash -lc 'bash /tmp/makia-v151/scripts/install.sh'

docker exec "$CONTAINER" bash -lc '
  set -Eeuo pipefail
  test "$(cat /opt/makia-vps-manager/VERSION)" = "1.5.1"
  systemctl enable --now nginx
  cd /opt/makia-vps-manager
  MAKIA_DATA_DIR=/opt/makia-vps-manager/data .venv/bin/python -c "from app.security import ensure_secret; ensure_secret()"
  systemctl restart makia-vps-manager
  healthy=0
  for _ in {1..20}; do
    if curl -fsS --max-time 2 http://127.0.0.1:8787/healthz | grep -q "1.5.1"; then healthy=1; break; fi
    sleep 1
  done
  test "$healthy" = "1"
  systemctl is-active --quiet xray
  systemctl is-active --quiet wg-quick@wg0
  systemctl is-active --quiet openvpn-server@server
  test ! -f /etc/makia-vps-manager/openvpn-wstunnel.env
'

docker exec -e MAKIA_DATA_DIR=/opt/makia-vps-manager/data "$CONTAINER" \
  /opt/makia-vps-manager/.venv/bin/python /tmp/upgrade_identity_probe.py >/tmp/makia-v151-pre-identity.json

docker exec -e MAKIA_REF="$CANDIDATE_SHA" -e MAKIA_FORCE_MAIN=0 \
  "$CONTAINER" bash -lc 'makia-upgrade'

docker exec "$CONTAINER" bash -lc '
  set -Eeuo pipefail
  test "$(cat /opt/makia-vps-manager/VERSION)" = "1.6.0"
  curl -fsS http://127.0.0.1:8787/healthz | grep -q "1.6.0"
  systemctl is-active --quiet makia-vps-manager
  systemctl is-active --quiet nginx
  systemctl is-active --quiet xray
  systemctl is-active --quiet wg-quick@wg0
  systemctl is-active --quiet openvpn-server@server

  # Upgrade must not opt production into WStunnel 443 or mutate Nginx/443.
  test ! -f /etc/makia-vps-manager/openvpn-wstunnel.env
  ! systemctl is-active --quiet makia-openvpn-wstunnel
  ! systemctl is-active --quiet openvpn-server@makia-ws
  ! grep -q "BEGIN MAKIA OPENVPN WSTUNNEL" /etc/nginx/sites-available/makia-vps-manager

  makia-doctor
  makia-uat-smoke
'

docker exec -e MAKIA_DATA_DIR=/opt/makia-vps-manager/data "$CONTAINER" \
  /opt/makia-vps-manager/.venv/bin/python /tmp/upgrade_identity_probe.py >/tmp/makia-v151-post-identity.json
cmp -s /tmp/makia-v151-pre-identity.json /tmp/makia-v151-post-identity.json

echo "UPGRADE 1.5.1 -> 1.6.0 SMOKE: PASS"
