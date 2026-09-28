#!/usr/bin/env python3
import json, os, shutil, socket, time, urllib.request

CONTROLLER=os.environ.get("MAKIA_CONTROLLER_URL","").rstrip("/")
TOKEN=os.environ.get("MAKIA_NODE_TOKEN","")
INTERVAL=max(15,int(os.environ.get("MAKIA_NODE_INTERVAL","30")))
REGION=os.environ.get("MAKIA_NODE_REGION","")
PUBLIC_URL=os.environ.get("MAKIA_NODE_PUBLIC_URL","")

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

def network_bytes():
    rx=tx=0
    try:
        with open("/proc/net/dev","r",encoding="utf-8") as f:
            for line in f:
                if ":" not in line:continue
                name,data=line.split(":",1)
                if name.strip()=="lo":continue
                p=data.split()
                rx+=int(p[0]);tx+=int(p[8])
    except Exception:pass
    return rx,tx

def service_state(name):
    try:
        import subprocess
        p=subprocess.run(["systemctl","is-active",name],text=True,capture_output=True,timeout=3,check=False)
        return (p.stdout or "").strip()=="active"
    except Exception:return False

def managed_counts():
    users=online=0
    try:
        import sqlite3
        db="/opt/makia-vps-manager/data/makia.db"
        if os.path.isfile(db):
            con=sqlite3.connect(db)
            users=int(con.execute("SELECT COUNT(*) FROM protocol_clients WHERE enabled=1").fetchone()[0])
            con.close()
    except Exception:pass
    try:
        import subprocess
        p=subprocess.run(["who"],text=True,capture_output=True,timeout=3,check=False)
        online=len({line.split()[0] for line in (p.stdout or "").splitlines() if line.split()})
    except Exception:pass
    return users,online

def version():
    for p in ("/opt/makia-vps-manager/VERSION","/etc/makia-node-version"):
        try:
            with open(p,"r",encoding="utf-8") as f:return f.read().strip()[:80]
        except OSError: pass
    return "node-agent"

def heartbeat():
    rx,tx=network_bytes();users,online=managed_counts()
    started=time.time()
    payload=json.dumps({
        "hostname":socket.gethostname(),
        "version":version(),
        "cpu":cpu_percent(),
        "memory":mem_percent(),
        "disk":disk_percent(),
        "region":REGION,
        "public_url":PUBLIC_URL,
        "users":users,
        "online_users":online,
        "rx":rx,
        "tx":tx,
        "latency_ms":round(max(0,(time.time()-started)*1000),1),
        "services":{
            "makia":service_state("makia-vps-manager"),
            "xray":service_state("xray"),
            "wireguard":service_state("wg-quick@wg0"),
            "nginx":service_state("nginx"),
        },
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
