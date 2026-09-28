#!/opt/makia-vps-manager/.venv/bin/python
import argparse
import datetime as dt
import getpass
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pyzipper

APP=Path("/opt/makia-vps-manager")
DATA=APP/"data"
BACKUP_ROOT=Path("/var/backups/makia-vps-manager")


def run(args,check=True):
    p=subprocess.run(args,text=True,capture_output=True,check=False)
    if check and p.returncode!=0:
        raise RuntimeError((p.stderr or p.stdout or "command failed").strip())
    return p


def safe_extract_tar(blob:bytes,destination:Path):
    destination=destination.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tf:
        for member in tf.getmembers():
            target=(destination/member.name).resolve()
            if target!=destination and destination not in target.parents:
                raise RuntimeError("unsafe path in migration archive")
        tf.extractall(destination)


def read_bundle(path:Path,password:str):
    with pyzipper.AESZipFile(path,"r") as zf:
        zf.setpassword(password.encode())
        names=set(zf.namelist())
        if "manifest.json" not in names:
            raise RuntimeError("manifest.json is missing")
        manifest=json.loads(zf.read("manifest.json").decode("utf-8"))
        version=int(manifest.get("format_version") or 0)
        if manifest.get("format")!="makia-portable-migration" or version not in {1,2}:
            raise RuntimeError("unsupported Makia migration format")
        payload={name:zf.read(name) for name in names if name.startswith("payload/")}
    expected=manifest.get("payload_sha256") or {}
    if version>=2:
        for name,digest in expected.items():
            blob=payload.get(name)
            if blob is None:
                raise RuntimeError(f"bundle payload missing: {name}")
            actual=hashlib.sha256(blob).hexdigest()
            if actual!=str(digest):
                raise RuntimeError(f"bundle checksum mismatch: {name}")
    return manifest,payload


MANAGED_RESTORE_PATHS=[
    DATA,
    Path("/etc/wireguard"),
    Path("/etc/openvpn"),
    Path("/etc/letsencrypt"),
    Path("/usr/local/etc/xray"),
    Path("/etc/xray"),
    Path("/etc/makia-vps-manager"),
    Path("/etc/stunnel"),
    Path("/etc/ipsec.d"),
    Path("/etc/ipsec.conf"),
    Path("/etc/ipsec.secrets"),
    Path("/etc/default/stunnel4"),
    Path("/etc/nginx/sites-available/makia-vps-manager"),
    Path("/etc/nginx/sites-enabled/makia-vps-manager"),
    Path("/etc/sysctl.d/99-makia-wireguard.conf"),
    Path("/etc/sysctl.d/99-makia-openvpn.conf"),
    Path("/etc/sysctl.d/99-makia-recovery.conf"),
]
for _unit in [
    "makia-vps-manager.service","makia-policy-enforcer.service","makia-metrics-sampler.service",
    "makia-protocol-traffic.service","makia-wstunnel.service","makia-ikev2-network.service",
    "makia-migration-restore@.service",
]:
    MANAGED_RESTORE_PATHS.append(Path("/etc/systemd/system")/_unit)


def _remove_path(path:Path):
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_path(src:Path,dst:Path):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_symlink():
        dst.symlink_to(os.readlink(src))
    elif src.is_dir():
        shutil.copytree(src,dst,symlinks=True)
    else:
        shutil.copy2(src,dst)


def _capture_user_state(username):
    passwd=run(["getent","passwd",username],check=False)
    if passwd.returncode!=0:
        return {"username":username,"existed":False}
    shadow=run(["getent","shadow",username],check=False)
    row={"username":username,"existed":True,"passwd":(passwd.stdout or "").strip(),"shadow":(shadow.stdout or "").strip()}
    parts=row["passwd"].split(":")
    home=Path(parts[5]) if len(parts)>=7 else Path(f"/home/{username}")
    auth=home/".ssh"/"authorized_keys"
    row["authorized_keys"]=auth.read_text(encoding="utf-8",errors="ignore") if auth.is_file() else None
    return row


