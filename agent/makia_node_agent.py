#!/usr/bin/env python3
import json, os, shutil, socket, sqlite3, subprocess, time, urllib.request

CONTROLLER=os.environ.get("MAKIA_CONTROLLER_URL","").rstrip("/")
TOKEN=os.environ.get("MAKIA_NODE_TOKEN","")
INTERVAL=max(15,int(os.environ.get("MAKIA_NODE_INTERVAL","30")))
REGION=os.environ.get("MAKIA_NODE_REGION","").strip()[:80]

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

def public_ip():
    try:
        values=socket.gethostbyname_ex(socket.gethostname())[2]
        for value in values:
            if not value.startswith(("127.","10.","192.168.")) and not value.startswith("172."):
                return value
    except OSError: pass
    try:
        out=subprocess.run(["hostname","-I"],text=True,capture_output=True,timeout=3,check=False).stdout
        for value in out.split():
            if "." in value and not value.startswith(("127.","10.","192.168.")):
                return value
    except Exception: pass
    return ""

def traffic_bytes():
    total=0
    try:
        with open("/proc/net/dev","r",encoding="utf-8") as f:
            for line in f.readlines()[2:]:
                if ":" not in line:continue
                iface,raw=line.split(":",1)
                if iface.strip()=="lo":continue
                p=raw.split()
                if len(p)>=9:total+=int(p[0])+int(p[8])
    except OSError:pass
    return total

def db_counts():
    db="/opt/makia-vps-manager/data/makia.db"
    if not os.path.isfile(db):return 0,0
    try:
        con=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
        users=int(con.execute("SELECT COUNT(*) FROM protocol_clients").fetchone()[0])
        # Current live-online counters are protocol-specific; report known active managed clients.
        online=int(con.execute("SELECT COUNT(*) FROM protocol_clients WHERE enabled=1").fetchone()[0])
        con.close()
        return users,online
    except Exception:return 0,0

def service_state(unit):
    try:
        p=subprocess.run(["systemctl","is-active",unit],text=True,capture_output=True,timeout=4,check=False)
        return p.returncode==0
    except Exception:return False

def services():
    return {
        "makia":service_state("makia-vps-manager"),
        "xray":service_state("xray"),
        "wireguard":service_state("wg-quick@wg0"),
        "openvpn":service_state("openvpn-server@server"),
        "outline":service_state("docker") and os.path.isfile("/opt/outline/access.txt"),
    }

def heartbeat():
    users,online=db_counts()
    payload=json.dumps({
        "hostname":socket.gethostname(),
        "version":version(),
        "cpu":cpu_percent(),
        "memory":mem_percent(),
        "disk":disk_percent(),
        "public_ip":public_ip(),
        "region":REGION,
        "users":users,
        "online_users":online,
        "traffic_bytes":traffic_bytes(),
        "services":services(),
        "last_error":"",
    }).encode()
    req=urllib.request.Request(
        CONTROLLER+"/api/node/heartbeat",
        data=payload,
        headers={"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=12) as response:
        response.read()

def main():
    if not CONTROLLER.startswith(("http://","https://")) or not TOKEN:
        raise SystemExit("MAKIA_CONTROLLER_URL and MAKIA_NODE_TOKEN are required")
    while True:
        try: heartbeat()
        except Exception as exc: print("heartbeat failed:",exc,flush=True)
        time.sleep(INTERVAL)

if __name__=="__main__":
    main()
