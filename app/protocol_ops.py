import base64
import hashlib
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
XRAY_VALIDATED_VERSION="v26.10.21"
# Immutable installer commit verified for explicit --version and -u nobody arguments.
XRAY_INSTALLER_COMMIT="e741a4f56d368afbb9e5be3361b40c4552d3710d"
XRAY_TLS_DIR=Path("/usr/local/etc/xray/tls")
WG_DIR=Path("/etc/wireguard")
OVPN_DIR=Path("/etc/openvpn")
OVPN_EASYRSA=OVPN_DIR/"easy-rsa"
IKEV2_CONF=Path("/etc/ipsec.conf")
IKEV2_SECRETS=Path("/etc/ipsec.secrets")
IKEV2_ENV=Path("/etc/makia-vps-manager/ikev2.env")
L2TP_ENV=Path("/etc/makia-vps-manager/l2tp.env")
L2TP_CONF=Path("/etc/xl2tpd/xl2tpd.conf")
L2TP_PPP_OPTIONS=Path("/etc/ppp/options.xl2tpd")
L2TP_CHAP=Path("/etc/ppp/chap-secrets")
STUNNEL_MAKIA_CONF=Path("/etc/stunnel/makia-openvpn.conf")
STUNNEL_MAKIA_SERVICE="makia-stealth"
WSTUNNEL_ENV=Path("/etc/makia-vps-manager/wstunnel.env")
WSTUNNEL_SERVICE="makia-wstunnel"
OVPN_WSTUNNEL_ENV=Path("/etc/makia-vps-manager/openvpn-wstunnel.env")
OVPN_WSTUNNEL_SERVICE="makia-openvpn-wstunnel"
OVPN_WSTUNNEL_BACKEND_CONF=OVPN_DIR/"server/makia-ws.conf"
OVPN_WSTUNNEL_BACKEND_SERVICE="openvpn-server@makia-ws"
OVPN_WSTUNNEL_NGINX=Path("/etc/nginx/sites-available/makia-vps-manager")
OVPN_WSTUNNEL_NGINX_BEGIN="# BEGIN MAKIA OPENVPN WSTUNNEL"
OVPN_WSTUNNEL_NGINX_END="# END MAKIA OPENVPN WSTUNNEL"
OVPN_WSTUNNEL_LIMITS_BEGIN="# BEGIN MAKIA WSTUNNEL EDGE LIMITS"
OVPN_WSTUNNEL_LIMITS_END="# END MAKIA WSTUNNEL EDGE LIMITS"
OVPN_TCP_FALLBACK_CONF=OVPN_DIR/"server/makia-tcp.conf"
OVPN_TCP_FALLBACK_SERVICE="openvpn-server@makia-tcp"
OVPN_CLIENT_POLICY_DIR=OVPN_DIR/"server/makia-client-policy"
OVPN_MANAGEMENT_SOCKET=Path("/run/makia-openvpn-management.sock")
OVPN_WSTUNNEL_MANAGEMENT_SOCKET=Path("/run/makia-openvpn-wstunnel-management.sock")
OVPN_POLICY_MARKER="# Managed by Makia Client Platform"


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

def _xray_tls_certificate_issue(domain):
    """Return a safe, actionable reason when a Let's Encrypt TLS identity cannot be used."""
    domain=str(domain or "").strip().lower().rstrip(".")
    if not domain:
        return "TLS requires a DNS hostname with a valid certificate; an IP address is not an SNI domain."
    try:
        ipaddress.ip_address(domain)
        return "TLS SNI must be a DNS hostname, not an IP address. Select a domain with a valid certificate."
    except ValueError:
        pass
    try:
        domain=_validate_endpoint_host(domain,"TLS domain")
    except ProtocolError as exc:
        return str(exc)
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    if not cert.is_file() or not key.is_file():
        return f"No Let's Encrypt certificate/key was found for TLS domain {domain}. Issue a certificate first."
    try:
        valid=subprocess.run(["openssl","x509","-in",str(cert),"-noout","-checkend","0"],capture_output=True,text=True,timeout=8,check=False)
        if valid.returncode!=0:
            return f"The TLS certificate for {domain} is expired or not yet valid. Renew it before creating this inbound."
        hostname=subprocess.run(["openssl","x509","-in",str(cert),"-noout","-checkhost",domain],capture_output=True,text=True,timeout=8,check=False)
        if hostname.returncode!=0:
            return f"The TLS certificate does not cover {domain}. Choose a domain included in the certificate SAN."
        cert_pub=subprocess.run(["openssl","x509","-in",str(cert),"-pubkey","-noout"],capture_output=True,text=True,timeout=8,check=False)
        key_pub=subprocess.run(["openssl","pkey","-in",str(key),"-pubout"],capture_output=True,text=True,timeout=8,check=False)
        if cert_pub.returncode!=0 or key_pub.returncode!=0 or cert_pub.stdout.strip()!=key_pub.stdout.strip():
            return f"The TLS certificate and private key for {domain} do not match. Reissue the certificate before creating this inbound."
    except (OSError,subprocess.SubprocessError) as exc:
        return f"Unable to validate the TLS certificate for {domain}: {type(exc).__name__}."
    return ""


