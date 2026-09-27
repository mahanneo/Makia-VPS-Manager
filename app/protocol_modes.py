import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from . import protocol_ops

STATE_DIR=Path("/etc/makia-vps-manager")
IKEV2_DIR=STATE_DIR/"ikev2"
IKEV2_USERS=IKEV2_DIR/"users.json"
IKEV2_ENV=STATE_DIR/"ikev2.env"
SWANCTL_MAIN=Path("/etc/swanctl/swanctl.conf")
SWANCTL_CONF=Path("/etc/swanctl/conf.d/makia.conf")
SWANCTL_SECRETS=Path("/etc/swanctl/conf.d/makia-secrets.conf")
SWANCTL_CERT=Path("/etc/swanctl/x509/makia-server.pem")
SWANCTL_CA=Path("/etc/swanctl/x509ca/makia-chain.pem")
SWANCTL_KEY=Path("/etc/swanctl/private/makia-server.pem")
STEALTH_CONF=Path("/etc/stunnel/makia-openvpn.conf")
WSTUNNEL_ENV=STATE_DIR/"wstunnel.env"
EAP_MSCHAPV2_PLUGIN=Path("/usr/lib/ipsec/plugins/libstrongswan-eap-mschapv2.so")

class ProtocolModeError(RuntimeError):
    pass

def _run(args,timeout=60):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ProtocolModeError(str(exc)) from exc
    if p.returncode!=0:
        raise ProtocolModeError((p.stderr or p.stdout or "operation failed").strip()[:1600])
    return (p.stdout or "").strip()

def _active(service):
    if not shutil.which("systemctl"):
        return False
    p=subprocess.run(["systemctl","is-active",service],text=True,capture_output=True,timeout=8,check=False)
    return p.returncode==0

def _listeners(proto="tcp"):
    ports=set()
    if not shutil.which("ss"):
        return ports
    flag="-ltn" if proto=="tcp" else "-lun"
    p=subprocess.run(["ss","-H",flag],text=True,capture_output=True,timeout=8,check=False)
    if p.returncode:
        return ports
    for line in (p.stdout or "").splitlines():
        m=re.search(r":(\d+)(?:\s|$)",line)
        if m:
            ports.add(int(m.group(1)))
    return ports

def _letsencrypt(domain):
    domain=protocol_ops._validate_endpoint_host(domain,"domain")
    base=Path("/etc/letsencrypt/live")/domain
    cert,chain,fullchain,key=base/"cert.pem",base/"chain.pem",base/"fullchain.pem",base/"privkey.pem"
    if not cert.exists() or not fullchain.exists() or not key.exists():
        raise ProtocolModeError("HTTPS certificate for this domain is required first (Settings → Domain / HTTPS)")
    return domain,cert,chain,fullchain,key

def _atomic_text(path,text,mode=0o600):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name("."+path.name+".makia.tmp")
    tmp.write_text(text,encoding="utf-8"); os.chmod(tmp,mode); os.replace(tmp,path)
    return path

def _snapshot_paths(paths):
    snapshot={}
    for item in paths:
        path=Path(item)
        if path.exists():
            snapshot[path]=(path.read_bytes(),path.stat().st_mode & 0o777)
        else:
            snapshot[path]=None
    return snapshot

def _restore_paths(snapshot):
    for path,state in snapshot.items():
        path=Path(path)
        if state is None:
            path.unlink(missing_ok=True)
            continue
        data,mode=state
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        os.chmod(path,mode)

def _rollback_service(service,was_active):
    try:
        _run(["systemctl","daemon-reload"],20)
        if was_active:
            _run(["systemctl","restart",service],30)
        else:
            subprocess.run(["systemctl","disable","--now",service],text=True,capture_output=True,timeout=30,check=False)
    except Exception:
        pass

def _service_restart(candidates):
    last=""
    for service in candidates:
        p=subprocess.run(["systemctl","restart",service],text=True,capture_output=True,timeout=45,check=False)
        if p.returncode==0:
            subprocess.run(["systemctl","enable",service],text=True,capture_output=True,timeout=20,check=False)
            return service
        last=(p.stderr or p.stdout or "").strip()
    raise ProtocolModeError(last or "unable to restart service")

def _openvpn_tcp_runtime():
    runtime=protocol_ops._openvpn_server_runtime()
    proto=str(runtime.get("proto") or "").lower()
    if not runtime.get("service_active") or not runtime.get("listener"):
        raise ProtocolModeError("OpenVPN runtime must be active before enabling this mode")
    if not proto.startswith("tcp"):
        raise ProtocolModeError("This mode wraps OpenVPN/TCP. Switch OpenVPN transport to TCP first.")
    return runtime

