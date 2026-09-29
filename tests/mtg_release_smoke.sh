#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="2.2.8"
ARCH="amd64"
NAME="mtg-${VERSION}-linux-${ARCH}.tar.gz"
URL="https://github.com/9seconds/mtg/releases/download/v${VERSION}/${NAME}"
EXPECTED="7ef19d079d85f4e00d4f8334ec1f3f3c8718e3d0ed1f3109ea9a8673138a2102"

tmp="$(mktemp -d)"
cleanup(){
  if [[ -n "${pid:-}" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT

curl -fsSL --retry 3 "$URL" -o "$tmp/$NAME"
actual="$(sha256sum "$tmp/$NAME" | awk '{print $1}')"
[[ "$actual" == "$EXPECTED" ]] || { echo "mtg checksum mismatch" >&2; exit 2; }
tar -xzf "$tmp/$NAME" -C "$tmp"
bin="$(find "$tmp" -type f -name mtg -perm -u+x | head -n1)"
[[ -n "$bin" ]] || { echo "mtg binary missing" >&2; exit 3; }

"$bin" --version | grep -F "2.2.8" >/dev/null
secret="$("$bin" generate-secret --hex example.com)"
[[ "$secret" =~ ^ee[0-9a-fA-F]+$ ]] || { echo "invalid FakeTLS secret" >&2; exit 4; }

port="$(python3 - <<'PY'
import socket
s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()
PY
)"
cat >"$tmp/mtg.toml" <<EOF
secret = "$secret"
bind-to = "127.0.0.1:$port"

[network]
dns = "https://1.1.1.1"
EOF

"$bin" run "$tmp/mtg.toml" >"$tmp/mtg.log" 2>&1 &
pid=$!
for _ in {1..30}; do
  if ! kill -0 "$pid" 2>/dev/null; then
    cat "$tmp/mtg.log" >&2
    exit 5
  fi
  if python3 - "$port" <<'PY'
import socket,sys
s=socket.socket();s.settimeout(.2)
try:
    s.connect(("127.0.0.1",int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    echo "mtg 2.2.8 binary/config/listener smoke PASS"
    exit 0
  fi
  sleep .2
done
cat "$tmp/mtg.log" >&2
echo "mtg listener did not become ready" >&2
exit 6
