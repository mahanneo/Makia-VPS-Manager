"""SSTP integration: non-disruptive status and explicitly provisioned local accounts.

An SSTP runtime needs its own dedicated public TCP/443 binding with a trusted TLS
certificate. Never steal Nginx's listener or silently run a second PPP daemon.
"""
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

from . import protocol_ops

SSTP_CHAP = Path("/etc/makia-vps-manager/sstp-chap-secrets")
CONFIG_LOCATIONS = (Path("/etc/accel-ppp/accel-ppp.conf"), Path("/etc/accel-ppp.conf"))
_NAME = re.compile(r"[A-Za-z0-9_.-]{3,48}\Z")
_PASSWORD = re.compile(r"[A-Za-z0-9._~-]{10,128}\Z")
_MANAGED = re.compile(r"^([A-Za-z0-9_.-]{3,48})\s+\*\s+([A-Za-z0-9._~-]{10,128})\s+\*\s+# makia-sstp:([A-Za-z0-9_.-]{3,48})$")


def _section(text, name):
    match = re.search(r"(?ms)^\[" + re.escape(name) + r"\]\s*\n(.*?)(?=^\[|\Z)", text)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if line and not line.startswith(("#", ";")):
            key, _, value = line.partition("=")
            result[key.strip().lower()] = value.strip()
    return result


def _run(args):
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _listener(bind, port):
    result = _run(["ss", "-lntpH", f"( sport = :{port} )"])
    if not result or result.returncode:
        return False, False
    lines = result.stdout.splitlines()
    occupied = bool(lines)
    # The dedicated IP and daemon process MUST own this exact listener.
    owned = any("accel-pppd" in line and
                re.search(r"(?:^|\s)" + re.escape(bind) + ":" + str(port) + r"\s", line)
                for line in lines)
    return occupied, owned


def sstp_status():
    config = next((p for p in CONFIG_LOCATIONS if p.is_file()), None)
    text = config.read_text(encoding="utf-8", errors="replace") if config else ""
    modules = _section(text, "modules")
    sstp = _section(text, "sstp")
    chap = _section(text, "chap-secrets")
    bind = sstp.get("bind", "")
    domain = sstp.get("host-name", "")
    try:
        port = int(sstp.get("port", "443"))
    except ValueError:
        port = 0
    # The IP must be dedicated; wildcard would displace the live HTTPS service.
    try:
        socket.inet_aton(bind)
        valid_bind = bind not in {"0.0.0.0", "127.0.0.1"}
    except OSError:
        valid_bind = False
    # Even with no SSTP config, surface an existing 443 owner in diagnostics.
    occupied, owned = _listener(bind if valid_bind else "0.0.0.0", port if port else 443)
    statuses = [_run(["systemctl", "is-active", name])
                for name in ("accel-ppp", "accel-pppd")]
    active = any(result and result.stdout.strip() == "active" for result in statuses)
    installed = bool(shutil.which("accel-pppd"))
    configured = bool(
        config and "sstp" in modules and "chap-secrets" in modules
        and valid_bind and port == 443
        and chap.get("chap-secrets") == str(SSTP_CHAP)
        and domain and sstp.get("ssl-pemfile") and sstp.get("ssl-keyfile")
    )
    cert = Path(sstp["ssl-pemfile"]) if configured else None
    key = Path(sstp["ssl-keyfile"]) if configured else None
    cert_present = bool(cert and key and cert.is_file() and key.is_file())
    tls_ready = False
    if cert_present:
        try:
            from datetime import datetime, timezone
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            from cryptography.x509.oid import ExtensionOID
            cert_obj=x509.load_pem_x509_certificate(cert.read_bytes())
            key_obj=serialization.load_pem_private_key(key.read_bytes(),password=None)
            sans=cert_obj.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
            names=sans.get_values_for_type(x509.DNSName)
            domain_ok=domain.lower() in {value.lower() for value in names}
            key_ok=cert_obj.public_key().public_numbers()==key_obj.public_key().public_numbers()
            now=datetime.now(timezone.utc)
            tls_ready=bool(domain_ok and key_ok and cert_obj.not_valid_before_utc <= now < cert_obj.not_valid_after_utc)
        except Exception:
            tls_ready=False
    store_ready = bool(SSTP_CHAP.is_file() and SSTP_CHAP.stat().st_mode & 0o077 == 0)
    warnings = []
    if not installed:
        warnings.append("accel-ppp SSTP daemon is not installed")
    if not configured:
        warnings.append("dedicated IPv4 TCP/443, SSTP TLS hostname and managed chap-secrets are not configured")
    if not tls_ready:
        warnings.append("trusted SSTP server certificate/domain/key needs validation")
    if occupied and not owned:
        warnings.append("TCP/443 belongs to an existing service; never displace Nginx or active VPN listeners")
    if not owned:
        warnings.append("no dedicated accel-pppd SSTP listener is verified")
    if not store_ready:
        warnings.append("root-only SSTP account store is not provisioned")
    return {
        "installed": installed, "configured": configured, "service_active": active,
        "listener": owned, "tcp_443_occupied": occupied, "tls_ready": tls_ready,
        "store_ready": store_ready, "domain": domain, "bind": bind, "port": port,
        "users": len(list_sstp_users()), "ready": bool(installed and configured and
        active and owned and tls_ready and store_ready),
        "warnings": warnings,
    }


