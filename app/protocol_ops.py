import base64
import ipaddress
import json
import os
import re
import shutil
import subprocess
import secrets
import socket
import time
import urllib.parse
import uuid
import pwd
import tempfile
from pathlib import Path

XRAY_BIN_CANDIDATES=["/usr/local/bin/xray","/usr/bin/xray"]
XRAY_CONFIG_CANDIDATES=["/usr/local/etc/xray/config.json","/etc/xray/config.json"]
XRAY_VALIDATED_VERSION="v26.3.27"
XRAY_TLS_DIR=Path("/usr/local/etc/xray/tls")
WG_DIR=Path("/etc/wireguard")
OVPN_DIR=Path("/etc/openvpn")
OVPN_EASYRSA=OVPN_DIR/"easy-rsa"
IKEV2_CONF=Path("/etc/ipsec.conf")
IKEV2_SECRETS=Path("/etc/ipsec.secrets")
IKEV2_ENV=Path("/etc/makia-vps-manager/ikev2.env")
STUNNEL_MAKIA_CONF=Path("/etc/stunnel/makia-openvpn.conf")
WSTUNNEL_ENV=Path("/etc/makia-vps-manager/wstunnel.env")
WSTUNNEL_SERVICE="makia-wstunnel"
OVPN_TCP_FALLBACK_CONF=OVPN_DIR/"server/makia-tcp.conf"
OVPN_TCP_FALLBACK_SERVICE="openvpn-server@makia-tcp"


def _backup_dir():
    """Return the writable Makia backup root used by protocol mutations.

    Tests and non-standard installations can override the production path via
    MAKIA_BACKUP_DIR; production keeps the root-only /var/backups location.
    """
    root=Path(os.getenv("MAKIA_BACKUP_DIR","/var/backups/makia-vps-manager"))
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return root


class ProtocolError(RuntimeError):
    pass

def _run(args, input_text=None, timeout=60):
    try:
        p=subprocess.run(args,input=input_text,text=True,capture_output=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ProtocolError(str(exc)) from exc
    if p.returncode!=0:
        raise ProtocolError((p.stderr or p.stdout or "operation failed").strip()[:1200])
    return p.stdout.strip()

def _active(service):
    if not shutil.which("systemctl"):
        return False
    p=subprocess.run(["systemctl","is-active",service],text=True,capture_output=True)
    return p.returncode==0

def _installed(binary):
    return bool(shutil.which(binary))

def _binary():
    for p in XRAY_BIN_CANDIDATES:
        if os.path.isfile(p) and os.access(p,os.X_OK):
            return p
    return shutil.which("xray")

def _config_path():
    for p in XRAY_CONFIG_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _xray_service_user():
    if shutil.which("systemctl"):
        p=subprocess.run(["systemctl","show","xray","-p","User","--value"],text=True,capture_output=True,timeout=8,check=False)
        if p.returncode==0:
            return (p.stdout or "").strip() or "root"
    return "root"

def _xray_secure_runtime_file(path,mode=0o600):
    path=Path(path)
    os.chmod(path,mode)
    user=_xray_service_user()
    if os.geteuid()==0 and user not in {"","root"}:
        try:
            info=pwd.getpwnam(user)
            os.chown(path,info.pw_uid,info.pw_gid)
        except (KeyError,OSError) as exc:
            raise ProtocolError(f"unable to set Xray runtime file ownership for {user}: {exc}") from exc
    return user

def _process_no_new_privileges():
    """Return True when this process is forbidden from gaining privileges.

    Makia intentionally runs with systemd NoNewPrivileges. On some Ubuntu
    builds, runuser/setuid from that service fails with EPERM even while the
    root process can safely validate and write the Xray configuration.
    """
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8",errors="ignore").splitlines():
            if line.startswith("NoNewPrivs:"):
                return line.split(":",1)[1].strip()=="1"
    except OSError:
        pass
    return False


def _mode_allows(st,uid,gid,bit_user,bit_group,bit_other):
    if uid==0:
        return True
    mode=st.st_mode
    if st.st_uid==uid:
        return bool(mode & bit_user)
    if st.st_gid==gid:
        return bool(mode & bit_group)
    return bool(mode & bit_other)


def _xray_assert_path_readable(path,user):
    """Statically prove that the configured Xray service user can traverse/read a path."""
    target=Path(path)
    if not target.exists():
        raise ProtocolError(f"Xray runtime file is missing: {target}")
    try:
        info=pwd.getpwnam(user)
    except KeyError as exc:
        raise ProtocolError(f"Xray service user does not exist: {user}") from exc
    uid,gid=info.pw_uid,info.pw_gid
    # Every parent needs execute/search permission.
    parents=list(target.parents)
    for parent in reversed(parents):
        try:
            st=parent.stat()
        except OSError as exc:
            raise ProtocolError(f"cannot stat Xray runtime directory {parent}: {exc}") from exc
        if not _mode_allows(st,uid,gid,0o100,0o010,0o001):
            raise ProtocolError(f"Xray service user {user} cannot traverse {parent}")
    st=target.stat()
    if not _mode_allows(st,uid,gid,0o400,0o040,0o004):
        raise ProtocolError(f"Xray service user {user} cannot read {target}")
    return True


def _xray_referenced_files(path):
    refs=[]
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return refs
    def walk(node):
        if isinstance(node,dict):
            for key,value in node.items():
                if key in {"certificateFile","keyFile"} and isinstance(value,str) and value.startswith("/"):
                    refs.append(value)
                else:
                    walk(value)
        elif isinstance(node,list):
            for value in node:
                walk(value)
    walk(data)
    return sorted(set(refs))


def _xray_static_service_validation(path,user):
    _xray_assert_path_readable(path,user)
    for ref in _xray_referenced_files(path):
        _xray_assert_path_readable(ref,user)
    return "static-permission-check"


def _xray_test_config_as_service(binary,path):
    args=[binary,"run","-test","-format=json","-config",str(path)]
    user=_xray_service_user()
    if user in {"","root"} or os.geteuid()!=0:
        _run(args,timeout=30)
        return "direct"

    # The root semantic validation is authoritative for the JSON/Core syntax.
    # Service-user validation here is about file visibility/permissions.
    # Do not weaken Makia's systemd NoNewPrivileges hardening merely to make
    # runuser work from inside the web service.
    if _process_no_new_privileges() or not shutil.which("runuser"):
        return _xray_static_service_validation(path,user)

    try:
        _run(["runuser","-u",user,"--",*args],timeout=30)
        return "runuser"
    except ProtocolError as exc:
        msg=str(exc).lower()
        if "cannot set user id" in msg or ("runuser" in msg and "operation not permitted" in msg) or "setuid" in msg:
            return _xray_static_service_validation(path,user)
        raise

def _xray_materialize_tls(domain):
    domain=_validate_endpoint_host(domain,"TLS domain")
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    if not cert.exists() or not key.exists():
        raise ProtocolError("TLS certificate not found for this domain; issue HTTPS/Let's Encrypt first")
    target=XRAY_TLS_DIR/domain
    target.mkdir(parents=True,exist_ok=True)
    if os.geteuid()==0:
        user=_xray_service_user()
        if user not in {"","root"}:
            info=pwd.getpwnam(user)
            os.chown(target,info.pw_uid,info.pw_gid)
    os.chmod(target,0o700)
    cert_out=target/"fullchain.pem"
    key_out=target/"privkey.pem"
    shutil.copyfile(cert,cert_out)
    shutil.copyfile(key,key_out)
    _xray_secure_runtime_file(cert_out,0o600)
    _xray_secure_runtime_file(key_out,0o600)
    return cert_out,key_out

def _rewrite_letsencrypt_certificates(data):
    changed=0
    def walk(node):
        nonlocal changed
        if isinstance(node,dict):
            cert=node.get("certificateFile")
            key=node.get("keyFile")
            if isinstance(cert,str) and isinstance(key,str) and cert.startswith("/etc/letsencrypt/live/") and key.startswith("/etc/letsencrypt/live/"):
                parts=Path(cert).parts
                try:
                    idx=parts.index("live")
                    domain=parts[idx+1]
                    cert_out,key_out=_xray_materialize_tls(domain)
                    node["certificateFile"]=str(cert_out)
                    node["keyFile"]=str(key_out)
                    changed+=1
                except (ValueError,IndexError):
                    pass
            for value in node.values():
                walk(value)
        elif isinstance(node,list):
            for value in node:
                walk(value)
    walk(data)
    return changed

def _xray_journal_tail(lines=24):
    if not shutil.which("journalctl"):
        return ""
    p=subprocess.run(["journalctl","-u","xray","-n",str(max(1,min(int(lines),80))),"--no-pager","-o","cat"],text=True,capture_output=True,timeout=10,check=False)
    text=(p.stdout or p.stderr or "").strip()
    return text[-6000:]

def xray_diagnostics():
    binary=_binary()
    config=_config_path()
    service_user=_xray_service_user()
    result={
        "installed":bool(binary),"binary":binary,"config_path":config,
        "service_user":service_user,"service_active":_active("xray"),
        "version":"","validated_version":False,"root_validation":False,
        "service_validation":False,"root_error":"","service_error":"",
        "journal":_xray_journal_tail(),"hints":[],
        "cert_sync_hook":Path("/etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync").is_file(),
    }
    if binary:
        try:
            p=subprocess.run([binary,"version"],text=True,capture_output=True,timeout=5,check=False)
            result["version"]=(p.stdout or p.stderr).splitlines()[0][:160] if (p.stdout or p.stderr) else ""
            result["validated_version"]="26.3.27" in result["version"]
        except Exception:
            pass
    if config:
        try:
            _xray_test_config(binary,config)
            result["root_validation"]=True
        except Exception as exc:
            result["root_error"]=str(exc)[:1200]
        try:
            result["service_validation_mode"]=_xray_test_config_as_service(binary,config)
            result["service_validation"]=True
        except Exception as exc:
            result["service_validation_mode"]="failed"
            result["service_error"]=str(exc)[:1200]
        try:
            st=os.stat(config)
            result["config_mode"]=oct(st.st_mode & 0o777)
            result["config_uid"]=st.st_uid
        except OSError:
            pass
    journal=(result["journal"] or "").lower()
    if result["root_validation"] and not result["service_validation"]:
        result["hints"].append("کانفیگ برای root معتبر است ولی کاربر systemd نمی‌تواند آن را بخواند؛ مشکل Permission/Certificate محتمل است.")
    if "permission denied" in journal:
        result["hints"].append("در journal خطای Permission denied دیده شد.")
    if "address already in use" in journal:
        result["hints"].append("یک Port موردنیاز Xray قبلاً توسط سرویس دیگری اشغال شده است.")
    if "certificate" in journal and ("permission" in journal or "failed" in journal or "cannot" in journal):
        result["hints"].append("خواندن Certificate/Private Key TLS ناموفق بوده است.")
    if not result["root_validation"] and result["root_error"]:
        result["hints"].append("خود Xray Core کانفیگ فعال را نامعتبر تشخیص داده است.")
    if binary and not result["validated_version"]:
        result["hints"].append("نسخه Core نصب‌شده با نسخه‌ای که Makia در CI اعتبارسنجی می‌کند (26.3.27) متفاوت است.")
    return result

def repair_xray_runtime():
    binary=_binary()
    config=_config_path()
    if not binary or not config:
        raise ProtocolError("Xray binary/config is not available")
    path=Path(config)
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProtocolError(f"cannot parse Xray config: {exc}") from exc
    _rewrite_letsencrypt_certificates(data)
    tmp=_xray_temp_json_path(path,"repair")
    backup_dir=_backup_dir()
    backup=backup_dir/f"xray-repair-{int(time.time())}.json"
    shutil.copy2(path,backup)
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","daemon-reload"],timeout=20)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray did not become active after repair")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            shutil.copy2(backup,path)
            _xray_secure_runtime_file(path)
            _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"ok":True,"backup":str(backup),"diagnostics":xray_diagnostics()}

def _xray_temp_json_path(path, purpose="validate"):
    path=Path(path)
    safe=re.sub(r"[^A-Za-z0-9_.-]+","-",str(purpose or "validate")).strip("-") or "validate"
    return path.with_name(f".{path.stem}.makia-{safe}-{os.getpid()}-{secrets.token_hex(4)}.json")

def _xray_test_config(binary, path):
    return _run([binary,"run","-test","-format=json","-config",str(path)],timeout=30)

def xray_status():
    binary=_binary()
    config=_config_path()
    version=None
    if binary:
        try:
            p=subprocess.run([binary,"version"],text=True,capture_output=True,timeout=5,check=False)
            version=(p.stdout or p.stderr).splitlines()[0][:160] if (p.stdout or p.stderr) else None
        except Exception:
            pass
    inbounds=[]
    error=None
    if config:
        try:
            with open(config,"r",encoding="utf-8") as fh:
                data=json.load(fh)
            for item in data.get("inbounds",[]) if isinstance(data,dict) else []:
                if not isinstance(item,dict):
                    continue
                settings=item.get("settings") or {}
                clients=settings.get("clients") if isinstance(settings,dict) else None
                users=settings.get("users") if isinstance(settings,dict) else None
                client_count=len(clients) if isinstance(clients,list) else (len(users) if isinstance(users,list) else 0)
                protocol=item.get("protocol") or "unknown"
                if protocol=="hysteria" and isinstance(settings,dict) and int(settings.get("version") or 0)==2:
                    protocol="hysteria2"
                inbounds.append({
                    "tag":item.get("tag") or "",
                    "protocol":protocol,
                    "listen":item.get("listen") or "0.0.0.0",
                    "port":item.get("port"),
                    "clients":client_count,
                })
        except Exception as exc:
            error=str(exc)[:300]
    return {
        "installed":bool(binary),
        "binary":binary,
        "version":version,
        "service_active":_active("xray"),
        "config_path":config,
        "config_error":error,
        "inbounds":inbounds,
    }

def wireguard_status():
    installed=_installed("wg")
    interfaces=[]
    peers=0
    if installed:
        try:
            out=_run(["wg","show","interfaces"],timeout=5)
            interfaces=[x for x in out.split() if x]
            for iface in interfaces:
                dump=_run(["wg","show",iface,"dump"],timeout=5)
                lines=[x for x in dump.splitlines() if x.strip()]
                peers+=max(0,len(lines)-1)
        except Exception:
            pass
    runtime=_wireguard_server_config("wg0")
    return {
        "installed":installed,
        "service_active":_active("wg-quick@wg0"),
        "interfaces":interfaces,
        "peers":peers,
        "config":str(WG_DIR/"wg0.conf") if (WG_DIR/"wg0.conf").exists() else None,
        "port":runtime.get("port") or None,
        "address":runtime.get("address") or "",
    }

def openvpn_status():
    installed=_installed("openvpn")
    configs=[]
    server_dir=OVPN_DIR/"server"
    if server_dir.exists():
        configs=[p.stem for p in server_dir.glob("*.conf")]
    active=any(_active(f"openvpn-server@{name}") for name in configs)
    runtime=_openvpn_server_runtime() if (server_dir/"server.conf").exists() else {}
    return {
        "installed":installed,
        "service_active":active,
        "servers":configs,
        "config":str(server_dir/"server.conf") if (server_dir/"server.conf").exists() else None,
        "port":runtime.get("port"),"proto":runtime.get("proto"),
        "options":_openvpn_server_options() if (server_dir/"server.conf").exists() else {},
    }

def stunnel_status():
    return {
        "installed":_installed("stunnel4"),
        "service_active":_active("stunnel4"),
    }


def _listener_present(port, proto="tcp"):
    port=int(port or 0)
    proto=str(proto or "tcp").lower()
    if not port:
        return False

    ss=shutil.which("ss")
    if ss:
        flag="-ltn" if proto=="tcp" else "-lun"
        try:
            p=subprocess.run([ss,"-H",flag],text=True,capture_output=True,timeout=8,check=False)
            if p.returncode==0 and any(re.search(rf":{port}\\b",line) for line in (p.stdout or "").splitlines()):
                return True
        except (OSError,subprocess.TimeoutExpired):
            pass

    # Fallback for hardened/minimal hosts where ss is unavailable, delayed or
    # restricted. /proc/net exposes the kernel socket table directly.
    hex_port=f"{port:04X}"
    tables=("/proc/net/tcp","/proc/net/tcp6") if proto=="tcp" else ("/proc/net/udp","/proc/net/udp6")
    for table in tables:
        try:
            for line in Path(table).read_text(encoding="utf-8",errors="ignore").splitlines()[1:]:
                cols=line.split()
                if len(cols)<4:
                    continue
                local=cols[1]
                state=cols[3].upper()
                if ":" not in local:
                    continue
                _,phex=local.rsplit(":",1)
                if phex.upper()!=hex_port:
                    continue
                # TCP LISTEN = 0A. UDP sockets do not have an equivalent listen
                # state, so presence on the requested local port is sufficient.
                if proto!="tcp" or state=="0A":
                    return True
        except OSError:
            continue
    return False


def _wait_listener(port, proto="tcp", timeout=8.0, interval=0.25):
    deadline=time.monotonic()+max(0.0,float(timeout))
    while True:
        if _listener_present(port,proto):
            return True
        if time.monotonic()>=deadline:
            return False
        time.sleep(max(0.05,float(interval)))


def ikev2_status():
    installed=bool(shutil.which("ipsec"))
    active=_active("strongswan-starter") or _active("strongswan")
    configured=False
    users=0
    domain=""
    cidr=""
    if IKEV2_CONF.exists():
        text=IKEV2_CONF.read_text(encoding="utf-8",errors="ignore")
        configured="# BEGIN MAKIA IKEV2" in text
        m=re.search(r"(?m)^\s*leftid=(\S+)\s*$",text)
        if m: domain=m.group(1).lstrip("@")
        m=re.search(r"(?m)^\s*rightsourceip=(\S+)\s*$",text)
        if m: cidr=m.group(1)
    if IKEV2_SECRETS.exists():
        for line in IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore").splitlines():
            if "# makia-eap:" in line:
                users+=1
    return {
        "installed":installed,"configured":configured,"service_active":active,
        "listeners":{"500_udp":_listener_present(500,"udp"),"4500_udp":_listener_present(4500,"udp")},
        "domain":domain,"cidr":cidr,"users":users,
    }


def stealth_status():
    installed=_installed("stunnel4") or _installed("stunnel")
    active=_active("stunnel4")
    listen_port=None
    backend_port=None
    configured=STUNNEL_MAKIA_CONF.exists()
    if configured:
        text=STUNNEL_MAKIA_CONF.read_text(encoding="utf-8",errors="ignore")
        m=re.search(r"(?m)^\s*accept\s*=\s*(?:[^:]+:)?(\d+)\s*$",text)
        if m: listen_port=int(m.group(1))
        m=re.search(r"(?m)^\s*connect\s*=\s*(?:[^:]+:)?(\d+)\s*$",text)
        if m: backend_port=int(m.group(1))
    return {
        "installed":installed,"configured":configured,"service_active":active,
        "port":listen_port,"backend_port":backend_port,
        "listener":_listener_present(listen_port,"tcp") if listen_port else False,
    }


