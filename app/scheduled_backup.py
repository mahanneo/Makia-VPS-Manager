import json
import time
from pathlib import Path

from .config import DATA_DIR, VERSION
from .db import init_db, get_setting, set_setting, all_profiles, audit
from . import access_ops, system_ops, integration_ops


def _config():
    try:
        raw=json.loads(get_setting("backup_schedule_json","{}") or "{}")
    except Exception:
        raw={}
    return raw if isinstance(raw,dict) else {}


def _secret():
    token=get_setting("backup_schedule_secret","") or ""
    if not token:
        return {}
    try:
        return integration_ops.open_secret(token)
    except Exception:
        return {}


def _notify(text):
    token=get_setting("telegram_secret","") or ""
    chat_id=get_setting("telegram_chat_id","") or ""
    if not token or not chat_id:
        return False
    try:
        secret=integration_ops.open_secret(token)
        integration_ops.telegram_send(secret.get("bot_token",""),chat_id,text)
        return True
    except Exception:
        return False


def run_once(force=False):
    init_db()
    cfg=_config()
    enabled=bool(cfg.get("enabled",False))
    if not enabled and not force:
        return {"skipped":True,"reason":"disabled"}

    frequency=max(1,min(int(cfg.get("frequency_hours") or 24),168))
    last=int(get_setting("backup_schedule_last_run","0") or 0)
    now=int(time.time())
    if not force and last and now-last<frequency*3600:
        return {"skipped":True,"reason":"not_due","next_at":last+frequency*3600}

    secret=_secret()
    password=str(secret.get("password") or "")
    if len(password)<10:
        raise RuntimeError("scheduled Full Migration Backup requires an encrypted password of at least 10 characters")

    files=system_ops.portable_migration_files(
        str(DATA_DIR),
        list(all_profiles().keys()),
        panel_domain=get_setting("panel_domain",""),
        version=VERSION,
    )
    blob=access_ops.protected_zip(files,password)
    access_ops.verify_protected_zip(blob,password,"manifest.json")
    manifest=json.loads(files["manifest.json"].decode("utf-8"))
    saved=system_ops.save_full_migration_backup(blob,VERSION,manifest)
    set_setting("backup_schedule_last_run",str(now))
    status={
        "ok":True,"name":saved["name"],"sha256":saved["sha256"],
        "created_at":now,"remote":False,"remote_target":"",
    }

    remote=cfg.get("remote") or {}
    if bool(remote.get("enabled")):
        target=system_ops.remote_backup_scp(
            saved["path"],
            remote.get("host",""),
            remote.get("user",""),
            remote.get("path",""),
            remote.get("port",22),
            remote.get("key_path",""),
        )
        status["remote"]=True
        status["remote_target"]=target.get("target","")

    keep=max(1,min(int(cfg.get("keep_local") or 7),50))
    system_ops.prune_backup_files(
        Path(saved["path"]).parent,
        "makia-full-migration-",
        keep,
    )
    set_setting("backup_schedule_status",json.dumps(status,ensure_ascii=False,separators=(",",":")))
    audit("system","scheduled_full_backup",saved["name"],f"remote={status['remote']}; sha256={saved['sha256']}")
    _notify(f"✅ Makia backup completed\n{saved['name']}\nSHA256: {saved['sha256'][:16]}…")
    return status


def main():
    try:
        result=run_once(False)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        status={"ok":False,"error":str(exc)[:500],"created_at":int(time.time())}
        try:
            set_setting("backup_schedule_status",json.dumps(status,ensure_ascii=False,separators=(",",":")))
            audit("system","scheduled_full_backup_failed",detail=str(exc)[:500])
            _notify("❌ Makia scheduled backup failed\n"+str(exc)[:500])
        except Exception:
            pass
        raise


if __name__=="__main__":
    main()
