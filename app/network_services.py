import ipaddress
import grp
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path


class NetworkServiceError(RuntimeError):
    pass


MTPROXY_ROOT=Path("/opt/makia-mtproxy")
MTPROXY_BIN=MTPROXY_ROOT/"mtg"
MTPROXY_CONFIG_DIR=Path("/etc/makia-vps-manager")
MTPROXY_ENV=MTPROXY_CONFIG_DIR/"mtproxy.env"
MTPROXY_CONFIG=MTPROXY_CONFIG_DIR/"mtproxy.toml"
MTPROXY_SERVICE="makia-mtproxy"

DNS_STATE=Path("/etc/makia-vps-manager/dns.json")
DNS_CONF=Path("/etc/unbound/unbound.conf.d/makia.conf")
DNS_SERVICE="unbound"

DNS_UPSTREAMS={
    "cloudflare":{
        "label":"Cloudflare DoT",
        "servers":["1.1.1.1@853#cloudflare-dns.com","1.0.0.1@853#cloudflare-dns.com"],
    },
    "quad9":{
        "label":"Quad9 DoT",
        "servers":["9.9.9.9@853#dns.quad9.net","149.112.112.112@853#dns.quad9.net"],
    },
    "google":{
        "label":"Google DoT",
        "servers":["8.8.8.8@853#dns.google","8.8.4.4@853#dns.google"],
    },
}


def _run(args,timeout=30):
    try:
        proc=subprocess.run(args,text=True,capture_output=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise NetworkServiceError(str(exc)) from exc
    if proc.returncode!=0:
        raise NetworkServiceError((proc.stderr or proc.stdout or "operation failed").strip()[:1200])
    return (proc.stdout or "").strip()


def _active(service):
    try:
        proc=subprocess.run(["systemctl","is-active","--quiet",service],timeout=5,check=False)
        return proc.returncode==0
    except Exception:
        return False


def _mtproxy_runtime_diagnostics(secret=""):
    parts=[]
    commands=(
        ["systemctl","status",MTPROXY_SERVICE,"--no-pager","--lines=18"],
        ["journalctl","-u",MTPROXY_SERVICE,"-n","28","--no-pager","-o","cat"],
    )
    for args in commands:
        try:
            proc=subprocess.run(args,text=True,capture_output=True,timeout=8,check=False)
            text=(proc.stdout or proc.stderr or "").strip()
            if text:
                parts.append(text)
        except Exception:
            pass
    text="\n".join(parts)
    if secret:
        text=text.replace(str(secret),"<redacted-secret>")
    # Keep API/audit responses bounded and single-line enough for the browser dialog.
    text=re.sub(r"\x1b\[[0-9;]*m","",text)
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[-12:])[:1800]


def _validate_port(value):
    try: port=int(value)
    except Exception as exc: raise NetworkServiceError("invalid port") from exc
    if not 1<=port<=65535:
        raise NetworkServiceError("invalid port")
    return port


def _validate_host(value):
    raw=str(value or "").strip()
    if not raw or len(raw)>253 or "://" in raw or any(ch.isspace() for ch in raw) or any(ch in raw for ch in "/?#@"):
        raise NetworkServiceError("enter only a hostname or IP address")
    host=raw.strip("[]")
    try:return ipaddress.ip_address(host).compressed
    except ValueError:pass
    if host.endswith("."):host=host[:-1]
    try:ascii_host=host.encode("idna").decode("ascii")
    except Exception as exc:raise NetworkServiceError("invalid hostname") from exc
    label_re=re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
    if not ascii_host or len(ascii_host)>253 or any(not label_re.fullmatch(p) for p in ascii_host.split(".")):
        raise NetworkServiceError("invalid hostname")
    return ascii_host.lower()