def wstunnel_status():
    installed=bool(shutil.which("wstunnel"))
    configured=WSTUNNEL_ENV.exists()
    active=_active(WSTUNNEL_SERVICE)
    data={}
    if configured:
        for line in WSTUNNEL_ENV.read_text(encoding="utf-8",errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k,v=line.split("=",1); data[k.strip()]=v.strip()
    try: listen_port=int(data.get("WSTUNNEL_LISTEN_PORT") or 0)
    except ValueError: listen_port=0
    try: target_port=int(data.get("WSTUNNEL_TARGET_PORT") or 0)
    except ValueError: target_port=0
    return {
        "installed":installed,"configured":configured,"service_active":active,
        "port":listen_port or None,"target_port":target_port or None,
        "path_prefix":data.get("WSTUNNEL_PATH_PREFIX",""),
        "listener":_listener_present(listen_port,"tcp") if listen_port else False,
    }


def _replace_managed_block(text, begin, end, body):
    text=str(text or "")
    pattern=re.compile(rf"(?ms)^\s*{re.escape(begin)}\s*$.*?^\s*{re.escape(end)}\s*$\n?")
    managed=f"{begin}\n{body.rstrip()}\n{end}\n"
    if pattern.search(text):
        return pattern.sub(managed,text,1)
    return text.rstrip()+"\n\n"+managed if text.strip() else managed


def bootstrap_ikev2(domain, cidr="10.77.0.0/24", dns="1.1.1.1"):
    if not shutil.which("ipsec"):
        raise ProtocolError("IKEv2/strongSwan tooling is not installed; run sudo makia-upgrade first")
    domain=validate_endpoint_selection(domain,"domain",direct=True)
    try:
        net=ipaddress.ip_network(cidr,strict=False)
    except Exception as exc:
        raise ProtocolError("invalid IKEv2 client CIDR") from exc
    if net.version!=4 or net.prefixlen<16 or net.prefixlen>29:
        raise ProtocolError("IKEv2 client CIDR must be IPv4 with prefix /16 to /29")
    try:
        dns_addr=ipaddress.ip_address(str(dns).strip())
    except ValueError as exc:
        raise ProtocolError("IKEv2 DNS must be an IP address") from exc
    if dns_addr.version!=4:
        raise ProtocolError("IKEv2 DNS must be IPv4")

    live=Path(f"/etc/letsencrypt/live/{domain}")
    cert,key,chain=live/"cert.pem",live/"privkey.pem",live/"chain.pem"
    if not cert.exists() or not key.exists() or not chain.exists():
        raise ProtocolError("IKEv2 requires the HTTPS/Let's Encrypt certificate for this domain first")

    backup_dir=_backup_dir()
    stamp=int(time.time())
    for src in (IKEV2_CONF,IKEV2_SECRETS):
        if src.exists():
            shutil.copy2(src,backup_dir/f"{src.name}.ikev2-{stamp}.bak")

    cert_out=Path("/etc/ipsec.d/certs/makia-ikev2.pem")
    key_out=Path("/etc/ipsec.d/private/makia-ikev2.key")
    ca_out=Path("/etc/ipsec.d/cacerts/makia-ikev2-chain.pem")
    cert_out.parent.mkdir(parents=True,exist_ok=True)
    key_out.parent.mkdir(parents=True,exist_ok=True)
    ca_out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(cert,cert_out); shutil.copyfile(key,key_out); shutil.copyfile(chain,ca_out)
    os.chmod(cert_out,0o644); os.chmod(ca_out,0o644); os.chmod(key_out,0o600)

    current=IKEV2_CONF.read_text(encoding="utf-8",errors="ignore") if IKEV2_CONF.exists() else "config setup\n    uniqueids=never\n"
    body=f"""conn makia-ikev2
    auto=add
    keyexchange=ikev2
    type=tunnel
    fragmentation=yes
    forceencaps=yes
    rekey=no
    dpdaction=clear
    dpddelay=300s
    left=%any
    leftid={domain}
    leftauth=pubkey
    leftcert=makia-ikev2.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0
    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip={net.with_prefixlen}
    rightdns={dns_addr.compressed}
    rightsendcert=never
    eap_identity=%identity
    ike=aes256-sha256-modp2048,aes128-sha256-modp2048!
    esp=aes256-sha256,aes128-sha256!"""
    IKEV2_CONF.write_text(_replace_managed_block(current,"# BEGIN MAKIA IKEV2","# END MAKIA IKEV2",body),encoding="utf-8")
    os.chmod(IKEV2_CONF,0o600)

    secret_text=IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore") if IKEV2_SECRETS.exists() else ""
    secret_body=": RSA makia-ikev2.key"
    IKEV2_SECRETS.write_text(_replace_managed_block(secret_text,"# BEGIN MAKIA IKEV2 SERVER","# END MAKIA IKEV2 SERVER",secret_body),encoding="utf-8")
    os.chmod(IKEV2_SECRETS,0o600)

    IKEV2_ENV.parent.mkdir(parents=True,exist_ok=True)
    IKEV2_ENV.write_text(f"MAKIA_IKEV2_CIDR={net.with_prefixlen}\n",encoding="utf-8")
    os.chmod(IKEV2_ENV,0o600)
    Path("/etc/sysctl.d/99-makia-ikev2.conf").write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
    _run(["sysctl","--system"],timeout=30)
    _run(["systemctl","daemon-reload"],timeout=20)
    _run(["systemctl","enable","--now","makia-ikev2-network"],timeout=30)
    service="strongswan-starter" if shutil.which("systemctl") else "strongswan"
    _run(["systemctl","enable","--now",service],timeout=60)
    _run(["systemctl","restart",service],timeout=60)
    _ufw_allow_if_active(500,"udp","IKEv2")
    _ufw_allow_if_active(4500,"udp","IKEv2 NAT-T")
    status=ikev2_status()
    if not status["service_active"]:
        raise ProtocolError("strongSwan did not become active after IKEv2 configuration")
    return {"ok":True,"domain":domain,"cidr":net.with_prefixlen,"dns":dns_addr.compressed,"status":status}


def create_ikev2_user(name, password=None):
    if not ikev2_status().get("configured"):
        raise ProtocolError("IKEv2 server is not configured")
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,48}",name):
        raise ProtocolError("IKEv2 username must be 3-48 characters: letters, numbers, dot, dash or underscore")
    password=str(password or secrets.token_urlsafe(18))
    if len(password)<10 or len(password)>128 or any(ch in password for ch in "\r\n\""):
        raise ProtocolError("IKEv2 password must be 10-128 characters and cannot contain quotes/newlines")
    text=IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore") if IKEV2_SECRETS.exists() else ""
    marker=re.compile(r"#\s*makia-eap:"+re.escape(name)+r"\s*$")
    lines=[line for line in text.splitlines() if not marker.search(line)]
    lines.append(f'{name} : EAP "{password}"  # makia-eap:{name}')
    IKEV2_SECRETS.write_text("\n".join(lines).rstrip()+"\n",encoding="utf-8")
    os.chmod(IKEV2_SECRETS,0o600)
    _run(["ipsec","rereadsecrets"],timeout=20)
    status=ikev2_status()
    profile=(
        f"Makia IKEv2\n"
        f"Server: {status.get('domain') or ''}\n"
        f"Remote ID: {status.get('domain') or ''}\n"
        f"Username: {name}\n"
        f"Password: {password}\n"
        "Authentication: Username / EAP-MSCHAPv2\n"
        "IKE version: IKEv2\n"
    )
    return {"ok":True,"name":name,"password":password,"server":status.get("domain") or "","profile":profile}


def list_ikev2_users():
    if not IKEV2_SECRETS.exists():
        return []
    out=[]
    pattern=re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*:\s*EAP\s+"[^"]*"\s*#\s*makia-eap:([A-Za-z0-9_.-]+)\s*$')
    for line in IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore").splitlines():
        m=pattern.match(line)
        if m and m.group(1)==m.group(2):
            out.append({"name":m.group(1)})
    return sorted(out,key=lambda item:item["name"].lower())


def remove_ikev2_user(name):
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,48}",name):
        raise ProtocolError("invalid IKEv2 username")
    if not IKEV2_SECRETS.exists():
        raise ProtocolError("IKEv2 secrets file is missing")
    text=IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore")
    marker=re.compile(r"#\s*makia-eap:"+re.escape(name)+r"\s*$")
    lines=text.splitlines()
    kept=[line for line in lines if not marker.search(line)]
    if len(kept)==len(lines):
        raise ProtocolError("IKEv2 user not found")
    IKEV2_SECRETS.write_text("\n".join(kept).rstrip()+"\n",encoding="utf-8")
    os.chmod(IKEV2_SECRETS,0o600)
    _run(["ipsec","rereadsecrets"],timeout=20)
    return {"ok":True,"name":name}


def bootstrap_stealth(domain, listen_port=9443):
    if not (_installed("stunnel4") or _installed("stunnel")):
        raise ProtocolError("Stunnel tooling is not installed; run sudo makia-upgrade first")
    domain=validate_endpoint_selection(domain,"domain",direct=True)
    listen_port=_validate_port(listen_port)
    fallback=_openvpn_named_runtime("makia-tcp")
    if not fallback.get("service_active") or not fallback.get("listener"):
        backend_port=_select_available_port_excluding(
            8443,"tcp",(10443,11940,12443),exclude_ports={listen_port}
        )
        fallback=ensure_openvpn_tcp_fallback(backend_port)["status"]
    backend_port=int(fallback.get("port") or 0)
    if listen_port==backend_port:
        raise ProtocolError(
            f"Stealth public TCP/{listen_port} conflicts with the active OpenVPN TCP backend. "
            "Choose a different public Stealth port; Makia will not move an active TCP backend silently."
        )
    existing=stealth_status()
    if _port_transport_in_use(listen_port,"tcp") and int(existing.get("port") or 0)!=listen_port:
        owner=_port_owner_label(listen_port,"tcp")
        suggestion=_suggest_free_port("tcp",(9443,10443,11443,12443),exclude_ports={backend_port})
        hint=f"; try TCP/{suggestion}" if suggestion else ""
        raise ProtocolError(f"TCP/{listen_port} is already owned by {owner}{hint}")
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    if not cert.exists() or not key.exists():
        raise ProtocolError("Stealth requires a valid HTTPS/Let's Encrypt certificate first")
    STUNNEL_MAKIA_CONF.parent.mkdir(parents=True,exist_ok=True)
    STUNNEL_MAKIA_CONF.write_text(
        "foreground = no\n"
        "client = no\n"
        "sslVersionMin = TLSv1.2\n"
        f"cert = {cert}\nkey = {key}\n\n"
        "[makia-openvpn]\n"
        f"accept = 0.0.0.0:{listen_port}\n"
        f"connect = 127.0.0.1:{backend_port}\n",
        encoding="utf-8",
    )
    defaults=Path("/etc/default/stunnel4")
    if defaults.exists():
        text=defaults.read_text(encoding="utf-8",errors="ignore")
        if re.search(r"(?m)^\s*ENABLED=",text):
            text=re.sub(r"(?m)^\s*ENABLED=.*$","ENABLED=1",text)
        else:
            text+="\nENABLED=1\n"
        defaults.write_text(text,encoding="utf-8")
    _run(["systemctl","enable","--now","stunnel4"],timeout=30)
    _run(["systemctl","restart","stunnel4"],timeout=30)
    _ufw_allow_if_active(listen_port,"tcp","OpenVPN Stealth")
    status=stealth_status()
    if not status.get("listener"):
        raise ProtocolError("Stunnel did not expose the requested TCP listener")
    client=(
        "client = yes\n"
        "foreground = yes\n"
        "verifyChain = yes\n"
        "checkHost = "+domain+"\n"
        "CAfile = /etc/ssl/certs/ca-certificates.crt\n\n"
        "[makia-openvpn]\n"
        "accept = 127.0.0.1:11940\n"
        f"connect = {domain}:{listen_port}\n"
    )
    return {"ok":True,"status":status,"domain":domain,"client_stunnel_config":client,"openvpn_local_endpoint":"127.0.0.1:11940"}


def bootstrap_wstunnel(domain, listen_port=8444, path_prefix=None):
    binary=shutil.which("wstunnel")
    if not binary:
        raise ProtocolError("WStunnel is not installed; run sudo makia-upgrade first")
    wg=wireguard_status()
    if not wg.get("service_active") or not wg.get("port"):
        raise ProtocolError("WStunnel mode requires an active WireGuard server")
    domain=validate_endpoint_selection(domain,"domain",direct=True)
    listen_port=_validate_port(listen_port)
    existing=wstunnel_status()
    if _port_transport_in_use(listen_port,"tcp") and int(existing.get("port") or 0)!=listen_port:
        raise ProtocolError(f"TCP/{listen_port} is already in use")
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    if not cert.exists() or not key.exists():
        raise ProtocolError("WStunnel WSS requires a valid HTTPS/Let's Encrypt certificate first")
    prefix=re.sub(r"[^A-Za-z0-9_-]","",str(path_prefix or "")) or secrets.token_urlsafe(18).replace("-","").replace("_","")
    if len(prefix)<12:
        raise ProtocolError("WStunnel path prefix must be at least 12 characters")
    WSTUNNEL_ENV.parent.mkdir(parents=True,exist_ok=True)
    WSTUNNEL_ENV.write_text(
        f"WSTUNNEL_LISTEN_PORT={listen_port}\n"
        f"WSTUNNEL_TARGET_PORT={int(wg['port'])}\n"
        f"WSTUNNEL_PATH_PREFIX={prefix}\n"
        f"WSTUNNEL_CERT={cert}\n"
        f"WSTUNNEL_KEY={key}\n",
        encoding="utf-8",
    )
    os.chmod(WSTUNNEL_ENV,0o600)
    _run(["systemctl","daemon-reload"],timeout=20)
    _run(["systemctl","enable","--now",WSTUNNEL_SERVICE],timeout=30)
    _run(["systemctl","restart",WSTUNNEL_SERVICE],timeout=30)
    _ufw_allow_if_active(listen_port,"tcp","WStunnel WSS")
    status=wstunnel_status()
    if not status.get("listener"):
        raise ProtocolError("WStunnel did not expose the requested TCP listener")
    local_port=int(wg.get("port") or 51820)
    command=(
        f"wstunnel client --http-upgrade-path-prefix {prefix} "
        f"-L 'udp://127.0.0.1:{local_port}:127.0.0.1:{int(wg['port'])}?timeout_sec=0' "
        f"wss://{domain}:{listen_port}"
    )
    return {
        "ok":True,"status":status,"domain":domain,"client_command":command,
        "wireguard_endpoint":f"127.0.0.1:{local_port}",
        "note":"Run the WStunnel client first, then use a WireGuard profile whose Endpoint points to the local UDP endpoint.",
    }


def protocol_modes():
    wg=wireguard_status()
    ov=_openvpn_server_runtime()
    ike=ikev2_status()
    st=stealth_status()
    ws=wstunnel_status()
    tcp=_openvpn_named_runtime("makia-tcp")
    return {
        "modes":[
            {"id":"ikev2","label":"IKEv2","ports":[500,4500],"transport":"UDP/IPsec","ready":bool(ike.get("configured") and ike.get("service_active")),"status":ike},
            {"id":"wireguard","label":"WireGuard","ports":[wg.get("port")] if wg.get("port") else [],"transport":"UDP","ready":bool(wg.get("service_active") and wg.get("config")),"status":wg},
            {"id":"udp","label":"UDP","ports":[ov.get("port")] if ov.get("port") and str(ov.get("proto") or "").startswith("udp") else [],"transport":"OpenVPN UDP","ready":bool(ov.get("service_active") and ov.get("listener") and str(ov.get("proto") or "").startswith("udp")),"status":ov},
            {"id":"tcp","label":"TCP","ports":[tcp.get("port")] if tcp.get("port") else ([ov.get("port")] if ov.get("port") and str(ov.get("proto") or "").startswith("tcp") else []),"transport":"OpenVPN TCP fallback","ready":bool((tcp.get("service_active") and tcp.get("listener")) or (ov.get("service_active") and ov.get("listener") and str(ov.get("proto") or "").startswith("tcp"))),"status":tcp if tcp.get("config") else ov},
            {"id":"stealth","label":"Stealth","ports":[st.get("port")] if st.get("port") else [],"transport":"OpenVPN over TLS/Stunnel","ready":bool(st.get("service_active") and st.get("listener")),"status":st},
            {"id":"wstunnel","label":"WStunnel","ports":[ws.get("port")] if ws.get("port") else [],"transport":"WireGuard over WSS","ready":bool(ws.get("service_active") and ws.get("listener")),"status":ws},
        ],
        "constraints":{
            "openvpn_primary_transport_switch":True,
            "tcp_fallback_parallel":True,
            "tcp_443_reserved_for_https":True,
            "note":"Primary OpenVPN can remain UDP while Makia runs a separate TCP fallback. Stealth reuses that TCP backend, so enabling it no longer disconnects UDP users.",
        },
        "port_plan":connection_port_plan(),
    }


def ssh_status():
    return {
        "installed":_installed("sshd") or _installed("ssh"),
        "service_active":_active("ssh") or _active("sshd"),
    }

def catalog():
    x=xray_status()
    wg=wireguard_status()
    ovpn=openvpn_status()
    st=stunnel_status()
    ssh=ssh_status()
    ike=ikev2_status()
    stealth=stealth_status()
    ws=wstunnel_status()
    return {
        "xray":x,
        "wireguard":wg,
        "openvpn":ovpn,
        "stunnel":st,
        "ikev2":ike,
        "stealth":stealth,
        "wstunnel":ws,
        "ssh":ssh,
        "capabilities":[
            {"id":"vless","engine":"xray","available":x["installed"]},
            {"id":"vmess","engine":"xray","available":x["installed"]},
            {"id":"trojan","engine":"xray","available":x["installed"]},
            {"id":"shadowsocks","engine":"xray","available":x["installed"]},
            {"id":"hysteria2","engine":"xray","available":x["installed"],"mode":"guided"},
            {"id":"http","engine":"xray","available":x["installed"],"mode":"guided"},
            {"id":"socks","engine":"xray","available":x["installed"],"mode":"guided"},
            {"id":"tunnel","engine":"xray","available":x["installed"],"mode":"guided"},
            {"id":"tun","engine":"xray","available":x["installed"],"mode":"advanced"},
            {"id":"wireguard","engine":"wireguard","available":wg["installed"],"mode":"guided"},
            {"id":"openvpn","engine":"openvpn","available":ovpn["installed"],"mode":"guided"},
            {"id":"ssh","engine":"openssh","available":ssh["installed"],"mode":"guided"},
            {"id":"stunnel","engine":"stunnel","available":st["installed"],"mode":"service"},
            {"id":"ikev2","engine":"strongswan","available":ike["installed"],"mode":"guided"},
            {"id":"stealth","engine":"stunnel","available":st["installed"],"mode":"guided"},
            {"id":"wstunnel","engine":"wstunnel","available":ws["installed"],"mode":"guided"},
            {"id":"tuic","engine":"external","available":False,"mode":"unavailable"},
            {"id":"amneziawg","engine":"external","available":False,"mode":"unavailable"},
            {"id":"mtproto","engine":"external","available":False,"mode":"unavailable"},
        ]
    }

