import os, pwd, shutil, socket, subprocess, platform, re, time, json, io, tarfile, tempfile, sqlite3
from datetime import datetime
from pathlib import Path
import psutil
from .config import ALLOWED_SERVICES

class OperationError(RuntimeError): pass

TTY_RE=re.compile(r"^[A-Za-z0-9._/-]{1,64}$")

def _run(args: list[str], input_text: str | None = None, timeout: int = 15):
    last_error = "operation failed"
    for attempt in range(3):
        try:
            p = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OperationError(str(exc)) from exc
        if p.returncode == 0:
            return p.stdout.strip()
        last_error = (p.stderr or p.stdout or "operation failed").strip()[:500]
        # shadow-utils can briefly contend on /etc/.pwd.lock during package/user operations.
        if "cannot lock /etc/passwd" in last_error.lower() and attempt < 2:
            time.sleep(1.0 + attempt)
            continue
        break
    raise OperationError(last_error)

def metrics():
    disk=psutil.disk_usage("/")
    mem=psutil.virtual_memory()
    swap=psutil.swap_memory()
    net=psutil.net_io_counters()
    return {
        "hostname":socket.gethostname(),
        "platform":platform.platform(),
        "kernel":platform.release(),
        "cpu":psutil.cpu_percent(interval=0.15),
        "cpu_cores":psutil.cpu_count(logical=True) or 1,
        "memory":mem.percent,
        "memory_used":mem.used,
        "memory_total":mem.total,
        "swap":swap.percent,
        "disk":disk.percent,
        "disk_used":disk.used,
        "disk_total":disk.total,
        "load":list(os.getloadavg()) if hasattr(os,"getloadavg") else [0,0,0],
        "uptime_seconds":int(datetime.now().timestamp()-psutil.boot_time()),
        "network":{"sent":net.bytes_sent,"recv":net.bytes_recv},
    }

def online_sessions():
    sessions=[]
    try: out=_run(["who"],timeout=5)
    except Exception: return sessions
    for line in out.splitlines():
        parts=line.split()
        if not parts: continue
        username=parts[0]
        tty=parts[1] if len(parts)>1 else ""
        when=" ".join(parts[2:4]) if len(parts)>3 else ""
        remote=""
        if "(" in line and ")" in line:
            remote=line.rsplit("(",1)[-1].rstrip(")")
        sessions.append({"username":username,"tty":tty,"since":when,"remote":remote})
    return sessions

def disconnect_session(tty: str):
    if not TTY_RE.fullmatch(tty or ""):
        raise OperationError("invalid terminal")
    # Use pkill against an exact terminal only; no shell expansion.
    _run(["pkill","-KILL","-t",tty],timeout=8)
    return {"tty":tty,"disconnected":True}

def service_status(name: str):
    if name not in ALLOWED_SERVICES:
        raise OperationError("service is not allowlisted")
    if not shutil.which("systemctl"):
        return {"name":name,"label":ALLOWED_SERVICES[name],"active":False,"state":"unsupported"}
    p=subprocess.run(["systemctl","is-active",name],text=True,capture_output=True)
    state=(p.stdout or p.stderr).strip() or "unknown"
    return {"name":name,"label":ALLOWED_SERVICES[name],"active":p.returncode==0,"state":state}

def service_action(name: str, action: str):
    if name not in ALLOWED_SERVICES or action not in {"start","stop","restart"}:
        raise OperationError("operation not allowed")
    _run(["systemctl",action,name])
    return service_status(name)

def ssh_users():
    users=[]
    for entry in pwd.getpwall():
        if entry.pw_uid>=1000 and entry.pw_shell not in {"/usr/sbin/nologin","/bin/false"}:
            users.append({"username":entry.pw_name,"uid":entry.pw_uid,"home":entry.pw_dir,"shell":entry.pw_shell})
    return users

def validate_username(username: str):
    if not username or len(username)>32 or not username.replace("-","").replace("_","").isalnum() or not username[0].isalpha():
        raise OperationError("invalid username")

def validate_user_password(password: str):
    if len(password)<4:
        raise OperationError("password/PIN must be at least 4 characters")
    if len(password)>128:
        raise OperationError("password is too long")

def create_ssh_user(username: str,password: str,expire: str|None=None):
    validate_username(username); validate_user_password(password)
    args=["useradd","-m","-s","/bin/bash"]
    if expire: args+=["-e",expire]
    args.append(username)
    _run(args)
    try:
        _run(["chpasswd"],input_text=f"{username}:{password}\n")
    except Exception:
        subprocess.run(["userdel","-r",username],capture_output=True)
        raise
    return {"username":username,"expire":expire}

def update_ssh_user(username: str,password: str|None=None,expire: str|None=None,clear_expire: bool=False):
    validate_username(username)
    if password:
        validate_user_password(password)
        _run(["chpasswd"],input_text=f"{username}:{password}\n")
    if clear_expire:
        _run(["usermod","-e","",username])
    elif expire:
        _run(["usermod","-e",expire,username])
    return {"username":username,"updated":True}

def lock_user(username: str,locked: bool):
    validate_username(username)
    _run(["usermod","-L" if locked else "-U",username])
    return {"username":username,"locked":locked}

def delete_user(username: str):
    validate_username(username)
    _run(["userdel","-r",username])
    return {"username":username,"deleted":True}