def _restore_user_state(row):
    username=str(row.get("username") or "")
    if not username:
        return
    if not row.get("existed"):
        if run(["id","-u",username],check=False).returncode==0:
            run(["userdel","-r",username],check=False)
        return
    passwd=str(row.get("passwd") or "").split(":")
    shadow=str(row.get("shadow") or "").split(":")
    if run(["id","-u",username],check=False).returncode!=0 and len(passwd)>=7:
        run(["useradd","-m","-s",passwd[6],username],check=False)
    if len(shadow)>=2 and shadow[1]:
        run(["usermod","-p",shadow[1],username],check=False)
    if len(passwd)>=7:
        home=Path(passwd[5])
        auth=home/".ssh"/"authorized_keys"
        previous=row.get("authorized_keys")
        if previous is None:
            auth.unlink(missing_ok=True)
        else:
            auth.parent.mkdir(parents=True,exist_ok=True)
            auth.write_text(str(previous),encoding="utf-8")
            os.chmod(auth.parent,0o700); os.chmod(auth,0o600)
            try:
                import pwd
                pw=pwd.getpwnam(username)
                os.chown(auth.parent,pw.pw_uid,pw.pw_gid); os.chown(auth,pw.pw_uid,pw.pw_gid)
            except Exception:
                pass


def capture_makia_ufw_rules():
    if not shutil.which("ufw"):
        return []
    p=run(["ufw","status","numbered"],check=False)
    if p.returncode!=0:
        return []
    rules=[]
    for line in (p.stdout or "").splitlines():
        if "makia" not in line.lower():
            continue
        m=__import__("re").match(
            r"^\s*\[\s*(\d+)\]\s+(\d+)/(tcp|udp)\s+ALLOW\b.*?#\s*(Makia.*)$",
            line,__import__("re").I,
        )
        if m:
            rules.append({
                "number":int(m.group(1)),"port":int(m.group(2)),
                "proto":m.group(3).lower(),"comment":m.group(4).strip()[:120],
            })
    return rules


def restore_makia_ufw_rules(previous):
    if not shutil.which("ufw"):
        return
    current=capture_makia_ufw_rules()
    # Delete only rules explicitly carrying a Makia comment; never touch operator rules.
    for row in sorted(current,key=lambda x:x["number"],reverse=True):
        run(["ufw","--force","delete",str(row["number"])],check=False)
    seen=set()
    for row in previous or []:
        key=(int(row["port"]),str(row["proto"]),str(row.get("comment") or "Makia restored"))
        if key in seen:
            continue
        seen.add(key)
        run(["ufw","allow",f"{key[0]}/{key[1]}","comment",key[2]],check=False)


def create_restore_rollback(payload):
    BACKUP_ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    root=Path(tempfile.mkdtemp(prefix=".restore-rollback-",dir=BACKUP_ROOT))
    os.chmod(root,0o700)
    records=[]
    for target in MANAGED_RESTORE_PATHS:
        rel=Path(str(target).lstrip("/"))
        backup=root/"fs"/rel
        existed=target.exists() or target.is_symlink()
        records.append({"target":str(target),"backup":str(backup),"existed":existed})
        if existed:
            _copy_path(target,backup)
    try:
        incoming=json.loads(payload["payload/ssh-users.json"].decode("utf-8"))
    except Exception:
        incoming=[]
    users=[_capture_user_state(str(row.get("username") or "")) for row in incoming if row.get("username")]
    ufw_rules=capture_makia_ufw_rules()
    return root,records,users,ufw_rules


def rollback_restore(root,records,users,ufw_rules):
    stop_stack()
    for rec in records:
        target=Path(rec["target"])
        try:
            if target.exists() or target.is_symlink():
                _remove_path(target)
            if rec.get("existed"):
                backup=Path(rec["backup"])
                if backup.exists() or backup.is_symlink():
                    _copy_path(backup,target)
        except Exception:
            pass
    for row in users:
        try: _restore_user_state(row)
        except Exception: pass
    restore_makia_ufw_rules(ufw_rules)
    run(["systemctl","daemon-reload"],check=False)
    restart_stack()


def restore_tree(blob:bytes,archive_root:str,target:Path):
    with tempfile.TemporaryDirectory(prefix="makia-restore-tree-") as tmp_name:
        tmp=Path(tmp_name)
        safe_extract_tar(blob,tmp)
        src=tmp/archive_root
        if not src.exists():
            raise RuntimeError(f"archive root missing: {archive_root}")
        if target.exists():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(src,target,symlinks=True)