def _read_env(path):
    result={}
    if not Path(path).exists(): return result
    for line in Path(path).read_text(encoding="utf-8",errors="ignore").splitlines():
        if "=" not in line or line.lstrip().startswith("#"): continue
        k,v=line.split("=",1); result[k.strip()]=v.strip()
    return result

def _write_env(path,values):
    for value in values.values():
        if any(ch in str(value) for ch in "\r\n"):
            raise ProtocolModeError("invalid service setting")
    return _atomic_text(path,"".join(f"{k}={v}\n" for k,v in values.items()),0o600)

def _strongswan_service():
    for name in ("strongswan","strongswan-swanctl","strongswan-starter"):
        if _active(name): return name
    return ""

def ikev2_status():
    installed=bool(shutil.which("swanctl"))
    service=_strongswan_service()
    udp=_listeners("udp")
    users=_load_ikev2_users(silent=True)
    domain=""
    if SWANCTL_CONF.exists():
        m=re.search(r"(?m)^\s*id\s*=\s*([^\s#]+)",SWANCTL_CONF.read_text(encoding="utf-8",errors="ignore"))
        domain=(m.group(1) if m else "").lstrip("@")
    return {
        "installed":installed,"service_active":bool(service),"service":service,
        "configured":SWANCTL_CONF.exists(),"domain":domain,"users":len(users),
        "udp500":500 in udp,"udp4500":4500 in udp,
        "ready":bool(installed and service and SWANCTL_CONF.exists() and 500 in udp and 4500 in udp),
    }

def _ensure_swanctl_include():
    SWANCTL_MAIN.parent.mkdir(parents=True,exist_ok=True)
    text=SWANCTL_MAIN.read_text(encoding="utf-8",errors="ignore") if SWANCTL_MAIN.exists() else ""
    if re.search(r"(?m)^\s*include\s+conf\.d/\*\.conf\s*$",text): return
    if text and not text.endswith("\n"): text+="\n"
    _atomic_text(SWANCTL_MAIN,text+"\n# Makia managed include\ninclude conf.d/*.conf\n",0o640)

def _copy_ikev2_credentials(cert,chain,key):
    for folder in (SWANCTL_CERT.parent,SWANCTL_CA.parent,SWANCTL_KEY.parent):
        folder.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(cert,SWANCTL_CERT); os.chmod(SWANCTL_CERT,0o644)
    if chain.exists():
        shutil.copyfile(chain,SWANCTL_CA); os.chmod(SWANCTL_CA,0o644)
    shutil.copyfile(key,SWANCTL_KEY); os.chmod(SWANCTL_KEY,0o600)