def install_component(component):
    # Host package/service installation belongs to the root installer/updater.
    # The web backend intentionally runs with NoNewPrivileges and
    # RestrictSUIDSGID; invoking APT or upstream installers from that sandbox
    # can fail on privilege drops (for example _apt UID 42) and is not a safe
    # package-management boundary.
    if _process_no_new_privileges():
        raise ProtocolError("Host component installation is disabled inside the hardened web service; run sudo makia-upgrade")
    packages={
        "wireguard":["wireguard","iptables"],
        "openvpn":["openvpn","easy-rsa","iptables"],
        "stunnel":["stunnel4"],
    }
    if component=="xray":
        # Official XTLS installer. It installs the core + systemd service and
        # verifies the release artifacts handled by the upstream installer.
        _run(["bash","-lc",f'bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install --version {XRAY_VALIDATED_VERSION} -u nobody'],timeout=600)
        config=Path("/usr/local/etc/xray/config.json")
        config.parent.mkdir(parents=True,exist_ok=True)
        if not config.exists():
            config.write_text(json.dumps({
                "log":{"loglevel":"warning"},
                "inbounds":[],
                "outbounds":[{"protocol":"freedom","tag":"direct"}]
            },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            os.chmod(config,0o600)
        _xray_secure_runtime_file(config)
        _xray_test_config_as_service(_binary(),config)
        _run(["systemctl","enable","--now","xray"],timeout=60)
        return xray_status()
    if component not in packages:
        raise ProtocolError("automatic installation is not available for this component")
    _run(["apt-get","update"],timeout=180)
    _run(["apt-get","install","-y",*packages[component]],timeout=300)
    return catalog().get(component)

def _default_iface():
    out=_run(["ip","-4","route","show","default"],timeout=8)
    m=re.search(r"\bdev\s+(\S+)",out)
    if not m:
        raise ProtocolError("unable to detect default network interface")
    return m.group(1)

def _ufw_allow_if_active(port,proto,label):
    if not shutil.which("ufw"):
        return {"active":False,"changed":False}
    status=subprocess.run(["ufw","status"],text=True,capture_output=True,timeout=8,check=False)
    text=(status.stdout or status.stderr or "").lower()
    if status.returncode!=0 or "status: active" not in text:
        return {"active":False,"changed":False}
    rule=f"{int(port)}/{proto}"
    p=subprocess.run(["ufw","allow",rule,"comment",f"Makia {label}"],text=True,capture_output=True,timeout=15,check=False)
    if p.returncode!=0:
        raise ProtocolError((p.stderr or p.stdout or f"unable to allow {rule} in UFW").strip()[:600])
    return {"active":True,"changed":True,"rule":rule}

def _validate_port(port):
    port=int(port)
    if port<1 or port>65535:
        raise ProtocolError("invalid port")
    return port


def _validate_endpoint_host(value, label="endpoint"):
    raw=str(value or "").strip()
    if not raw or len(raw)>255:
        raise ProtocolError(f"invalid {label}")
    if "://" in raw or any(ch.isspace() for ch in raw) or any(ch in raw for ch in "/?#@"):
        raise ProtocolError(f"invalid {label}; enter only a hostname or IP address, without scheme, path or port")
    host=raw
    if host.startswith("[") and host.endswith("]"):
        host=host[1:-1].strip()
    try:
        ip=ipaddress.ip_address(host)
        return ip.compressed
    except ValueError:
        pass
    if host.endswith("."):
        host=host[:-1]
    try:
        ascii_host=host.encode("idna").decode("ascii")
    except Exception as exc:
        raise ProtocolError(f"invalid {label}") from exc
    if not ascii_host or len(ascii_host)>253:
        raise ProtocolError(f"invalid {label}")
    label_re=re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
    if any(not label_re.fullmatch(part) for part in ascii_host.split(".")):
        raise ProtocolError(f"invalid {label}")
    return ascii_host.lower()

def _uri_host(host):
    try:
        ip=ipaddress.ip_address(host)
        return f"[{ip.compressed}]" if ip.version==6 else ip.compressed
    except ValueError:
        return host

def validate_endpoint_selection(value, mode="auto", direct=False, check_aaaa=False):
    """Validate the address used in client exports before provisioning a service.

    Explicit domain mode checks IPv4 DNS. Direct TCP/UDP services additionally
    reject a known mismatch with a publicly assigned VPS IPv4. Xray transports
    may intentionally use a proxy, so their DNS is not required to match.
    """
    host=_validate_endpoint_host(value)
    mode=str(mode or "auto").lower()
    if mode not in {"auto","ip","domain"}:
        raise ProtocolError("endpoint mode must be IP or domain")
    try: address=ipaddress.ip_address(host)
    except ValueError: address=None
    if mode=="ip" and (address is None or address.version!=4):
        raise ProtocolError("IP mode requires a public IPv4 address")
    if mode=="domain" and address is not None:
        raise ProtocolError("Domain mode requires a hostname, not an IP address")
    if mode=="ip" and not address.is_global:
        raise ProtocolError("IP mode requires a public IPv4 address")
    if mode=="domain":
        try: resolved={row[4][0] for row in socket.getaddrinfo(host,None,socket.AF_INET)}
        except (OSError,ValueError): resolved=set()
        if not resolved:
            raise ProtocolError("Domain has no reachable A/IPv4 record")
        if direct:
            local={x for x in _local_ipv4_candidates() if ipaddress.ip_address(x).is_global}
            if local and not resolved.issubset(local):
                raise ProtocolError("Domain A record does not match this VPS public IPv4; disable HTTP/CDN proxy for this protocol")
        if check_aaaa:
            try:
                resolved6={str(ipaddress.IPv6Address(row[4][0].split("%",1)[0])) for row in socket.getaddrinfo(host,None,socket.AF_INET6)}
            except (OSError,ValueError): resolved6=set()
            if resolved6 and not resolved6.issubset(set(_local_ipv6_candidates())):
                raise ProtocolError("Domain AAAA record does not match a public VPS IPv6; use an A-only hostname or repair IPv6 routing")
    return host


def _endpoint_is_private(host):
    try:
        ip=ipaddress.ip_address(host)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        lowered=str(host or "").lower()
        return lowered=="localhost" or lowered.endswith(".local")

def _validate_wireguard_allowed_ips(value):
    raw=str(value or "0.0.0.0/0").strip()
    items=[x.strip() for x in raw.split(",") if x.strip()]
    if not items:
        raise ProtocolError("WireGuard AllowedIPs cannot be empty")
    normalized=[]
    for item in items:
        try:
            normalized.append(str(ipaddress.ip_network(item,strict=False)))
        except Exception as exc:
            raise ProtocolError(f"invalid WireGuard AllowedIPs entry: {item}") from exc
    return ", ".join(normalized)

def _validate_wireguard_mtu(value):
    mtu=int(value or 0)
    if mtu and (mtu<576 or mtu>1500):
        raise ProtocolError("WireGuard MTU must be 0 (auto) or between 576 and 1500")
    return mtu

def _validate_keepalive(value):
    keepalive=int(value or 0)
    if keepalive<0 or keepalive>3600:
        raise ProtocolError("WireGuard keepalive must be between 0 and 3600 seconds")
    return keepalive

def bootstrap_wireguard(port=51820, cidr="10.66.66.1/24", iface="wg0", mtu=0):
    if not re.fullmatch(r"wg\d{1,2}",iface):
        raise ProtocolError("invalid WireGuard interface name")
    _validate_port(port)
    mtu=_validate_wireguard_mtu(mtu)
    try:
        net=ipaddress.ip_interface(cidr)
    except Exception as exc:
        raise ProtocolError("invalid WireGuard CIDR") from exc
    if net.version!=4:
        raise ProtocolError("only IPv4 WireGuard bootstrap is supported in this release")
    if not _installed("wg"):
        install_component("wireguard")
    WG_DIR.mkdir(mode=0o700,parents=True,exist_ok=True)
    conf=WG_DIR/f"{iface}.conf"
    if conf.exists():
        raise ProtocolError(f"{conf} already exists")
    private=_run(["wg","genkey"])
    public=_run(["wg","pubkey"],input_text=private+"\n")
    uplink=_default_iface()
    conf.write_text(
        "[Interface]\n"
        f"Address = {net}\n"
        f"ListenPort = {int(port)}\n"
        f"PrivateKey = {private}\n"
        +(f"MTU = {mtu}\n" if mtu else "")
        +f"PostUp = iptables -C FORWARD -i {iface} -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i {iface} -j ACCEPT; iptables -C FORWARD -o {iface} -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o {iface} -j ACCEPT; iptables -t nat -C POSTROUTING -s {net.network} -o {uplink} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s {net.network} -o {uplink} -j MASQUERADE\n"
        f"PostDown = iptables -D FORWARD -i {iface} -j ACCEPT 2>/dev/null || true; iptables -D FORWARD -o {iface} -j ACCEPT 2>/dev/null || true; iptables -t nat -D POSTROUTING -s {net.network} -o {uplink} -j MASQUERADE 2>/dev/null || true\n",
        encoding="utf-8"
    )
    os.chmod(conf,0o600)
    Path("/etc/sysctl.d/99-makia-wireguard.conf").write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
    _run(["sysctl","--system"],timeout=30)
    _run(["systemctl","enable","--now",f"wg-quick@{iface}"],timeout=30)
    firewall=_ufw_allow_if_active(port,"udp","WireGuard")
    return {"interface":iface,"address":str(net),"port":int(port),"public_key":public,"mtu":mtu,"firewall":firewall}

def _wg_used_ips(iface):
    used=set()
    conf=WG_DIR/f"{iface}.conf"
    if conf.exists():
        text=conf.read_text(encoding="utf-8",errors="ignore")
        for m in re.finditer(r"AllowedIPs\s*=\s*([^\n#]+)",text):
            for item in m.group(1).split(","):
                item=item.strip()
                try:
                    used.add(str(ipaddress.ip_interface(item).ip))
                except Exception:
                    pass
    return used

def create_wireguard_peer(name, endpoint, iface="wg0", dns="1.1.1.1", mtu=1280, keepalive=15, allowed_ips="0.0.0.0/0"):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid peer name")
    endpoint=_validate_endpoint_host(endpoint)
    check=wireguard_endpoint_diagnostics(endpoint,iface)
    if not check["endpoint_ok"]:
        raise ProtocolError("WireGuard endpoint is not ready: "+"; ".join(check["warnings"]))
    mtu=_validate_wireguard_mtu(mtu)
    keepalive=_validate_keepalive(keepalive)
    allowed_ips=_validate_wireguard_allowed_ips(allowed_ips)
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        raise ProtocolError("WireGuard server is not bootstrapped")
    if any(peer["name"]==name for peer in list_wireguard_peers(iface)):
        raise ProtocolError("WireGuard peer name already exists")
    text=conf.read_text(encoding="utf-8",errors="ignore")
    m=re.search(r"Address\s*=\s*([^\n]+)",text)
    p=re.search(r"ListenPort\s*=\s*(\d+)",text)
    if not m or not p:
        raise ProtocolError("invalid WireGuard server config")
    server_if=ipaddress.ip_interface(m.group(1).strip())
    network=server_if.network
    used=_wg_used_ips(iface)|{str(server_if.ip)}
    client_ip=None
    for host in network.hosts():
        if str(host) not in used:
            client_ip=host
            break
    if client_ip is None:
        raise ProtocolError("WireGuard address pool exhausted")
    client_private=_run(["wg","genkey"])
    client_public=_run(["wg","pubkey"],input_text=client_private+"\n")
    server_public=_run(["wg","show",iface,"public-key"])
    block=f"\n# Makia peer: {name}\n[Peer]\nPublicKey = {client_public}\nAllowedIPs = {client_ip}/32\n"
    _run(["wg","set",iface,"peer",client_public,"allowed-ips",f"{client_ip}/32"])
    try:
        _write_wireguard_config(conf,text+block)
    except OSError as exc:
        try:
            _run(["wg","set",iface,"peer",client_public,"remove"])
        except ProtocolError as cleanup_exc:
            raise ProtocolError(f"WireGuard config save and runtime cleanup failed for {client_public}: {cleanup_exc}") from cleanup_exc
        raise ProtocolError(f"WireGuard peer config could not be saved: {exc}") from exc
    client=(
        "[Interface]\n"
        f"PrivateKey = {client_private}\n"
        f"Address = {client_ip}/32\n"
        f"DNS = {dns}\n"
        +(f"MTU = {mtu}\n" if mtu else "")
        +"\n[Peer]\n"
        f"PublicKey = {server_public}\n"
        f"Endpoint = {_uri_host(endpoint)}:{p.group(1)}\n"
        f"AllowedIPs = {allowed_ips}\n"
        f"PersistentKeepalive = {keepalive}\n"
    )
    return {"name":name,"address":str(client_ip),"public_key":client_public,"config":client,"endpoint":endpoint,"port":int(p.group(1)),"dns":dns,"mtu":mtu,"keepalive":keepalive,"allowed_ips":allowed_ips}

def list_wireguard_peers(iface="wg0"):
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        return []
    lines=conf.read_text(encoding="utf-8",errors="ignore").splitlines()
    peers=[]; current=None; pending_name=None; disabled=False
    for line in lines:
        stripped=line.strip()
        if stripped.startswith("# Makia peer:"):
            if current: peers.append(current)
            current=None
            pending_name=stripped.split(":",1)[1].strip()
            disabled=False
        elif stripped=="# Makia disabled" and pending_name:
            disabled=True
        elif stripped=="[Peer]" or (disabled and stripped=="# [Peer]"):
            if current: peers.append(current)
            is_disabled=(stripped=="# [Peer]")
            current={"name":pending_name or "wireguard-peer","public_key":"","allowed_ips":"","interface":iface,"enabled":not is_disabled}
            pending_name=None
            disabled=False
        elif current and "=" in stripped and (not stripped.startswith("#") or not current["enabled"]):
            if not current["enabled"]: stripped=stripped.removeprefix("# ")
            key,value=[x.strip() for x in stripped.split("=",1)]
            if key=="PublicKey": current["public_key"]=value
            elif key=="AllowedIPs": current["allowed_ips"]=value
    if current: peers.append(current)
    return [p for p in peers if p.get("public_key")]

def _write_wireguard_config(path, text):
    """Replace a wg-quick config without exposing a partially written peer block."""
    fd,temp=tempfile.mkstemp(prefix=".makia-wg-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            os.fchmod(fh.fileno(),0o600)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def set_wireguard_peer_enabled(name, enabled, iface="wg0"):
    """Persistently toggle only Makia-owned canonical peer blocks, then update wg."""
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        raise ProtocolError("WireGuard server config not found")
    peer=next((p for p in list_wireguard_peers(iface) if p["name"]==name),None)
    if not peer or not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name):
        raise ProtocolError("Makia WireGuard peer not found")
    enabled=bool(enabled)
    if peer["enabled"]==enabled:
        return peer
    key=peer["public_key"]
    address=peer["allowed_ips"]
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{20,100}",key) or not re.fullmatch(r"[0-9./]+",address):
        raise ProtocolError("Unsupported WireGuard peer block")
    active=f"# Makia peer: {name}\n[Peer]\nPublicKey = {key}\nAllowedIPs = {address}\n"
    inactive=f"# Makia peer: {name}\n# Makia disabled\n# [Peer]\n# PublicKey = {key}\n# AllowedIPs = {address}\n"
    before=conf.read_text(encoding="utf-8")
    old,new=(inactive,active) if enabled else (active,inactive)
    if before.count(old)!=1:
        raise ProtocolError("WireGuard peer block differs from Makia format; no changes applied")
    updated=before.replace(old,new,1)
    try:
        _write_wireguard_config(conf,updated)
        command=["wg","set",iface,"peer",key,"allowed-ips",address] if enabled else ["wg","set",iface,"peer",key,"remove"]
        _run(command)
    except (OSError,ProtocolError) as exc:
        _write_wireguard_config(conf,before)
        raise ProtocolError(f"WireGuard peer state update failed; config restored: {exc}") from exc
    return {**peer,"enabled":enabled}

def remove_wireguard_peer(public_key, iface="wg0"):
    public_key=str(public_key or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{20,100}",public_key):
        raise ProtocolError("invalid WireGuard public key")
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        raise ProtocolError("WireGuard server config not found")
    disabled=next((p for p in list_wireguard_peers(iface) if p["public_key"]==public_key and not p["enabled"]),None)
    if disabled:
        text=conf.read_text(encoding="utf-8")
        block=(f"# Makia peer: {disabled['name']}\n# Makia disabled\n# [Peer]\n"
               f"# PublicKey = {public_key}\n# AllowedIPs = {disabled['allowed_ips']}\n")
        if text.count(block)!=1:
            raise ProtocolError("WireGuard disabled peer block differs from Makia format")
        _write_wireguard_config(conf,text.replace(block,"",1))
        return {"removed":True,"public_key":public_key,"interface":iface}
    before=conf.read_text(encoding="utf-8",errors="ignore")
    if f"PublicKey = {public_key}" not in before:
        raise ProtocolError("WireGuard public key not found in server config")
    lines=before.splitlines()
    out=[]; block=[]; in_peer=False
    for line in lines+["[__END__]"]:
        if line.startswith("[") and line.endswith("]"):
            if in_peer:
                text="\n".join(block)
                if f"PublicKey = {public_key}" not in text:
                    out.extend(block)
                block=[]
            in_peer=(line=="[Peer]")
            if line!="[__END__]":
                block=[line] if in_peer else []
                if not in_peer:
                    out.append(line)
        elif in_peer:
            block.append(line)
        else:
            out.append(line)
    # Remove a Makia comment immediately before a removed peer if it became orphaned.
    cleaned=[]
    for idx,line in enumerate(out):
        if line.startswith("# Makia peer:") and idx+1<len(out) and out[idx+1]!="[Peer]":
            continue
        cleaned.append(line)
    after="\n".join(cleaned).rstrip()+"\n"
    if after==before:
        raise ProtocolError("WireGuard public key not found in server config")
    _write_wireguard_config(conf,after)
    try:
        _run(["wg","set",iface,"peer",public_key,"remove"])
    except ProtocolError:
        _write_wireguard_config(conf,before)
        raise
    return {"removed":True,"public_key":public_key,"interface":iface}

def _wireguard_server_config(iface="wg0"):
    conf=WG_DIR/f"{iface}.conf"
    result={"config":str(conf),"exists":conf.exists(),"address":"","port":0,"mtu":0,"network":"","uplink":""}
    if not conf.exists():
        return result
    text=conf.read_text(encoding="utf-8",errors="ignore")
    address_m=re.search(r"(?m)^Address\s*=\s*([^\n#]+)",text)
    port_m=re.search(r"(?m)^ListenPort\s*=\s*(\d+)",text)
    mtu_m=re.search(r"(?m)^MTU\s*=\s*(\d+)",text)
    if address_m:
        try:
            interface=ipaddress.ip_interface(address_m.group(1).strip())
            result["address"]=str(interface)
            result["network"]=str(interface.network)
        except Exception:
            result["address"]=address_m.group(1).strip()
    if port_m:
        result["port"]=int(port_m.group(1))
    if mtu_m:
        result["mtu"]=int(mtu_m.group(1))
    try:
        result["uplink"]=_default_iface()
    except Exception:
        result["uplink"]=""
    return result

def _wireguard_udp_listener(port):
    if not port or not shutil.which("ss"):
        return False
    p=subprocess.run(["ss","-H","-lun"],text=True,capture_output=True,timeout=8,check=False)
    if p.returncode!=0:
        return False
    return any(re.search(rf":{int(port)}\b",line) for line in (p.stdout or "").splitlines())

def _iptables_check(args):
    if not shutil.which("iptables"):
        return None
    p=subprocess.run(["iptables",*args],text=True,capture_output=True,timeout=8,check=False)
    return p.returncode==0

def _wireguard_peer_runtime(iface="wg0"):
    peers=[]
    if not _installed("wg"):
        return peers
    try:
        latest={}
        for line in _run(["wg","show",iface,"latest-handshakes"],timeout=5).splitlines():
            cols=line.split()
            if len(cols)>=2:
                latest[cols[0]]=int(cols[1] or 0)
        transfers={}
        for line in _run(["wg","show",iface,"transfer"],timeout=5).splitlines():
            cols=line.split()
            if len(cols)>=3:
                transfers[cols[0]]={"rx":int(cols[1] or 0),"tx":int(cols[2] or 0)}
        now_ts=int(time.time())
        for peer in list_wireguard_peers(iface):
            key=peer.get("public_key","")
            ts=int(latest.get(key) or 0)
            age=(now_ts-ts) if ts else None
            tr=transfers.get(key,{"rx":0,"tx":0})
            peers.append({**peer,"latest_handshake":ts,"handshake_age":age,"rx":tr["rx"],"tx":tr["tx"]})
    except Exception:
        pass
    return peers

def wireguard_endpoint_diagnostics(endpoint="",iface="wg0"):
    endpoint=str(endpoint or "").strip()
    cfg=_wireguard_server_config(iface)
    service_active=_active(f"wg-quick@{iface}")
    interfaces=[]
    try:
        interfaces=[x for x in _run(["wg","show","interfaces"],timeout=5).split() if x]
    except Exception:
        interfaces=[]
    interface_present=iface in interfaces
    ip_forward=False
    try:
        ip_forward=Path("/proc/sys/net/ipv4/ip_forward").read_text(encoding="utf-8").strip()=="1"
    except Exception:
        pass
    listener=_wireguard_udp_listener(cfg.get("port"))
    uplink=cfg.get("uplink") or ""
    network=cfg.get("network") or ""
    forward_in=_iptables_check(["-C","FORWARD","-i",iface,"-j","ACCEPT"])
    forward_out=_iptables_check(["-C","FORWARD","-o",iface,"-j","ACCEPT"])
    nat=None
    if network and uplink:
        nat=_iptables_check(["-t","nat","-C","POSTROUTING","-s",network,"-o",uplink,"-j","MASQUERADE"])
        if nat is False:
            # Historical Makia configs used a broad MASQUERADE rule without -s.
            nat=_iptables_check(["-t","nat","-C","POSTROUTING","-o",uplink,"-j","MASQUERADE"])
    resolved4=[]; resolved6=[]; endpoint_is_ip=False; ip_version=None; dns_matches_server=None
    local6=_local_ipv6_candidates()
    ipv6_matches_server=None
    warnings=[]
    if endpoint:
        endpoint=_validate_endpoint_host(endpoint,"WireGuard endpoint")
        try:
            parsed=ipaddress.ip_address(endpoint)
            endpoint_is_ip=True; ip_version=parsed.version
            if parsed.version==4: resolved4=[parsed.compressed]
            else: resolved6=[parsed.compressed]
        except ValueError:
            try: resolved4=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET)})
            except Exception: resolved4=[]
            try: resolved6=sorted({str(ipaddress.IPv6Address(x[4][0].split("%",1)[0])) for x in socket.getaddrinfo(endpoint,None,socket.AF_INET6)})
            except Exception: resolved6=[]
        local4=_local_ipv4_candidates()
        if not endpoint_is_ip:
            public_local4=[x for x in local4 if ipaddress.ip_address(x).is_global]
            dns_matches_server=set(resolved4).issubset(set(public_local4)) if resolved4 and public_local4 else None
            ipv6_matches_server=set(resolved6).issubset(set(local6)) if resolved6 and local6 else None
            if not resolved4:
                warnings.append("دامنه WireGuard رکورد A/IPv4 قابل استفاده ندارد.")
            if resolved6:
                if ipv6_matches_server is not True:
                    warnings.append("دامنه AAAA هم دارد، اما IPv6 عمومی مطابق با VPS تأیید نشد. کلاینت WireGuard ممکن است این مسیر را انتخاب کند؛ از زیر دامنه A-only استفاده کنید یا مسیر IPv6/UDP را جداگانه تأیید کنید.")
                else:
                    warnings.append("دامنه AAAA مطابق IPv6 محلی دارد؛ دسترسی UDP از بیرون و فایروال IPv6 هنوز باید با Client واقعی تأیید شود.")
            if dns_matches_server is False:
                warnings.append("رکورد A دامنه با IPv4 این VPS تطابق ندارد. WireGuard خام از HTTP/CDN Proxy عبور نمی‌کند؛ رکورد باید DNS-only و مستقیم به VPS باشد.")
            if dns_matches_server is None and resolved4:
                warnings.append("IPv4 عمومی VPS از این سرور قابل تأیید نیست (احتمال NAT). رکورد A را با Public IP پنل VPS مقایسه کنید؛ این نتیجه اتصال را تأیید نمی‌کند.")
        elif ip_version!=4:
            warnings.append("Bootstrap فعلی WireGuard سرور IPv4-only است؛ Endpoint IPv6 برای این Runtime توصیه نمی‌شود.")
    else:
        local4=_local_ipv4_candidates()
    public_local4=[x for x in local4 if ipaddress.ip_address(x).is_global]
    if endpoint_is_ip and ip_version==4 and public_local4 and endpoint not in public_local4:
        warnings.append("IPv4 انتخاب‌شده با IPv4 عمومی این VPS تطابق ندارد.")
    if not cfg.get("exists"): warnings.append("فایل wg0.conf وجود ندارد.")
    if not service_active: warnings.append("سرویس wg-quick@wg0 فعال نیست.")
    if not interface_present: warnings.append("Interface wg0 در runtime دیده نمی‌شود.")
    if not listener and cfg.get("port"): warnings.append(f"UDP listener روی Port {cfg.get('port')} دیده نشد.")
    if not ip_forward: warnings.append("net.ipv4.ip_forward فعال نیست.")
    if forward_in is False or forward_out is False: warnings.append("Forwarding ruleهای WireGuard در iptables کامل نیستند.")
    if nat is False: warnings.append("NAT/MASQUERADE برای شبکه WireGuard روی uplink پیدا نشد.")
    peers=_wireguard_peer_runtime(iface)
    recent=sum(1 for p in peers if p.get("handshake_age") is not None and int(p["handshake_age"])<=180)
    if any(p.get("enabled",True) for p in peers) and recent==0:
        warnings.append("هیچ Handshake تازه‌ای از Peerها دیده نشده است. اگر Client در حال تلاش برای اتصال است، علاوه بر Endpoint/Key، احتمال مسدودبودن UDP در فایروال دیتاسنتر، NAT بالادست یا شبکه/ISP را بررسی کنید؛ سلامت سمت سرور به‌تنهایی دسترسی UDP از اینترنت را اثبات نمی‌کند.")
    endpoint_ok=True
    if endpoint:
        endpoint_ok=bool(
            (endpoint_is_ip and ip_version==4 and (not public_local4 or endpoint in public_local4)) or
            ((not endpoint_is_ip) and resolved4 and dns_matches_server is not False and (not resolved6 or ipv6_matches_server is True))
        )
    runtime_ok=bool(cfg.get("exists") and service_active and interface_present and listener and ip_forward and forward_in is not False and forward_out is not False and nat is not False)
    return {
        "ok":bool(runtime_ok and endpoint_ok),
        "runtime_ok":runtime_ok,
        "endpoint_ok":endpoint_ok,
        "interface":iface,
        "config":cfg.get("config"),
        "address":cfg.get("address"),
        "network":network,
        "port":cfg.get("port"),
        "mtu":cfg.get("mtu"),
        "uplink":uplink,
        "service_active":service_active,
        "interface_present":interface_present,
        "listener":listener,
        "ip_forward":ip_forward,
        "forward_in":forward_in,
        "forward_out":forward_out,
        "nat":nat,
        "endpoint":endpoint,
        "endpoint_is_ip":endpoint_is_ip,
        "endpoint_ip_version":ip_version,
        "resolved_ipv4":resolved4,
        "resolved_ipv6":resolved6,
        "local_ipv4":local4,
        "local_ipv6":local6,
        "dns_matches_server":dns_matches_server,
        "ipv6_matches_server":ipv6_matches_server,
        "peers":peers,
        "recent_handshakes":recent,
        "external_udp_verified":False,
        "external_udp_note":"برای اثبات دسترسی UDP باید Handshake واقعی از Client خارج VPS دیده شود؛ Diagnostics سمت سرور نمی‌تواند فیلترینگ اپراتور/کشور یا فایروال بالادست را به‌تنهایی رد کند.",
        "warnings":warnings,
    }