def security_status():
    def cmd_state(binary,args):
        if not shutil.which(binary): return {"installed":False,"active":False,"detail":"not installed"}
        p=subprocess.run(args,text=True,capture_output=True)
        text=(p.stdout or p.stderr or "").strip()
        return {"installed":True,"active":p.returncode==0,"detail":text[:400]}
    ufw=cmd_state("ufw",["ufw","status"])
    fail2ban=cmd_state("systemctl",["systemctl","is-active","fail2ban"])
    ssh=cmd_state("systemctl",["systemctl","is-active","ssh"])
    return {"ufw":ufw,"fail2ban":fail2ban,"ssh":ssh}


def backup_list():
    root="/var/backups/makia-vps-manager"
    if not os.path.isdir(root): return []
    items=[]
    for name in sorted(os.listdir(root),reverse=True):
        path=os.path.join(root,name)
        if os.path.isfile(path) and name.endswith(".tar.gz"):
            st=os.stat(path)
            items.append({"name":name,"size":st.st_size,"created_at":int(st.st_mtime)})
    return items[:50]

def create_backup(data_dir: str):
    root="/var/backups/makia-vps-manager"
    os.makedirs(root,mode=0o700,exist_ok=True)
    stamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out=os.path.join(root,f"makia-data-{stamp}.tar.gz")
    blob=_portable_data_tar(data_dir)
    Path(out).write_bytes(blob)
    os.chmod(out,0o600)
    return {"name":os.path.basename(out),"path":out,"size":os.path.getsize(out)}


def _tar_bytes(path, arcname):
    path=Path(path)
    if not path.exists():
        return None
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w:gz",dereference=False) as tf:
        tf.add(path,arcname=arcname,recursive=True)
    return buf.getvalue()

def _portable_data_tar(data_dir):
    data_dir=Path(data_dir)
    if not data_dir.is_dir():
        raise OperationError("data directory not found")
    with tempfile.TemporaryDirectory(prefix="makia-portable-") as tmp_name:
        tmp=Path(tmp_name)/"data"
        tmp.mkdir(parents=True,exist_ok=True)
        for item in data_dir.iterdir():
            if item.name in {"makia.db","makia.db-wal","makia.db-shm"}:
                continue
            target=tmp/item.name
            if item.is_dir():
                shutil.copytree(item,target,symlinks=True)
            elif item.is_symlink():
                target.symlink_to(os.readlink(item))
            else:
                shutil.copy2(item,target)
        src_db=data_dir/"makia.db"
        if src_db.exists():
            source=sqlite3.connect(f"file:{src_db}?mode=ro",uri=True)
            target=sqlite3.connect(tmp/"makia.db")
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
                source.close()
            os.chmod(tmp/"makia.db",0o600)
        return _tar_bytes(tmp,"data")

def _managed_ssh_export(usernames):
    rows=[]
    for username in sorted(set(str(x) for x in usernames if x)):
        try:
            validate_username(username)
            passwd_line=_run(["getent","passwd",username],timeout=5)
            shadow_line=_run(["getent","shadow",username],timeout=5)
        except Exception:
            continue
        p=passwd_line.split(":")
        sh=shadow_line.split(":")
        if len(p)<7 or len(sh)<9:
            continue
        rows.append({
            "username":username,
            "uid":int(p[2]),"gid":int(p[3]),
            "home":p[5],"shell":p[6],
            "password_hash":sh[1],
            "shadow_last_change":sh[2],
            "shadow_min":sh[3],"shadow_max":sh[4],"shadow_warn":sh[5],
            "shadow_inactive":sh[6],"shadow_expire":sh[7],
        })
    return rows

def portable_migration_files(data_dir,managed_users,panel_domain="",version="",system_paths=None):
    defaults={
        "wireguard":"/etc/wireguard",
        "openvpn":"/etc/openvpn",
        "letsencrypt":"/etc/letsencrypt",
        "xray":"/usr/local/etc/xray",
        "xray_alt":"/etc/xray",
        "protocol_modes_state":"/etc/makia-vps-manager",
        "swanctl":"/etc/swanctl",
        "stunnel":"/etc/stunnel",
        "nginx_site":"/etc/nginx/sites-available/makia-vps-manager",
    }
    paths={**defaults,**(system_paths or {})}
    files={
        "payload/data.tar.gz":_portable_data_tar(data_dir),
        "payload/ssh-users.json":json.dumps(_managed_ssh_export(managed_users),ensure_ascii=False,indent=2).encode("utf-8"),
    }
    components={}
    for name in ("wireguard","openvpn","letsencrypt","xray","xray_alt","protocol_modes_state","swanctl","stunnel"):
        blob=_tar_bytes(paths[name],name)
        if blob:
            files[f"payload/{name}.tar.gz"]=blob
            components[name]=True
        else:
            components[name]=False
    nginx=Path(paths["nginx_site"])
    if nginx.is_file():
        files["payload/nginx-site.conf"]=nginx.read_bytes()
        components["nginx_site"]=True
    else:
        components["nginx_site"]=False
    manifest={
        "format":"makia-portable-migration",
        "format_version":1,
        "created_at":datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_version":str(version or ""),
        "panel_domain":str(panel_domain or ""),
        "managed_ssh_users":len(json.loads(files["payload/ssh-users.json"].decode("utf-8"))),
        "components":components,
        "cutover_note":"Keep the same public domain and update its DNS A/AAAA record to the new VPS after restore. Existing client credentials remain unchanged.",
    }
    files["manifest.json"]=json.dumps(manifest,ensure_ascii=False,indent=2).encode("utf-8")
    return files