def restore_data(blob:bytes):
    with tempfile.TemporaryDirectory(prefix="makia-restore-data-") as tmp_name:
        tmp=Path(tmp_name)
        safe_extract_tar(blob,tmp)
        src=tmp/"data"
        if not src.is_dir():
            raise RuntimeError("portable data archive is invalid")
        if DATA.exists():
            shutil.rmtree(DATA)
        shutil.copytree(src,DATA,symlinks=True)
        os.chmod(DATA,0o750)
        secret=DATA/".secret"
        if secret.exists(): os.chmod(secret,0o600)
        db=DATA/"makia.db"
        if db.exists(): os.chmod(db,0o600)


def restore_ssh_users(blob:bytes):
    rows=json.loads(blob.decode("utf-8"))
    restored=[]
    for row in rows:
        username=str(row.get("username") or "")
        if not username:
            continue
        exists=run(["id","-u",username],check=False).returncode==0
        if not exists:
            shell=str(row.get("shell") or "/bin/bash")
            run(["useradd","-m","-s",shell,username])
        password_hash=str(row.get("password_hash") or "")
        if password_hash:
            run(["usermod","-p",password_hash,username])
        expire=str(row.get("shadow_expire") or "")
        if expire and expire not in {"-1","0"}:
            try:
                day=dt.date(1970,1,1)+dt.timedelta(days=int(expire))
                run(["chage","-E",day.isoformat(),username])
            except Exception:
                pass
        elif expire=="-1":
            run(["chage","-E","-1",username],check=False)
        authorized=str(row.get("authorized_keys") or "")
        if authorized.strip():
            home=Path(str(row.get("home") or f"/home/{username}"))
            ssh_dir=home/".ssh"
            ssh_dir.mkdir(parents=True,exist_ok=True)
            auth=ssh_dir/"authorized_keys"
            auth.write_text(authorized.rstrip()+"\n",encoding="utf-8")
            os.chmod(ssh_dir,0o700); os.chmod(auth,0o600)
            try:
                pw=__import__("pwd").getpwnam(username)
                os.chown(ssh_dir,pw.pw_uid,pw.pw_gid)
                os.chown(auth,pw.pw_uid,pw.pw_gid)
            except Exception:
                pass
        restored.append(username)
    return restored


def stop_stack():
    services=[
        "makia-vps-manager","makia-policy-enforcer","makia-metrics-sampler","makia-protocol-traffic",
        "xray","wg-quick@wg0","stunnel4","makia-wstunnel","makia-ikev2-network",
        "strongswan-starter","strongswan",
    ]
    server_dir=Path("/etc/openvpn/server")
    if server_dir.exists():
        services.extend(f"openvpn-server@{p.stem}" for p in server_dir.glob("*.conf"))
    for svc in services:
        run(["systemctl","stop",svc],check=False)


def restore_v2_system_payload(payload):
    mappings=[
        ("payload/wireguard.tar.gz","wireguard",Path("/etc/wireguard")),
        ("payload/openvpn.tar.gz","openvpn",Path("/etc/openvpn")),
        ("payload/letsencrypt.tar.gz","letsencrypt",Path("/etc/letsencrypt")),
        ("payload/xray.tar.gz","xray",Path("/usr/local/etc/xray")),
        ("payload/xray_alt.tar.gz","xray_alt",Path("/etc/xray")),
        ("payload/makia_etc.tar.gz","makia_etc",Path("/etc/makia-vps-manager")),
        ("payload/stunnel.tar.gz","stunnel",Path("/etc/stunnel")),
        ("payload/ipsec_d.tar.gz","ipsec_d",Path("/etc/ipsec.d")),
    ]
    for key,root,target in mappings:
        if key in payload:
            restore_tree(payload[key],root,target)

    file_mappings=[
        ("payload/nginx_site",Path("/etc/nginx/sites-available/makia-vps-manager"),0o644),
        ("payload/ipsec_conf",Path("/etc/ipsec.conf"),0o600),
        ("payload/ipsec_secrets",Path("/etc/ipsec.secrets"),0o600),
        ("payload/stunnel_defaults",Path("/etc/default/stunnel4"),0o644),
    ]
    # v1 compatibility
    if "payload/nginx-site.conf" in payload and "payload/nginx_site" not in payload:
        file_mappings.append(("payload/nginx-site.conf",Path("/etc/nginx/sites-available/makia-vps-manager"),0o644))
    for key,target,mode in file_mappings:
        if key in payload:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(payload[key])
            os.chmod(target,mode)

    allowed_units={
        "makia-vps-manager.service","makia-policy-enforcer.service","makia-metrics-sampler.service",
        "makia-protocol-traffic.service","makia-wstunnel.service","makia-ikev2-network.service",
        "makia-migration-restore@.service",
    }
    for key,blob in payload.items():
        if not key.startswith("payload/systemd/"):
            continue
        unit=Path(key).name
        if unit not in allowed_units:
            raise RuntimeError(f"unexpected systemd unit in bundle: {unit}")
        target=Path("/etc/systemd/system")/unit
        target.write_bytes(blob)
        os.chmod(target,0o644)

    site=Path("/etc/nginx/sites-available/makia-vps-manager")
    if site.exists():
        enabled=Path("/etc/nginx/sites-enabled/makia-vps-manager")
        enabled.parent.mkdir(parents=True,exist_ok=True)
        if enabled.exists() or enabled.is_symlink(): enabled.unlink()
        enabled.symlink_to(site)


