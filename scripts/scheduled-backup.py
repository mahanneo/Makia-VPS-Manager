#!/opt/makia-vps-manager/.venv/bin/python
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,"/opt/makia-vps-manager")
os.environ.setdefault("MAKIA_DATA_DIR","/opt/makia-vps-manager/data")

from app.config import DATA_DIR, VERSION
from app.db import init_db, get_setting, set_setting, all_profiles, add_notification_event
from app import access_ops, system_ops

def secret(name):
    raw=get_setting("secret:"+name,"")
    if not raw:return {}
    try:return access_ops.open_payload(raw)
    except Exception:return {}

def notify(title,detail,level="info"):
    delivered=False
    tg=secret("telegram")
    if tg.get("enabled") and tg.get("bot_token") and tg.get("chat_id"):
        try:
            system_ops.telegram_send(tg["bot_token"],tg["chat_id"],f"[Makia] {title}\n{detail}".strip())
            delivered=True
        except Exception:
            delivered=False
    add_notification_event("scheduled_backup",title,detail,level,delivered)

def main():
    init_db()
    cfg=secret("backup_schedule")
    if not cfg.get("enabled"):
        return 0
    now=datetime.now(timezone.utc)
    if now.hour!=int(cfg.get("hour",4) or 4):
        return 0
    today=now.strftime("%Y-%m-%d")
    if get_setting("backup_schedule_last_run","")==today:
        return 0
    password=str(cfg.get("password") or "")
    if len(password)<10:
        notify("Scheduled backup failed","Backup password is missing or too short.","error")
        return 2
    try:
        files=system_ops.portable_migration_files(
            str(DATA_DIR),list(all_profiles().keys()),
            panel_domain=get_setting("panel_domain",""),version=VERSION
        )
        blob=access_ops.protected_zip(files,password)
        access_ops.verify_protected_zip(blob,password,"manifest.json")
        manifest=json.loads(files["manifest.json"].decode("utf-8"))
        saved=system_ops.save_full_migration_backup(blob,VERSION,manifest)
        remote=""
        if cfg.get("remote_enabled"):
            pushed=system_ops.remote_backup_push(
                saved["path"],cfg.get("remote_host"),cfg.get("remote_user"),
                cfg.get("remote_path"),cfg.get("remote_key_path"),cfg.get("remote_port",22)
            )
            remote=pushed.get("target","")
        system_ops.prune_backups(cfg.get("keep",7),"full_migration")
        set_setting("backup_schedule_last_run",today)
        detail=f"{saved['name']} · {saved['size']} bytes · sha256={saved['sha256']}"
        if remote:detail+=f" · remote={remote}"
        notify("Scheduled migration backup PASS",detail,"info")
        return 0
    except Exception as exc:
        notify("Scheduled backup failed",str(exc)[:1000],"error")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
