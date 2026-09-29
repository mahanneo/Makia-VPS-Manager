import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from . import access_ops, system_ops, outline_ops
from .config import DATA_DIR
from .db import (
    all_profiles, due_backup_schedules, update_backup_schedule_state,
    add_backup_run, list_backup_runs, get_setting, set_setting,
    add_alert_event, list_alert_events, list_protocol_clients, set_protocol_client_enabled,
)

_scheduler_started=False
_scheduler_lock=threading.Lock()


class AutomationError(RuntimeError):
    pass


def seal_config(value):
    return access_ops.seal_payload(value or {})


def open_config(value):
    if not value:
        return {}
    try:
        result=access_ops.open_payload(value)
        return result if isinstance(result,dict) else {}
    except Exception as exc:
        raise AutomationError("encrypted automation configuration cannot be opened") from exc


def _json_request(url,method="GET",headers=None,payload=None,timeout=15):
    data=None
    request_headers={"Accept":"application/json",**(headers or {})}
    if payload is not None:
        data=json.dumps(payload,separators=(",",":")).encode("utf-8")
        request_headers.setdefault("Content-Type","application/json")
    req=urllib.request.Request(url,data=data,headers=request_headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as res:
            raw=res.read(2_000_000)
            return int(res.status),json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw=exc.read(200_000)
        try:detail=json.loads(raw.decode("utf-8") or "{}")
        except Exception:detail={"message":raw.decode("utf-8",errors="ignore")}
        raise AutomationError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise AutomationError(str(exc)) from exc


def cloudflare_resolve(api_token,zone_name,record_name):
    token=str(api_token or "").strip()
    zone=str(zone_name or "").strip().lower().rstrip(".")
    record=str(record_name or "").strip().lower().rstrip(".")
    if len(token)<20 or not zone or not record:
        raise AutomationError("Cloudflare token, zone and record name are required")
    headers={"Authorization":f"Bearer {token}"}
    _,zones=_json_request(
        "https://api.cloudflare.com/client/v4/zones?"+urllib.parse.urlencode({"name":zone,"status":"active"}),
        headers=headers,
    )
    results=zones.get("result") or []
    if len(results)!=1:
        raise AutomationError("Cloudflare zone was not uniquely resolved")
    zone_id=results[0]["id"]
    _,records=_json_request(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?"+
        urllib.parse.urlencode({"type":"A","name":record}),
        headers=headers,
    )
    rows=records.get("result") or []
    if len(rows)>1:
        raise AutomationError("multiple Cloudflare A records matched")
    current=rows[0] if rows else None
    return {"zone_id":zone_id,"record":current,"zone":zone,"name":record}


def cloudflare_update_a(api_token,zone_name,record_name,ip_address,ttl=60,proxied=False):
    import ipaddress
    try:
        ip=ipaddress.ip_address(str(ip_address or "").strip())
    except ValueError as exc:
        raise AutomationError("new Cloudflare A record value must be a valid IP") from exc
    if ip.version!=4:
        raise AutomationError("A record requires IPv4")
    state=cloudflare_resolve(api_token,zone_name,record_name)
    headers={"Authorization":f"Bearer {str(api_token).strip()}"}
    body={"type":"A","name":state["name"],"content":ip.compressed,"ttl":max(60,min(int(ttl or 60),86400)),"proxied":bool(proxied)}
    if state["record"]:
        record_id=state["record"]["id"]
        _,result=_json_request(
            f"https://api.cloudflare.com/client/v4/zones/{state['zone_id']}/dns_records/{record_id}",
            method="PUT",headers=headers,payload=body,
        )
    else:
        _,result=_json_request(
            f"https://api.cloudflare.com/client/v4/zones/{state['zone_id']}/dns_records",
            method="POST",headers=headers,payload=body,
        )
    if not result.get("success"):
        raise AutomationError("Cloudflare rejected the DNS update")
    return {"zone_id":state["zone_id"],"record":result.get("result") or body}


def telegram_send(bot_token,chat_id,text):
    token=str(bot_token or "").strip()
    chat=str(chat_id or "").strip()
    if not re.fullmatch(r"[0-9]{6,12}:[A-Za-z0-9_-]{20,}",token):
        raise AutomationError("invalid Telegram bot token format")
    if not re.fullmatch(r"-?[0-9]{4,20}",chat):
        raise AutomationError("invalid Telegram chat id")
    _,result=_json_request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        method="POST",
        payload={"chat_id":chat,"text":str(text)[:3900],"disable_web_page_preview":True},
    )
    if not result.get("ok"):
        raise AutomationError("Telegram rejected the message")
    return result.get("result") or {}


