#!/usr/bin/env python3
import json, os, shutil, socket, time, urllib.request

CONTROLLER=os.environ.get("MAKIA_CONTROLLER_URL","").rstrip("/")
TOKEN=os.environ.get("MAKIA_NODE_TOKEN","")
INTERVAL=max(15,int(os.environ.get("MAKIA_NODE_INTERVAL","30")))
REGION=os.environ.get("MAKIA_NODE_REGION","")
ENDPOINT=os.environ.get("MAKIA_NODE_ENDPOINT","")

def cpu_times():
    with open("/proc/stat","r",encoding="utf-8") as f:
        p=f.readline().split()[1:]
    vals=[int(x) for x in p]
    idle=vals[3]+(vals[4] if len(vals)>4 else 0)
    return sum(vals),idle

def cpu_percent():
    t1,i1=cpu_times(); time.sleep(0.2); t2,i2=cpu_times()
    dt=max(1,t2-t1)
    return round((1-(i2-i1)/dt)*100,1)

def mem_percent():
    data={}
    with open("/proc/meminfo","r",encoding="utf-8") as f:
        for line in f:
            k,v=line.split(":",1); data[k]=int(v.strip().split()[0])
    total=data.get("MemTotal",1)
    avail=data.get("MemAvailable",data.get("MemFree",0))
    return round((1-avail/total)*100,1)

def disk_percent():
    d=shutil.disk_usage("/")
    return round(d.used/d.total*100,1) if d.total else 0.0

def version():
    for p in ("/opt/makia-vps-manager/VERSION","/etc/makia-node-version"):
        try:
            with open(p,"r",encoding="utf-8") as f:return f.read().strip()[:80]
        except OSError: pass
    return "node-agent"

def heartbeat():
    users=online=0
    try:
        import sqlite3
        db="/var/lib/makia-vps-manager/makia.db"
        if os.path.exists(db):
            con=sqlite3.connect(db)
            users=int(con.execute("SELECT COUNT(*) FROM protocol_clients").fetchone()[0])
            online=int(con.execute("SELECT COUNT(*) FROM protocol_clients WHERE enabled=1").fetchone()[0])
            con.close()
    except Exception:
        pass
    try:
        with open("/proc/net/dev","r",encoding="utf-8") as f:
            rows=[x.split(":",1)[1].split() for x in f if ":" in x and not x.strip().startswith(("lo:","Inter-"))]
        rx=sum(int(x[0]) for x in rows); tx=sum(int(x[8]) for x in rows)
    except Exception:
        rx=tx=0
    payload=json.dumps({
        "hostname":socket.gethostname(),
        "version":version(),
        "cpu":cpu_percent(),
        "memory":mem_percent(),
        "disk":disk_percent(),
        "endpoint":ENDPOINT,
        "region":REGION,
        "users":users,
        "online":online,
        "rx":rx,
        "tx":tx,
        "latency_ms":None,
    }).encode()
    req=urllib.request.Request(
        CONTROLLER+"/api/node/heartbeat",
        data=payload,
        headers={"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=12) as r:
        r.read()

def main():
    if not CONTROLLER.startswith(("http://","https://")) or not TOKEN:
        raise SystemExit("MAKIA_CONTROLLER_URL and MAKIA_NODE_TOKEN are required")
    while True:
        try: heartbeat()
        except Exception as exc: print("heartbeat failed:",exc,flush=True)
        time.sleep(INTERVAL)

if __name__=="__main__":
    main()
