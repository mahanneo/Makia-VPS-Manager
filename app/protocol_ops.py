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
from pathlib import Path

XRAY_BIN_CANDIDATES=["/usr/local/bin/xray","/usr/bin/xray"]
XRAY_CONFIG_CANDIDATES=["/usr/local/etc/xray/config.json","/etc/xray/config.json"]
XRAY_VALIDATED_VERSION="v26.3.27"
XRAY_TLS_DIR=Path("/usr/local/etc/xray/tls")
WG_DIR=Path("/etc/wireguard")
OVPN_DIR=Path("/etc/openvpn")
OVPN_EASYRSA=OVPN_DIR/"easy-rsa"

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

def _xray_test_config_as_service(binary,path):
    args=[binary,"run","-test","-format=json","-config",str(path)]
    user=_xray_service_user()
    if os.geteuid()==0 and user not in {"","root"} and shutil.which("runuser"):
        args=["runuser","-u",user,"--",*args]
    return _run(args,timeout=30)

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
            _xray_test_config_as_service(binary,config)
            result["service_validation"]=True
        except Exception as exc:
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
    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
    return {
        "installed":installed,
        "service_active":_active("wg-quick@wg0"),
        "interfaces":interfaces,
        "peers":peers,
        "config":str(WG_DIR/"wg0.conf") if (WG_DIR/"wg0.conf").exists() else None,
    }

def openvpn_status():
    installed=_installed("openvpn")
    configs=[]
    server_dir=OVPN_DIR/"server"
    if server_dir.exists():
        configs=[p.stem for p in server_dir.glob("*.conf")]
    active=any(_active(f"openvpn-server@{name}") for name in configs)
    return {
        "installed":installed,
        "service_active":active,
        "servers":configs,
        "config":str(server_dir/"server.conf") if (server_dir/"server.conf").exists() else None,
    }

def stunnel_status():
    return {
        "installed":_installed("stunnel4"),
        "service_active":_active("stunnel4"),
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
    return {
        "xray":x,
        "wireguard":wg,
        "openvpn":ovpn,
        "stunnel":st,
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
            {"id":"tuic","engine":"external","available":False,"mode":"unavailable"},
            {"id":"amneziawg","engine":"external","available":False,"mode":"unavailable"},
            {"id":"mtproto","engine":"external","available":False,"mode":"unavailable"},
        ]
    }

def install_component(component):
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
    mtu=_validate_wireguard_mtu(mtu)
    keepalive=_validate_keepalive(keepalive)
    allowed_ips=_validate_wireguard_allowed_ips(allowed_ips)
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        raise ProtocolError("WireGuard server is not bootstrapped")
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
    _run(["wg","set",iface,"peer",client_public,"allowed-ips",f"{client_ip}/32"])
    with conf.open("a",encoding="utf-8") as fh:
        fh.write(f"\n# Makia peer: {name}\n[Peer]\nPublicKey = {client_public}\nAllowedIPs = {client_ip}/32\n")
    os.chmod(conf,0o600)
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
    peers=[]; current=None; pending_name=None
    for line in lines:
        stripped=line.strip()
        if stripped.startswith("# Makia peer:"):
            pending_name=stripped.split(":",1)[1].strip()
        elif stripped=="[Peer]":
            if current: peers.append(current)
            current={"name":pending_name or "wireguard-peer","public_key":"","allowed_ips":"","interface":iface}
            pending_name=None
        elif current and "=" in stripped:
            key,value=[x.strip() for x in stripped.split("=",1)]
            if key=="PublicKey": current["public_key"]=value
            elif key=="AllowedIPs": current["allowed_ips"]=value
    if current: peers.append(current)
    return [p for p in peers if p.get("public_key")]

