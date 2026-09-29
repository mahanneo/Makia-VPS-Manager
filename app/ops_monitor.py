import json
import time
from datetime import date, datetime

from .db import (
    init_db,get_setting,set_setting,all_profiles,list_protocol_clients,list_nodes,
    add_notification_event,audit
)
from . import system_ops, protocol_ops, integration_ops


def _telegram(text):
    secret=get_setting("telegram_secret","") or ""
    chat=get_setting("telegram_chat_id","") or ""
    if not secret or not chat:
        return False
    try:
        token=integration_ops.open_secret(secret).get("bot_token","")
        integration_ops.telegram_send(token,chat,text)
        return True
    except Exception:
        return False


def _expiry_count(days=3):
    today=date.today();now=int(time.time());count=0;expired=0
    for p in all_profiles().values():
        raw=p.get("expire_date")
        if not raw:continue
        try:left=(date.fromisoformat(str(raw))-today).days
        except Exception:continue
        if left<=days:
            count+=1
            if left<0:expired+=1
    for row in list_protocol_clients():
        exp=int(row.get("expire_at") or 0)
        if not exp:continue
        left=(exp-now)//86400
        if left<=days:
            count+=1
            if exp<now:expired+=1
    return count,expired


def _snapshot():
    m=system_ops.metrics()
    stack=protocol_ops.catalog()
    services={
        "xray":bool(stack.get("xray",{}).get("service_active")),
        "wireguard":bool(stack.get("wireguard",{}).get("service_active")),
        "openvpn":bool(stack.get("openvpn",{}).get("service_active")),
    }
    try:
        outline=integration_ops.outline_status()
        if outline.get("installed"):
            services["outline"]=bool(outline.get("container_active") and outline.get("api_ok"))
    except Exception:
        pass
    expiring,expired=_expiry_count(3)
    offline=0
    now=time.time()
    for node in list_nodes():
        if not node.get("active"):continue
        seen=node.get("last_seen_at")
        age=None
        if seen:
            try:age=now-datetime.fromisoformat(str(seen)).timestamp()
            except Exception:age=None
        if age is None or age>180:offline+=1
    return {
        "services":services,
        "disk_high":float(m.get("disk") or 0)>=85,
        "disk":round(float(m.get("disk") or 0),1),
        "expiring_3d":expiring,
        "expired":expired,
        "nodes_offline":offline,
    }


def run_once():
    init_db()
    current=_snapshot()
    try:previous=json.loads(get_setting("ops_monitor_state","{}") or "{}")
    except Exception:previous={}
    messages=[]
    old_services=previous.get("services") or {}
    for name,healthy in current["services"].items():
        if old_services.get(name) is True and not healthy:
            messages.append(("error","service_down",f"{name} is DOWN",f"Makia detected {name} runtime is down."))
        elif old_services.get(name) is False and healthy:
            messages.append(("info","service_recovered",f"{name} recovered",f"{name} runtime is healthy again."))
    if current["disk_high"] and not previous.get("disk_high"):
        messages.append(("warn","disk_high",f"Disk usage {current['disk']}%", "Disk usage crossed the 85% alert threshold."))
    if current["expiring_3d"] and current["expiring_3d"]!=previous.get("expiring_3d"):
        messages.append(("warn","expiry",f"{current['expiring_3d']} access(es) expire within 3 days",f"Expired already: {current['expired']}"))
    if current["nodes_offline"] and current["nodes_offline"]!=previous.get("nodes_offline"):
        messages.append(("warn","node_offline",f"{current['nodes_offline']} node(s) offline","No recent node heartbeat."))

    for level,event,title,detail in messages:
        delivered=_telegram(("⚠️ " if level!="info" else "✅ ")+title+"\n"+detail)
        add_notification_event(event,title,detail,level,delivered)
        audit("system","ops_notification",event,f"delivered={delivered}; {detail}"[:500])
    set_setting("ops_monitor_state",json.dumps(current,ensure_ascii=False,separators=(",",":")))
    return {"ok":True,"events":len(messages),"snapshot":current}


def main():
    print(json.dumps(run_once(),ensure_ascii=False))


if __name__=="__main__":
    main()
