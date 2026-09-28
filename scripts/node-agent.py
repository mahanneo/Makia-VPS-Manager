#!/opt/makia-vps-manager/.venv/bin/python
import json, os, socket, sys, urllib.request
from pathlib import Path

sys.path.insert(0,"/opt/makia-vps-manager")
os.environ.setdefault("MAKIA_DATA_DIR","/opt/makia-vps-manager/data")

from app.config import VERSION
from app import system_ops
from app.main import account_rows
from app.db import init_db

ENV=Path("/etc/makia-vps-manager/node.env")

def env_file():
    data={}
    if not ENV.is_file():return data
    for line in ENV.read_text(encoding="utf-8",errors="ignore").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:continue
        k,v=line.split("=",1);data[k.strip()]=v.strip()
    return data

def main():
    init_db()
    cfg=env_file()
    controller=cfg.get("MAKIA_NODE_CONTROLLER","").rstrip("/")
    token=cfg.get("MAKIA_NODE_TOKEN","")
    public_url=cfg.get("MAKIA_NODE_PUBLIC_URL","")
    if not controller or not token:return 0
    m=system_ops.metrics()
    sessions=system_ops.online_sessions()
    services={}
    for name in ["xray","wg-quick@wg0","openvpn-server@server","nginx","ssh"]:
        try:services[name]=system_ops.service_status(name).get("active",False)
        except Exception:services[name]=False
    payload={
        "hostname":socket.gethostname(),"version":VERSION,
        "cpu":m["cpu"],"memory":m["memory"],"disk":m["disk"],
        "public_url":public_url,"users":len(account_rows()),
        "online_users":len({x.get("username") for x in sessions if x.get("username")}),
        "rx":int(m["network"]["recv"]),"tx":int(m["network"]["sent"]),"services":services,
    }
    req=urllib.request.Request(
        controller+"/api/node/heartbeat",
        data=json.dumps(payload,separators=(",",":")).encode(),
        method="POST",
        headers={"Content-Type":"application/json","Authorization":"Bearer "+token,"User-Agent":"Makia-Node-Agent"}
    )
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            return 0 if 200<=response.status<300 else 1
    except Exception:
        return 1

if __name__=="__main__":
    raise SystemExit(main())