def _upload_s3(path,config):
    try:
        import boto3
    except Exception as exc:
        raise AutomationError("S3 support requires boto3; run the Makia updater") from exc
    bucket=str(config.get("bucket") or "").strip()
    if not bucket:raise AutomationError("S3 bucket is required")
    client=boto3.client(
        "s3",
        endpoint_url=str(config.get("endpoint_url") or "").strip() or None,
        region_name=str(config.get("region") or "").strip() or None,
        aws_access_key_id=str(config.get("access_key") or "").strip() or None,
        aws_secret_access_key=str(config.get("secret_key") or "").strip() or None,
    )
    prefix=str(config.get("prefix") or "makia").strip("/")
    key=(prefix+"/" if prefix else "")+path.name
    try:
        client.upload_file(str(path),bucket,key,ExtraArgs={"ServerSideEncryption":"AES256"})
    except Exception as exc:
        raise AutomationError(f"S3 upload failed: {exc}") from exc
    return {"remote_type":"s3","remote_status":"uploaded","remote_key":f"s3://{bucket}/{key}"}


def _upload_sftp(path,config):
    scp=shutil.which("scp")
    if not scp:raise AutomationError("scp is not installed")
    host=str(config.get("host") or "").strip()
    user=str(config.get("user") or "").strip()
    remote_path=str(config.get("path") or "").strip()
    key_file=Path(str(config.get("identity_file") or "")).expanduser()
    port=max(1,min(int(config.get("port") or 22),65535))
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,255}",host):raise AutomationError("invalid SFTP host")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",user):raise AutomationError("invalid SFTP user")
    if not remote_path.startswith("/") or ".." in Path(remote_path).parts:raise AutomationError("remote SFTP path must be absolute")
    if not key_file.is_absolute() or not key_file.is_file():raise AutomationError("SFTP identity file is missing")
    mode=key_file.stat().st_mode & 0o777
    if mode & 0o077:raise AutomationError("SFTP identity file permissions must be 0600/0400")
    target=f"{user}@{host}:{remote_path.rstrip('/')}/{path.name}"
    args=[scp,"-q","-P",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-i",str(key_file),str(path),target]
    p=subprocess.run(args,text=True,capture_output=True,timeout=600,check=False)
    if p.returncode!=0:raise AutomationError((p.stderr or p.stdout or "SFTP upload failed").strip()[:1000])
    return {"remote_type":"sftp","remote_status":"uploaded","remote_key":target}


def upload_remote(path,remote):
    remote=dict(remote or {})
    kind=str(remote.get("type") or "none").lower()
    if kind in {"","none"}:return {"remote_type":"none","remote_status":"skipped","remote_key":""}
    if kind in {"s3","r2","b2"}:return _upload_s3(path,remote)
    if kind in {"sftp","scp"}:return _upload_sftp(path,remote)
    raise AutomationError("unsupported remote backup destination")


def _cleanup_schedule_files(schedule_id,keep_last):
    runs=[x for x in list_backup_runs(500) if int(x.get("schedule_id") or 0)==int(schedule_id) and x.get("status")=="success"]
    for old in runs[max(1,int(keep_last)):]:
        name=str(old.get("backup_name") or "")
        if not name:continue
        try:
            p=system_ops.backup_download_path(name)
            p.unlink(missing_ok=True)
            Path(str(p)+".meta.json").unlink(missing_ok=True)
        except Exception:
            pass


def execute_backup_schedule(schedule,version):
    schedule_id=int(schedule["id"])
    cfg=open_config(schedule.get("config_enc") or "")
    backup_type=str(schedule.get("backup_type") or "quick")
    result=None
    remote_result={"remote_type":"none","remote_status":"skipped","remote_key":""}
    try:
        if backup_type=="quick":
            result=system_ops.create_backup(str(DATA_DIR),version)
        elif backup_type=="full_migration":
            password=str(cfg.get("password") or "")
            if len(password)<10:raise AutomationError("scheduled Full Migration password must be at least 10 characters")
            files=system_ops.portable_migration_files(
                str(DATA_DIR),list(all_profiles().keys()),
                panel_domain=get_setting("panel_domain",""),version=version,
            )
            blob=access_ops.protected_zip(files,password)
            access_ops.verify_protected_zip(blob,password,"manifest.json")
            manifest=json.loads(files["manifest.json"].decode("utf-8"))
            result=system_ops.save_full_migration_backup(blob,version,manifest)
        else:
            raise AutomationError("invalid scheduled backup type")
        path=system_ops.backup_download_path(result["name"])
        remote_result=upload_remote(path,cfg.get("remote") or {})
        add_backup_run(schedule_id,result["name"],backup_type,remote_result["remote_type"],remote_result["remote_status"],result.get("sha256",""),result.get("size",0),"success",remote_result.get("remote_key",""))
        _cleanup_schedule_files(schedule_id,int(schedule.get("keep_last") or 7))
        return {"ok":True,"backup":result,**remote_result}
    except Exception as exc:
        add_backup_run(schedule_id,(result or {}).get("name",""),backup_type,remote_result.get("remote_type",""),remote_result.get("remote_status",""),(result or {}).get("sha256",""),(result or {}).get("size",0),"failed",str(exc))
        raise


def _alert_recent(kind,seconds):
    now=time.time()
    for row in list_alert_events(100):
        if row.get("kind")!=kind:continue
        try:
            created=row.get("created_at") or ""
            from datetime import datetime
            ts=datetime.fromisoformat(created).timestamp()
            return now-ts<seconds
        except Exception:return False
    return False


def send_configured_alert(kind,severity,title,message):
    if _alert_recent(kind,3600):return False
    delivered=False
    config_enc=get_setting("integrations_config_enc","")
    cfg=open_config(config_enc) if config_enc else {}
    telegram=cfg.get("telegram") or {}
    if telegram.get("enabled"):
        try:
            telegram_send(telegram.get("bot_token"),telegram.get("chat_id"),f"[Makia {str(severity).upper()}] {title}\n{message}")
            delivered=True
        except Exception:
            delivered=False
    add_alert_event(kind,severity,title,message,delivered)
    return delivered


def telegram_poll_commands(version):
    raw=get_setting("integrations_config_enc","")
    if not raw:return
    cfg=open_config(raw); tg=cfg.get("telegram") or {}
    if not tg.get("enabled") or not tg.get("bot_token") or not tg.get("chat_id") or not tg.get("commands",True):
        return
    token=str(tg["bot_token"]); expected_chat=str(tg["chat_id"])
    offset=int(get_setting("telegram_update_offset","0") or 0)
    url=f"https://api.telegram.org/bot{token}/getUpdates?"+urllib.parse.urlencode({"timeout":0,"offset":offset,"allowed_updates":json.dumps(["message"])})
    try:
        _,result=_json_request(url,timeout=10)
    except Exception:return
    if not result.get("ok"):return
    for update in result.get("result") or []:
        offset=max(offset,int(update.get("update_id") or 0)+1)
        message=update.get("message") or {}
        chat=str((message.get("chat") or {}).get("id") or "")
        text=str(message.get("text") or "").strip()
        if chat!=expected_chat or not text.startswith("/"):continue
        cmd=text.split()[0].split("@")[0].lower()
        try:
            if cmd in {"/start","/help"}:
                reply="Makia commands:\n/status — server health\n/expiry — expiring users\n/backups — latest backups"
            elif cmd=="/status":
                m=system_ops.metrics()
                clients=list_protocol_clients()
                reply=f"Makia {version}\nCPU {m.get('cpu',0)}% · RAM {m.get('memory',0)}% · Disk {m.get('disk',0)}%\nManaged protocol clients: {len(clients)}"
            elif cmd=="/expiry":
                now_ts=int(time.time()); exp=[]
                for row in list_protocol_clients():
                    e=int(row.get("expire_at") or 0)
                    if e and e-now_ts<=7*86400:
                        exp.append(f"{row.get('name')} · {max(0,(e-now_ts)//86400)}d")
                reply="Expiring ≤7d:\n"+("\n".join(exp[:30]) if exp else "None")
            elif cmd=="/backups":
                rows=system_ops.backup_list()[:5]
                reply="Latest backups:\n"+("\n".join(f"{x['name']} · {x.get('type')} · {x.get('size',0)}B" for x in rows) if rows else "None")
            else:
                reply="Unknown command. Use /help"
            telegram_send(token,expected_chat,reply)
        except Exception:
            pass
    set_setting("telegram_update_offset",str(offset))


def enforce_outline_expiry():
    now_ts=int(time.time())
    for row in list_protocol_clients():
        if row.get("engine")!="outline" or not row.get("enabled"):continue
        expire=int(row.get("expire_at") or 0)
        if expire and expire<=now_ts:
            outline_id=str(row.get("inbound_tag") or "").replace("outline:","")
            try:outline_ops.delete_key(outline_id)
            except Exception:continue
            set_protocol_client_enabled(row["id"],False,"expiry")


def health_alerts():
    try:
        m=system_ops.metrics()
        disk=float(m.get("disk") or 0)
        if disk>=90:send_configured_alert("disk-high","error","Disk usage critical",f"Disk usage is {disk:.1f}%")
    except Exception:pass
    for svc in ("makia-vps-manager","xray","nginx","wg-quick@wg0","openvpn-server@server"):
        try:
            s=system_ops.service_status(svc)
            if s.get("installed") and not s.get("active"):
                send_configured_alert(f"service:{svc}","error",f"Service down: {svc}",str(s.get("state") or "inactive"))
        except Exception:pass
    try:
        now_ts=int(time.time())
        expiring=[]
        for row in list_protocol_clients():
            expire=int(row.get("expire_at") or 0)
            if row.get("enabled") and expire and 0 < expire-now_ts <= 3*86400:
                expiring.append(row.get("name") or str(row.get("id")))
        if expiring:
            send_configured_alert(
                "expiry-soon","warn","Managed access expiring soon",
                f"{len(expiring)} client(s) expire within 3 days: "+", ".join(expiring[:20])
            )
    except Exception:pass


def scheduler_tick(version):
    now_ts=int(time.time())
    for schedule in due_backup_schedules(now_ts):
        interval=max(1,int(schedule.get("interval_hours") or 24))*3600
        next_run=now_ts+interval
        try:
            result=execute_backup_schedule(schedule,version)
            update_backup_schedule_state(schedule["id"],next_run,"success",f"{result['backup']['name']} / {result.get('remote_status')}",now_ts)
            send_configured_alert(f"backup:{schedule['id']}","info","Scheduled backup completed",result["backup"]["name"])
        except Exception as exc:
            update_backup_schedule_state(schedule["id"],next_run,"failed",str(exc),now_ts)
            send_configured_alert(f"backup-failed:{schedule['id']}","error","Scheduled backup failed",str(exc))
    enforce_outline_expiry()
    health_alerts()
    telegram_poll_commands(version)


def _scheduler_loop(version):
    while True:
        try:scheduler_tick(version)
        except Exception:pass
        time.sleep(60)


def start_scheduler_once(version):
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:return
        _scheduler_started=True
        t=threading.Thread(target=_scheduler_loop,args=(version,),daemon=True,name="makia-automation")
        t.start()