def normalize_destination_runtime(payload=None):
    sys.path.insert(0,str(APP))
    from app import protocol_ops

    if shutil.which("xray") and (Path("/usr/local/etc/xray/config.json").exists() or Path("/etc/xray/config.json").exists()):
        protocol_ops.repair_xray_runtime()

    if Path("/etc/wireguard/wg0.conf").exists():
        # Rewrites PostUp/PostDown with the replacement VPS default interface
        # while preserving the server private key and every peer public key.
        protocol_ops.repair_wireguard_runtime("wg0")

    if Path("/etc/openvpn/server/server.conf").exists():
        # Rebuilds Makia forwarding scripts for the new uplink without touching
        # CA, server/client certificates, CRL or tls-crypt keys.
        primary=protocol_ops.repair_openvpn_ipv4_runtime().get("runtime") or {}
        if primary.get("port"):
            protocol_ops._ufw_allow_if_active(
                int(primary["port"]),
                "tcp" if str(primary.get("proto") or "").startswith("tcp") else "udp",
                "OpenVPN restored primary",
            )

    tcp_conf=Path("/etc/openvpn/server/makia-tcp.conf")
    if tcp_conf.exists():
        text=tcp_conf.read_text(encoding="utf-8",errors="ignore")
        match=__import__("re").search(r"(?m)^port\s+(\d+)\s*$",text)
        tcp_port=int(match.group(1)) if match else 8443
        # Recreate destination-interface NAT scripts while preserving the same
        # OpenVPN PKI and client certificates.
        protocol_ops.ensure_openvpn_tcp_fallback(tcp_port)

    stealth=Path("/etc/stunnel/makia-openvpn.conf")
    if stealth.exists():
        text=stealth.read_text(encoding="utf-8",errors="ignore")
        match=__import__("re").search(r"(?m)^\s*accept\s*=\s*(?:[^:]+:)?(\d+)\s*$",text)
        if match:
            protocol_ops._ufw_allow_if_active(int(match.group(1)),"tcp","Stealth restored")

    ws_env=Path("/etc/makia-vps-manager/wstunnel.env")
    if ws_env.exists():
        text=ws_env.read_text(encoding="utf-8",errors="ignore")
        match=__import__("re").search(r"(?m)^WSTUNNEL_LISTEN_PORT=(\d+)\s*$",text)
        if match:
            protocol_ops._ufw_allow_if_active(int(match.group(1)),"tcp","WStunnel restored")

    if Path("/etc/ipsec.conf").exists() and "# BEGIN MAKIA IKEV2" in Path("/etc/ipsec.conf").read_text(encoding="utf-8",errors="ignore"):
        protocol_ops._ufw_allow_if_active(500,"udp","IKEv2 restored")
        protocol_ops._ufw_allow_if_active(4500,"udp","IKEv2 NAT-T restored")

    if payload and "payload/makia-firewall.json" in payload and shutil.which("ufw"):
        try:
            for rule in json.loads(payload["payload/makia-firewall.json"].decode("utf-8")):
                port=int(rule.get("port") or 0); proto=str(rule.get("proto") or "").lower()
                if 1<=port<=65535 and proto in {"tcp","udp"}:
                    protocol_ops._ufw_allow_if_active(port,proto,"Restored rule")
        except Exception as exc:
            raise RuntimeError(f"unable to restore Makia firewall rules: {exc}") from exc

    Path("/etc/sysctl.d/99-makia-recovery.conf").write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
    run(["sysctl","-w","net.ipv4.ip_forward=1"],check=False)