def xray_tls_certificate_inventory():
    """Return valid, matching Let's Encrypt certificate domains available to Xray."""
    root=Path("/etc/letsencrypt/live")
    if not root.is_dir():
        return []
    domains=[]
    try:
        entries=sorted(root.iterdir(),key=lambda x:x.name.lower())
    except OSError:
        return []
    for entry in entries:
        domain=entry.name.lower().rstrip(".")
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",domain):
            continue
        if not _xray_tls_certificate_issue(domain):
            domains.append(domain)
    return domains


def xray_tls_domain_inventory():
    """List valid certificate domains that resolve directly to this VPS."""
    local4={x for x in _local_ipv4_candidates() if ipaddress.ip_address(x).is_global}
    local6=set(_local_ipv6_candidates())
    domains=[]
    for domain in xray_tls_certificate_inventory():
        try:
            resolved4=sorted({x[4][0] for x in socket.getaddrinfo(domain,None,socket.AF_INET,socket.SOCK_STREAM)})
        except OSError:
            resolved4=[]
        if not resolved4 or not local4 or not set(resolved4).issubset(local4):
            continue
        try:
            resolved6=sorted({str(ipaddress.IPv6Address(x[4][0].split("%",1)[0])) for x in socket.getaddrinfo(domain,None,socket.AF_INET6,socket.SOCK_STREAM)})
        except OSError:
            resolved6=[]
        if resolved6 and (not local6 or not set(resolved6).issubset(local6)):
            continue
        domains.append(domain)
    return domains


def _xray_prepare_tls_root():
    """Allow the Xray service identity to traverse the TLS root without listing it."""
    root=Path(XRAY_TLS_DIR)
    root.mkdir(parents=True,exist_ok=True,mode=0o710)
    user=_xray_service_user()
    if os.geteuid()==0 and user not in {"","root"}:
        try:
            info=pwd.getpwnam(user)
            os.chown(root,0,info.pw_gid)
            os.chmod(root,0o710)
        except (KeyError,OSError) as exc:
            raise ProtocolError(f"unable to prepare Xray TLS directory permissions for {user}: {exc}") from exc
    else:
        os.chmod(root,0o700)
    return root


