#!/opt/makia-vps-manager/.venv/bin/python
import argparse
import datetime as dt
import getpass
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
        if manifest.get("format")!="makia-portable-migration" or int(manifest.get("format_version") or 0)!=1:
            raise RuntimeError("unsupported Makia migration format")
        payload={name:zf.read(name) for name in names if name.startswith("payload/")}
    return manifest,payload


def install_components(payload):
    sys.path.insert(0,str(APP))
    from app import protocol_ops
    if "payload/wireguard.tar.gz" in payload and not shutil.which("wg"):
        protocol_ops.install_component("wireguard")
    if "payload/openvpn.tar.gz" in payload and not shutil.which("openvpn"):
        protocol_ops.install_component("openvpn")
    if ("payload/xray.tar.gz" in payload or "payload/xray_alt.tar.gz" in payload) and not shutil.which("xray"):
        protocol_ops.install_component("xray")


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
        if secret.exists():
            os.chmod(secret,0o600)
        db=DATA/"makia.db"
        if db.exists():
            os.chmod(db,0o600)


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
        restored.append(username)
    return restored


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
    for svc in ["makia-vps-manager","makia-policy-enforcer","makia-metrics-sampler","makia-protocol-traffic","fail2ban"]:
        run(["systemctl","enable","--now",svc],check=False)
        run(["systemctl","restart",svc],check=False)
    if shutil.which("nginx"):
        test=run(["nginx","-t"],check=False)
        if test.returncode!=0:
            raise RuntimeError((test.stderr or test.stdout or "nginx validation failed").strip())
        run(["systemctl","enable","--now","nginx"],check=False)
        run(["systemctl","reload","nginx"],check=False)


def validate_restored():
    checks=[]
    health=run(["curl","-fsS","--max-time","5","http://127.0.0.1:8787/healthz"],check=False)
    checks.append(("backend",health.returncode==0))
    if shutil.which("xray"):
        config=None
        for candidate in [Path("/usr/local/etc/xray/config.json"),Path("/etc/xray/config.json")]:
            if candidate.exists():
                config=candidate
                break
        if config:
            p=run(["xray","run","-test","-format=json","-config",str(config)],check=False)
            checks.append(("xray",p.returncode==0))
    if Path("/etc/wireguard/wg0.conf").exists():
        try:
            sys.path.insert(0,str(APP))
            from app import protocol_ops
            checks.append(("wireguard",bool(protocol_ops.wireguard_diagnostics("wg0").get("runtime_ok"))))
        except Exception:
            checks.append(("wireguard",False))
    if Path("/etc/openvpn/server/server.conf").exists():
        try:
            sys.path.insert(0,str(APP))
            from app import protocol_ops
            d=protocol_ops._openvpn_server_runtime()
            checks.append(("openvpn",bool(d.get("service_active") and d.get("listener") and str(d.get("proto") or "") in {"udp4","tcp4-server"})))
        except Exception:
            checks.append(("openvpn",False))
    return checks


def main():
    parser=argparse.ArgumentParser(description="Restore a Makia portable migration bundle on a fresh Makia VPS.")
    parser.add_argument("bundle",type=Path)
    parser.add_argument("--apply",action="store_true",help="perform the restore; without this flag only validate the bundle")
    parser.add_argument("--password",help="bundle password (prefer prompt or MAKIA_MIGRATION_PASSWORD)")
    parser.add_argument("--allow-version-mismatch",action="store_true",help="allow restore when bundle/app versions differ")
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise SystemExit("Run as root.")
    password=args.password or os.getenv("MAKIA_MIGRATION_PASSWORD") or getpass.getpass("Migration bundle password: ")
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

    for svc in ["makia-vps-manager","makia-policy-enforcer","makia-metrics-sampler","makia-protocol-traffic","xray","wg-quick@wg0"]:
        run(["systemctl","stop",svc],check=False)

    install_components(payload)
    restore_data(payload["payload/data.tar.gz"])
    restore_ssh_users(payload["payload/ssh-users.json"])

    mappings=[
        ("payload/wireguard.tar.gz","wireguard",Path("/etc/wireguard")),
        ("payload/openvpn.tar.gz","openvpn",Path("/etc/openvpn")),
        ("payload/letsencrypt.tar.gz","letsencrypt",Path("/etc/letsencrypt")),
        ("payload/xray.tar.gz","xray",Path("/usr/local/etc/xray")),
        ("payload/xray_alt.tar.gz","xray_alt",Path("/etc/xray")),
    ]
    for key,root,target in mappings:
        if key in payload:
            restore_tree(payload[key],root,target)
    if "payload/nginx-site.conf" in payload:
        site=Path("/etc/nginx/sites-available/makia-vps-manager")
        site.parent.mkdir(parents=True,exist_ok=True)
        site.write_bytes(payload["payload/nginx-site.conf"])
        Path("/etc/nginx/sites-enabled").mkdir(parents=True,exist_ok=True)
        enabled=Path("/etc/nginx/sites-enabled/makia-vps-manager")
        if enabled.exists() or enabled.is_symlink():
            enabled.unlink()
        enabled.symlink_to(site)

    # Normalize restored Xray ownership/TLS paths for the destination
    # systemd user before the final stack restart.
    if shutil.which("xray") and (Path("/usr/local/etc/xray/config.json").exists() or Path("/etc/xray/config.json").exists()):
        sys.path.insert(0,str(APP))
        from app import protocol_ops
        protocol_ops.repair_xray_runtime()

    # Normalize restored protocol runtimes before the final stack validation.
    sys.path.insert(0,str(APP))
    from app import protocol_ops
    if Path("/etc/wireguard/wg0.conf").exists():
        protocol_ops.repair_wireguard_runtime("wg0")
    if Path("/etc/openvpn/server/server.conf").exists():
        protocol_ops.repair_openvpn_ipv4_runtime()

    restart_stack()
    checks=validate_restored()
    failed=[name for name,ok in checks if not ok]
    for name,ok in checks:
        print(("PASS" if ok else "FAIL"),name)
    if failed:
        raise SystemExit("Restore completed but validation failed: "+", ".join(failed))
    domain=str(manifest.get("panel_domain") or "")
    print("\nPortable restore PASS.")
    if domain:
        print(f"Cutover: point DNS for {domain} to this VPS. Existing Xray/WireGuard/SSH credentials remain unchanged.")


if __name__=="__main__":
    main()