def _read_users():
    if not SSTP_CHAP.is_file():
        return []
    return [line for line in SSTP_CHAP.read_text(encoding="utf-8").splitlines()]


def list_sstp_users():
    users = []
    for line in _read_users():
        match = _MANAGED.fullmatch(line.strip())
        if match and match[1] == match[3]:
            users.append({"name": match[1]})
    return sorted(users, key=lambda x: x["name"].lower())


def get_sstp_user_credentials(name):
    if not _NAME.fullmatch(str(name)):
        return None
    for line in _read_users():
        match = _MANAGED.fullmatch(line.strip())
        if match and match[1] == name and match[3] == name:
            return {"name": name, "password": match[2]}
    return None


def _atomic_store(text):
    if not SSTP_CHAP.parent.is_dir():
        raise protocol_ops.ProtocolError("SSTP credentials directory is not provisioned")
    fd, temp = tempfile.mkstemp(prefix=".makia-sstp-", dir=str(SSTP_CHAP.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, SSTP_CHAP)
    finally:
        Path(temp).unlink(missing_ok=True)


def create_sstp_user(name, password=None):
    status = sstp_status()
    if not status["ready"]:
        raise protocol_ops.ProtocolError("SSTP unavailable: verified dedicated TCP/443, TLS and accel-ppp are required")
    name = str(name or "").strip()
    if not _NAME.fullmatch(name):
        raise protocol_ops.ProtocolError("invalid SSTP username")
    if get_sstp_user_credentials(name):
        raise protocol_ops.ProtocolError("SSTP user already exists")
    password = str(password or secrets.token_urlsafe(18))
    if not _PASSWORD.fullmatch(password):
        raise protocol_ops.ProtocolError("invalid SSTP password format")
    # Strictly managed records. Do not modify L2TP/strongSwan authentication.
    before = "\n".join(_read_users()).rstrip()
    new = f"{name} * {password} * # makia-sstp:{name}"
    _atomic_store((before + "\n" if before else "") + new + "\n")
    return {"ok": True, "name": name, "password": password,
            "server": status["domain"], "port": 443}


def remove_sstp_user(name):
    name = str(name or "").strip()
    if not _NAME.fullmatch(name):
        raise protocol_ops.ProtocolError("invalid SSTP username")
    lines = _read_users()
    kept = [line for line in lines if not (_MANAGED.fullmatch(line.strip()) and
            line.strip().endswith("# makia-sstp:" + name) and
            line.strip().split()[0] == name)]
    if len(lines) == len(kept):
        raise protocol_ops.ProtocolError("SSTP managed user not found")
    _atomic_store("\n".join(kept).rstrip() + "\n")
    return {"ok": True, "name": name,
            "warning": "Existing active PPP sessions need verified runtime termination; credentials are removed for future authentication."}