def restart_stack():
    run(["systemctl","daemon-reload"],check=False)

    if Path("/etc/wireguard/wg0.conf").exists():
        run(["systemctl","enable","--now","wg-quick@wg0"],check=False)
        run(["systemctl","restart","wg-quick@wg0"],check=False)

    if shutil.which("xray"):
        run(["systemctl","enable","--now","xray"],check=False)
        run(["systemctl","restart","xray"],check=False)

    server_dir=Path("/etc/openvpn/server")
    if shutil.which("openvpn") and server_dir.exists():
        for conf in server_dir.glob("*.conf"):
            unit=f"openvpn-server@{conf.stem}"
            run(["systemctl","enable","--now",unit],check=False)
            run(["systemctl","restart",unit],check=False)

    if Path("/etc/ipsec.conf").exists() and "# BEGIN MAKIA IKEV2" in Path("/etc/ipsec.conf").read_text(encoding="utf-8",errors="ignore"):
        run(["systemctl","enable","--now","makia-ikev2-network"],check=False)
        if shutil.which("ipsec"):
            if run(["systemctl","is-enabled","strongswan-starter"],check=False).returncode==0:
                run(["systemctl","enable","--now","strongswan-starter"],check=False)
                run(["systemctl","restart","strongswan-starter"],check=False)
            else:
                run(["systemctl","enable","--now","strongswan"],check=False)
                run(["systemctl","restart","strongswan"],check=False)

    if Path("/etc/stunnel/makia-openvpn.conf").exists():
        run(["systemctl","enable","--now","stunnel4"],check=False)
        run(["systemctl","restart","stunnel4"],check=False)

    if Path("/etc/makia-vps-manager/wstunnel.env").exists() and shutil.which("wstunnel"):
        run(["systemctl","enable","--now","makia-wstunnel"],check=False)
        run(["systemctl","restart","makia-wstunnel"],check=False)

    for svc in ["makia-vps-manager","makia-policy-enforcer","makia-metrics-sampler","makia-protocol-traffic","fail2ban"]:
        run(["systemctl","enable","--now",svc],check=False)
        run(["systemctl","restart",svc],check=False)

    if shutil.which("nginx"):
        test=run(["nginx","-t"],check=False)
        if test.returncode!=0:
            raise RuntimeError((test.stderr or test.stdout or "nginx validation failed").strip())
        run(["systemctl","enable","--now","nginx"],check=False)
        run(["systemctl","reload","nginx"],check=False)


def validate_restored(panel_domain=""):
    checks=[]
    health=run(["curl","-fsS","--max-time","5","http://127.0.0.1:8787/healthz"],check=False)
    checks.append(("backend",health.returncode==0))

    if shutil.which("xray"):
        config=next((p for p in [Path("/usr/local/etc/xray/config.json"),Path("/etc/xray/config.json")] if p.exists()),None)
        if config:
            checks.append(("xray",run(["xray","run","-test","-format=json","-config",str(config)],check=False).returncode==0))

    if Path("/etc/wireguard/wg0.conf").exists():
        checks.append(("wireguard",run(["wg","show","wg0"],check=False).returncode==0))

    server_dir=Path("/etc/openvpn/server")
    if server_dir.exists():
        for conf in server_dir.glob("*.conf"):
            checks.append((f"openvpn:{conf.stem}",run(["systemctl","is-active",f"openvpn-server@{conf.stem}"],check=False).returncode==0))

    if Path("/etc/ipsec.conf").exists() and "# BEGIN MAKIA IKEV2" in Path("/etc/ipsec.conf").read_text(encoding="utf-8",errors="ignore"):
        checks.append(("ikev2",run(["ipsec","status"],check=False).returncode==0))

    if Path("/etc/stunnel/makia-openvpn.conf").exists():
        checks.append(("stealth",run(["systemctl","is-active","stunnel4"],check=False).returncode==0))

    if Path("/etc/makia-vps-manager/wstunnel.env").exists():
        checks.append(("wstunnel",run(["systemctl","is-active","makia-wstunnel"],check=False).returncode==0))

    if panel_domain and Path(f"/etc/letsencrypt/live/{panel_domain}/fullchain.pem").exists():
        p=run(["curl","-fsS","--max-time","8","--resolve",f"{panel_domain}:443:127.0.0.1",f"https://{panel_domain}/healthz"],check=False)
        checks.append(("https-local-cutover",p.returncode==0))
    return checks