def _wireguard_set_interface_directive(config_text,key,value_line):
    """Replace or insert an Interface directive without ever appending it inside a Peer block."""
    pattern=rf"(?m)^{re.escape(key)}\s*=.*$"
    if re.search(pattern,config_text):
        return re.sub(pattern,value_line,config_text,count=1)
    peer=re.search(r"(?m)^\[Peer\]\s*$",config_text)
    insert_at=peer.start() if peer else len(config_text)
    head=config_text[:insert_at].rstrip()
    tail=config_text[insert_at:].lstrip("\n")
    merged=head+"\n"+value_line+"\n"
    if tail:
        merged+="\n"+tail
    return merged

def repair_wireguard_runtime(iface="wg0"):
    if not re.fullmatch(r"wg\d{1,2}",iface):
        raise ProtocolError("invalid WireGuard interface name")
    cfg=_wireguard_server_config(iface)
    conf=Path(cfg["config"])
    if not conf.exists():
        raise ProtocolError("WireGuard server config is not available")
    if not cfg.get("port") or not cfg.get("network"):
        raise ProtocolError("WireGuard config is missing Address or ListenPort")
    uplink=_default_iface()
    original=conf.read_text(encoding="utf-8",errors="ignore")
    backup_dir=_backup_dir()
    backup=backup_dir/f"wireguard-repair-{int(time.time())}.conf"
    shutil.copy2(conf,backup)
    network=cfg["network"]
    post_up=(
        f"PostUp = iptables -C FORWARD -i {iface} -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i {iface} -j ACCEPT; "
        f"iptables -C FORWARD -o {iface} -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o {iface} -j ACCEPT; "
        f"iptables -t nat -C POSTROUTING -s {network} -o {uplink} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s {network} -o {uplink} -j MASQUERADE"
    )
    post_down=(
        f"PostDown = iptables -D FORWARD -i {iface} -j ACCEPT 2>/dev/null || true; "
        f"iptables -D FORWARD -o {iface} -j ACCEPT 2>/dev/null || true; "
        f"iptables -t nat -D POSTROUTING -s {network} -o {uplink} -j MASQUERADE 2>/dev/null || true"
    )
    updated=_wireguard_set_interface_directive(original,"PostUp",post_up)
    updated=_wireguard_set_interface_directive(updated,"PostDown",post_down)
    sysctl_dir=Path(os.getenv("MAKIA_SYSCTL_DIR","/etc/sysctl.d"))
    sysctl_dir.mkdir(parents=True,exist_ok=True)
    sysctl=sysctl_dir/"99-makia-wireguard.conf"
    sysctl_existed=sysctl.exists()
    sysctl_previous=sysctl.read_bytes() if sysctl_existed else b""
    try:
        conf.write_text(updated.rstrip()+"\n",encoding="utf-8")
        os.chmod(conf,0o600)
        sysctl.write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
        _run(["sysctl","-w","net.ipv4.ip_forward=1"],timeout=10)
        _ufw_allow_if_active(cfg["port"],"udp","WireGuard")
        _run(["systemctl","enable",f"wg-quick@{iface}"],timeout=20)
        _run(["systemctl","restart",f"wg-quick@{iface}"],timeout=30)
        diagnostics=wireguard_endpoint_diagnostics("",iface)
        if not diagnostics.get("runtime_ok"):
            raise ProtocolError("WireGuard runtime remains unhealthy after repair: "+"; ".join(diagnostics.get("warnings") or []))
    except Exception:
        try:
            shutil.copy2(backup,conf)
            os.chmod(conf,0o600)
            if sysctl_existed:
                sysctl.write_bytes(sysctl_previous)
            elif sysctl.exists():
                sysctl.unlink()
            _run(["systemctl","restart",f"wg-quick@{iface}"],timeout=30)
        except Exception:
            pass
        raise
    return {"ok":True,"backup":str(backup),"diagnostics":wireguard_endpoint_diagnostics("",iface)}

def protocol_endpoint_matrix(endpoint):
    endpoint=_validate_endpoint_host(endpoint,"public endpoint")
    local4=_local_ipv4_candidates()
    try:
        parsed=ipaddress.ip_address(endpoint)
        is_ip=True
        resolved4=[parsed.compressed] if parsed.version==4 else []
        resolved6=[parsed.compressed] if parsed.version==6 else []
    except ValueError:
        is_ip=False
        try: resolved4=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET)})
        except Exception: resolved4=[]
        try: resolved6=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET6)})
        except Exception: resolved6=[]
    dns_match=True if is_ip else (bool(set(resolved4)&set(local4)) if resolved4 and local4 else None)
    x=xray_status()
    wg=wireguard_endpoint_diagnostics(endpoint) if (WG_DIR/"wg0.conf").exists() else {"ok":False,"runtime_ok":False,"warnings":["WireGuard server not bootstrapped"]}
    ov=openvpn_endpoint_diagnostics(endpoint) if (OVPN_DIR/"server/server.conf").exists() else {"ok":False,"warnings":["OpenVPN server not bootstrapped"]}
    ssh=ssh_status()
    x_ports=[int(i.get("port")) for i in (x.get("inbounds") or []) if i.get("port")]
    rows=[
        {"id":"ssh","label":"SSH","transport":"TCP","ports":[22],"runtime":bool(ssh.get("service_active")),"endpoint_ok":bool(is_ip or (resolved4 and dns_match is not False))},
        {"id":"xray","label":"Xray","transport":"TCP/UDP by inbound","ports":x_ports,"runtime":bool(x.get("service_active") and x_ports),"endpoint_ok":bool(is_ip or (resolved4 and dns_match is not False))},
        {"id":"wireguard","label":"WireGuard","transport":"UDP","ports":[wg.get("port")] if wg.get("port") else [],"runtime":bool(wg.get("runtime_ok")),"endpoint_ok":bool(wg.get("endpoint_ok",False))},
        {"id":"openvpn","label":"OpenVPN","transport":str(ov.get("proto") or "").upper(),"ports":[ov.get("port")] if ov.get("port") else [],"runtime":bool(ov.get("service_active") and ov.get("listener")),"endpoint_ok":bool(ov.get("endpoint_is_ip") or (ov.get("resolved_ipv4") and ov.get("dns_matches_server") is not False))},
    ]
    for row in rows:
        row["ready"]=bool(row["runtime"] and row["endpoint_ok"])
    return {
        "endpoint":endpoint,"endpoint_is_ip":is_ip,"resolved_ipv4":resolved4,"resolved_ipv6":resolved6,
        "local_ipv4":local4,"dns_matches_server":dns_match,
        "rows":rows,"all_ready":all(r["ready"] for r in rows),
        "wireguard":wg,"openvpn":ov,
        "note":"این تست Readiness سمت سرور، DNS و Listener را بررسی می‌کند؛ تأیید نهایی اتصال از اینترنت باید با Client واقعی خارج از VPS انجام شود."
    }

def _openvpn_proto(proto,server=False):
    proto=str(proto or "udp").strip().lower()
    if proto in {"udp","udp4"}:
        return "udp4"
    if proto in {"tcp","tcp4","tcp-client","tcp4-client","tcp-server","tcp4-server"}:
        return "tcp4-server" if server else "tcp4-client"
    raise ProtocolError("invalid OpenVPN protocol")

def _local_ipv4_candidates():
    found=set()
    try:
        out=_run(["ip","-4","addr","show","scope","global"],timeout=8)
        for item in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/",out):
            try: found.add(str(ipaddress.ip_address(item)))
            except ValueError: pass
    except Exception:
        pass
    try:
        out=_run(["ip","-4","route","get","1.1.1.1"],timeout=8)
        m=re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)",out)
        if m: found.add(str(ipaddress.ip_address(m.group(1))))
    except Exception:
        pass
    return sorted(found)

def _local_ipv6_candidates():
    found=set()
    try:
        out=_run(["ip","-6","addr","show","scope","global"],timeout=8)
        for item in re.findall(r"\binet6\s+([0-9a-fA-F:]+)/",out):
            addr=ipaddress.IPv6Address(item)
            if addr.is_global: found.add(addr.compressed)
    except Exception:
        pass
    return sorted(found)

def _openvpn_named_runtime(stem):
    conf=OVPN_DIR/"server"/f"{stem}.conf"
    service=f"openvpn-server@{stem}"
    result={"config":str(conf),"port":None,"proto":None,"service_active":_active(service),"listener":False,"service":service}
    if conf.exists():
        text=conf.read_text(encoding="utf-8",errors="ignore")
        pm=re.search(r"(?m)^port\s+(\d+)\s*$",text)
        proto_m=re.search(r"(?m)^proto\s+(\S+)\s*$",text)
        result["port"]=int(pm.group(1)) if pm else None
        result["proto"]=(proto_m.group(1) if proto_m else "").lower()
    if result["port"] and shutil.which("ss"):
        flag="-ltn" if str(result["proto"]).startswith("tcp") else "-lun"
        p=subprocess.run(["ss","-H",flag],text=True,capture_output=True,timeout=8,check=False)
        if p.returncode==0:
            result["listener"]=any(re.search(rf":{int(result['port'])}\b",line) for line in (p.stdout or "").splitlines())
    return result


def _openvpn_aux_forward_scripts(stem,network):
    uplink=_default_iface()
    up=OVPN_DIR/f"makia-{stem}-up.sh"
    down=OVPN_DIR/f"makia-{stem}-down.sh"
    up.write_text(
        "#!/bin/sh\n"
        'iptables -C FORWARD -i "$dev" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i "$dev" -j ACCEPT\n'
        'iptables -C FORWARD -o "$dev" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o "$dev" -j ACCEPT\n'
        f"iptables -t nat -C POSTROUTING -s {network} -o {uplink} -j MASQUERADE 2>/dev/null || "
        f"iptables -t nat -A POSTROUTING -s {network} -o {uplink} -j MASQUERADE\n",
        encoding="utf-8",
    )
    down.write_text(
        "#!/bin/sh\n"
        'iptables -D FORWARD -i "$dev" -j ACCEPT 2>/dev/null || true\n'
        'iptables -D FORWARD -o "$dev" -j ACCEPT 2>/dev/null || true\n'
        f"iptables -t nat -D POSTROUTING -s {network} -o {uplink} -j MASQUERADE 2>/dev/null || true\n",
        encoding="utf-8",
    )
    os.chmod(up,0o700); os.chmod(down,0o700)
    return up,down


def ensure_openvpn_tcp_fallback(port=8443):
    """Run a parallel TCP OpenVPN listener without changing the primary UDP server."""
    port=_validate_port(port)
    server_dir=OVPN_DIR/"server"
    required=[server_dir/"ca.crt",server_dir/"server.crt",server_dir/"server.key",server_dir/"dh.pem",server_dir/"crl.pem",server_dir/"ta.key"]
    missing=[p.name for p in required if not p.exists()]
    if missing:
        raise ProtocolError(
            "OpenVPN TCP fallback requires the existing OpenVPN PKI; missing: "
            +", ".join(missing)
        )

    current=_openvpn_named_runtime("makia-tcp")
    same_configured=int(current.get("port") or 0)==port and Path(current.get("config") or "").exists()
    if _port_transport_in_use(port,"tcp") and not (same_configured and current.get("listener")):
        owner=_port_owner_label(port,"tcp")
        suggestion=_suggest_free_port("tcp",(8443,10443,11940,12443),exclude_ports={port})
        hint=f"; try TCP/{suggestion}" if suggestion else ""
        raise ProtocolError(f"TCP/{port} is already owned by {owner}{hint}")

    network="10.9.0.0/24"
    conf=OVPN_TCP_FALLBACK_CONF
    backup_dir=_backup_dir()
    stamp=f"{int(time.time())}-{secrets.token_hex(3)}"
    backups={}
    for path in [conf,OVPN_DIR/"makia-tcp-up.sh",OVPN_DIR/"makia-tcp-down.sh"]:
        if path.exists():
            target=backup_dir/f"{path.name}.{stamp}.bak"
            shutil.copy2(path,target)
            backups[path]=target

    try:
        up,down=_openvpn_aux_forward_scripts("tcp",network)
        conf.parent.mkdir(parents=True,exist_ok=True)
        conf.write_text(
            f"port {port}\nproto tcp4-server\nlocal 0.0.0.0\ndev tun-tcp\n"
            "topology subnet\nserver 10.9.0.0 255.255.255.0\n"
            f"ca {server_dir/'ca.crt'}\ncert {server_dir/'server.crt'}\nkey {server_dir/'server.key'}\n"
            f"dh {server_dir/'dh.pem'}\ncrl-verify {server_dir/'crl.pem'}\ntls-crypt {server_dir/'ta.key'}\n"
            'push "redirect-gateway def1 bypass-dhcp"\n'
            'push "dhcp-option DNS 1.1.1.1"\npush "dhcp-option DNS 8.8.8.8"\n'
            "keepalive 10 120\npersist-key\npersist-tun\nuser nobody\ngroup nogroup\n"
            "data-ciphers AES-256-GCM:AES-128-GCM\ndata-ciphers-fallback AES-256-GCM\nauth SHA256\nverb 3\n"
            f"script-security 2\nup {up}\ndown {down}\n",
            encoding="utf-8",
        )
        os.chmod(conf,0o600)
        sysctl_dir=Path(os.getenv("MAKIA_SYSCTL_DIR","/etc/sysctl.d"))
        sysctl_dir.mkdir(parents=True,exist_ok=True)
        (sysctl_dir/"99-makia-openvpn.conf").write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
        _run(["sysctl","-w","net.ipv4.ip_forward=1"],timeout=10)
        _run(["systemctl","enable","--now",OVPN_TCP_FALLBACK_SERVICE],timeout=30)
        _run(["systemctl","restart",OVPN_TCP_FALLBACK_SERVICE],timeout=30)
        _ufw_allow_if_active(port,"tcp","OpenVPN TCP fallback")
        status=_openvpn_named_runtime("makia-tcp")
        if not status.get("service_active") or not status.get("listener"):
            raise ProtocolError("OpenVPN TCP fallback service started but no TCP listener was detected")
        return {"ok":True,"status":status,"port":port,"proto":"tcp"}
    except Exception:
        for path in [conf,OVPN_DIR/"makia-tcp-up.sh",OVPN_DIR/"makia-tcp-down.sh"]:
            backup=backups.get(path)
            try:
                if backup and backup.exists():
                    shutil.copy2(backup,path)
                elif path.exists() and path not in backups:
                    path.unlink()
            except OSError:
                pass
        if current.get("config") and Path(current.get("config") or "").exists():
            try:
                _run(["systemctl","restart",OVPN_TCP_FALLBACK_SERVICE],timeout=30)
            except Exception:
                pass
        else:
            subprocess.run(["systemctl","stop",OVPN_TCP_FALLBACK_SERVICE],capture_output=True,text=True,check=False)
        raise


def _openvpn_server_runtime():
    server_conf=OVPN_DIR/"server/server.conf"
    result={"config":str(server_conf),"port":None,"proto":None,"service_active":_active("openvpn-server@server"),"listener":False}
    if server_conf.exists():
        text=server_conf.read_text(encoding="utf-8",errors="ignore")
        pm=re.search(r"(?m)^port\s+(\d+)\s*$",text)
        proto_m=re.search(r"(?m)^proto\s+(\S+)\s*$",text)
        result["port"]=int(pm.group(1)) if pm else 1194
        result["proto"]=(proto_m.group(1) if proto_m else "udp4").lower()
    if result["port"] and shutil.which("ss"):
        p=subprocess.run(["ss","-H","-lntu"],text=True,capture_output=True,timeout=8,check=False)
        if p.returncode==0:
            wanted=str(result["port"])
            for line in (p.stdout or "").splitlines():
                if re.search(rf":{re.escape(wanted)}\b",line):
                    kind=line.split(None,1)[0].lower() if line.split() else ""
                    if (str(result["proto"]).startswith("udp") and kind=="udp") or (str(result["proto"]).startswith("tcp") and kind=="tcp"):
                        result["listener"]=True
                        break
    return result

def _openvpn_forward_scripts(uplink):
    """Permit tunnel routing even when the host firewall denies forwarded packets."""
    up=OVPN_DIR/"makia-up.sh"
    down=OVPN_DIR/"makia-down.sh"
    up.write_text(
        "#!/bin/sh\n"
        'iptables -C FORWARD -i "$dev" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i "$dev" -j ACCEPT\n'
        'iptables -C FORWARD -o "$dev" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o "$dev" -j ACCEPT\n'
        f"iptables -t nat -C POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE 2>/dev/null || "
        f"iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE\n",
        encoding="utf-8"
    )
    down.write_text(
        "#!/bin/sh\n"
        'iptables -D FORWARD -i "$dev" -j ACCEPT 2>/dev/null || true\n'
        'iptables -D FORWARD -o "$dev" -j ACCEPT 2>/dev/null || true\n'
        f"iptables -t nat -D POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE 2>/dev/null || true\n",
        encoding="utf-8"
    )
    os.chmod(up,0o700); os.chmod(down,0o700)
    return up,down

def _openvpn_forwarding_runtime():
    try:
        output=_run(["ip","-o","-4","addr","show"],timeout=8)
        match=re.search(r"(?m)^\d+:\s+(\S+)\s+inet\s+10\.8\.0\.1/24\b",output)
        iface=match.group(1).split("@",1)[0] if match else ""
        uplink=_default_iface()
    except Exception:
        return {"interface":"","forward_in":None,"forward_out":None,"nat":None}
    if not iface:
        return {"interface":"","forward_in":None,"forward_out":None,"nat":None}
    return {"interface":iface,
            "forward_in":_iptables_check(["-C","FORWARD","-i",iface,"-j","ACCEPT"]),
            "forward_out":_iptables_check(["-C","FORWARD","-o",iface,"-j","ACCEPT"]),
            "nat":_iptables_check(["-t","nat","-C","POSTROUTING","-s","10.8.0.0/24","-o",uplink,"-j","MASQUERADE"])}

