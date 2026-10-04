#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("MAKIA_DATA_DIR","/opt/makia-vps-manager/data")
sys.path.insert(0,"/opt/makia-vps-manager")

from app.db import connect

with connect() as con:
    row=con.execute("SELECT password_hash FROM admins WHERE username=?",("admin",)).fetchone()
if not row or not row[0]:
    raise SystemExit("admin password hash missing")

wg=Path("/etc/wireguard/wg0.conf").read_text(encoding="utf-8",errors="ignore")
m=re.search(r"(?m)^\s*PrivateKey\s*=\s*(\S+)\s*$",wg)
if not m:
    raise SystemExit("WireGuard private key missing")

ovpn=Path("/etc/openvpn/server/server.conf")
if not ovpn.exists():
    raise SystemExit("OpenVPN server config missing")

xp=Path("/usr/local/etc/xray/config.json")
if not xp.exists():
    xp=Path("/etc/xray/config.json")
obj=json.loads(xp.read_text(encoding="utf-8"))
ids=[]
for inbound in obj.get("inbounds",[]):
    for client in ((inbound.get("settings") or {}).get("clients") or []):
        if client.get("id"):
            ids.append(str(client["id"]))

print(json.dumps({
    "admin_password_hash":row[0],
    "wireguard_private_key":m.group(1),
    "openvpn_server_config_sha256":hashlib.sha256(ovpn.read_bytes()).hexdigest(),
    "xray_client_ids":sorted(set(ids)),
},sort_keys=True,separators=(",",":")))
