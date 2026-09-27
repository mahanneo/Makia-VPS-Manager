import ipaddress
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from cryptography import x509

NGINX_SITE=Path("/etc/nginx/sites-available/makia-vps-manager")
DOMAIN_RE=re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$")
EMAIL_RE=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

class PanelOperationError(RuntimeError):
    pass

def _run(args, timeout=120):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise PanelOperationError(str(exc)) from exc
    if p.returncode!=0:
        raise PanelOperationError((p.stderr or p.stdout or "operation failed").strip()[:1200])
    return p.stdout.strip()

def validate_domain(domain):
    domain=(domain or "").strip().lower().rstrip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise PanelOperationError("invalid domain name")
    return domain

def _local_ipv4_candidates():
    found=set()
    if shutil.which("ip"):
        p=subprocess.run(["ip","-4","-o","addr","show","scope","global"],text=True,capture_output=True,timeout=8,check=False)
        if p.returncode==0:
            for value in re.findall(r"\binet\s+(\d+(?:\.\d+){3})/",p.stdout or ""):
                try:
                    addr=ipaddress.ip_address(value)
                    if addr.version==4 and addr.is_global:
                        found.add(addr.compressed)
                except ValueError:
                    pass
    return sorted(found)

def _service_active(name):
    if not shutil.which("systemctl"):
        return False
    p=subprocess.run(["systemctl","is-active",name],text=True,capture_output=True,timeout=8,check=False)
    return p.returncode==0 and (p.stdout or "").strip()=="active"

def _nginx_config_ok():
    if not shutil.which("nginx"):
        return False
    p=subprocess.run(["nginx","-t"],text=True,capture_output=True,timeout=15,check=False)
    return p.returncode==0

def _listen_ports():
    ports=set()
    if not shutil.which("ss"):
        return ports
    p=subprocess.run(["ss","-H","-ltn"],text=True,capture_output=True,timeout=8,check=False)
    if p.returncode!=0:
        return ports
    for line in (p.stdout or "").splitlines():
        for value in re.findall(r":(\d+)\b",line):
            try: ports.add(int(value))
            except ValueError: pass
    return ports

def domain_status(domain=None):
    resolved=[]
    if domain:
        try:
            resolved=sorted({x[4][0] for x in socket.getaddrinfo(domain,None,socket.AF_INET)})
        except Exception:
            resolved=[]
    local_ipv4=_local_ipv4_candidates()
    dns_matches_server=None
    if resolved and local_ipv4:
        dns_matches_server=bool(set(resolved)&set(local_ipv4))
    cert_exists=False
    cert_expires_at=None
    cert_days_left=None
    if domain:
        cert_path=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
        cert_exists=cert_path.exists()
        if cert_exists:
            try:
                cert=x509.load_pem_x509_certificate(cert_path.read_bytes())
                expires=getattr(cert,"not_valid_after_utc",None)
                if expires is None:
                    expires=cert.not_valid_after.replace(tzinfo=timezone.utc)
                cert_expires_at=expires.isoformat()
                cert_days_left=int((expires-datetime.now(timezone.utc)).total_seconds()//86400)
            except Exception:
                pass
    listeners=_listen_ports()
    return {
        "domain":domain,
        "resolved_ipv4":resolved,
        "local_ipv4":local_ipv4,
        "dns_matches_server":dns_matches_server,
        "certificate":cert_exists,
        "certificate_expires_at":cert_expires_at,
        "certificate_days_left":cert_days_left,
        "certbot_installed":bool(shutil.which("certbot")),
        "nginx_site":str(NGINX_SITE),
        "nginx_installed":bool(shutil.which("nginx")),
        "nginx_active":_service_active("nginx"),
        "nginx_config_ok":_nginx_config_ok(),
        "http_listener":80 in listeners,
        "https_listener":443 in listeners,
    }

def apply_domain(domain):
    domain=validate_domain(domain)
    if not NGINX_SITE.exists():
        raise PanelOperationError("Makia Nginx site is not installed")
    original=NGINX_SITE.read_text(encoding="utf-8")
    backup=NGINX_SITE.with_suffix(".conf.makia-backup")
    backup.write_text(original,encoding="utf-8")
    if re.search(r"(?m)^\s*server_name\s+[^;]+;",original):
        # This file is dedicated to Makia. Certbot may create a second HTTPS
        # server block, so keep every Makia server_name in sync.
        updated=re.sub(r"(?m)^\s*server_name\s+[^;]+;",f"    server_name {domain};",original)
    else:
        updated=original.replace("server {","server {\n    server_name "+domain+";",1)
    NGINX_SITE.write_text(updated,encoding="utf-8")
    try:
        _run(["nginx","-t"],timeout=20)
        _run(["systemctl","reload","nginx"],timeout=20)
    except Exception:
        NGINX_SITE.write_text(original,encoding="utf-8")
        try:
            _run(["nginx","-t"],timeout=20)
            _run(["systemctl","reload","nginx"],timeout=20)
        except Exception:
            pass
        raise
    return domain_status(domain)

def issue_certificate(domain,email):
    domain=validate_domain(domain)
    email=(email or "").strip()
    if not EMAIL_RE.fullmatch(email):
        raise PanelOperationError("invalid email address")
    if not NGINX_SITE.exists():
        raise PanelOperationError("Makia Nginx site is not installed")

    pre=domain_status(domain)
    if not pre["resolved_ipv4"]:
        raise PanelOperationError("domain has no IPv4/A record; point the domain to this VPS before issuing HTTPS")
    if pre["dns_matches_server"] is False:
        raise PanelOperationError(
            "domain A record does not point to this VPS public IPv4; use a direct/DNS-only record before issuing HTTPS"
        )

    original=NGINX_SITE.read_text(encoding="utf-8")
    try:
        # Certificate issuance must be self-contained: users should not have to
        # remember to press the separate Apply-domain button first.
        apply_domain(domain)
        if not shutil.which("certbot"):
            _run(["apt-get","update"],timeout=180)
            _run(["apt-get","install","-y","certbot","python3-certbot-nginx"],timeout=300)
        _run([
            "certbot","--nginx","-d",domain,
            "--non-interactive","--agree-tos","--email",email,
            "--redirect"
        ],timeout=300)
        _run(["nginx","-t"],timeout=20)
        _run(["systemctl","reload","nginx"],timeout=20)
        result=domain_status(domain)
        if not result.get("certificate"):
            raise PanelOperationError("Certbot completed but the expected certificate file was not found")
        if not result.get("https_listener"):
            raise PanelOperationError("certificate exists but Nginx is not listening on TCP/443")
        return result
    except Exception:
        # Restore the complete pre-operation Nginx site. This also reverses
        # partial Certbot edits if issuance or verification fails.
        try:
            NGINX_SITE.write_text(original,encoding="utf-8")
            _run(["nginx","-t"],timeout=20)
            _run(["systemctl","reload","nginx"],timeout=20)
        except Exception:
            pass
        raise