def configure_ikev2(domain,pool="10.99.0.0/24",dns_servers=None):
    if not shutil.which("swanctl"):
        raise ProtocolModeError("StrongSwan is not installed. Run sudo makia-upgrade, then configure IKEv2 again.")
    if not EAP_MSCHAPV2_PLUGIN.exists():
        raise ProtocolModeError("StrongSwan EAP-MSCHAPv2 plugin is missing. Run sudo makia-upgrade, then configure IKEv2 again.")
    if not Path("/etc/systemd/system/makia-ikev2-firewall.service").exists():
        raise ProtocolModeError("Makia IKEv2 host unit is missing. Run sudo makia-upgrade first.")
    domain,cert,chain,fullchain,key=_letsencrypt(domain)
    try: network=ipaddress.ip_network(str(pool),strict=False)
    except ValueError as exc: raise ProtocolModeError("invalid IKEv2 client pool") from exc
    if network.version!=4 or not (16<=network.prefixlen<=28):
        raise ProtocolModeError("IKEv2 pool must be an IPv4 CIDR between /16 and /28")
    dns=[]
    for value in (dns_servers or ["1.1.1.1","8.8.8.8"]):
        try: addr=ipaddress.ip_address(str(value).strip())
        except ValueError as exc: raise ProtocolModeError("invalid IKEv2 DNS address") from exc
        if addr.version!=4: raise ProtocolModeError("IKEv2 DNS must be IPv4 in this release")
        dns.append(addr.compressed)
    dns=dns[:3] or ["1.1.1.1"]
    sysctl_path=Path("/etc/sysctl.d/99-makia-ikev2.conf")
    snapshot=_snapshot_paths([SWANCTL_MAIN,SWANCTL_CONF,SWANCTL_SECRETS,SWANCTL_CERT,SWANCTL_CA,SWANCTL_KEY,IKEV2_ENV,sysctl_path])
    was_active=_active("strongswan")
    try:
        _ensure_swanctl_include(); _copy_ikev2_credentials(cert,chain,key)
        conf=f"""# Managed by Makia VPS Manager.
connections {{
  makia-ikev2 {{
    version = 2
    local_addrs = 0.0.0.0
    pools = makia-pool
    proposals = aes256-sha256-modp2048,aes128-sha256-modp2048
    fragmentation = yes
    mobike = yes
    send_cert = always
    local {{
      auth = pubkey
      certs = makia-server.pem
      id = {domain}
    }}
    remote {{
      auth = eap-mschapv2
      eap_id = %any
    }}
    children {{
      makia-net {{
        local_ts = 0.0.0.0/0
        esp_proposals = aes256-sha256,aes128-sha256
        dpd_action = clear
      }}
    }}
  }}
}}
pools {{
  makia-pool {{
    addrs = {network.with_prefixlen}
    dns = {",".join(dns)}
  }}
}}
"""
        _atomic_text(SWANCTL_CONF,conf,0o640); _render_ikev2_secrets()
        _write_env(IKEV2_ENV,{"MAKIA_IKEV2_POOL":network.with_prefixlen,"MAKIA_IKEV2_UPLINK":protocol_ops._default_iface()})
        _atomic_text(sysctl_path,"net.ipv4.ip_forward=1\n",0o644)
        _run(["sysctl","--system"],45)
        service=_service_restart(("strongswan","strongswan-swanctl","strongswan-starter"))
        _run(["swanctl","--load-all"],45)
        _run(["systemctl","daemon-reload"],20)
        _run(["systemctl","enable","--now","makia-ikev2-firewall"],30)
        protocol_ops._ufw_allow_if_active(500,"udp","IKEv2")
        protocol_ops._ufw_allow_if_active(4500,"udp","IKEv2 NAT-T")
        status=ikev2_status()
        if not status.get("ready"):
            raise ProtocolModeError("IKEv2 did not reach READY state after configuration")
        return {"ok":True,"service":service,"pool":network.with_prefixlen,"dns":dns,**status}
    except Exception as exc:
        _restore_paths(snapshot)
        _rollback_service("strongswan",was_active)
        try: _run(["sysctl","--system"],45)
        except Exception: pass
        if isinstance(exc,ProtocolModeError): raise
        raise ProtocolModeError(str(exc)) from exc

def _load_ikev2_users(silent=False):
    if not IKEV2_USERS.exists(): return {}
    try:
        data=json.loads(IKEV2_USERS.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except Exception as exc:
        if silent: return {}
        raise ProtocolModeError(f"cannot read IKEv2 users: {exc}") from exc

def _swan_quote(value):
    return '"'+str(value).replace("\\","\\\\").replace('"','\\"')+'"'

def _render_ikev2_secrets():
    lines=["# Managed by Makia VPS Manager.","secrets {"]
    for idx,(name,item) in enumerate(sorted(_load_ikev2_users(silent=True).items())):
        secret=str((item or {}).get("password") or "")
        if secret:
            lines += [f"  eap-makia-{idx} {{",f"    id = {_swan_quote(name)}",f"    secret = {_swan_quote(secret)}","  }"]
    lines.append("}")
    _atomic_text(SWANCTL_SECRETS,"\n".join(lines)+"\n",0o600)

def create_ikev2_user(name,password=None):
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,47}",name):
        raise ProtocolModeError("IKEv2 username must be 1-48 safe ASCII characters")
    if not SWANCTL_CONF.exists(): raise ProtocolModeError("Configure IKEv2 server before creating users")
    password=str(password or secrets.token_urlsafe(18))
    if len(password)<8 or len(password)>128 or any(ord(ch)<33 or ord(ch)>126 for ch in password):
        raise ProtocolModeError("IKEv2 password must be 8-128 printable ASCII characters without spaces")
    users=_load_ikev2_users()
    if name in users: raise ProtocolModeError("IKEv2 username already exists")
    users[name]={"password":password}
    IKEV2_DIR.mkdir(parents=True,exist_ok=True)
    _atomic_text(IKEV2_USERS,json.dumps(users,ensure_ascii=False,indent=2)+"\n",0o600)
    _render_ikev2_secrets(); _run(["swanctl","--load-creds"],30)
    domain=ikev2_status().get("domain") or ""
    return {"name":name,"password":password,"server":domain,"remote_id":domain,"authentication":"EAP-MSCHAPv2","ports":[500,4500],"native":"IKEv2"}