def openvpn_endpoint_diagnostics(endpoint):
    endpoint=_validate_endpoint_host(endpoint,"OpenVPN endpoint")
    runtime=_openvpn_server_runtime()
    forwarding=_openvpn_forwarding_runtime() if runtime.get("service_active") else {"interface":"","forward_in":None,"forward_out":None,"nat":None}
    resolved4=[]
    resolved6=[]
    is_ip=False
    ip_version=None
    try:
        parsed=ipaddress.ip_address(endpoint)
        is_ip=True
        ip_version=parsed.version
        if parsed.version==4: resolved4=[parsed.compressed]
        else: resolved6=[parsed.compressed]
    except ValueError:
        try:
            resolved4=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET)})
        except Exception:
            resolved4=[]
        try:
            resolved6=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET6)})
        except Exception:
            resolved6=[]
    local4=_local_ipv4_candidates()
    matches=set(resolved4).issubset(set(local4)) if resolved4 and local4 else None
    warnings=[]
    if not is_ip and not resolved4:
        warnings.append("دامنه هیچ رکورد IPv4/A قابل استفاده‌ای ندارد؛ OpenVPN این پنل روی IPv4 ساخته می‌شود.")
    if not is_ip and resolved6:
        warnings.append("دامنه رکورد IPv6/AAAA هم دارد؛ Makia برای جلوگیری از انتخاب اشتباه IPv6، پروفایل OpenVPN را روی udp4/tcp4 قفل می‌کند.")
    if not is_ip and matches is False:
        warnings.append("رکورد A دامنه با IPv4های Global این VPS تطابق ندارد. اگر DNS پشت Proxy/CDN مثل Cloudflare باشد، OpenVPN خام از آن عبور نمی‌کند؛ رکورد VPN باید DNS-only و مستقیم به VPS باشد.")
    if not runtime.get("service_active"):
        warnings.append("سرویس OpenVPN فعال نیست.")
    if runtime.get("port") and not runtime.get("listener"):
        warnings.append("برای Port تنظیم‌شده Listener فعال OpenVPN دیده نشد.")
    if forwarding["forward_in"] is False or forwarding["forward_out"] is False:
        warnings.append("قانون FORWARD تونل OpenVPN کامل نیست؛ کلاینت ممکن است وصل شود اما اینترنت نداشته باشد.")
    if forwarding["nat"] is False:
        warnings.append("قانون NAT/MASQUERADE تونل OpenVPN دیده نشد؛ اینترنت کلاینت برقرار نمی‌شود.")
    if int(runtime.get("port") or 0)==443 and str(runtime.get("proto") or "").startswith("tcp"):
        warnings.append("OpenVPN روی TCP/443 با HTTPS/Nginx همان IP تداخل دارد مگر Port-sharing یا IP جدا داشته باشید. UDP/443 می‌تواند هم‌زمان با HTTPS/TCP 443 استفاده شود.")
    cert_info={}
    cert=OVPN_DIR/"server/server.crt"
    if cert.exists() and shutil.which("openssl"):
        p=subprocess.run(["openssl","x509","-in",str(cert),"-noout","-subject","-issuer","-enddate"],text=True,capture_output=True,timeout=8,check=False)
        if p.returncode==0:
            for line in (p.stdout or "").splitlines():
                if "=" in line:
                    k,v=line.split("=",1)
                    cert_info[k.strip()]=v.strip()
    return {
        "endpoint":endpoint,
        "endpoint_is_ip":is_ip,
        "endpoint_ip_version":ip_version,
        "resolved_ipv4":resolved4,
        "resolved_ipv6":resolved6,
        "local_ipv4":local4,
        "dns_matches_server":matches,
        "service_active":runtime.get("service_active",False),
        "listener":runtime.get("listener",False),
        "forwarding":forwarding,
        "port":runtime.get("port"),
        "proto":runtime.get("proto"),
        "certificate":cert_info,
        "warnings":warnings,
        "hybrid_fallback_ipv4":next((x for x in resolved4 if x in set(local4)), "") if not is_ip else "",
        "hybrid_available":bool((not is_ip) and any(x in set(local4) for x in resolved4)),
        "ok":bool(runtime.get("service_active") and runtime.get("listener") and (is_ip or (resolved4 and matches is not False))),
    }

def bootstrap_openvpn(port=1194, proto="udp"):
    port=_validate_port(port)
    requested_proto=str(proto or "udp").lower()
    if requested_proto not in {"udp","tcp","udp4","tcp4"}:
        raise ProtocolError("invalid OpenVPN protocol")
    if (OVPN_DIR/"server/server.conf").exists():
        raise ProtocolError("OpenVPN server already exists; use Repair Runtime to preserve existing client certificates")
    transport="tcp" if requested_proto.startswith("tcp") else "udp"
    if _port_transport_in_use(port,transport):
        raise ProtocolError(f"{transport.upper()} port {port} is already in use; choose another OpenVPN port")
    server_proto=_openvpn_proto(requested_proto,server=True)
    if not _installed("openvpn"):
        install_component("openvpn")
    if not OVPN_EASYRSA.exists():
        shutil.copytree("/usr/share/easy-rsa",OVPN_EASYRSA)
    server_dir=OVPN_DIR/"server"
    server_dir.mkdir(parents=True,exist_ok=True)
    pki=OVPN_EASYRSA/"pki"
    env=os.environ.copy()
    env["EASYRSA_BATCH"]="1"
    def er(args,timeout=180):
        try:
            p=subprocess.run([str(OVPN_EASYRSA/"easyrsa"),*args],cwd=str(OVPN_EASYRSA),env=env,text=True,capture_output=True,timeout=timeout,check=False)
        except Exception as exc:
            raise ProtocolError(str(exc)) from exc
        if p.returncode!=0:
            raise ProtocolError((p.stderr or p.stdout or "easy-rsa failed").strip()[:1200])
    if not pki.exists():
        er(["init-pki"])
    if not (pki/"ca.crt").exists():
        er(["build-ca","nopass"])
    if not (pki/"issued/server.crt").exists():
        er(["build-server-full","server","nopass"])
    if not (pki/"dh.pem").exists():
        er(["gen-dh"],timeout=300)
    er(["gen-crl"])
    ta=server_dir/"ta.key"
    if not ta.exists():
        _run(["openvpn","--genkey","secret",str(ta)])
    for src,dst in [
        (pki/"ca.crt",server_dir/"ca.crt"),
        (pki/"issued/server.crt",server_dir/"server.crt"),
        (pki/"private/server.key",server_dir/"server.key"),
        (pki/"dh.pem",server_dir/"dh.pem"),
        (pki/"crl.pem",server_dir/"crl.pem"),
    ]:
        shutil.copy2(src,dst)
    uplink=_default_iface()
    up,down=_openvpn_forward_scripts(uplink)
    server_conf=server_dir/"server.conf"
    server_conf.write_text(
        f"port {port}\nproto {server_proto}\nlocal 0.0.0.0\ndev tun\n"
        "topology subnet\nserver 10.8.0.0 255.255.255.0\n"
        "ca ca.crt\ncert server.crt\nkey server.key\ndh dh.pem\ncrl-verify crl.pem\n"
        "tls-crypt ta.key\n"
        "push \"redirect-gateway def1 bypass-dhcp\"\n"
        "push \"dhcp-option DNS 1.1.1.1\"\npush \"dhcp-option DNS 8.8.8.8\"\n"
        "keepalive 10 120\npersist-key\npersist-tun\nuser nobody\ngroup nogroup\n"
        "data-ciphers AES-256-GCM:AES-128-GCM\ndata-ciphers-fallback AES-256-GCM\nauth SHA256\nverb 3\n"
        f"script-security 2\nup {up}\ndown {down}\n",
        encoding="utf-8"
    )
    Path("/etc/sysctl.d/99-makia-openvpn.conf").write_text("net.ipv4.ip_forward=1\n",encoding="utf-8")
    _run(["sysctl","--system"],timeout=30)
    _run(["systemctl","enable","--now","openvpn-server@server"],timeout=30)
    firewall=_ufw_allow_if_active(port,"udp" if server_proto.startswith("udp") else "tcp","OpenVPN")
    return {"server":"server","port":port,"proto":"udp" if server_proto.startswith("udp") else "tcp","server_proto":server_proto,"firewall":firewall}

def repair_openvpn_ipv4_runtime():
    server_conf=OVPN_DIR/"server/server.conf"
    if not server_conf.exists():
        raise ProtocolError("OpenVPN server config is not available")
    original=server_conf.read_text(encoding="utf-8",errors="ignore")
    updated=original
    proto_m=re.search(r"(?m)^proto\s+(\S+)\s*$",updated)
    current=(proto_m.group(1) if proto_m else "udp").lower()
    target="tcp4-server" if current.startswith("tcp") else "udp4"
    if proto_m:
        updated=re.sub(r"(?m)^proto\s+\S+\s*$",f"proto {target}",updated,count=1)
    else:
        updated=f"proto {target}\n"+updated
    if not re.search(r"(?m)^local\s+",updated):
        updated=re.sub(r"(?m)^(proto\s+\S+\s*)$",r"\1\nlocal 0.0.0.0",updated,count=1)
    backup=server_conf.with_name(f"server.conf.makia-{int(time.time())}.bak")
    shutil.copy2(server_conf,backup)
    up=OVPN_DIR/"makia-up.sh"
    down=OVPN_DIR/"makia-down.sh"
    managed=f"up {up}" in original and f"down {down}" in original
    scripts={p:(p.read_bytes(),p.stat().st_mode & 0o777) if p.exists() else None for p in (up,down)} if managed else {}
    script_backups={}
    try:
        if updated!=original:
            server_conf.write_text(updated,encoding="utf-8")
        if managed:
            for p,saved in scripts.items():
                if saved is not None:
                    script_backup=p.with_name(f"{p.name}.makia-{int(time.time())}.bak")
                    shutil.copy2(p,script_backup)
                    script_backups[str(p)]=str(script_backup)
            _openvpn_forward_scripts(_default_iface())
        _run(["systemctl","restart","openvpn-server@server"],timeout=30)
        if not _active("openvpn-server@server"):
            raise ProtocolError("OpenVPN did not become active after IPv4 normalization")
    except Exception:
        shutil.copy2(backup,server_conf)
        for p,saved in scripts.items():
            if saved is None: p.unlink(missing_ok=True)
            else:
                p.write_bytes(saved[0]); os.chmod(p,saved[1])
        try: _run(["systemctl","restart","openvpn-server@server"],timeout=30)
        except Exception: pass
        raise
    runtime=_openvpn_server_runtime()
    return {"ok":True,"backup":str(backup),"script_backups":script_backups,"runtime":runtime}

def _openvpn_server_options():
    server_conf=OVPN_DIR/"server/server.conf"
    result={
        "port":1194,"proto":"udp","dns":["1.1.1.1","8.8.8.8"],
        "keepalive_ping":10,"keepalive_timeout":120,
        "redirect_gateway":True,"client_to_client":False,
    }
    if not server_conf.exists():
        return result
    text=server_conf.read_text(encoding="utf-8",errors="ignore")
    pm=re.search(r"(?m)^port\s+(\d+)\s*$",text)
    proto_m=re.search(r"(?m)^proto\s+(\S+)\s*$",text)
    keep_m=re.search(r"(?m)^keepalive\s+(\d+)\s+(\d+)\s*$",text)
    dns=re.findall(r'(?m)^push\s+"dhcp-option DNS\s+([^"]+)"\s*$',text)
    result["port"]=int(pm.group(1)) if pm else 1194
    raw_proto=(proto_m.group(1) if proto_m else "udp4").lower()
    result["proto"]="tcp" if raw_proto.startswith("tcp") else "udp"
    if keep_m:
        result["keepalive_ping"]=int(keep_m.group(1));result["keepalive_timeout"]=int(keep_m.group(2))
    if dns:
        result["dns"]=dns[:3]
    result["redirect_gateway"]=bool(re.search(r'(?m)^push\s+"redirect-gateway\s+def1(?:\s+bypass-dhcp)?"\s*$',text))
    result["client_to_client"]=bool(re.search(r"(?m)^client-to-client\s*$",text))
    return result


def _validate_openvpn_dns(values):
    out=[]
    for value in values or []:
        raw=str(value or "").strip()
        if not raw:
            continue
        try:
            addr=ipaddress.ip_address(raw)
        except ValueError as exc:
            raise ProtocolError(f"invalid OpenVPN DNS server: {raw}") from exc
        if addr.version!=4:
            raise ProtocolError("OpenVPN managed DNS currently requires IPv4 addresses")
        normalized=addr.compressed
        if normalized not in out:
            out.append(normalized)
    if not out:
        raise ProtocolError("at least one OpenVPN DNS server is required")
    return out[:3]


def reconfigure_openvpn_server(port=1194,proto="udp",dns_servers=None,keepalive_ping=10,keepalive_timeout=120,redirect_gateway=True,client_to_client=False):
    """Safely change the managed OpenVPN server while preserving PKI and clients."""
    server_conf=OVPN_DIR/"server/server.conf"
    if not server_conf.exists():
        raise ProtocolError("OpenVPN server config is not available")
    port=_validate_port(port)
    requested="tcp" if str(proto or "").lower().startswith("tcp") else "udp"
    if str(proto or "").lower() not in {"udp","tcp","udp4","tcp4","tcp4-server","udp4"}:
        raise ProtocolError("OpenVPN transport must be UDP or TCP")
    dns=_validate_openvpn_dns(dns_servers or ["1.1.1.1","8.8.8.8"])
    keepalive_ping=max(1,min(int(keepalive_ping),3600))
    keepalive_timeout=max(10,min(int(keepalive_timeout),7200))
    if keepalive_timeout<=keepalive_ping:
        raise ProtocolError("OpenVPN keepalive timeout must be greater than ping interval")

    current=_openvpn_server_runtime()
    current_transport="tcp" if str(current.get("proto") or "").startswith("tcp") else "udp"
    current_port=int(current.get("port") or 0)
    if (port!=current_port or requested!=current_transport) and _port_transport_in_use(port,requested):
        raise ProtocolError(f"{requested.upper()} port {port} is already in use")

    original=server_conf.read_text(encoding="utf-8",errors="ignore")
    backup_dir=_backup_dir()
    backup=backup_dir/f"openvpn-config-{int(time.time())}.conf"
    shutil.copy2(server_conf,backup)

    updated=original
    server_proto=_openvpn_proto(requested,server=True)
    if re.search(r"(?m)^port\s+\d+\s*$",updated):
        updated=re.sub(r"(?m)^port\s+\d+\s*$",f"port {port}",updated,count=1)
    else:
        updated=f"port {port}\n"+updated
    if re.search(r"(?m)^proto\s+\S+\s*$",updated):
        updated=re.sub(r"(?m)^proto\s+\S+\s*$",f"proto {server_proto}",updated,count=1)
    else:
        updated=f"proto {server_proto}\n"+updated

    # Managed policy lines are regenerated atomically to avoid duplicate pushes.
    updated=re.sub(r'(?m)^push\s+"dhcp-option DNS\s+[^"]+"\s*\n?',"",updated)
    updated=re.sub(r'(?m)^push\s+"redirect-gateway\s+def1(?:\s+bypass-dhcp)?"\s*\n?',"",updated)
    updated=re.sub(r"(?m)^keepalive\s+\d+\s+\d+\s*\n?","",updated)
    updated=re.sub(r"(?m)^client-to-client\s*\n?","",updated)
    policy=[]
    if redirect_gateway:
        policy.append('push "redirect-gateway def1 bypass-dhcp"')
    policy.extend(f'push "dhcp-option DNS {item}"' for item in dns)
    policy.append(f"keepalive {keepalive_ping} {keepalive_timeout}")
    if client_to_client:
        policy.append("client-to-client")
    updated=updated.rstrip()+"\n"+"\n".join(policy)+"\n"

    try:
        server_conf.write_text(updated,encoding="utf-8")
        os.chmod(server_conf,0o600)
        _run(["systemctl","restart","openvpn-server@server"],timeout=30)
        runtime=_openvpn_server_runtime()
        actual_transport="tcp" if str(runtime.get("proto") or "").startswith("tcp") else "udp"
        if not runtime.get("service_active") or not runtime.get("listener") or int(runtime.get("port") or 0)!=port or actual_transport!=requested:
            raise ProtocolError("OpenVPN did not reach the requested listener after reconfiguration")
        firewall=_ufw_allow_if_active(port,requested,"OpenVPN")
    except Exception:
        shutil.copy2(backup,server_conf)
        try:_run(["systemctl","restart","openvpn-server@server"],timeout=30)
        except Exception:pass
        raise
    return {"ok":True,"backup":str(backup),"runtime":runtime,"options":_openvpn_server_options(),"firewall":firewall}


def _openvpn_remote_block(endpoint,port):
    endpoint=_validate_endpoint_host(endpoint,"OpenVPN endpoint")
    candidates=[endpoint]
    fallback=""
    try:
        parsed=ipaddress.ip_address(endpoint)
        if parsed.version==4:
            return f"remote {parsed.compressed} {int(port)}\n","",False
    except ValueError:
        pass
    try:
        diag=openvpn_endpoint_diagnostics(endpoint)
        direct=[x for x in (diag.get("resolved_ipv4") or []) if x in set(diag.get("local_ipv4") or [])]
        if direct:
            fallback=direct[0]
            if fallback not in candidates:
                candidates.append(fallback)
    except Exception:
        fallback=""
    lines="".join(f"remote {item} {int(port)}\n" for item in candidates)
    return lines,fallback,len(candidates)>1

def create_openvpn_client(name, endpoint, port=1194, proto="udp"):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid client name")
    endpoint=_validate_endpoint_host(endpoint)
    port=_validate_port(port)
    if proto not in {"udp","tcp","udp4","tcp4"}:
        raise ProtocolError("invalid OpenVPN protocol")
    if not (OVPN_EASYRSA/"pki/ca.crt").exists():
        raise ProtocolError("OpenVPN server is not bootstrapped")
    runtime=_openvpn_server_runtime()
    server_port=int(runtime.get("port") or 0)
    server_proto="tcp" if str(runtime.get("proto") or "").startswith("tcp") else "udp"
    requested_proto="tcp" if proto.startswith("tcp") else "udp"
    if port!=server_port or requested_proto!=server_proto:
        raise ProtocolError(f"Client port/transport must match the OpenVPN server ({server_proto}/{server_port})")
    env=os.environ.copy(); env["EASYRSA_BATCH"]="1"
    p=subprocess.run([str(OVPN_EASYRSA/"easyrsa"),"build-client-full",name,"nopass"],cwd=str(OVPN_EASYRSA),env=env,text=True,capture_output=True,timeout=180,check=False)
    if p.returncode!=0:
        raise ProtocolError((p.stderr or p.stdout or "easy-rsa failed").strip()[:1200])
    pki=OVPN_EASYRSA/"pki"
    ca=(pki/"ca.crt").read_text(encoding="utf-8")
    cert=(pki/f"issued/{name}.crt").read_text(encoding="utf-8")
    key=(pki/f"private/{name}.key").read_text(encoding="utf-8")
    ta=(OVPN_DIR/"server/ta.key").read_text(encoding="utf-8")
    transport=_openvpn_proto(proto,server=False)
    remotes,fallback_ipv4,hybrid=_openvpn_remote_block(endpoint,port)
    client=(
        "client\ndev tun\n"
        f"proto {transport}\n"
        +remotes+
        ("resolv-retry 5\nserver-poll-timeout 8\n" if hybrid else "resolv-retry infinite\n")+
        "connect-retry 2 30\nnobind\npersist-key\npersist-tun\nauth-nocache\n"
        "remote-cert-tls server\nverify-x509-name server name\n"
        "data-ciphers AES-256-GCM:AES-128-GCM\nauth SHA256\nverb 3\n"
        f"<ca>\n{ca}</ca>\n<cert>\n{cert}</cert>\n<key>\n{key}</key>\n<tls-crypt>\n{ta}</tls-crypt>\n"
    )
    return {"name":name,"config":client,"endpoint":endpoint,"fallback_ipv4":fallback_ipv4,"hybrid_endpoint":hybrid,"port":port,"proto":"udp" if transport.startswith("udp") else "tcp","client_proto":transport}

def list_openvpn_clients():
    issued=OVPN_EASYRSA/"pki/issued"
    if not issued.exists():
        return []
    out=[]
    for cert in sorted(issued.glob("*.crt")):
        if cert.stem=="server":
            continue
        out.append({"name":cert.stem,"certificate":str(cert)})
    return out

def render_openvpn_client(name,endpoint):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid client name")
    endpoint=_validate_endpoint_host(endpoint)
    server_conf=OVPN_DIR/"server/server.conf"
    pki=OVPN_EASYRSA/"pki"
    cert=pki/f"issued/{name}.crt"
    key=pki/f"private/{name}.key"
    if not server_conf.exists() or not cert.exists() or not key.exists():
        raise ProtocolError("OpenVPN client material is not available")
    text=server_conf.read_text(encoding="utf-8",errors="ignore")
    pm=re.search(r"(?m)^port\s+(\d+)\s*$",text)
    proto_m=re.search(r"(?m)^proto\s+(\S+)\s*$",text)
    port=int(pm.group(1)) if pm else 1194
    server_proto=(proto_m.group(1) if proto_m else "udp").lower()
    transport="tcp4-client" if server_proto.startswith("tcp") else "udp4"
    ca=(pki/"ca.crt").read_text(encoding="utf-8")
    cert_text=cert.read_text(encoding="utf-8")
    key_text=key.read_text(encoding="utf-8")
    ta=(OVPN_DIR/"server/ta.key").read_text(encoding="utf-8")
    remotes,fallback_ipv4,hybrid=_openvpn_remote_block(endpoint,port)
    client=(
        "client\ndev tun\n"
        f"proto {transport}\n"
        +remotes+
        ("resolv-retry 5\nserver-poll-timeout 8\n" if hybrid else "resolv-retry infinite\n")+
        "connect-retry 2 30\nnobind\npersist-key\npersist-tun\nauth-nocache\n"
        "remote-cert-tls server\nverify-x509-name server name\n"
        "data-ciphers AES-256-GCM:AES-128-GCM\nauth SHA256\nverb 3\n"
        f"<ca>\n{ca}</ca>\n<cert>\n{cert_text}</cert>\n<key>\n{key_text}</key>\n<tls-crypt>\n{ta}</tls-crypt>\n"
    )
    return {"name":name,"config":client,"endpoint":endpoint,"fallback_ipv4":fallback_ipv4,"hybrid_endpoint":hybrid,"port":port,"proto":"tcp" if transport.startswith("tcp") else "udp","client_proto":transport}

