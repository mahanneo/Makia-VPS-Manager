#!/usr/bin/env python3
import json, os, platform, socket, urllib.request
from pathlib import Path
try:
    import psutil
except Exception as exc:
    raise SystemExit("psutil is required: "+str(exc))

URL=(os.getenv("MAKIA_COORDINATOR_URL") or "").rstrip("/")
TOKEN=os.getenv("MAKIA_NODE_TOKEN") or ""
REGION=os.getenv("MAKIA_NODE_REGION") or ""
ENDPOINT=os.getenv("MAKIA_NODE_ENDPOINT") or ""
if not URL or not TOKEN:
    raise SystemExit("MAKIA_COORDINATOR_URL and MAKIA_NODE_TOKEN are required")

disk=psutil.disk_usage("/")
mem=psutil.virtual_memory()
net=psutil.net_io_counters()
payload={
    "hostname":socket.gethostname(),
    "version":os.getenv("MAKIA_NODE_VERSION") or "agent-v1",
    "cpu":psutil.cpu_percent(interval=0.2),
    "memory":mem.percent,
    "disk":disk.percent,
    "endpoint":ENDPOINT,
    "region":REGION,
    "users":0,
    "online":0,
    "rx":int(net.bytes_recv),
    "tx":int(net.bytes_sent),
    "latency_ms":None,
}
try:
    from pathlib import Path
    db=Path("/var/lib/makia-vps-manager/makia.db")
    if db.exists():
        import sqlite3
        con=sqlite3.connect(db)
        payload["users"]=int(con.execute("SELECT COUNT(*) FROM protocol_clients").fetchone()[0])
        payload["online"]=int(con.execute("SELECT COUNT(*) FROM protocol_clients WHERE enabled=1").fetchone()[0])
        con.close()
except Exception:
    pass
req=urllib.request.Request(
    URL+"/api/node/heartbeat",
    data=json.dumps(payload,separators=(",",":")).encode(),
    headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json","User-Agent":"Makia-Node-Agent"},
    method="POST",
)
with urllib.request.urlopen(req,timeout=15) as response:
    if response.status>=300:
        raise SystemExit("heartbeat failed: "+str(response.status))
