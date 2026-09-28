#!/opt/makia-vps-manager/.venv/bin/python
import os, sys, time
from pathlib import Path
sys.path.insert(0,"/opt/makia-vps-manager")
os.environ.setdefault("MAKIA_DATA_DIR","/opt/makia-vps-manager/data")

from app.config import ALLOWED_SERVICES
from app.db import init_db, get_setting, set_setting, list_protocol_clients, add_notification_event
from app import access_ops, system_ops, protocol_ops

def secret(name):
    raw=get_setting("secret:"+name,"")
    if not raw:return {}
    try:return access_ops.open_payload(raw)
    except Exception:return {}

def send(kind,title,detail,level="warn"):
    dedupe_key="alert:"+kind
    fingerprint=(title+"|"+detail)[:800]
    if get_setting(dedupe_key,"")==fingerprint:
        return
    delivered=False
    tg=secret("telegram")
    if tg.get("enabled") and tg.get("bot_token") and tg.get("chat_id"):
        try:
            system_ops.telegram_send(tg["bot_token"],tg["chat_id"],f"[Makia] {title}\n{detail}")
            delivered=True
        except Exception:
            delivered=False
    add_notification_event(kind,title,detail,level,delivered)
    set_setting(dedupe_key,fingerprint)

def clear(kind):
    set_setting("alert:"+kind,"")

def main():
    init_db()
    m=system_ops.metrics()
    thresholds={
        "cpu":float(get_setting("alert_cpu_percent","90") or 90),
        "memory":float(get_setting("alert_memory_percent","90") or 90),
        "disk":float(get_setting("alert_disk_percent","90") or 90),
    }
    for key in ("cpu","memory","disk"):
        value=float(m.get(key,0) or 0)
        if value>=thresholds[key]:
            send("resource_"+key,f"{key.upper()} usage high",f"{value:.1f}% ≥ {thresholds[key]:.1f}%","warn")
        else: clear("resource_"+key)
    for service in ["xray","openvpn-server@server","wg-quick@wg0","nginx","ssh"]:
        try:
            st=system_ops.service_status(service)
            if st.get("state") not in {"not-found","unknown"} and not st.get("active"):
                send("service_"+service.replace("@","_"),f"Service down: {service}",st.get("state","inactive"),"error")
            else:clear("service_"+service.replace("@","_"))
        except Exception:
            pass
    now=int(time.time())
    expiring=[]
    for row in list_protocol_clients():
        exp=int(row.get("expire_at") or 0)
        if row.get("engine")=="xray" and exp and 0<=exp-now<=3*86400:
            expiring.append(f"{row.get('name')} ({max(0,(exp-now)//86400)}d)")
    if expiring:
        send("expiring_xray","Xray clients expiring soon",", ".join(expiring[:20]),"info")
    else:clear("expiring_xray")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