def _port_busy(port,proto="tcp",address="0.0.0.0"):
    port=_validate_port(port)
    kind=socket.SOCK_DGRAM if str(proto).lower()=="udp" else socket.SOCK_STREAM
    family=socket.AF_INET6 if ":" in str(address) else socket.AF_INET
    sock=socket.socket(family,kind)
    try:
        sock.bind((str(address),port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def _free_port(requested,candidates,proto="tcp",kernel_fallback=False):
    ordered=[]
    for raw in (requested,*candidates):
        try:port=_validate_port(raw)
        except Exception:continue
        if port not in ordered:ordered.append(port)
    for port in ordered:
        if not _port_busy(port,proto):
            return port
    if kernel_fallback and str(proto).lower()=="tcp":
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0",0))
            port=int(sock.getsockname()[1])
        except OSError as exc:
            raise NetworkServiceError("unable to allocate a free TCP port") from exc
        finally:
            sock.close()
        if port>=1024:
            return port
    raise NetworkServiceError(f"no free {proto.upper()} port found in the managed candidate set")


def _read_env(path):
    result={}
    if not Path(path).exists():return result
    for line in Path(path).read_text(encoding="utf-8",errors="ignore").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:continue
        key,value=line.split("=",1)
        result[key.strip()]=value.strip()
    return result


def _atomic_write(path,text,mode=0o600):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".makia-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            os.fchmod(fh.fileno(),mode)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp,path)
        os.chmod(path,mode)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _ensure_mtproxy_config_access():
    try:
        gid=grp.getgrnam("makia-mtproxy").gr_gid
    except KeyError as exc:
        raise NetworkServiceError(
            "makia-mtproxy system user/group is missing; run sudo makia-upgrade"
        ) from exc
    MTPROXY_CONFIG_DIR.mkdir(parents=True,exist_ok=True)
    # root owns the directory. Group gets traverse only, not directory listing.
    os.chown(MTPROXY_CONFIG_DIR,0,gid)
    os.chmod(MTPROXY_CONFIG_DIR,0o710)
    return gid


def _mtproxy_secret():
    if not MTPROXY_CONFIG.exists():
        return ""
    try:
        text=MTPROXY_CONFIG.read_text(encoding="utf-8",errors="strict")
    except OSError:
        return ""
    match=re.search(r'(?m)^secret\s*=\s*"([^"]+)"\s*$',text)
    return match.group(1).strip() if match else ""


def _write_mtproxy_config(secret,port):
    if not re.fullmatch(r"ee[0-9a-fA-F]+",str(secret or "")):
        raise NetworkServiceError("invalid mtg FakeTLS secret")
    port=_validate_port(port)
    text=(
        f'secret = "{secret}"\n'
        f'bind-to = "0.0.0.0:{port}"\n\n'
        '[network]\n'
        'dns = "https://1.1.1.1"\n'
    )
    gid=_ensure_mtproxy_config_access()
    _atomic_write(MTPROXY_CONFIG,text,0o640)
    os.chown(MTPROXY_CONFIG,0,gid)
    os.chmod(MTPROXY_CONFIG,0o640)

def _ufw_allow(port,proto,label):
    if not shutil.which("ufw"):
        return {"active":False,"allowed":True}
    proc=subprocess.run(["ufw","status"],text=True,capture_output=True,timeout=8,check=False)
    if proc.returncode!=0 or "status: active" not in (proc.stdout or "").lower():
        return {"active":False,"allowed":True}
    run=subprocess.run(["ufw","allow",f"{int(port)}/{proto}","comment",f"Makia {label}"],text=True,capture_output=True,timeout=15,check=False)
    if run.returncode!=0:
        raise NetworkServiceError((run.stderr or run.stdout or "unable to update UFW").strip()[:600])
    return {"active":True,"allowed":True,"rule":f"{int(port)}/{proto}"}


def _ufw_port_status(port,proto="tcp"):
    if not port or not shutil.which("ufw"):
        return {"active":False,"allowed":True}
    proc=subprocess.run(["ufw","status"],text=True,capture_output=True,timeout=8,check=False)
    text=(proc.stdout or "")
    if proc.returncode!=0 or "status: active" not in text.lower():
        return {"active":False,"allowed":True}
    needle=f"{int(port)}/{str(proto).lower()}"
    allowed=any(needle in line.lower() and "allow" in line.lower() for line in text.splitlines())
    return {"active":True,"allowed":allowed}


def _ufw_reconcile_dns(allowed_networks):
    """Expose DNS only to explicit source networks; never add a global port-53 rule."""
    if not shutil.which("ufw"):
        return {"active":False,"rules":[]}
    proc=subprocess.run(["ufw","status","numbered"],text=True,capture_output=True,timeout=8,check=False)
    if proc.returncode!=0 or "status: active" not in (proc.stdout or "").lower():
        return {"active":False,"rules":[]}
    numbers=[]
    for line in (proc.stdout or "").splitlines():
        if "makia dns" not in line.lower():
            continue
        match=re.match(r"^\s*\[\s*(\d+)\]",line)
        if match:numbers.append(int(match.group(1)))
    for number in sorted(numbers,reverse=True):
        deleted=subprocess.run(["ufw","--force","delete",str(number)],text=True,capture_output=True,timeout=15,check=False)
        if deleted.returncode!=0:
            raise NetworkServiceError((deleted.stderr or deleted.stdout or "unable to remove old Makia DNS UFW rule").strip()[:600])
    created=[]
    for network in dict.fromkeys(str(x) for x in allowed_networks if str(x)):
        for proto in ("udp","tcp"):
            run=subprocess.run(
                ["ufw","allow","from",network,"to","any","port","53","proto",proto,"comment","Makia DNS"],
                text=True,capture_output=True,timeout=15,check=False,
            )
            if run.returncode!=0:
                raise NetworkServiceError((run.stderr or run.stdout or "unable to add Makia DNS UFW rule").strip()[:600])
            created.append({"source":network,"port":53,"proto":proto})
    return {"active":True,"rules":created}


def mtproxy_install_command(host="",port=0,install_only=False):
    args=["sudo","/usr/local/sbin/makia-install-mtproxy"]
    if install_only:
        args.append("--install-only")
    if host:
        args+=["--host",_validate_host(host)]
    if int(port or 0):
        args+=["--port",str(_validate_port(port))]
    return " ".join(args)


def mtproxy_status(host_hint=""):
    env=_read_env(MTPROXY_ENV)
    host=env.get("MTPROXY_PUBLIC_HOST") or (str(host_hint or "").strip())
    port=int(env.get("MTPROXY_PORT") or 0)
    secret=_mtproxy_secret()
    front_domain=env.get("MTPROXY_FRONT_DOMAIN") or ""
    configured=bool(host and port and re.fullmatch(r"ee[0-9a-fA-F]+",secret))
    active=_active(MTPROXY_SERVICE)
    listener=bool(port and _port_busy(port,"tcp"))
    firewall=_ufw_port_status(port,"tcp")
    runtime_error=_mtproxy_runtime_diagnostics(secret) if configured and not active else ""
    client_secret=secret.lower() if secret else ""
    query=urllib.parse.urlencode({"server":host,"port":port,"secret":client_secret}) if configured else ""
    return {
        "installed":MTPROXY_BIN.exists(),
        "configured":configured,
        "service_active":active,
        "listener":listener,
        "firewall_active":bool(firewall.get("active")),
        "firewall_allowed":bool(firewall.get("allowed")),
        "runtime_error":runtime_error,
        "host":host,
        "port":port,
        "front_domain":front_domain,
        "secret":client_secret,
        "secret_last4":secret[-4:] if secret else "",
        "tg_link":f"tg://proxy?{query}" if query else "",
        "https_link":f"https://t.me/proxy?{query}" if query else "",
        "install_command":mtproxy_install_command(install_only=True),
    }


def configure_mtproxy(host,port=0,rotate_secret=False):
    if not MTPROXY_BIN.exists():
        raise NetworkServiceError("Telegram MTProxy is not installed; run the install command first")
    host=_validate_host(host)
    previous_state=MTPROXY_ENV.read_bytes() if MTPROXY_ENV.exists() else None
    previous_config=MTPROXY_CONFIG.read_bytes() if MTPROXY_CONFIG.exists() else None
    old=_read_env(MTPROXY_ENV)
    try: requested=int(port or 0)
    except Exception as exc: raise NetworkServiceError("invalid port") from exc
    if requested<0 or requested>65535:
        raise NetworkServiceError("invalid port")
    current_port=int(old.get("MTPROXY_PORT") or 0)
    # AUTO (0) keeps an already-running Makia port, otherwise selects a free
    # managed high port. 443 is deliberately not preferred because the panel's
    # HTTPS listener commonly owns it.
    if requested==0 and current_port and (_active(MTPROXY_SERVICE) or not _port_busy(current_port,"tcp")):
        selected=current_port
    elif requested and requested==current_port and (_active(MTPROXY_SERVICE) or not _port_busy(current_port,"tcp")):
        selected=current_port
    else:
        selected=_free_port(
            requested,(8443,9443,10443,11443,12443,13010,18080,24443,30443,40443,50443),
            "tcp",kernel_fallback=True
        )
    secret=_mtproxy_secret()
    front_domain=host
    try:
        ipaddress.ip_address(host)
        raise NetworkServiceError("Telegram FakeTLS proxy requires a DNS hostname pointing to this VPS, not a raw IP")
    except ValueError:
        pass
    if rotate_secret or not re.fullmatch(r"ee[0-9a-fA-F]+",secret) or old.get("MTPROXY_FRONT_DOMAIN")!=front_domain:
        secret=_run([str(MTPROXY_BIN),"generate-secret","--hex",front_domain],timeout=15).strip()
        if not re.fullmatch(r"ee[0-9a-fA-F]+",secret):
            raise NetworkServiceError("mtg returned an invalid FakeTLS secret")
    state=(
        f"MTPROXY_PUBLIC_HOST={host}\n"
        f"MTPROXY_PORT={selected}\n"
        f"MTPROXY_FRONT_DOMAIN={front_domain}\n"
    )
    _ensure_mtproxy_config_access()
    _atomic_write(MTPROXY_ENV,state,0o600)
    _write_mtproxy_config(secret,selected)
    try:
        # Do not make mtg doctor a start gate: doctor also probes external
        # Telegram/fronting connectivity. The generated TOML is deterministic;
        # the critical host preflight is that the real service account can
        # traverse/read it before systemd is started.
        _run(["runuser","-u","makia-mtproxy","--","test","-r",str(MTPROXY_CONFIG)],timeout=10)
        _run(["systemctl","daemon-reload"],timeout=15)
        _run(["systemctl","enable","--now",MTPROXY_SERVICE],timeout=30)
        _run(["systemctl","restart",MTPROXY_SERVICE],timeout=30)
        deadline=time.monotonic()+25
        while time.monotonic()<deadline and not (_active(MTPROXY_SERVICE) and _port_busy(selected,"tcp")):
            time.sleep(.25)
        if not _active(MTPROXY_SERVICE) or not _port_busy(selected,"tcp"):
            detail=_mtproxy_runtime_diagnostics(secret)
            suffix=f": {detail}" if detail else ""
            raise NetworkServiceError(f"MTProxy did not reach an active TCP listener{suffix}")
    except Exception:
        if previous_state is not None:
            MTPROXY_ENV.write_bytes(previous_state);os.chmod(MTPROXY_ENV,0o600)
        if previous_config is not None:
            MTPROXY_CONFIG.write_bytes(previous_config);os.chmod(MTPROXY_CONFIG,0o640)
            try:
                os.chown(MTPROXY_CONFIG,0,_ensure_mtproxy_config_access())
            except Exception:pass
        try:
            if previous_state is not None and previous_config is not None:
                _run(["systemctl","restart",MTPROXY_SERVICE],timeout=20)
            else:
                # Keep the first attempted host/secret/port for diagnostics/retry,
                # but stop the failed runtime rather than deleting operator input.
                _run(["systemctl","disable","--now",MTPROXY_SERVICE],timeout=20)
        except Exception:pass
        raise
    firewall_warning=""
    try:
        _ufw_allow(selected,"tcp","Telegram MTProxy")
    except Exception as exc:
        # Firewall integration is fail-closed. Do not destroy an otherwise
        # valid MTProxy identity/runtime just because the UFW helper failed.
        firewall_warning=str(exc)[:600]
    result=mtproxy_status(host)
    result["firewall_warning"]=firewall_warning
    result["requested_port"]=requested
    result["port_adjusted"]=selected!=requested
    result["secret_rotated"]=bool(rotate_secret)
    return result


def _interface_ipv4(name):
    if not name or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}",name):
        return ""
    try:out=_run(["ip","-o","-4","addr","show","dev",name,"scope","global"],timeout=5)
    except Exception:return ""
    m=re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/\d+",out)
    return m.group(1) if m else ""


def _default_public_ipv4():
    try:out=_run(["ip","-o","-4","addr","show","scope","global"],timeout=5)
    except Exception:return ""
    for raw in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/\d+",out):
        try:
            addr=ipaddress.ip_address(raw)
            if addr.is_global:return addr.compressed
        except ValueError:pass
    return ""


def _cidr(value):
    try:return str(ipaddress.ip_network(str(value).strip(),strict=False))
    except ValueError as exc:raise NetworkServiceError(f"invalid allowed CIDR: {value}") from exc


def _dns_state():
    if not DNS_STATE.exists():return {}
    try:
        obj=json.loads(DNS_STATE.read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else {}
    except Exception:return {}


def dns_install_command():
    return "sudo /usr/local/sbin/makia-install-dns --install-only"


def dns_status():
    state=_dns_state()
    bind=list(state.get("bind_addresses") or [])
    active=_active(DNS_SERVICE)
    query_ms=None
    if active and shutil.which("dig"):
        try:
            proc=subprocess.run(
                ["dig","@127.0.0.1","example.com","+stats","+time=2","+tries=1"],
                text=True,capture_output=True,timeout=4,check=False,
            )
            match=re.search(r"Query time:\s*(\d+)\s*msec",proc.stdout or "")
            if proc.returncode==0 and match:query_ms=int(match.group(1))
        except Exception:pass
    return {
        "installed":bool(shutil.which("unbound")) and bool(shutil.which("unbound-checkconf")),
        "configured":DNS_CONF.exists(),
        "service_active":active,
        "mode":state.get("mode") or "private",
        "upstream":state.get("upstream") or "cloudflare",
        "upstream_label":DNS_UPSTREAMS.get(state.get("upstream") or "cloudflare",{}).get("label",""),
        "bind_addresses":bind,
        "allowed_cidrs":list(state.get("allowed_cidrs") or []),
        "public_address":state.get("public_address") or "",
        "wireguard_address":state.get("wireguard_address") or _interface_ipv4("wg0"),
        "query_ms":query_ms,
        "install_command":dns_install_command(),
        "upstreams":[{"id":key,"label":value["label"]} for key,value in DNS_UPSTREAMS.items()],
        "warning":"DNS resolver latency is not the same as game-server ping and DNS alone cannot guarantee geo-restriction bypass.",
    }


def configure_dns(mode="private",upstream="cloudflare",allowed_cidrs=None,public_address=""):
    if not shutil.which("unbound") or not shutil.which("unbound-checkconf"):
        raise NetworkServiceError("Unbound is not installed; run the install command first")
    mode=str(mode or "private").lower()
    if mode not in {"private","public"}:
        raise NetworkServiceError("DNS mode must be private or public")
    if upstream not in DNS_UPSTREAMS:
        raise NetworkServiceError("unsupported DNS upstream")
    allowed=[_cidr(x) for x in (allowed_cidrs or []) if str(x).strip()]
    wg=_interface_ipv4("wg0")
    public=""
    bind=["127.0.0.1"]
    access=["127.0.0.0/8"]
    if wg:
        bind.append(wg)
        # The standard Makia WireGuard subnet is /24; infer only the local /24
        # for resolver ACL and never open the resolver to the whole Internet.
        access.append(str(ipaddress.ip_network(f"{wg}/24",strict=False)))
    if mode=="public":
        if not allowed:
            raise NetworkServiceError("public DNS requires at least one client IP/CIDR allowlist entry; open resolvers are blocked")
        public=_validate_host(public_address or _default_public_ipv4())
        try:
            address=ipaddress.ip_address(public)
            if address.version!=4:
                raise NetworkServiceError("public DNS currently requires IPv4")
        except ValueError as exc:
            raise NetworkServiceError("public DNS bind address must be this VPS IPv4") from exc
        local=_default_public_ipv4()
        if local and public!=local:
            raise NetworkServiceError("public DNS bind address does not match this VPS global IPv4")
        if _port_busy(53,"udp",public) or _port_busy(53,"tcp",public):
            current=set(_dns_state().get("bind_addresses") or [])
            if public not in current or not _active(DNS_SERVICE):
                raise NetworkServiceError("TCP/UDP 53 is already occupied on the public address")
        bind.append(public)
        access.extend(allowed)

    bind=list(dict.fromkeys(bind))
    access=list(dict.fromkeys(access))
    lines=[
        "server:",
        "    verbosity: 1",
        "    port: 53",
        "    do-ip4: yes",
        "    do-ip6: no",
        "    do-udp: yes",
        "    do-tcp: yes",
        "    hide-identity: yes",
        "    hide-version: yes",
        "    qname-minimisation: yes",
        "    harden-glue: yes",
        "    harden-dnssec-stripped: yes",
        "    prefetch: yes",
        "    serve-expired: yes",
        "    cache-min-ttl: 30",
        "    cache-max-ttl: 86400",
        "    access-control: 0.0.0.0/0 refuse",
    ]
    for address in bind:
        lines.append(f"    interface: {address}")
    for network in access:
        lines.append(f"    access-control: {network} allow")
    lines+=["","forward-zone:","    name: \".\"","    forward-tls-upstream: yes"]
    for server in DNS_UPSTREAMS[upstream]["servers"]:
        lines.append(f"    forward-addr: {server}")
    text="\n".join(lines)+"\n"

    DNS_CONF.parent.mkdir(parents=True,exist_ok=True)
    DNS_STATE.parent.mkdir(parents=True,exist_ok=True)
    old_conf=DNS_CONF.read_bytes() if DNS_CONF.exists() else None
    old_state=DNS_STATE.read_bytes() if DNS_STATE.exists() else None
    fd,tmp=tempfile.mkstemp(prefix=".makia-unbound-",suffix=".conf",dir=str(DNS_CONF.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            os.fchmod(fh.fileno(),0o600);fh.write(text);fh.flush();os.fsync(fh.fileno())
        _run(["unbound-checkconf",tmp],timeout=10)
        os.replace(tmp,DNS_CONF);os.chmod(DNS_CONF,0o600)
        state={
            "mode":mode,"upstream":upstream,"bind_addresses":bind,
            "allowed_cidrs":allowed,"public_address":public,"wireguard_address":wg,
        }
        _atomic_write(DNS_STATE,json.dumps(state,ensure_ascii=False,indent=2)+"\n",0o600)
        _run(["systemctl","enable","--now",DNS_SERVICE],timeout=30)
        _run(["systemctl","restart",DNS_SERVICE],timeout=30)
        if not _active(DNS_SERVICE):
            raise NetworkServiceError("Unbound did not become active")
        # Mirror Unbound ACLs at the firewall. Loopback needs no UFW rule;
        # WireGuard/public clients receive source-scoped rules only.
        firewall_sources=[network for network in access if network!="127.0.0.0/8"]
        _ufw_reconcile_dns(firewall_sources)
    except Exception:
        if os.path.exists(tmp):os.unlink(tmp)
        if old_conf is None:DNS_CONF.unlink(missing_ok=True)
        else:DNS_CONF.write_bytes(old_conf);os.chmod(DNS_CONF,0o600)
        if old_state is None:DNS_STATE.unlink(missing_ok=True)
        else:DNS_STATE.write_bytes(old_state);os.chmod(DNS_STATE,0o600)
        try:_run(["systemctl","restart",DNS_SERVICE],timeout=20)
        except Exception:pass
        raise
    return dns_status()