def revoke_openvpn_client(name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid client name")
    if not OVPN_EASYRSA.exists():
        raise ProtocolError("OpenVPN PKI is not available")
    env=os.environ.copy(); env["EASYRSA_BATCH"]="1"
    p=subprocess.run([str(OVPN_EASYRSA/"easyrsa"),"revoke",name],cwd=str(OVPN_EASYRSA),env=env,text=True,capture_output=True,timeout=180,check=False)
    if p.returncode!=0 and "already revoked" not in ((p.stderr or p.stdout or "").lower()):
        raise ProtocolError((p.stderr or p.stdout or "OpenVPN revoke failed").strip()[:1200])
    p=subprocess.run([str(OVPN_EASYRSA/"easyrsa"),"gen-crl"],cwd=str(OVPN_EASYRSA),env=env,text=True,capture_output=True,timeout=180,check=False)
    if p.returncode!=0:
        raise ProtocolError((p.stderr or p.stdout or "OpenVPN CRL generation failed").strip()[:1200])
    crl=OVPN_EASYRSA/"pki/crl.pem"
    if crl.exists():
        shutil.copy2(crl,OVPN_DIR/"server/crl.pem")
    archive=OVPN_DIR/"revoked"
    archive.mkdir(parents=True,exist_ok=True)
    os.chmod(archive,0o700)
    for src in [OVPN_EASYRSA/f"pki/issued/{name}.crt",OVPN_EASYRSA/f"pki/private/{name}.key"]:
        if src.exists():
            shutil.move(str(src),str(archive/src.name))
    return {"revoked":True,"name":name}

def _port_transport_in_use(port, proto):
    port=_validate_port(port)
    proto=str(proto or "").lower()
    if proto not in {"tcp","udp"}:
        raise ProtocolError("port transport must be tcp or udp")
    kind=socket.SOCK_STREAM if proto=="tcp" else socket.SOCK_DGRAM
    s=socket.socket(socket.AF_INET,kind)
    try:
        s.bind(("0.0.0.0",port))
    except OSError:
        return True
    finally:
        s.close()
    return False

def _port_in_use(port):
    return _port_transport_in_use(port,"tcp") or _port_transport_in_use(port,"udp")


def _suggest_free_port(proto,candidates,exclude_ports=None):
    excluded={int(x) for x in (exclude_ports or set()) if x}
    for candidate in candidates:
        try:
            candidate=_validate_port(candidate)
        except Exception:
            continue
        if candidate in excluded:
            continue
        if not _port_transport_in_use(candidate,proto):
            return candidate
    return None


def _select_available_port_excluding(preferred,proto,fallbacks=(),exclude_ports=None):
    excluded={int(x) for x in (exclude_ports or set()) if x}
    candidates=[]
    for value in (preferred,*fallbacks):
        try:
            value=_validate_port(value)
        except Exception:
            continue
        if value not in excluded and value not in candidates:
            candidates.append(value)
    for value in candidates:
        if not _port_transport_in_use(value,proto):
            return value
    raise ProtocolError(
        f"no free {str(proto).upper()} port found outside reserved ports: "
        +", ".join(str(x) for x in candidates)
    )


def _port_owner_label(port,proto):
    """Best-effort human-readable owner for a real occupied listener."""
    port=_validate_port(port)
    proto=str(proto or "").lower()
    if not _port_transport_in_use(port,proto):
        return "free"

    if proto=="tcp":
        if port==443 and (_active("nginx") or _active("apache2")):
            return "HTTPS web server (TCP/443)"
        tcp=_openvpn_named_runtime("makia-tcp")
        if int(tcp.get("port") or 0)==port and (tcp.get("service_active") or tcp.get("listener")):
            return "OpenVPN TCP fallback"
        st=stealth_status()
        if int(st.get("port") or 0)==port and (st.get("configured") or st.get("listener")):
            return "Stealth / Stunnel"
        ws=wstunnel_status()
        if int(ws.get("port") or 0)==port and (ws.get("configured") or ws.get("listener")):
            return "WStunnel"
        try:
            xr=xray_status()
            for inbound in xr.get("inbounds") or []:
                if int(inbound.get("port") or 0)==port:
                    return f"Xray inbound {inbound.get('tag') or inbound.get('protocol') or ''}".strip()
        except Exception:
            pass
    elif proto=="udp":
        wg=wireguard_status()
        if int(wg.get("port") or 0)==port and wg.get("service_active"):
            return "WireGuard"
        ov=_openvpn_server_runtime()
        if int(ov.get("port") or 0)==port and str(ov.get("proto") or "").startswith("udp"):
            return "OpenVPN UDP"
    return "another host service"


def connection_port_plan():
    """Describe actual TCP listener ownership and safe alternatives without mutating runtime."""
    tcp=_openvpn_named_runtime("makia-tcp")
    st=stealth_status()
    ws=wstunnel_status()
    rows=[]
    for service,port in [
        ("HTTPS",443),
        ("OpenVPN TCP fallback",int(tcp.get("port") or 8443)),
        ("Stealth public TLS",int(st.get("port") or 9443)),
        ("WStunnel WSS",int(ws.get("port") or 8444)),
    ]:
        occupied=_port_transport_in_use(port,"tcp")
        rows.append({
            "service":service,"port":port,"transport":"tcp","occupied":occupied,
            "owner":_port_owner_label(port,"tcp") if occupied else "",
        })
    server_dir=OVPN_DIR/"server"
    required=["ca.crt","server.crt","server.key","dh.pem","crl.pem","ta.key"]
    missing_pki=[name for name in required if not (server_dir/name).exists()]
    tcp_blockers=[]
    if missing_pki:
        tcp_blockers.append("Missing OpenVPN PKI: "+", ".join(missing_pki))
    if not tcp.get("listener") and not _suggest_free_port("tcp",(8443,10443,11940,12443)):
        tcp_blockers.append("No free TCP fallback port in the managed candidate set")
    stealth_blockers=[]
    if not (_installed("stunnel4") or _installed("stunnel")):
        stealth_blockers.append("Stunnel tooling is not installed")
    if missing_pki:
        stealth_blockers.append("Stealth needs the existing OpenVPN PKI/TCP backend")
    return {
        "rows":rows,
        "suggested":{
            "openvpn_tcp":int(tcp.get("port") or 0) or _suggest_free_port("tcp",(8443,10443,11940,12443)),
            "stealth":int(st.get("port") or 0) or _suggest_free_port("tcp",(9443,10443,11443,12443),exclude_ports={int(tcp.get("port") or 0)}),
            "wstunnel":int(ws.get("port") or 0) or _suggest_free_port("tcp",(8444,10444,11444,12444)),
        },
        "blockers":{"openvpn_tcp":tcp_blockers,"stealth":stealth_blockers},
        "https_tcp_443_reserved":bool(_port_transport_in_use(443,"tcp")),
        "note":"TCP/443 has one owner. UDP/443 may coexist because TCP and UDP are independent transports.",
    }

def _select_available_port(preferred, proto, fallbacks=()):
    proto=str(proto or "").lower()
    candidates=[]
    for value in (preferred,*fallbacks):
        try: value=_validate_port(value)
        except Exception: continue
        if value not in candidates:
            candidates.append(value)
    for value in candidates:
        if not _port_transport_in_use(value,proto):
            return value
    raise ProtocolError(f"no free {proto.upper()} port found in candidates: "+", ".join(str(x) for x in candidates))

def ensure_full_protocol_stack():
    """Install and bootstrap the server-side protocol stack idempotently.

    Fresh Makia installs should finish with Xray, WireGuard and OpenVPN ready.
    Existing configurations are preserved; missing engines/configs are created
    and unhealthy managed runtimes are repaired where possible.
    """
    result={"xray":None,"wireguard":None,"openvpn":None,"stunnel":None,"ports":{}}

    x=xray_status()
    if not x.get("installed"):
        x=install_component("xray")
    else:
        config=x.get("config_path")
        if not config:
            path=Path("/usr/local/etc/xray/config.json")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(_xray_default_config(path),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            os.chmod(path,0o600)
            _xray_secure_runtime_file(path)
            _xray_test_config_as_service(_binary(),path)
        try:
            _run(["systemctl","enable","--now","xray"],timeout=60)
        except ProtocolError:
            pass
        x=xray_status()
        if not x.get("service_active"):
            x=repair_xray_runtime().get("diagnostics") or xray_status()
    if not x.get("installed") or not x.get("service_active") or not x.get("config_path"):
        raise ProtocolError("Xray full-stack provisioning did not reach READY state")
    result["xray"]=x

    wg=wireguard_status()
    if not wg.get("installed"):
        install_component("wireguard")
        wg=wireguard_status()
    if not wg.get("config"):
        wg_port=_select_available_port(443,"udp",(51820,51821,8443,2053,2083))
        bootstrap_wireguard(wg_port,"10.66.66.1/24","wg0",1280)
    elif not wg.get("service_active"):
        repair_wireguard_runtime("wg0")
    wg_diag=wireguard_endpoint_diagnostics("","wg0")
    if not wg_diag.get("runtime_ok"):
        raise ProtocolError("WireGuard full-stack provisioning failed: "+"; ".join(wg_diag.get("warnings") or []))
    result["wireguard"]=wireguard_status()
    result["ports"]["wireguard"]=int(wg_diag.get("port") or result["wireguard"].get("port") or 0)

    ov=openvpn_status()
    if not ov.get("installed"):
        install_component("openvpn")
        ov=openvpn_status()
    if not ov.get("config"):
        ov_port=_select_available_port(1194,"udp",(1195,1196,2443,9443,10443))
        bootstrap_openvpn(ov_port,"udp")
    elif not ov.get("service_active"):
        repair_openvpn_ipv4_runtime()
    ov_runtime=_openvpn_server_runtime()
    if not ov_runtime.get("service_active") or not ov_runtime.get("listener"):
        raise ProtocolError("OpenVPN full-stack provisioning did not reach READY state")
    result["openvpn"]=openvpn_status()
    result["ports"]["openvpn"]=int(ov_runtime.get("port") or result["openvpn"].get("port") or 0)

    st=stunnel_status()
    if not st.get("installed"):
        st=install_component("stunnel")
    result["stunnel"]=stunnel_status()

    return result

def _ensure_xray_stats(data):
    if not isinstance(data,dict):
        raise ProtocolError("invalid Xray configuration root")
    data.setdefault("stats",{})
    api=data.setdefault("api",{})
    api["tag"]="api"
    api["listen"]="127.0.0.1:10085"
    services=set(api.get("services") or [])
    services.update(["StatsService","HandlerService"])
    api["services"]=sorted(services)
    policy=data.setdefault("policy",{})
    levels=policy.setdefault("levels",{})
    level0=levels.setdefault("0",{})
    level0["statsUserUplink"]=True
    level0["statsUserDownlink"]=True
    level0["statsUserOnline"]=True
    system=policy.setdefault("system",{})
    system["statsInboundUplink"]=True
    system["statsInboundDownlink"]=True
    system["statsOutboundUplink"]=True
    system["statsOutboundDownlink"]=True

    # Remove only the legacy Makia API tunnel created by earlier RC builds.
    inbounds=data.get("inbounds")
    if isinstance(inbounds,list):
        data["inbounds"]=[
            item for item in inbounds
            if not (
                isinstance(item,dict)
                and item.get("tag")=="api"
                and int(item.get("port") or -1)==10085
                and str(item.get("listen") or "")=="127.0.0.1"
            )
        ]
    routing=data.get("routing")
    if isinstance(routing,dict) and isinstance(routing.get("rules"),list):
        routing["rules"]=[
            rule for rule in routing["rules"]
            if not (
                isinstance(rule,dict)
                and rule.get("inboundTag")==["api"]
                and rule.get("outboundTag")=="api"
            )
        ]
    return data

def xray_client_traffic(email, reset=False):
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    pattern=f"user>>>{email}>>>traffic>>>"
    args=[binary,"api","statsquery","--server=127.0.0.1:10085","-pattern",pattern]
    if reset:
        args += ["-reset=true"]
    p=subprocess.run(args,text=True,capture_output=True,timeout=8,check=False)
    if p.returncode!=0:
        return {"uplink":0,"downlink":0,"total":0,"available":False,"error":(p.stderr or p.stdout or "")[:240]}
    text=p.stdout or ""
    up=down=0
    parsed=False
    try:
        payload=json.loads(text)
        rows=payload.get("stat") or payload.get("stats") or []
        if isinstance(rows,list):
            for item in rows:
                if not isinstance(item,dict): continue
                name=str(item.get("name") or "")
                try: value=int(item.get("value") or 0)
                except Exception: value=0
                if name.endswith(">>>uplink"): up+=value
                elif name.endswith(">>>downlink"): down+=value
            parsed=True
    except Exception:
        pass
    if not parsed:
        blocks=re.split(r"\n\s*\n",text)
        for block in blocks:
            name_m=re.search(r'["\']?name["\']?\s*:\s*"([^"]+)"',block)
            value_m=re.search(r'["\']?value["\']?\s*:\s*"?(\d+)"?',block)
            if not name_m or not value_m:
                continue
            name=name_m.group(1); value=int(value_m.group(1))
            if name.endswith(">>>uplink"): up+=value
            elif name.endswith(">>>downlink"): down+=value
    return {"uplink":up,"downlink":down,"total":up+down,"available":True,"error":None}
def xray_client_online_ips(email):
    binary=_binary()
    if not binary:
        return {"available":False,"ips":[],"error":"Xray core is not installed"}
    args=[binary,"api","statsonlineiplist","--server=127.0.0.1:10085","--email="+str(email)]
    p=subprocess.run(args,text=True,capture_output=True,timeout=8,check=False)
    if p.returncode!=0:
        err=(p.stderr or p.stdout or "").strip()
        # Older Xray cores do not expose this RPC/CLI.
        return {"available":False,"ips":[],"error":err[:240]}
    text=p.stdout or ""
    entries=[]
    try:
        payload=json.loads(text)
        raw=payload.get("ips") or {}
        if isinstance(raw,dict):
            entries=[{"ip":str(ip),"last_seen":int(ts or 0)} for ip,ts in raw.items()]
    except Exception:
        # Fallback for protobuf-text-like command output.
        for ip,ts in re.findall(r'key:\s*"([^"]+)"[\s\S]*?value:\s*(\d+)',text):
            entries.append({"ip":ip,"last_seen":int(ts)})
    entries.sort(key=lambda item:item.get("last_seen",0),reverse=True)
    return {"available":True,"ips":entries,"error":None}


def _xray_default_config(path):
    return {
        "log":{"loglevel":"warning"},
        "inbounds":[],
        "outbounds":[{"protocol":"freedom","tag":"direct"}],
    }

def _x25519_pair(binary):
    out=_run([binary,"x25519"],timeout=10)
    private=None; public=None
    for line in out.splitlines():
        if ":" not in line: continue
        key,value=line.split(":",1)
        k=key.strip().lower().replace(" ","")
        value=value.strip()
        if k in {"privatekey","privatekey"} or k.startswith("private"):
            private=private or value
        elif k.startswith("password") or k.startswith("public"):
            public=public or value
    if not private or not public:
        raise ProtocolError("unable to parse Xray x25519 output")
    return private,public

def _build_xray_stream(binary,protocol,transport,security,path_value,server_name,reality_dest):
    transport=(transport or "tcp").lower()
    security=(security or "none").lower()
    aliases={"tcp":"raw","ws":"websocket","kcp":"mkcp"}
    transport=aliases.get(transport,transport)
    if transport not in {"raw","websocket","grpc","httpupgrade","xhttp","mkcp"}:
        raise ProtocolError("unsupported transport")
    if security not in {"none","tls","reality"}:
        raise ProtocolError("unsupported transport security")
    if security=="reality":
        if protocol not in {"vless","trojan"}:
            raise ProtocolError("REALITY is only available for VLESS or Trojan")
        if transport not in {"raw","grpc","xhttp"}:
            raise ProtocolError("REALITY is only compatible with TCP/RAW, gRPC or XHTTP here")
    stream={"method":transport,"security":security}
    path_value=(path_value or "/").strip() or "/"
    if not path_value.startswith("/") and transport in {"websocket","httpupgrade","xhttp"}:
        path_value="/"+path_value
    if transport=="websocket":
        stream["wsSettings"]={"path":path_value}
    elif transport=="grpc":
        stream["grpcSettings"]={"serviceName":path_value.strip("/")}
    elif transport=="httpupgrade":
        stream["httpupgradeSettings"]={"path":path_value}
    elif transport=="xhttp":
        stream["xhttpSettings"]={"path":path_value,"mode":"auto"}
    elif transport=="mkcp":
        # Xray 26.3.27 removed the legacy kcpSettings.header/seed fields.
        # Guided mKCP therefore uses Core defaults without hidden obfuscation
        # state, which also keeps exported client links reproducible.
        stream["kcpSettings"]={}
    reality_meta={}
    if security=="tls":
        sni=(server_name or "").strip().lower()
        if not sni:
            raise ProtocolError("TLS requires a domain/SNI")
        cert,key=_xray_materialize_tls(sni)
        stream["tlsSettings"]={
            "serverName":sni,
            "alpn":["h2","http/1.1"],
            "certificates":[{"certificateFile":str(cert),"keyFile":str(key)}],
        }
    elif security=="reality":
        sni=(server_name or "").strip().lower()
        target=(reality_dest or "").strip()
        if not sni or not target:
            raise ProtocolError("REALITY requires server name and target such as www.cloudflare.com:443")
        private,public=_x25519_pair(binary)
        sid=secrets.token_hex(8)
        stream["realitySettings"]={
            "show":False,
            "target":target,
            "xver":0,
            "serverNames":[sni],
            "privateKey":private,
            "shortIds":[sid],
        }
        reality_meta={"public_key":public,"short_id":sid,"server_name":sni}
    return stream,reality_meta

def xray_guided_compatibility():
    return {
        "vless":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["reality","tls","none"]},
        "vmess":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
        "trojan":{"transports":["tcp","ws","grpc","httpupgrade","xhttp"],"security":["tls"]},
        "shadowsocks":{"transports":["tcp"],"security":["none"]},
        "hysteria2":{"transports":["hysteria"],"security":["tls"]},
        "http":{"transports":["tcp"],"security":["none"]},
        "socks":{"transports":["tcp"],"security":["none"]},
    }


def xray_manual_compatibility():
    """Form-builder capabilities for expert mode.

    Expert mode removes Makia's opinionated public-endpoint policy and lets the
    pinned Xray Core be the final syntax authority. We still constrain fields
    that cannot produce a faithful client export.
    """
    return {
        "vless":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls","reality"]},
        "vmess":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
        "trojan":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
        "shadowsocks":{"transports":["tcp"],"security":["none"]},
        "hysteria2":{"transports":["hysteria"],"security":["tls"]},
        "http":{"transports":["tcp"],"security":["none"]},
        "socks":{"transports":["tcp"],"security":["none"]},
    }


def _validate_xray_manual_combo(protocol,transport,security):
    protocol=str(protocol or "").lower()
    transport=str(transport or "tcp").lower()
    security=str(security or "none").lower()
    aliases={"raw":"tcp","websocket":"ws","mkcp":"kcp"}
    transport=aliases.get(transport,transport)
    spec=xray_manual_compatibility().get(protocol)
    if not spec:
        raise ProtocolError("unsupported Xray protocol")
    if protocol=="hysteria2":
        return "hysteria","tls"
    if security=="reality" and protocol!="vless":
        raise ProtocolError("REALITY requires VLESS")
    if security=="reality" and transport not in {"tcp","grpc","xhttp"}:
        raise ProtocolError("REALITY requires VLESS with TCP/RAW, gRPC or XHTTP")
    if transport not in spec["transports"]:
        raise ProtocolError(f"{protocol.upper()} cannot be exported with transport={transport}")
    if security not in spec["security"]:
        raise ProtocolError(f"{protocol.upper()} cannot be exported with security={security}")
    return transport,security


def _validate_xray_guided_combo(protocol,transport,security):
    protocol=str(protocol or "").lower()
    transport=str(transport or "tcp").lower()
    security=str(security or "none").lower()
    aliases={"raw":"tcp","websocket":"ws","mkcp":"kcp"}
    transport=aliases.get(transport,transport)
    spec=xray_guided_compatibility().get(protocol)
    if not spec:
        raise ProtocolError("unsupported Xray quick protocol")
    if protocol=="hysteria2":
        return "hysteria","tls"
    if transport not in spec["transports"]:
        raise ProtocolError(f"{protocol.upper()} does not support {transport.upper()} in Makia guided mode")
    if security not in spec["security"]:
        raise ProtocolError(f"{protocol.upper()} does not support security={security} in Makia guided mode")
    if security=="reality" and transport not in {"tcp","grpc","xhttp"}:
        raise ProtocolError("VLESS REALITY guided mode supports TCP/RAW, gRPC or XHTTP")
    return transport,security



def xray_inbound_builder_capabilities():
    """3x-ui inspired capability map, constrained to the pinned Makia Core."""
    return {
        "protocols":{
            "vless":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls","reality"]},
            "vmess":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
            "trojan":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["tls","reality"]},
            "shadowsocks":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
            "hysteria2":{"transports":["hysteria"],"security":["tls"]},
            "http":{"transports":["tcp"],"security":["none"]},
            "socks":{"transports":["tcp"],"security":["none"]},
        },
        "transport_options":{
            "tcp":["accept_proxy_protocol","header_type","http_host","http_path"],
            "ws":["path","host","heartbeat_period","accept_proxy_protocol"],
            "grpc":["service_name","authority","multi_mode"],
            "httpupgrade":["path","host","accept_proxy_protocol"],
            "xhttp":["path","host","mode","x_padding_bytes"],
            "kcp":["mtu","tti","uplink_capacity","downlink_capacity","cwnd_multiplier","max_sending_window"],
            "hysteria":["udp_idle_timeout"],
        },
        "security_options":{
            "tls":["server_name","alpn"],
            "reality":["server_name","target","fingerprint","short_id","spider_x","xver"],
        },
        "sniffing":["enabled","dest_override","route_only","metadata_only"],
        "sockopt":["tcp_fast_open","tcp_no_delay","tcp_congestion","domain_strategy","mark","interface","tproxy"],
        "shadowsocks_methods":[
            "aes-128-gcm","aes-256-gcm","chacha20-poly1305",
            "2022-blake3-aes-128-gcm","2022-blake3-aes-256-gcm"
        ],
        "xhttp_modes":["auto","packet-up","stream-up","stream-one"],
        "flow":["","xtls-rprx-vision"],
    }