def remove_ikev2_user(name):
    users=_load_ikev2_users()
    if name not in users: raise ProtocolModeError("IKEv2 user not found")
    users.pop(name,None); _atomic_text(IKEV2_USERS,json.dumps(users,ensure_ascii=False,indent=2)+"\n",0o600)
    _render_ikev2_secrets(); _run(["swanctl","--load-creds"],30)
    return {"ok":True}

def stealth_status():
    text=STEALTH_CONF.read_text(encoding="utf-8",errors="ignore") if STEALTH_CONF.exists() else ""
    m=re.search(r"(?m)^\s*accept\s*=\s*(?:[^:]+:)?(\d+)\s*$",text)
    port=int(m.group(1)) if m else None
    active=_active("makia-stealth")
    return {"installed":bool(shutil.which("stunnel4") or shutil.which("stunnel")),"configured":STEALTH_CONF.exists(),"service_active":active,"port":port,"listener":bool(port and port in _listeners("tcp")),"ready":bool(active and port and port in _listeners("tcp"))}

def configure_stealth(domain,listen_port=8443):
    domain,cert,chain,fullchain,key=_letsencrypt(domain); port=protocol_ops._validate_port(listen_port)
    runtime=_openvpn_tcp_runtime(); target=int(runtime.get("port") or 1194); current=stealth_status()
    if protocol_ops._port_transport_in_use(port,"tcp") and not (current.get("service_active") and current.get("port")==port):
        raise ProtocolModeError(f"TCP/{port} is already in use; choose another Stealth port")
    if not Path("/etc/systemd/system/makia-stealth.service").exists():
        raise ProtocolModeError("Makia Stealth service unit is missing. Run sudo makia-upgrade first.")
    snapshot=_snapshot_paths([STEALTH_CONF])
    was_active=_active("makia-stealth")
    try:
        _atomic_text(STEALTH_CONF,f"""foreground = yes
client = no
[makia-openvpn]
accept = 0.0.0.0:{port}
connect = 127.0.0.1:{target}
cert = {fullchain}
key = {key}
TIMEOUTclose = 0
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1
""",0o600)
        _run(["systemctl","daemon-reload"],20); _run(["systemctl","enable","--now","makia-stealth"],30)
        status=stealth_status()
        if not status["ready"]: raise ProtocolModeError("Stealth service did not reach a listening state")
        protocol_ops._ufw_allow_if_active(port,"tcp","Stealth TLS")
        return {"ok":True,"domain":domain,"listen_port":port,"target_port":target,"client_note":"Use an stunnel-capable client, then point OpenVPN/TCP to the local stunnel port.",**status}
    except Exception as exc:
        _restore_paths(snapshot); _rollback_service("makia-stealth",was_active)
        if isinstance(exc,ProtocolModeError): raise
        raise ProtocolModeError(str(exc)) from exc

def wstunnel_status():
    env=_read_env(WSTUNNEL_ENV); bind=env.get("WSTUNNEL_BIND",""); m=re.search(r":(\d+)$",bind); port=int(m.group(1)) if m else None
    binary=shutil.which("wstunnel"); version=""
    if binary:
        try:
            p=subprocess.run([binary,"--version"],text=True,capture_output=True,timeout=5,check=False)
            version=(p.stdout or p.stderr or "").strip().splitlines()[0][:120]
        except Exception: pass
    active=_active("makia-wstunnel")
    return {"installed":bool(binary),"version":version,"configured":WSTUNNEL_ENV.exists(),"service_active":active,"port":port,"listener":bool(port and port in _listeners("tcp")),"path_prefix_set":bool(env.get("WSTUNNEL_PATH_PREFIX")),"ready":bool(binary and active and port and port in _listeners("tcp"))}