def main():
    parser=argparse.ArgumentParser(description="Restore a Makia full migration bundle on a replacement VPS.")
    parser.add_argument("bundle",type=Path)
    parser.add_argument("--apply",action="store_true",help="perform the restore; without this flag only validate the bundle")
    parser.add_argument("--password",help="bundle password (prefer prompt or MAKIA_MIGRATION_PASSWORD)")
    parser.add_argument("--password-file",type=Path,help="root-only file containing the bundle password")
    parser.add_argument("--allow-version-mismatch",action="store_true",help="allow restore when bundle/app versions differ")
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise SystemExit("Run as root.")
    file_password=""
    if args.password_file:
        st=args.password_file.stat()
        if st.st_mode & 0o077:
            raise SystemExit("Password file permissions must be 0600 or stricter.")
        file_password=args.password_file.read_text(encoding="utf-8").rstrip("\r\n")
    password=args.password or file_password or os.getenv("MAKIA_MIGRATION_PASSWORD") or getpass.getpass("Migration bundle password: ")
    manifest,payload=read_bundle(args.bundle,password)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    required={"payload/data.tar.gz","payload/ssh-users.json"}
    missing=required-set(payload)
    if missing:
        raise SystemExit("Missing required payload: "+", ".join(sorted(missing)))
    if not args.apply:
        print("\nBundle validation PASS. Re-run with --apply on the destination VPS.")
        return
    if not APP.exists():
        raise SystemExit("Install Makia on the destination VPS before restore.")
    installed_version=(APP/"VERSION").read_text(encoding="utf-8").strip() if (APP/"VERSION").exists() else ""
    bundle_version=str(manifest.get("app_version") or "").strip()
    if installed_version and bundle_version and installed_version!=bundle_version and not args.allow_version_mismatch:
        raise SystemExit(f"Version mismatch: destination={installed_version}, bundle={bundle_version}. Install the matching Makia version or use --allow-version-mismatch after compatibility review.")

    BACKUP_ROOT.mkdir(parents=True,exist_ok=True)
    if shutil.which("makia-backup"):
        run(["makia-backup"],check=False)

    rollback_root=None
    rollback_records=[]
    rollback_users=[]
    rollback_ufw=[]
    mutated=False
    try:
        # The restore runner is a separate systemd unit, so it survives this stop.
        # Snapshot only after writers are stopped to keep DB/WAL and runtime files coherent.
        stop_stack()
        rollback_root,rollback_records,rollback_users,rollback_ufw=create_restore_rollback(payload)
        mutated=True
        restore_data(payload["payload/data.tar.gz"])
        restore_ssh_users(payload["payload/ssh-users.json"])
        restore_v2_system_payload(payload)
        normalize_destination_runtime(payload)
        restart_stack()

        domain=str(manifest.get("panel_domain") or "")
        checks=validate_restored(domain)
        failed=[name for name,ok in checks if not ok]
        for name,ok in checks:
            print(("PASS" if ok else "FAIL"),name)
        if failed:
            raise RuntimeError("runtime validation failed: "+", ".join(failed))
    except Exception as exc:
        rollback_error=None
        if mutated:
            try:
                rollback_restore(rollback_root,rollback_records,rollback_users,rollback_ufw)
            except Exception as rb_exc:
                rollback_error=rb_exc
        else:
            # Snapshot creation itself may fail after services were stopped.
            # No target data was mutated yet, so simply bring the original stack back.
            try:
                restart_stack()
            except Exception as rb_exc:
                rollback_error=rb_exc
        if rollback_error:
            raise SystemExit(f"Restore failed ({exc}); automatic rollback/restart also failed ({rollback_error}).")
        if mutated:
            raise SystemExit(f"Restore failed and automatic rollback completed: {exc}")
        raise SystemExit(f"Restore aborted before mutation; original services restarted: {exc}")
    finally:
        if rollback_root:
            shutil.rmtree(rollback_root,ignore_errors=True)

    print("\nFULL MIGRATION RESTORE: PASS")
    if domain:
        print(f"Cloudflare A record: {domain} → NEW_VPS_IP")
        print("Update A/AAAA only after runtime verification and DNS diagnostics pass.")
        print("Raw VPN/SSH hostnames must be DNS-only in Cloudflare, not proxied.")
        print("Domain-based Xray/WireGuard/OpenVPN/SSH client credentials remain unchanged.")
        print("Profiles containing the old literal VPS IP require re-export; DNS cannot change a literal IP.")


if __name__=="__main__":
    main()