def _xray_builder_validate_combo(protocol,transport,security):
    protocol=str(protocol or "").lower()
    transport=str(transport or "tcp").lower()
    security=str(security or "none").lower()
    aliases={"raw":"tcp","websocket":"ws","mkcp":"kcp"}
    transport=aliases.get(transport,transport)
    caps=xray_inbound_builder_capabilities()["protocols"].get(protocol)
    if not caps:
        raise ProtocolError("unsupported Xray protocol")
    if transport not in caps["transports"]:
        raise ProtocolError(f"{protocol.upper()} does not support {transport.upper()} in the Makia inbound builder")
    if security not in caps["security"]:
        raise ProtocolError(f"{protocol.upper()} does not support security={security} in the Makia inbound builder")
    if security=="reality" and transport not in {"tcp","grpc","xhttp"}:
        raise ProtocolError("REALITY is only valid with TCP/RAW, gRPC or XHTTP")
    if protocol=="hysteria2":
        return "hysteria","tls"
    return transport,security


def _xray_builder_listen(value):
    raw=str(value or "").strip()
    if not raw or raw=="*":
        return "0.0.0.0"
    try:
        return ipaddress.ip_address(raw.strip("[]")).compressed
    except ValueError as exc:
        raise ProtocolError("Xray listen must be an IPv4/IPv6 address or left blank") from exc


def _xray_builder_headers(value):
    if value in (None,""):
        return {}
    if not isinstance(value,dict):
        raise ProtocolError("transport headers must be a JSON object")
    out={}
    for key,val in value.items():
        name=str(key or "").strip()
        if not name or len(name)>80 or not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_|~-]+",name):
            raise ProtocolError("invalid transport header name")
        if isinstance(val,(list,dict)):
            raise ProtocolError("transport header values must be scalar strings")
        text=str(val)
        if len(text)>1024:
            raise ProtocolError("transport header value is too long")
        out[name]=text
    return out


def _xray_deep_merge(base,extra):
    if not isinstance(extra,dict):
        return base
    for key,value in extra.items():
        if key in {"method","network","security","tlsSettings","realitySettings"}:
            continue
        if isinstance(value,dict) and isinstance(base.get(key),dict):
            _xray_deep_merge(base[key],value)
        else:
            base[key]=value
    return base


def _xray_public_from_private(binary,private_key):
    if not private_key:
        return ""
    out=_run([binary,"x25519","-i",str(private_key)],timeout=10)
    public=""
    for line in out.splitlines():
        if ":" not in line:
            continue
        key,value=line.split(":",1)
        normalized=key.strip().lower().replace(" ","")
        if normalized.startswith("public") or normalized.startswith("password"):
            public=value.strip()
    if not public:
        raise ProtocolError("unable to derive REALITY client key from server private key")
    return public


def _xray_builder_stream(binary,protocol,transport,security,options):
    options=dict(options or {})
    path_value=str(options.get("path") or "/").strip() or "/"
    server_name=str(options.get("server_name") or "").strip().lower()
    reality_dest=str(options.get("reality_dest") or options.get("target") or "").strip()

    if protocol=="hysteria2":
        if not server_name:
            raise ProtocolError("Hysteria2 requires a TLS domain/SNI")
        cert,key=_xray_materialize_tls(server_name)
        stream={
            "method":"hysteria","security":"tls",
            "hysteriaSettings":{"version":2},
            "tlsSettings":{
                "serverName":server_name,"alpn":["h3"],
                "certificates":[{"certificateFile":str(cert),"keyFile":str(key)}],
            },
        }
        idle=int(options.get("udp_idle_timeout") or 0)
        if idle:
            if not 2<=idle<=600:
                raise ProtocolError("Hysteria UDP idle timeout must be 2-600 seconds")
            stream["hysteriaSettings"]["udpIdleTimeout"]=idle
        return stream,{}

    stream,reality_meta=_build_xray_stream(
        binary,protocol,transport,security,path_value,server_name,reality_dest
    )
    method=stream.get("method","raw")
    headers=_xray_builder_headers(options.get("headers") or {})

    if method=="raw":
        raw={}
        if bool(options.get("accept_proxy_protocol")):
            raw["acceptProxyProtocol"]=True
        header_type=str(options.get("header_type") or "none").lower()
        if header_type not in {"none","http"}:
            raise ProtocolError("RAW header type must be none or http")
        raw["header"]={"type":header_type}
        if header_type=="http":
            http_path=str(options.get("http_path") or path_value or "/")
            http_host=str(options.get("http_host") or options.get("host") or "")
            request={"path":[http_path],"headers":{}}
            if http_host:
                request["headers"]["Host"]=[http_host]
            raw["header"]["request"]=request
        stream["rawSettings"]=raw
    elif method=="websocket":
        ws=stream.setdefault("wsSettings",{})
        ws["path"]=path_value if path_value.startswith("/") else "/"+path_value
        host=str(options.get("host") or "").strip()
        if host: ws["host"]=host
        if headers: ws["headers"]=headers
        heartbeat=int(options.get("heartbeat_period") or 0)
        if heartbeat<0 or heartbeat>3600:
            raise ProtocolError("WebSocket heartbeat must be 0-3600 seconds")
        if heartbeat: ws["heartbeatPeriod"]=heartbeat
        if bool(options.get("accept_proxy_protocol")): ws["acceptProxyProtocol"]=True
    elif method=="grpc":
        grpc=stream.setdefault("grpcSettings",{})
        service=str(options.get("service_name") or path_value.strip("/") or "")
        grpc["serviceName"]=service
        authority=str(options.get("authority") or "").strip()
        if authority: grpc["authority"]=authority
        if bool(options.get("multi_mode")): grpc["multiMode"]=True
    elif method=="httpupgrade":
        hu=stream.setdefault("httpupgradeSettings",{})
        hu["path"]=path_value if path_value.startswith("/") else "/"+path_value
        host=str(options.get("host") or "").strip()
        if host: hu["host"]=host
        if headers: hu["headers"]=headers
        if bool(options.get("accept_proxy_protocol")): hu["acceptProxyProtocol"]=True
    elif method=="xhttp":
        xh=stream.setdefault("xhttpSettings",{})
        xh["path"]=path_value if path_value.startswith("/") else "/"+path_value
        host=str(options.get("host") or "").strip()
        if host: xh["host"]=host
        mode=str(options.get("xhttp_mode") or options.get("mode") or "auto")
        if mode not in xray_inbound_builder_capabilities()["xhttp_modes"]:
            raise ProtocolError("invalid XHTTP mode")
        xh["mode"]=mode
        padding=str(options.get("x_padding_bytes") or "").strip()
        if padding: xh["xPaddingBytes"]=padding
    elif method=="mkcp":
        kcp=stream.setdefault("kcpSettings",{})
        ranges={
            "mtu":(576,1460,1350),
            "tti":(10,100,20),
            "uplink_capacity":(1,100000,5),
            "downlink_capacity":(1,100000,20),
            "cwnd_multiplier":(1,1000,1),
            "max_sending_window":(576,268435456,2097152),
        }
        keys={
            "mtu":"mtu","tti":"tti","uplink_capacity":"uplinkCapacity",
            "downlink_capacity":"downlinkCapacity","cwnd_multiplier":"cwndMultiplier",
            "max_sending_window":"maxSendingWindow",
        }
        for src,(low,high,default) in ranges.items():
            raw_value=options.get(src)
            value=default if raw_value in (None,"") else int(raw_value)
            if not low<=value<=high:
                raise ProtocolError(f"mKCP {src} is out of range")
            kcp[keys[src]]=value

    if security=="tls":
        alpn=options.get("alpn")
        if isinstance(alpn,str):
            alpn=[x.strip() for x in alpn.split(",") if x.strip()]
        if alpn:
            stream.setdefault("tlsSettings",{})["alpn"]=list(alpn)[:8]
    elif security=="reality":
        rs=stream.setdefault("realitySettings",{})
        fingerprint=str(options.get("fingerprint") or "chrome").strip()
        spider_x=str(options.get("spider_x") or "/")
        rs_meta=dict(reality_meta)
        rs_meta["fingerprint"]=fingerprint
        rs_meta["spider_x"]=spider_x
        short_id=str(options.get("short_id") or "").strip().lower()
        if short_id:
            if not re.fullmatch(r"[0-9a-f]{0,16}",short_id) or len(short_id)%2:
                raise ProtocolError("REALITY Short ID must be even-length hex up to 16 characters")
            rs["shortIds"]=[short_id]
            rs_meta["short_id"]=short_id
        xver=int(options.get("xver") or 0)
        if xver not in {0,1,2}:
            raise ProtocolError("REALITY xver must be 0, 1 or 2")
        rs["xver"]=xver
        reality_meta=rs_meta

    sock={}
    sock_map={
        "tcp_fast_open":"tcpFastOpen","tcp_no_delay":"tcpNoDelay",
        "tcp_congestion":"tcpcongestion","domain_strategy":"domainStrategy",
        "mark":"mark","interface":"interface","tproxy":"tproxy",
    }
    for src,dst in sock_map.items():
        value=options.get(src)
        if value in (None,"",False,0,"0"):
            continue
        if src in {"tcp_fast_open","tcp_no_delay"}:
            sock[dst]=bool(value)
        elif src=="mark":
            sock[dst]=int(value)
        else:
            sock[dst]=str(value)
    if sock:
        stream["sockopt"]=sock

    extra=options.get("extra_stream")
    if extra:
        if not isinstance(extra,dict):
            raise ProtocolError("Extra stream options must be a JSON object")
        _xray_deep_merge(stream,extra)
    stream["method"]=method
    stream["security"]=security
    return stream,reality_meta


def _xray_builder_sniffing(options):
    options=dict(options or {})
    enabled=bool(options.get("sniffing_enabled",True))
    override=options.get("sniffing_dest_override",["http","tls","quic"])
    if isinstance(override,str):
        override=[x.strip().lower() for x in override.split(",") if x.strip()]
    allowed={"http","tls","quic","fakedns","fakedns+others"}
    clean=[str(x).lower() for x in (override or []) if str(x).lower() in allowed]
    return {
        "enabled":enabled,
        "destOverride":clean,
        "routeOnly":bool(options.get("sniffing_route_only",True)),
        "metadataOnly":bool(options.get("sniffing_metadata_only",False)),
    }


def _xray_builder_client(protocol,name,credential,flow="",ss_method="aes-128-gcm"):
    if protocol in {"vless","vmess"}:
        item={"id":credential,"email":name,"level":0}
        if protocol=="vless" and flow:
            item["flow"]=flow
        settings={"clients":[item]}
        if protocol=="vless":settings["decryption"]="none"
        return settings,item
    if protocol=="trojan":
        item={"password":credential,"email":name,"level":0}
        return {"clients":[item]},item
    if protocol=="hysteria2":
        item={"auth":credential,"email":name,"level":0}
        return {"version":2,"users":[item]},item
    if protocol=="http":
        return {"accounts":[{"user":name,"pass":credential}]},None
    if protocol=="socks":
        return {"auth":"password","accounts":[{"user":name,"pass":credential}],"udp":True,"ip":"127.0.0.1"},None
    if protocol=="shadowsocks":
        return {"method":ss_method,"password":credential,"network":"tcp,udp"},None
    raise ProtocolError("unsupported Xray protocol")


def _xray_builder_credential(protocol,value=""):
    value=str(value or "").strip()
    if protocol in {"vless","vmess"}:
        if value:
            try:return str(uuid.UUID(value))
            except ValueError as exc:raise ProtocolError("VLESS/VMess credential must be a valid UUID") from exc
        return str(uuid.uuid4())
    if value:
        if len(value)<6 or len(value)>128:
            raise ProtocolError("client credential must be 6-128 characters")
        return value
    return secrets.token_urlsafe(24 if protocol=="hysteria2" else 18)


def _xray_builder_share_link(protocol,inbound,credential,name,endpoint,reality_meta=None,flow="",fingerprint="chrome",spider_x="/"):
    stream=inbound.get("streamSettings") or {}
    method=stream.get("method") or "raw"
    security=stream.get("security") or "none"
    host=_uri_host(endpoint)
    port=int(inbound.get("port") or 0)
    label=urllib.parse.quote(name,safe="")
    link_type={"raw":"tcp","websocket":"ws","mkcp":"kcp"}.get(method,method)
    q={"type":link_type,"security":security}
    if method=="raw":
        raw=stream.get("rawSettings") or {}
        header=raw.get("header") or {}
        if header.get("type")=="http":
            q["headerType"]="http"
            req=header.get("request") or {}
            paths=req.get("path") or []
            if paths:q["path"]=str(paths[0])
            hosts=((req.get("headers") or {}).get("Host") or [])
            if hosts:q["host"]=str(hosts[0])
    elif method=="websocket":
        ws=stream.get("wsSettings") or {}
        q["path"]=ws.get("path") or "/"
        if ws.get("host"):q["host"]=ws["host"]
    elif method=="grpc":
        gs=stream.get("grpcSettings") or {}
        q["serviceName"]=gs.get("serviceName") or ""
        if gs.get("authority"):q["authority"]=gs["authority"]
        if gs.get("multiMode"):q["mode"]="multi"
    elif method=="httpupgrade":
        hu=stream.get("httpupgradeSettings") or {}
        q["path"]=hu.get("path") or "/"
        if hu.get("host"):q["host"]=hu["host"]
    elif method=="xhttp":
        xh=stream.get("xhttpSettings") or {}
        q["path"]=xh.get("path") or "/"
        if xh.get("host"):q["host"]=xh["host"]
        if xh.get("mode"):q["mode"]=xh["mode"]
        if xh.get("xPaddingBytes"):q["x_padding_bytes"]=xh["xPaddingBytes"]
    if security=="tls":
        tls=stream.get("tlsSettings") or {}
        q["sni"]=tls.get("serverName") or ""
        alpn=tls.get("alpn") or []
        if alpn:q["alpn"]=",".join(str(x) for x in alpn)
    elif security=="reality":
        meta=dict(reality_meta or {})
        q.update({
            "sni":meta.get("server_name") or "","fp":fingerprint or meta.get("fingerprint") or "chrome",
            "pbk":meta.get("public_key") or "","sid":meta.get("short_id") or "",
            "spx":spider_x or meta.get("spider_x") or "/",
        })
        if flow:q["flow"]=flow
    query=urllib.parse.urlencode({k:v for k,v in q.items() if v not in (None,"")})
    if protocol=="vless":
        return f"vless://{credential}@{host}:{port}?{query}#{label}"
    if protocol=="trojan":
        return f"trojan://{urllib.parse.quote(credential,safe='')}@{host}:{port}?{query}#{label}"
    if protocol=="vmess":
        obj={
            "v":"2","ps":name,"add":endpoint,"port":str(port),"id":credential,
            "aid":"0","scy":"auto","net":link_type,"type":"none",
            "host":q.get("host",""),"path":q.get("path") or q.get("serviceName") or "",
            "tls":"tls" if security=="tls" else "",
        }
        if security=="tls":obj["sni"]=q.get("sni","")
        return "vmess://"+base64.b64encode(json.dumps(obj,separators=(",",":")).encode()).decode()
    if protocol=="hysteria2":
        tls=stream.get("tlsSettings") or {}
        hq={"sni":tls.get("serverName") or "","insecure":"0"}
        return f"hysteria2://{urllib.parse.quote(credential,safe='')}@{host}:{port}/?{urllib.parse.urlencode(hq)}#{label}"
    if protocol=="shadowsocks":
        settings=inbound.get("settings") or {}
        method=settings.get("method") or "aes-128-gcm"
        userinfo=base64.urlsafe_b64encode(f"{method}:{credential}".encode()).decode().rstrip("=")
        return f"ss://{userinfo}@{host}:{port}#{label}"
    if protocol=="http":
        return f"http://{urllib.parse.quote(name,safe='')}:{urllib.parse.quote(credential,safe='')}@{host}:{port}#{label}"
    if protocol=="socks":
        return f"socks://{urllib.parse.quote(name,safe='')}:{urllib.parse.quote(credential,safe='')}@{host}:{port}#{label}"
    return ""