def remove_wireguard_peer(public_key, iface="wg0"):
    public_key=str(public_key or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{20,100}",public_key):
        raise ProtocolError("invalid WireGuard public key")
    conf=WG_DIR/f"{iface}.conf"
    if not conf.exists():
        raise ProtocolError("WireGuard server config not found")
    _run(["wg","set",iface,"peer",public_key,"remove"])
    lines=conf.read_text(encoding="utf-8",errors="ignore").splitlines()
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
    conf.write_text("\n".join(cleaned).rstrip()+"\n",encoding="utf-8")
    os.chmod(conf,0o600)
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
            try: resolved6=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET6)})
            except Exception: resolved6=[]
        local4=_local_ipv4_candidates()
        if not endpoint_is_ip:
            dns_matches_server=bool(set(resolved4)&set(local4)) if resolved4 and local4 else None
            if not resolved4:
                warnings.append("دامنه WireGuard رکورد A/IPv4 قابل استفاده ندارد.")
            if resolved6:
                warnings.append("دامنه AAAA هم دارد؛ WireGuard می‌تواند IPv6 را انتخاب کند. اگر VPS مسیر IPv6 کامل ندارد، برای Endpoint از A/IPv4 مستقیم یا دامنه بدون AAAA ناسازگار استفاده کنید.")
            if dns_matches_server is False:
                warnings.append("رکورد A دامنه با IPv4 این VPS تطابق ندارد. WireGuard خام از HTTP/CDN Proxy عبور نمی‌کند؛ رکورد باید DNS-only و مستقیم به VPS باشد.")
        elif ip_version!=4:
            warnings.append("Bootstrap فعلی WireGuard سرور IPv4-only است؛ Endpoint IPv6 برای این Runtime توصیه نمی‌شود.")
    else:
        local4=_local_ipv4_candidates()
    if not cfg.get("exists"): warnings.append("فایل wg0.conf وجود ندارد.")
    if not service_active: warnings.append("سرویس wg-quick@wg0 فعال نیست.")
    if not interface_present: warnings.append("Interface wg0 در runtime دیده نمی‌شود.")
    if not listener and cfg.get("port"): warnings.append(f"UDP listener روی Port {cfg.get('port')} دیده نشد.")
    if not ip_forward: warnings.append("net.ipv4.ip_forward فعال نیست.")
    if forward_in is False or forward_out is False: warnings.append("Forwarding ruleهای WireGuard در iptables کامل نیستند.")
    if nat is False: warnings.append("NAT/MASQUERADE برای شبکه WireGuard روی uplink پیدا نشد.")
    peers=_wireguard_peer_runtime(iface)
    recent=sum(1 for p in peers if p.get("handshake_age") is not None and int(p["handshake_age"])<=180)
    if peers and recent==0:
        warnings.append("هیچ Handshake تازه‌ای از Peerها دیده نشده است. اگر Client در حال تلاش برای اتصال است، علاوه بر Endpoint/Key، احتمال مسدودبودن UDP در فایروال دیتاسنتر، NAT بالادست یا شبکه/ISP را بررسی کنید؛ سلامت سمت سرور به‌تنهایی دسترسی UDP از اینترنت را اثبات نمی‌کند.")
    endpoint_ok=True
    if endpoint:
        endpoint_ok=bool(
            (endpoint_is_ip and ip_version==4) or
            ((not endpoint_is_ip) and resolved4 and dns_matches_server is not False)
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
        "dns_matches_server":dns_matches_server,
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
    backup_dir=Path(os.getenv("MAKIA_BACKUP_DIR","/var/backups/makia-vps-manager"))
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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

def openvpn_endpoint_diagnostics(endpoint):
    endpoint=_validate_endpoint_host(endpoint,"OpenVPN endpoint")
    runtime=_openvpn_server_runtime()
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
    matches=bool(set(resolved4)&set(local4)) if resolved4 and local4 else None
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
    up=OVPN_DIR/"makia-up.sh"
    down=OVPN_DIR/"makia-down.sh"
    up.write_text(f"#!/bin/sh\niptables -t nat -C POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE\n",encoding="utf-8")
    down.write_text(f"#!/bin/sh\niptables -t nat -D POSTROUTING -s 10.8.0.0/24 -o {uplink} -j MASQUERADE 2>/dev/null || true\n",encoding="utf-8")
    os.chmod(up,0o700); os.chmod(down,0o700)
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
    if updated!=original:
        server_conf.write_text(updated,encoding="utf-8")
    try:
        _run(["systemctl","restart","openvpn-server@server"],timeout=30)
        if not _active("openvpn-server@server"):
            raise ProtocolError("OpenVPN did not become active after IPv4 normalization")
    except Exception:
        shutil.copy2(backup,server_conf)
        try: _run(["systemctl","restart","openvpn-server@server"],timeout=30)
        except Exception: pass
        raise
    runtime=_openvpn_server_runtime()
    return {"ok":True,"backup":str(backup),"runtime":runtime}

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

def _port_in_use(port):
    port=int(port)
    for kind in (socket.SOCK_STREAM,socket.SOCK_DGRAM):
        s=socket.socket(socket.AF_INET,kind)
        try:
            s.bind(("0.0.0.0",port))
        except OSError:
            return True
        finally:
            s.close()
    return False

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
        if protocol!="vless":
            raise ProtocolError("Makia currently enables REALITY only for VLESS")
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
        stream["kcpSettings"]={"seed":path_value.strip("/") or "makia"}
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

def create_xray_inbound(protocol, port, name, endpoint, transport="tcp", security="none", path_value="/", server_name="", reality_dest=""):
    protocol=(protocol or "").lower()
    if protocol not in {"vless","vmess","trojan","shadowsocks","hysteria2","http","socks"}:
        raise ProtocolError("unsupported Xray quick protocol")
    port=_validate_port(port)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name or ""):
        raise ProtocolError("invalid client name")
    endpoint=_validate_endpoint_host(endpoint)
    security=(security or "none").lower()
    if protocol in {"vless","trojan"} and security=="none" and not _endpoint_is_private(endpoint):
        raise ProtocolError(f"{protocol.upper()} with security=none is not valid for a public endpoint in this guided mode; choose REALITY or TLS")
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
    if _port_in_use(port):
        raise ProtocolError("this port is already in use on the server")
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
    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
        "reality":reality_meta,
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
    if _port_in_use(listen_port):
        raise ProtocolError("listen port is already in use")
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
    backup_dir=Path("/var/backups/makia-vps-manager"); backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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

    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
    backup_dir=Path("/var/backups/makia-vps-manager")
    backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
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