def _xray_materialize_tls(domain):
    domain=str(domain or "").strip().lower().rstrip(".")
    issue=_xray_tls_certificate_issue(domain)
    if issue:
        available=xray_tls_domain_inventory()
        suffix=(" Available TLS domains on this VPS: "+", ".join(available)+".") if available else " Configure a domain that points directly to this VPS and issue its certificate."
        raise ProtocolError(issue+suffix)
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    root=_xray_prepare_tls_root()
    target=root/domain
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
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
        "outbound_count":0,"outbound_ready":False,
        "cert_sync_hook":Path("/etc/letsencrypt/renewal-hooks/deploy/makia-xray-sync").is_file(),
    }
    if binary:
        try:
            p=subprocess.run([binary,"version"],text=True,capture_output=True,timeout=5,check=False)
            result["version"]=(p.stdout or p.stderr).splitlines()[0][:160] if (p.stdout or p.stderr) else ""
            result["validated_version"]="26.10.21" in result["version"]
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
    try:
        current=json.loads(Path(config).read_text(encoding="utf-8")) if config else {}
        outbounds=current.get("outbounds") or []
        result["outbound_count"]=len(outbounds) if isinstance(outbounds,list) else 0
        result["outbound_ready"]=bool(result["outbound_count"])
    except Exception:
        pass
    journal=(result["journal"] or "").lower()
    if not result["outbound_ready"]:
        result["hints"].append("هیچ Outbound در کانفیگ Xray تعریف نشده؛ اتصال ممکن است برقرار شود اما ترافیک به اینترنت مسیر نداشته باشد.")
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
        result["hints"].append("نسخه Core نصب‌شده با نسخه‌ای که Makia در CI اعتبارسنجی می‌کند (26.10.21) متفاوت است.")
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
                stream=item.get("streamSettings") or {}
                inbounds.append({
                    "tag":item.get("tag") or "",
                    "protocol":protocol,
                    "listen":item.get("listen") or "0.0.0.0",
                    "port":item.get("port"),
                    "clients":client_count,
                    "transport":stream.get("network") or stream.get("method") or "raw",
                    "security":stream.get("security") or "none",
                    "sniffing":bool((item.get("sniffing") or {}).get("enabled")),
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


def _vpn_network_status(cidr,service_name):
    network_active=_active(service_name)
    try:
        ip_forward=Path("/proc/sys/net/ipv4/ip_forward").read_text(encoding="utf-8").strip()=="1"
    except OSError:
        ip_forward=False
    uplink=""
    try:
        route=_run(["ip","-4","route","show","default"],timeout=5)
        match=re.search(r"(?m)^default\s+.*?\bdev\s+(\S+)",route)
        if match: uplink=match.group(1)
    except ProtocolError:
        pass
    forward_in=_iptables_check(["-C","FORWARD","-s",cidr,"-j","ACCEPT"]) if cidr else False
    forward_out=_iptables_check(["-C","FORWARD","-d",cidr,"-m","state","--state","ESTABLISHED,RELATED","-j","ACCEPT"]) if cidr else False
    nat=_iptables_check(["-t","nat","-C","POSTROUTING","-s",cidr,"-o",uplink,"-j","MASQUERADE"]) if cidr and uplink else False
    return {
        "network_active":network_active,"ip_forward":ip_forward,"uplink":uplink,
        "forward_in":forward_in,"forward_out":forward_out,"nat":nat,
        "forwarding_ready":bool(network_active and ip_forward and forward_in and forward_out and nat),
    }


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
    listeners={"500_udp":_listener_present(500,"udp"),"4500_udp":_listener_present(4500,"udp")}
    cert_path=Path("/etc/ipsec.d/certs/makia-ikev2.pem")
    key_path=Path("/etc/ipsec.d/private/makia-ikev2.key")
    cert_valid=False; cert_matches_domain=False; cert_key_matches=False; cert_error=""
    if cert_path.is_file() and key_path.is_file() and domain:
        try:
            valid=subprocess.run(["openssl","x509","-in",str(cert_path),"-noout","-checkend","0"],capture_output=True,text=True,timeout=8,check=False)
            host=subprocess.run(["openssl","x509","-in",str(cert_path),"-noout","-checkhost",domain],capture_output=True,text=True,timeout=8,check=False)
            cert_pub=subprocess.run(["openssl","x509","-in",str(cert_path),"-pubkey","-noout"],capture_output=True,text=True,timeout=8,check=False)
            key_pub=subprocess.run(["openssl","pkey","-in",str(key_path),"-pubout"],capture_output=True,text=True,timeout=8,check=False)
            cert_valid=valid.returncode==0
            cert_matches_domain=host.returncode==0
            cert_key_matches=cert_pub.returncode==0 and key_pub.returncode==0 and cert_pub.stdout.strip()==key_pub.stdout.strip()
            if not cert_valid: cert_error="IKEv2 certificate is expired or not yet valid."
            elif not cert_matches_domain: cert_error="IKEv2 certificate SAN does not match the configured Remote ID."
            elif not cert_key_matches: cert_error="IKEv2 certificate and private key do not match."
        except (OSError,subprocess.SubprocessError) as exc:
            cert_error="Unable to inspect IKEv2 certificate: "+type(exc).__name__
    else:
        cert_error="IKEv2 server certificate or private key is missing."
    network=_vpn_network_status(cidr,"makia-ikev2-network") if cidr else _vpn_network_status("","makia-ikev2-network")
    ready=bool(installed and configured and active and all(listeners.values()) and cert_valid and cert_matches_domain and cert_key_matches and network["forwarding_ready"])
    return {
        "installed":installed,"configured":configured,"service_active":active,
        "listeners":listeners,"domain":domain,"cidr":cidr,"users":users,
        "certificate_valid":cert_valid,"certificate_matches_domain":cert_matches_domain,
        "certificate_key_matches":cert_key_matches,"certificate_error":cert_error,
        **network,"ready":ready,
    }


def stealth_status():
    installed=_installed("stunnel4") or _installed("stunnel")
    active=_active(STUNNEL_MAKIA_SERVICE)
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


def get_ikev2_user_credentials(name):
    """Return the current managed EAP password for internal encrypted export only."""
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,48}",name) or not IKEV2_SECRETS.exists():
        return None
    marker=re.compile(r"#\s*makia-eap:"+re.escape(name)+r"\s*$")
    for line in IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore").splitlines():
        if not marker.search(line):
            continue
        match=re.match(r"^\s*"+re.escape(name)+r"\s*:\s*EAP\s+\"([^\"]*)\"\s+#\s*makia-eap:"+re.escape(name)+r"\s*$",line)
        if match:
            return {"name":name,"password":match.group(1)}
    return None


def _l2tp_environment():
    data={}
    if L2TP_ENV.exists():
        for line in L2TP_ENV.read_text(encoding="utf-8",errors="ignore").splitlines():
            s=line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key,value=s.split("=",1)
            data[key.strip()]=value.strip().strip('"').strip("'")
    return data


def _l2tp_shared_psk():
    env=_l2tp_environment()
    psk=str(env.get("MAKIA_L2TP_PSK") or "")
    if not psk or not IKEV2_SECRETS.exists():
        raise ProtocolError("L2TP/IPsec pre-shared key is not configured; run sudo makia-upgrade")
    matches=[]
    for line in IKEV2_SECRETS.read_text(encoding="utf-8",errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "PSK" not in line.upper():
            continue
        match=re.search(r"\bPSK\s+(?:\"([^\"]+)\"|([^\s]+))",line,re.I)
        if match:
            matches.append(match.group(1) or match.group(2))
    if psk not in matches:
        raise ProtocolError("L2TP/IPsec pre-shared key does not match the active strongSwan configuration")
    return psk


def _l2tp_ppp_option_issues(ppp_text):
    issues=[]
    if not str(ppp_text or "").strip():
        issues.append("PPP options file /etc/ppp/options.xl2tpd is missing or empty.")
    if re.search(r"(?m)^\s*lock\s*(?:#.*)?$",str(ppp_text or "")):
        issues.append("The active xl2tpd/pppd session rejected the 'lock' option and exited before PPP authentication; remove it from options.xl2tpd.")
    return issues


def l2tp_status():
    env=_l2tp_environment()
    ipsec_text=IKEV2_CONF.read_text(encoding="utf-8",errors="ignore") if IKEV2_CONF.exists() else ""
    l2tp_text=L2TP_CONF.read_text(encoding="utf-8",errors="ignore") if L2TP_CONF.exists() else ""
    ppp_text=L2TP_PPP_OPTIONS.read_text(encoding="utf-8",errors="ignore") if L2TP_PPP_OPTIONS.exists() else ""
    ppp_issues=_l2tp_ppp_option_issues(ppp_text)
    ppp_options_ready=not ppp_issues
    psk_ready=False
    try:
        _l2tp_shared_psk()
        psk_ready=True
    except ProtocolError:
        pass
    users=len(list_l2tp_users()) if L2TP_CHAP.exists() else 0
    ike=ikev2_status()
    listeners={
        "1701_udp":_listener_present(1701,"udp"),
        "500_udp":_listener_present(500,"udp"),
        "4500_udp":_listener_present(4500,"udp"),
    }
    configured=bool(
        "# BEGIN MAKIA L2TP" in ipsec_text and "# END MAKIA L2TP" in ipsec_text
        and "; BEGIN MAKIA L2TP" in l2tp_text and "; END MAKIA L2TP" in l2tp_text
        and "# BEGIN MAKIA L2TP PPP OPTIONS" in ppp_text and "# END MAKIA L2TP PPP OPTIONS" in ppp_text
        and psk_ready and ppp_options_ready
    )
    active=_active("xl2tpd")
    network_active=_active("makia-l2tp-network")
    domain=str(env.get("MAKIA_L2TP_SERVER") or ike.get("domain") or "")
    cidr=str(env.get("MAKIA_L2TP_CIDR") or "10.78.0.0/24")
    network=_vpn_network_status(cidr,"makia-l2tp-network")
    ready=bool(configured and active and all(listeners.values()) and ike.get("ready") and network["forwarding_ready"] and ppp_options_ready)
    return {
        "installed":bool(shutil.which("xl2tpd") and shutil.which("ipsec")),
        "configured":configured,"service_active":active,"network_active":network_active,
        "listeners":listeners,"domain":domain,"cidr":cidr,"users":users,
        "psk_ready":psk_ready,"ppp_options_ready":ppp_options_ready,"warnings":ppp_issues,
        **network,"ikev2_ready":bool(ike.get("ready")),"ready":ready,
    }


def get_l2tp_user_credentials(name):
    """Return a managed L2TP username/password for internal encrypted export only."""
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,48}",name) or not L2TP_CHAP.exists():
        return None
    marker=re.compile(r"#\s*makia-l2tp:"+re.escape(name)+r"\s*$")
    for line in L2TP_CHAP.read_text(encoding="utf-8",errors="ignore").splitlines():
        if not marker.search(line):
            continue
        parts=line.split()
