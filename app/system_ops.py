import os, pwd, shutil, socket, subprocess, platform, re, time, json, io, tarfile, tempfile, sqlite3, hashlib
from datetime import datetime
from pathlib import Path
import psutil
import pyzipper
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


def _backup_root():
    root=Path(os.getenv("MAKIA_BACKUP_DIR","/var/backups/makia-vps-manager"))
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    try: os.chmod(root,0o700)
    except OSError: pass
    return root


def _sha256_file(path):
    digest=hashlib.sha256()
    with open(path,"rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_metadata_path(path):
    return Path(str(path)+".meta.json")


def _write_backup_metadata(path,metadata):
    meta=_backup_metadata_path(path)
    meta.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(meta,0o600)


def backup_list():
    root=_backup_root()
    items=[]
    paths=[p for p in root.iterdir() if p.is_file() and (p.name.endswith(".tar.gz") or p.name.endswith(".zip"))]
    for path in sorted(paths,key=lambda p:p.stat().st_mtime,reverse=True):
        st=path.stat()
        meta={}
        meta_path=_backup_metadata_path(path)
        if meta_path.is_file():
            try: meta=json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception: meta={}
        kind=meta.get("type") or ("full_migration" if path.name.endswith(".zip") else "quick")
        items.append({
            "name":path.name,
            "size":st.st_size,
            "created_at":int(meta.get("created_at_epoch") or st.st_mtime),
            "type":kind,
            "version":str(meta.get("version") or ""),
            "sha256":str(meta.get("sha256") or _sha256_file(path)),
            "encrypted":bool(meta.get("encrypted",path.name.endswith(".zip"))),
            "restore_ready":bool(meta.get("restore_ready",kind=="quick")),
        })
    return items[:50]


def create_backup(data_dir: str,version=""):
    root=_backup_root()
    stamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out=root/f"makia-data-{stamp}.tar.gz"
    blob=_portable_data_tar(data_dir)
    out.write_bytes(blob)
    os.chmod(out,0o600)
    metadata={
        "type":"quick","version":str(version or ""),"encrypted":False,
        "restore_ready":True,"sha256":hashlib.sha256(blob).hexdigest(),
        "created_at_epoch":int(time.time()),
    }
    _write_backup_metadata(out,metadata)
    return {"name":out.name,"path":str(out),"size":out.stat().st_size,**metadata}


def save_full_migration_backup(blob,version="",manifest=None):
    root=_backup_root()
    stamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out=root/f"makia-full-migration-{stamp}.zip"
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as fh:
            fh.write(bytes(blob))
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try: out.unlink()
        except OSError: pass
        raise
    metadata={
        "type":"full_migration","version":str(version or ""),"encrypted":True,
        "restore_ready":True,"sha256":hashlib.sha256(blob).hexdigest(),
        "created_at_epoch":int(time.time()),
        "format_version":int((manifest or {}).get("format_version") or 0),
        "panel_domain":str((manifest or {}).get("panel_domain") or ""),
    }
    _write_backup_metadata(out,metadata)
    return {"name":out.name,"path":str(out),"size":out.stat().st_size,**metadata}


def backup_download_path(name):
    raw=str(name or "")
    safe=Path(raw).name
    if safe!=raw or not (safe.endswith(".tar.gz") or safe.endswith(".zip")):
        raise OperationError("invalid backup name")
    path=_backup_root()/safe
    if not path.is_file():
        raise OperationError("backup not found")
    return path


def inspect_portable_migration_blob(blob,password,expected_version=""):
    if len(blob)<100:
        raise OperationError("migration bundle is empty or invalid")
    try:
        with pyzipper.AESZipFile(io.BytesIO(bytes(blob)),"r") as zf:
            zf.setpassword(str(password or "").encode("utf-8"))
            names=set(zf.namelist())
            if "manifest.json" not in names:
                raise OperationError("manifest.json is missing")
            manifest=json.loads(zf.read("manifest.json").decode("utf-8"))
            if manifest.get("format")!="makia-portable-migration" or int(manifest.get("format_version") or 0)!=2:
                raise OperationError("unsupported migration bundle format")
            payload_names=[name for name in names if name.startswith("payload/")]
            expected=manifest.get("payload_sha256") or {}
            for name,digest in expected.items():
                if name not in names:
                    raise OperationError(f"bundle payload missing: {name}")
                if hashlib.sha256(zf.read(name)).hexdigest()!=str(digest):
                    raise OperationError(f"bundle checksum mismatch: {name}")
            required={"payload/data.tar.gz","payload/ssh-users.json"}
            if not required.issubset(names):
                raise OperationError("migration bundle is missing required Makia data")
    except OperationError:
        raise
    except Exception as exc:
        raise OperationError("encrypted migration bundle verification failed") from exc
    bundle_version=str(manifest.get("app_version") or "")
    compatible=not expected_version or not bundle_version or bundle_version==str(expected_version)
    return {
        "manifest":manifest,"sha256":hashlib.sha256(blob).hexdigest(),"size":len(blob),
        "compatible":compatible,"expected_version":str(expected_version or ""),"bundle_version":bundle_version,
        "components":manifest.get("components") or {},"payload_count":len(payload_names),
    }


def stage_migration_restore(blob,password,expected_version=""):
    preview=inspect_portable_migration_blob(blob,password,expected_version)
    if not preview["compatible"]:
        raise OperationError(
            f"migration version mismatch: bundle={preview['bundle_version']} destination={preview['expected_version']}"
        )
    job_id=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")+"-"+os.urandom(4).hex()
    job_root=_backup_root()/"restore-jobs"/job_id
    job_root.mkdir(parents=True,mode=0o700)
    os.chmod(job_root,0o700)
    bundle_path=job_root/"bundle.zip"
    password_path=job_root/"password"
    bundle_path.write_bytes(bytes(blob)); os.chmod(bundle_path,0o600)
    password_path.write_text(str(password),encoding="utf-8"); os.chmod(password_path,0o600)
    status={
        "job_id":job_id,"state":"verified","created_at":datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256":preview["sha256"],"bundle_version":preview["bundle_version"],
        "panel_domain":str(preview["manifest"].get("panel_domain") or ""),
        "components":preview["components"],"payload_count":preview["payload_count"],
        "message":"Bundle integrity and compatibility verified. Ready to restore.",
    }
    status_path=job_root/"status.json"
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(status_path,0o600)
    return {**status,"restore_ready":True}


def migration_restore_status(job_id):
    job_id=str(job_id or "")
    if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}",job_id):
        raise OperationError("invalid restore job id")
    path=_backup_root()/"restore-jobs"/job_id/"status.json"
    if not path.is_file():
        raise OperationError("restore job not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OperationError("restore job status is invalid") from exc


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
        authorized_keys=""
        auth_path=Path(p[5]) / ".ssh" / "authorized_keys"
        try:
            if auth_path.is_file():
                authorized_keys=auth_path.read_text(encoding="utf-8",errors="ignore")
        except OSError:
            authorized_keys=""
        rows.append({
            "username":username,
            "uid":int(p[2]),"gid":int(p[3]),
            "home":p[5],"shell":p[6],
            "password_hash":sh[1],
            "shadow_last_change":sh[2],
            "shadow_min":sh[3],"shadow_max":sh[4],"shadow_warn":sh[5],
            "shadow_inactive":sh[6],"shadow_expire":sh[7],
            "authorized_keys":authorized_keys,
        })
    return rows

def portable_migration_files(data_dir,managed_users,panel_domain="",version="",system_paths=None):
    """Build an encrypted-bundle payload for full VPS disaster recovery.

    Format v2 preserves Makia application data plus protocol identity material
    and root-owned runtime configuration required to bring the same users and
    keys up on a replacement VPS.
    """
    defaults={
        "wireguard":"/etc/wireguard",
        "openvpn":"/etc/openvpn",
        "letsencrypt":"/etc/letsencrypt",
        "xray":"/usr/local/etc/xray",
        "xray_alt":"/etc/xray",
        "nginx_site":"/etc/nginx/sites-available/makia-vps-manager",
        "makia_etc":"/etc/makia-vps-manager",
        "stunnel":"/etc/stunnel",
        "ipsec_d":"/etc/ipsec.d",
        "ipsec_conf":"/etc/ipsec.conf",
        "ipsec_secrets":"/etc/ipsec.secrets",
        "stunnel_defaults":"/etc/default/stunnel4",
    }
    paths={**defaults,**(system_paths or {})}
    files={
        "payload/data.tar.gz":_portable_data_tar(data_dir),
        "payload/ssh-users.json":json.dumps(_managed_ssh_export(managed_users),ensure_ascii=False,indent=2).encode("utf-8"),
    }
    components={}

    for name in ("wireguard","openvpn","letsencrypt","xray","xray_alt","makia_etc","stunnel","ipsec_d"):
        blob=_tar_bytes(paths[name],name)
        if blob:
            files[f"payload/{name}.tar.gz"]=blob
            components[name]=True
        else:
            components[name]=False

    for name in ("nginx_site","ipsec_conf","ipsec_secrets","stunnel_defaults"):
        src=Path(paths[name])
        if src.is_file():
            files[f"payload/{name}"]=src.read_bytes()
            components[name]=True
        else:
            components[name]=False

    checksums={
        name:hashlib.sha256(blob).hexdigest()
        for name,blob in files.items()
    }
    manifest={
        "format":"makia-portable-migration",
        "format_version":2,
        "created_at":datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_version":str(version or ""),
        "panel_domain":str(panel_domain or ""),
        "managed_ssh_users":len(json.loads(files["payload/ssh-users.json"].decode("utf-8"))),
        "components":components,
        "payload_sha256":checksums,
        "restore_contract":{
            "preserve_credentials":True,
            "rebind_destination_network":True,
            "dns_cutover_required":bool(panel_domain),
            "cloudflare_mode":"DNS only for raw VPN/SSH endpoints",
        },
        "cutover_note":"Restore on the replacement VPS, validate all services, then update the same DNS A/AAAA record to the new VPS. Domain-based client credentials remain unchanged.",
    }
    files["manifest.json"]=json.dumps(manifest,ensure_ascii=False,indent=2).encode("utf-8")
    return files