def create_xray_full_inbound(spec):
    if not isinstance(spec,dict):
        raise ProtocolError("invalid Xray inbound payload")
    protocol=str(spec.get("protocol") or "").lower()
    transport,security=_xray_builder_validate_combo(protocol,spec.get("transport"),spec.get("security"))
    port=_validate_port(spec.get("port"))
    listen=_xray_builder_listen(spec.get("listen"))
    remark=str(spec.get("remark") or "").strip()
    if not remark or len(remark)>80:
        raise ProtocolError("Inbound remark is required and must be at most 80 characters")
    name=str(spec.get("name") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name):
        raise ProtocolError("client name must use letters, numbers, dot, dash or underscore")
    endpoint=_validate_endpoint_host(spec.get("endpoint"))
    flow=str(spec.get("flow") or "").strip()
    if flow not in {"","xtls-rprx-vision"}:
        raise ProtocolError("unsupported Xray flow")
    if flow and not (protocol=="vless" and ((transport=="tcp" and security in {"tls","reality"}) or transport=="xhttp")):
        raise ProtocolError("XTLS Vision is only available for supported VLESS transport/security combinations")
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    path=Path(_config_path() or "/usr/local/etc/xray/config.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try:data=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:raise ProtocolError(f"cannot parse existing Xray config: {exc}") from exc
    else:
        data=_xray_default_config(path)
    data=_ensure_xray_stats(data)
    inbounds=data.setdefault("inbounds",[])
    if not isinstance(inbounds,list):
        raise ProtocolError("invalid Xray inbounds collection")
    if any(isinstance(item,dict) and int(item.get("port") or -1)==port for item in inbounds):
        raise ProtocolError("this port is already used by another Xray inbound")
    transport_proto="udp" if transport in {"kcp","hysteria"} else "tcp"
    if _port_transport_in_use(port,transport_proto):
        owner=_port_owner_label(port,transport_proto)
        raise ProtocolError(f"{transport_proto.upper()}/{port} is already in use by {owner}")
    options=dict(spec.get("options") or {})
    options.setdefault("path",spec.get("path") or "/")
    options.setdefault("server_name",spec.get("server_name") or "")
    options.setdefault("reality_dest",spec.get("reality_dest") or "")
    stream,reality_meta=_xray_builder_stream(binary,protocol,transport,security,options)
    credential=_xray_builder_credential(protocol,spec.get("credential"))
    ss_method=str(spec.get("shadowsocks_method") or "aes-128-gcm")
    if protocol=="shadowsocks" and ss_method not in xray_inbound_builder_capabilities()["shadowsocks_methods"]:
        raise ProtocolError("unsupported Shadowsocks method in Makia builder")
    settings,client_obj=_xray_builder_client(protocol,name,credential,flow,ss_method)
    tag_base=re.sub(r"[^A-Za-z0-9_.-]+","-",remark).strip(".-")[:40] or protocol
    tag=f"makia-{tag_base}-{port}"
    if any(isinstance(item,dict) and item.get("tag")==tag for item in inbounds):
        tag=f"{tag}-{secrets.token_hex(2)}"
    inbound={
        "tag":tag,"listen":listen,"port":port,
        "protocol":"hysteria" if protocol=="hysteria2" else protocol,
        "settings":settings,"streamSettings":stream,
        "sniffing":_xray_builder_sniffing(options),
    }
    inbounds.append(inbound)
    tmp=_xray_temp_json_path(path,"inbound-builder")
    backup_dir=_backup_dir()
    backup=None
    if path.exists():
        backup=backup_dir/f"xray-builder-{int(time.time())}.json"
        shutil.copy2(path,backup)
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray did not become active after inbound apply")
        if not _wait_listener(port,transport_proto,timeout=8.0,interval=0.25):
            raise ProtocolError(f"Xray {transport_proto.upper()}/{port} did not become ready within 8 seconds")
        _ufw_allow_if_active(port,transport_proto,f"Xray {protocol}")
    except Exception:
        try:
            if tmp.exists():tmp.unlink()
            if backup and backup.exists():
                shutil.copy2(backup,path)
                _xray_secure_runtime_file(path)
                _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    fingerprint=str(options.get("fingerprint") or "chrome")
    spider_x=str(options.get("spider_x") or "/")
    share=_xray_builder_share_link(protocol,inbound,credential,name,endpoint,reality_meta,flow,fingerprint,spider_x)
    return {
        "protocol":protocol,"tag":tag,"remark":remark,"listen":listen,"port":port,
        "name":name,"credential":credential,"transport":stream.get("method"),
        "security":stream.get("security"),"share_link":share,
        "reality":reality_meta,"backup":str(backup) if backup else None,
        "inbound":inbound,
    }


def create_xray_inbound(protocol, port, name, endpoint, transport="tcp", security="none", path_value="/", server_name="", reality_dest="", manual=False):
    protocol=(protocol or "").lower()
    if protocol not in {"vless","vmess","trojan","shadowsocks","hysteria2","http","socks"}:
        raise ProtocolError("unsupported Xray quick protocol")
    port=_validate_port(port)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid client name")
    endpoint=_validate_endpoint_host(endpoint)
    transport,security=(
        _validate_xray_manual_combo(protocol,transport,security)
        if manual else
        _validate_xray_guided_combo(protocol,transport,security)
    )
    if (not manual) and protocol in {"vless","trojan"} and security=="none" and not _endpoint_is_private(endpoint):
        raise ProtocolError(f"{protocol.upper()} with security=none is intentionally blocked in Guided mode on public endpoints; switch to Manual/Expert mode if you explicitly want an unencrypted profile")
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    config_path=_config_path() or "/usr/local/etc/xray/config.json"
    path=Path(config_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ProtocolError(f"cannot parse existing Xray config: {exc}") from exc
    else:
        data=_xray_default_config(path)
    data=_ensure_xray_stats(data)
    inbounds=data.setdefault("inbounds",[])
    if not isinstance(inbounds,list):
        raise ProtocolError("invalid Xray inbounds collection")
    if any(isinstance(i,dict) and int(i.get("port") or -1)==port for i in inbounds):
        raise ProtocolError("this port is already used by another Xray inbound")
    port_transports={"udp"} if protocol=="hysteria2" or str(transport or "").lower() in {"kcp","mkcp"} else ({"tcp","udp"} if protocol in {"shadowsocks","socks"} else {"tcp"})
    if any(_port_transport_in_use(port,item) for item in port_transports):
        raise ProtocolError("this port/transport is already in use on the server")
    tag=f"makia-{protocol}-{port}"
    credential=None
    client_obj=None
    xray_protocol="hysteria" if protocol=="hysteria2" else protocol
    if protocol in {"vless","vmess"}:
        credential=str(uuid.uuid4())
        client_obj={"id":credential,"email":name,"level":0}
        if protocol=="vless":
            settings={"clients":[client_obj],"decryption":"none"}
        else:
            settings={"clients":[client_obj]}
    elif protocol=="trojan":
        credential=secrets.token_urlsafe(18)
        client_obj={"password":credential,"email":name,"level":0}
        settings={"clients":[client_obj]}
    elif protocol=="hysteria2":
        credential=secrets.token_urlsafe(24)
        client_obj={"auth":credential,"email":name,"level":0}
        settings={"version":2,"users":[client_obj]}
        transport="hysteria"
        security="tls"
    elif protocol=="http":
        credential=secrets.token_urlsafe(12)
        settings={"accounts":[{"user":name,"pass":credential}]}
        transport="tcp"; security="none"
    elif protocol=="socks":
        credential=secrets.token_urlsafe(12)
        settings={"auth":"password","accounts":[{"user":name,"pass":credential}],"udp":True,"ip":"127.0.0.1"}
        transport="tcp"; security="none"
    else:
        credential=secrets.token_urlsafe(18)
        settings={"method":"aes-128-gcm","password":credential,"network":"tcp,udp"}
    if protocol in {"http","socks"}:
        stream={"method":"raw","security":"none"}
        reality_meta={}
    elif protocol=="hysteria2":
        sni=(server_name or "").strip().lower()
        if not sni:
            raise ProtocolError("Hysteria2 requires a TLS domain/SNI")
        cert,key=_xray_materialize_tls(sni)
        stream={
            "method":"hysteria",
            "security":"tls",
            "hysteriaSettings":{"version":2},
            "tlsSettings":{
                "serverName":sni,
                "alpn":["h3"],
                "certificates":[{"certificateFile":str(cert),"keyFile":str(key)}],
            },
        }
        reality_meta={}
    else:
        stream,reality_meta=_build_xray_stream(binary,protocol,transport,security,path_value,server_name,reality_dest)
    if protocol=="vless" and security=="reality" and stream.get("method")=="raw":
        client_obj["flow"]="xtls-rprx-vision"
    inbound={
        "tag":tag,
        "listen":"0.0.0.0",
        "port":port,
        "protocol":xray_protocol,
        "settings":settings,
        "streamSettings":stream,
        "sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"routeOnly":True},
    }
    inbounds.append(inbound)
    tmp=_xray_temp_json_path(path,"create")
    backup_dir=_backup_dir()
    backup=None
    if path.exists():
        backup=backup_dir/f"xray-{int(time.time())}.json"
        shutil.copy2(path,backup)
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray did not become active after restart")
        firewall_proto="udp" if protocol=="hysteria2" or stream.get("method")=="mkcp" else "tcp"
        if not _wait_listener(port,firewall_proto,timeout=8.0,interval=0.25):
            detail=""
            try:
                p=subprocess.run(
                    ["systemctl","status","xray","--no-pager","--lines=12"],
                    text=True,capture_output=True,timeout=8,check=False
                )
                detail=(p.stdout or p.stderr or "").strip().replace("\n"," | ")
            except Exception:
                detail=""
            suffix=f"; status: {detail[:700]}" if detail else ""
            raise ProtocolError(
                f"Xray service is active but {firewall_proto.upper()}/{port} did not become ready within 8 seconds"
                f"{suffix}; the previous config has been restored"
            )
        _ufw_allow_if_active(port,firewall_proto,f"Xray {protocol}")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            if backup and backup.exists():
                shutil.copy2(backup,path)
                _xray_secure_runtime_file(path)
                _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    label=urllib.parse.quote(name,safe="")
    host=_uri_host(endpoint)
    method=stream.get("method","raw")
    link_type={"raw":"tcp","websocket":"ws","mkcp":"kcp"}.get(method,method)
    q={"type":link_type,"security":security}
    if method=="websocket": q["path"]=path_value
    elif method=="grpc": q["serviceName"]=path_value.strip("/")
    elif method in {"httpupgrade","xhttp"}: q["path"]=path_value
    if security=="tls":
        q["sni"]=(server_name or "").strip().lower()
    elif security=="reality":
        q.update({"sni":reality_meta["server_name"],"fp":"chrome","pbk":reality_meta["public_key"],"sid":reality_meta["short_id"]})
        if protocol=="vless" and method=="raw": q["flow"]="xtls-rprx-vision"
    query=urllib.parse.urlencode(q)
    if protocol=="hysteria2":
        hq={"sni":(server_name or "").strip().lower(),"insecure":"0"}
        link=f"hysteria2://{urllib.parse.quote(credential,safe='')}@{host}:{port}/?{urllib.parse.urlencode(hq)}#{label}"
    elif protocol=="vless":
        link=f"vless://{credential}@{host}:{port}?{query}#{label}"
    elif protocol=="trojan":
        link=f"trojan://{urllib.parse.quote(credential,safe='')}@{host}:{port}?{query}#{label}"
    elif protocol=="vmess":
        obj={"v":"2","ps":name,"add":host,"port":str(port),"id":credential,"aid":"0","scy":"auto","net":link_type,"type":"none","host":"","path":path_value if method!="grpc" else "","tls":"tls" if security=="tls" else ""}
        if security=="tls": obj["sni"]=(server_name or "").strip().lower()
        if method=="grpc": obj["path"]=path_value.strip("/")
        link="vmess://"+base64.b64encode(json.dumps(obj,separators=(",",":")).encode()).decode()
    elif protocol=="http":
        link=f"http://{urllib.parse.quote(name,safe='')}:{urllib.parse.quote(credential,safe='')}@{host}:{port}#{label}"
    elif protocol=="socks":
        link=f"socks://{urllib.parse.quote(name,safe='')}:{urllib.parse.quote(credential,safe='')}@{host}:{port}#{label}"
    else:
        userinfo=base64.urlsafe_b64encode(f"aes-128-gcm:{credential}".encode()).decode().rstrip("=")
        link=f"ss://{userinfo}@{host}:{port}#{label}"
    return {
        "protocol":protocol,"tag":tag,"port":port,"name":name,"credential":credential,
        "transport":method,"security":security,"share_link":link,"backup":str(backup) if backup else None,
        "reality":reality_meta,"manual":bool(manual),
    }

def create_xray_tunnel(listen_port, target_host, target_port, network="tcp,udp", name="tunnel"):
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    listen_port=_validate_port(listen_port)
    target_port=_validate_port(target_port)
    network=(network or "tcp,udp").lower()
    if network not in {"tcp","udp","tcp,udp"}:
        raise ProtocolError("network must be tcp, udp or tcp,udp")
    target_host=_validate_endpoint_host(target_host,"target host")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid tunnel name")
    requested_transports={"tcp","udp"} if network=="tcp,udp" else {network}
    if any(_port_transport_in_use(listen_port,item) for item in requested_transports):
        raise ProtocolError("listen port/transport is already in use")
    config_path=_config_path() or "/usr/local/etc/xray/config.json"
    path=Path(config_path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try: data=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: raise ProtocolError(f"cannot parse existing Xray config: {exc}") from exc
    else:
        data=_xray_default_config(path)
    inbounds=data.setdefault("inbounds",[])
    if not isinstance(inbounds,list):
        raise ProtocolError("invalid Xray inbounds collection")
    if any(isinstance(i,dict) and int(i.get("port") or -1)==listen_port for i in inbounds):
        raise ProtocolError("listen port already exists in Xray config")
    tag=f"makia-tunnel-{name}-{listen_port}"
    inbounds.append({
        "tag":tag,
        "listen":"0.0.0.0",
        "port":listen_port,
        "protocol":"dokodemo-door",
        "settings":{
            "address":target_host,
            "port":target_port,
            "network":network,
            "followRedirect":False,
        },
    })
    tmp=_xray_temp_json_path(path,"tunnel")
    backup_dir=_backup_dir()
    backup=None
    if path.exists():
        backup=backup_dir/f"xray-tunnel-{int(time.time())}.json"
        shutil.copy2(path,backup)
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray did not become active after tunnel apply")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            if backup and backup.exists():
                shutil.copy2(backup,path)
                _xray_secure_runtime_file(path)
                _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"tag":tag,"listen_port":listen_port,"target_host":target_host,"target_port":target_port,"network":network,"backup":str(backup) if backup else None}


def remove_xray_inbound(inbound_tag):
    binary=_binary()
    config_path=_config_path()
    if not binary or not config_path:
        raise ProtocolError("Xray core/config is not available")
    path=Path(config_path)
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProtocolError(f"cannot parse Xray config: {exc}") from exc
    inbounds=data.get("inbounds")
    if not isinstance(inbounds,list):
        raise ProtocolError("invalid Xray inbounds collection")
    before=len(inbounds)
    data["inbounds"]=[x for x in inbounds if not (isinstance(x,dict) and x.get("tag")==inbound_tag)]
    if len(data["inbounds"])==before:
        raise ProtocolError("Xray inbound not found")
    backup_dir=_backup_dir()
    backup=backup_dir/f"xray-remove-{int(time.time())}.json"
    shutil.copy2(path,backup)
    tmp=_xray_temp_json_path(path,"remove")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray did not become active after inbound removal")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            shutil.copy2(backup,path)
            _xray_secure_runtime_file(path)
            _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"removed":True,"tag":inbound_tag,"backup":str(backup)}

def disable_xray_client(inbound_tag,email):
    binary=_binary()
    config_path=_config_path()
    if not binary or not config_path:
        raise ProtocolError("Xray core/config is not available")
    path=Path(config_path)
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProtocolError(f"cannot parse Xray config: {exc}") from exc
    changed=False
    for inbound in data.get("inbounds",[]) if isinstance(data,dict) else []:
        if not isinstance(inbound,dict) or inbound.get("tag")!=inbound_tag:
            continue
        settings=inbound.get("settings") or {}
        clients=settings.get("clients")
        users=settings.get("users")
        if isinstance(clients,list):
            before=len(clients)
            settings["clients"]=[x for x in clients if not (isinstance(x,dict) and x.get("email")==email)]
            changed=len(settings["clients"])!=before
        elif isinstance(users,list):
            before=len(users)
            settings["users"]=[x for x in users if not (isinstance(x,dict) and x.get("email")==email)]
            changed=len(settings["users"])!=before
        elif isinstance(settings.get("accounts"),list):
            accounts=settings["accounts"]
            before=len(accounts)
            settings["accounts"]=[x for x in accounts if not (isinstance(x,dict) and x.get("user")==email)]
            changed=len(settings["accounts"])!=before
    if not changed:
        return {"disabled":False,"reason":"client not found in config"}
    backup_dir=_backup_dir()
    backup=backup_dir/f"xray-policy-{int(time.time())}.json"
    shutil.copy2(path,backup)
    tmp=_xray_temp_json_path(path,"policy")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray failed after client disable")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            shutil.copy2(backup,path)
            _xray_secure_runtime_file(path)
            _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"disabled":True,"backup":str(backup)}
def enable_xray_client(inbound_tag,email,protocol,credential):
    binary=_binary()
    config_path=_config_path()
    if not binary or not config_path:
        raise ProtocolError("Xray core/config is not available")
    path=Path(config_path)
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProtocolError(f"cannot parse Xray config: {exc}") from exc
    target=None
    for inbound in data.get("inbounds",[]) if isinstance(data,dict) else []:
        if isinstance(inbound,dict) and inbound.get("tag")==inbound_tag:
            target=inbound
            break
    if not target:
        raise ProtocolError("target Xray inbound no longer exists")
    settings=target.setdefault("settings",{})
    protocol=(protocol or "").lower()
    if protocol=="vless":
        clients=settings.setdefault("clients",[])
        if any(isinstance(x,dict) and x.get("email")==email for x in clients):
            return {"enabled":True,"already_present":True}
        item={"id":credential,"email":email,"level":0}
        stream=target.get("streamSettings") or {}
        method=stream.get("method") or stream.get("network")
        if stream.get("security")=="reality" and method in {"raw","tcp"}:
            item["flow"]="xtls-rprx-vision"
        clients.append(item)
    elif protocol=="vmess":
        clients=settings.setdefault("clients",[])
        if any(isinstance(x,dict) and x.get("email")==email for x in clients):
            return {"enabled":True,"already_present":True}
        clients.append({"id":credential,"email":email,"level":0})
    elif protocol=="trojan":
        clients=settings.setdefault("clients",[])
        if any(isinstance(x,dict) and x.get("email")==email for x in clients):
            return {"enabled":True,"already_present":True}
        clients.append({"password":credential,"email":email,"level":0})
    elif protocol=="hysteria2":
        users=settings.setdefault("users",[])
        if any(isinstance(x,dict) and x.get("email")==email for x in users):
            return {"enabled":True,"already_present":True}
        users.append({"auth":credential,"email":email,"level":0})
    elif protocol=="http":
        accounts=settings.setdefault("accounts",[])
        if any(isinstance(x,dict) and x.get("user")==email for x in accounts):
            return {"enabled":True,"already_present":True}
        accounts.append({"user":email,"pass":credential})
    elif protocol=="socks":
        settings["auth"]="password"; settings["udp"]=True; settings.setdefault("ip","127.0.0.1")
        accounts=settings.setdefault("accounts",[])
        if any(isinstance(x,dict) and x.get("user")==email for x in accounts):
            return {"enabled":True,"already_present":True}
        accounts.append({"user":email,"pass":credential})
    else:
        raise ProtocolError("automatic re-enable is not supported for this protocol")

    backup_dir=_backup_dir()
    backup=backup_dir/f"xray-enable-{int(time.time())}.json"
    shutil.copy2(path,backup)
    tmp=_xray_temp_json_path(path,"enable")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray failed after client enable")
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            shutil.copy2(backup,path)
            _xray_secure_runtime_file(path)
            _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"enabled":True,"backup":str(backup)}


def reset_xray_client_traffic(email):
    return xray_client_traffic(email,reset=True)

def read_xray_config():
    path=_config_path()
    if not path:
        raise ProtocolError("Xray config file is not available")
    try:
        raw=Path(path).read_text(encoding="utf-8")
        data=json.loads(raw)
    except Exception as exc:
        raise ProtocolError(f"cannot read Xray config: {exc}") from exc
    return {"path":path,"config":data}

def validate_xray_config(data):
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    if not isinstance(data,dict):
        raise ProtocolError("Xray config must be a JSON object")
    config_path=_config_path() or "/usr/local/etc/xray/config.json"
    path=Path(config_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=_xray_temp_json_path(path,"validate")
    try:
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.chmod(tmp,0o600)
        _xray_test_config(binary,tmp)
        return {"ok":True}
    finally:
        try:
            if tmp.exists(): tmp.unlink()
        except Exception:
            pass

def _xray_firewall_rules(data):
    rules=[]
    for inbound in data.get("inbounds",[]) if isinstance(data,dict) else []:
        if not isinstance(inbound,dict):
            continue
        listen=str(inbound.get("listen") or "0.0.0.0").strip().lower()
        if listen in {"127.0.0.1","localhost","::1"}:
            continue
        try:
            port=_validate_port(inbound.get("port"))
        except Exception:
            continue
        protocol=str(inbound.get("protocol") or "xray").lower()
        settings=inbound.get("settings") if isinstance(inbound.get("settings"),dict) else {}
        stream=inbound.get("streamSettings") if isinstance(inbound.get("streamSettings"),dict) else {}
        network=str(stream.get("network") or stream.get("method") or settings.get("network") or "").lower()
        transports=set()
        if protocol in {"hysteria","hysteria2"} or network in {"kcp","mkcp","quic","hysteria","hysteria2"}:
            transports.add("udp")
        elif network in {"tcp,udp","udp,tcp"}:
            transports.update({"tcp","udp"})
        elif protocol=="dokodemo-door" and "udp" in str(settings.get("network") or "").lower():
            transports.update({"tcp","udp"} if "tcp" in str(settings.get("network") or "").lower() else {"udp"})
        else:
            transports.add("tcp")
        for proto in sorted(transports):
            rules.append((port,proto,f"Xray {protocol}"))
    return sorted(set(rules))

def apply_xray_config(data):
    binary=_binary()
    if not binary:
        raise ProtocolError("Xray core is not installed")
    if not isinstance(data,dict):
        raise ProtocolError("Xray config must be a JSON object")
    # Advanced JSON may legitimately reference Certbot's live paths, whose
    # private-key permissions are intentionally not readable by the Xray
    # service user. Materialize only those known Let's Encrypt references.
    data=json.loads(json.dumps(data))
    _rewrite_letsencrypt_certificates(data)
    config_path=_config_path() or "/usr/local/etc/xray/config.json"
    path=Path(config_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=_xray_temp_json_path(path,"apply")
    backup_dir=_backup_dir()
    backup=None
    if path.exists():
        backup=backup_dir/f"xray-manual-{int(time.time())}.json"
        shutil.copy2(path,backup)
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(tmp,0o600)
    try:
        _xray_test_config(binary,tmp)
        os.replace(tmp,path)
        _xray_secure_runtime_file(path)
        _xray_test_config_as_service(binary,path)
        _run(["systemctl","restart","xray"],timeout=30)
        if not _active("xray"):
            raise ProtocolError("Xray failed to become active")
        for fw_port,fw_proto,fw_label in _xray_firewall_rules(data):
            _ufw_allow_if_active(fw_port,fw_proto,fw_label)
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
            if backup and backup.exists():
                shutil.copy2(backup,path)
                _run(["systemctl","restart","xray"],timeout=30)
        except Exception:
            pass
        raise
    return {"ok":True,"path":str(path),"backup":str(backup) if backup else None}


def status():
    return xray_status()
