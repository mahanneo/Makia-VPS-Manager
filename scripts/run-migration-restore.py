#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("/var/backups/makia-vps-manager/restore-jobs")


def write_status(path,state,message,extra=None):
    current={}
    if path.is_file():
        try: current=json.loads(path.read_text(encoding="utf-8"))
        except Exception: current={}
    current.update({
        "state":state,
        "message":str(message)[:4000],
        "updated_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    if extra: current.update(extra)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    os.replace(tmp,path)


def main():
    if os.geteuid()!=0:
        raise SystemExit("restore runner must run as root")
    if len(sys.argv)!=2 or not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}",sys.argv[1]):
        raise SystemExit("invalid restore job id")
    job=ROOT/sys.argv[1]
    bundle=job/"bundle.zip"
    password=job/"password"
    status=job/"status.json"
    if not bundle.is_file() or not password.is_file() or not status.is_file():
        raise SystemExit("restore job is incomplete")
    write_status(status,"running","Transactional restore started. Makia may restart during this operation.")
    try:
        p=subprocess.run(
            ["/usr/local/sbin/makia-restore-portable",str(bundle),"--apply","--password-file",str(password)],
            text=True,capture_output=True,check=False,timeout=1800,
        )
        output=((p.stdout or "")+"\n"+(p.stderr or "")).strip()[-12000:]
        if p.returncode!=0:
            write_status(status,"failed","Restore failed. The restore engine attempted automatic rollback.",{
                "exit_code":p.returncode,"output":output,
            })
            raise SystemExit(p.returncode)
        write_status(status,"passed","Restore and runtime verification passed.",{
            "exit_code":0,"output":output,
        })
        bundle.unlink(missing_ok=True)
    except subprocess.TimeoutExpired as exc:
        write_status(status,"failed","Restore timed out. Inspect the host and rollback state before retrying.",{
            "output":str(exc)[-4000:],
        })
        raise SystemExit(124)
    finally:
        try:
            password.write_text("",encoding="utf-8")
            password.unlink(missing_ok=True)
        except OSError:
            pass


if __name__=="__main__":
    main()