def configure_wstunnel(domain,listen_port=9443,path_prefix=None):
    if not shutil.which("wstunnel"): raise ProtocolModeError("wstunnel is not installed. Run sudo makia-upgrade first.")
    if not Path("/etc/systemd/system/makia-wstunnel.service").exists():
        raise ProtocolModeError("Makia WStunnel service unit is missing. Run sudo makia-upgrade first.")
    domain,cert,chain,fullchain,key=_letsencrypt(domain); port=protocol_ops._validate_port(listen_port)
    runtime=_openvpn_tcp_runtime(); target=int(runtime.get("port") or 1194); current=wstunnel_status()
    if protocol_ops._port_transport_in_use(port,"tcp") and not (current.get("service_active") and current.get("port")==port):
        raise ProtocolModeError(f"TCP/{port} is already in use; choose another WStunnel port")
    prefix=str(path_prefix or secrets.token_urlsafe(18)).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,96}",prefix): raise ProtocolModeError("WStunnel path secret must be 12-96 URL-safe characters")
    snapshot=_snapshot_paths([WSTUNNEL_ENV])
    was_active=_active("makia-wstunnel")
    try:
        _write_env(WSTUNNEL_ENV,{"WSTUNNEL_PATH_PREFIX":prefix,"WSTUNNEL_RESTRICT_TO":f"127.0.0.1:{target}","WSTUNNEL_CERT":str(fullchain),"WSTUNNEL_KEY":str(key),"WSTUNNEL_BIND":f"wss://0.0.0.0:{port}"})
        _run(["systemctl","daemon-reload"],20); _run(["systemctl","enable","--now","makia-wstunnel"],30)
        status=wstunnel_status()
        if not status["ready"]: raise ProtocolModeError("WStunnel service did not reach a listening state")
        protocol_ops._ufw_allow_if_active(port,"tcp","WStunnel")
        return {"ok":True,"domain":domain,"listen_port":port,"target_port":target,"path_prefix":prefix,"client_command":f"wstunnel client --http-upgrade-path-prefix {prefix} -L tcp://127.0.0.1:11940:127.0.0.1:{target} wss://{domain}:{port}","openvpn_local_endpoint":"127.0.0.1:11940/tcp",**status}
    except Exception as exc:
        _restore_paths(snapshot); _rollback_service("makia-wstunnel",was_active)
        if isinstance(exc,ProtocolModeError): raise
        raise ProtocolModeError(str(exc)) from exc

def connection_modes():
    wg=protocol_ops.wireguard_status(); ov=protocol_ops.openvpn_status(); ovp=str(ov.get("proto") or "").lower()
    ike=ikev2_status(); stealth=stealth_status(); ws=wstunnel_status()
    return {"modes":[
        {"id":"ikev2","label":"IKEv2","port":"500 / 4500","transport":"UDP","ready":ike["ready"],"installed":ike["installed"],"description":"Native IPsec/IKEv2 with StrongSwan and EAP-MSCHAPv2.","client":"Native OS IKEv2 client","status":ike},
        {"id":"wireguard","label":"WireGuard","port":wg.get("port") or 443,"transport":"UDP","ready":bool(wg.get("service_active") and wg.get("config")),"installed":wg.get("installed",False),"description":"Fast native WireGuard tunnel with per-peer keys.","client":"Official WireGuard client","status":wg},
        {"id":"udp","label":"UDP","port":ov.get("port") or 1194,"transport":"OpenVPN UDP","ready":bool(ov.get("service_active") and ovp.startswith("udp")),"installed":ov.get("installed",False),"description":"OpenVPN over UDP for normal low-overhead operation.","client":"OpenVPN Connect","status":ov},
        {"id":"tcp","label":"TCP","port":ov.get("port") or 1194,"transport":"OpenVPN TCP","ready":bool(ov.get("service_active") and ovp.startswith("tcp")),"installed":ov.get("installed",False),"description":"OpenVPN over TCP where UDP is unavailable.","client":"OpenVPN Connect","status":ov},
        {"id":"stealth","label":"Stealth","port":stealth.get("port") or 8443,"transport":"TLS / Stunnel","ready":stealth["ready"],"installed":stealth["installed"],"description":"Wraps OpenVPN/TCP in a real TLS tunnel using Stunnel.","client":"Stunnel-capable client + OpenVPN","status":stealth},
        {"id":"wstunnel","label":"WStunnel","port":ws.get("port") or 9443,"transport":"WSS / WebSocket","ready":ws["ready"],"installed":ws["installed"],"description":"Wraps OpenVPN/TCP through authenticated WSS using wstunnel.","client":"wstunnel client + OpenVPN","status":ws},
    ],"note":"Modes may coexist when ports do not collide. OpenVPN UDP and TCP are one managed server profile, so switching transport changes that profile."}
