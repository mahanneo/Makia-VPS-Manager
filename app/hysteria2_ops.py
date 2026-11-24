"""Managed Hysteria2 inbound backed by the pinned sing-box runtime.

Secrets are stored only in the root-owned service config and delivered through
Makia's existing encrypted access-artifact workflow. The UI never exposes the
raw sing-box config.
"""
import grp
import ipaddress
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
from datetime import datetime, timezone
from pathlib import Path

from .db import get_setting

BINARY_CANDIDATES = ("/usr/bin/sing-box", "/usr/local/bin/sing-box")
CONFIG_PATH = Path("/etc/sing-box/makia-hysteria2.json")
STATE_PATH = Path("/etc/makia-vps-manager/hysteria2-state.json")
TLS_CERT = Path("/etc/sing-box/tls/fullchain.pem")
TLS_KEY = Path("/etc/sing-box/tls/privkey.pem")
SERVICE = "makia-hysteria2"
DEFAULT_PORT = 8446
INBOUND_TAG = "makia-hysteria2-in"
BACKUP_ROOT = Path("/var/backups/makia-vps-manager/hysteria2")


class Hysteria2Error(RuntimeError):
    pass


def _binary():
    for candidate in BINARY_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("sing-box")


def _run(args, timeout=30):
    try:
        result = subprocess.run(
            [str(x) for x in args], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Hysteria2Error(f"Hysteria2 operation failed: {type(exc).__name__}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "operation failed").strip()
        raise Hysteria2Error(detail[:800])
    return (result.stdout or "").strip()


def _active():
    if not shutil.which("systemctl"):
        return False
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE],
        capture_output=True, text=True, timeout=8, check=False,
    )
    return result.returncode == 0


def _read_json(path, default=None):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default
    return value if isinstance(value, dict) else default


def _load_config():
    config = _read_json(CONFIG_PATH)
    if not config:
        raise Hysteria2Error("Hysteria2 is not configured; run the Makia Hysteria2 setup script first.")
    inbounds = config.get("inbounds")
    inbound = next(
        (item for item in inbounds or [] if isinstance(item, dict) and item.get("tag") == INBOUND_TAG),
        None,
    )
    if not inbound or inbound.get("type") != "hysteria2":
        raise Hysteria2Error("Managed Hysteria2 inbound is missing from the sing-box config.")
    return config, inbound


def _state():
    return _read_json(STATE_PATH, {}) or {}


def _port_listener(port):
    if not shutil.which("ss"):
        return False
    result = subprocess.run(
        ["ss", "-H", "-lunp"], capture_output=True, text=True,
        timeout=8, check=False,
    )
    if result.returncode:
        return False
    for line in (result.stdout or "").splitlines():
        fields = line.split()
        # `ss -H` omits the netid column: state, recv-q, send-q, local, peer, users.
        if len(fields) < 5:
            continue
        local = fields[3]
        if not re.search(rf":{int(port)}$", local):
            continue
        if "sing-box" in line:
            return True
    return False


def _certificate_status(domain):
    if not domain or not TLS_CERT.is_file() or not TLS_KEY.is_file():
        return False, "Hysteria2 TLS certificate or private key is missing."
    try:
        valid = subprocess.run(
            ["openssl", "x509", "-in", str(TLS_CERT), "-noout", "-checkend", "0"],
            capture_output=True, text=True, timeout=8, check=False,
        )
        host = subprocess.run(
            ["openssl", "x509", "-in", str(TLS_CERT), "-noout", "-checkhost", domain],
            capture_output=True, text=True, timeout=8, check=False,
        )
        cert_pub = subprocess.run(
            ["openssl", "x509", "-in", str(TLS_CERT), "-pubkey", "-noout"],
            capture_output=True, text=True, timeout=8, check=False,
        )
        key_pub = subprocess.run(
            ["openssl", "pkey", "-in", str(TLS_KEY), "-pubout"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False, "Unable to validate the Hysteria2 TLS certificate."
    if valid.returncode:
        return False, "Hysteria2 TLS certificate is expired or not yet valid."
    if host.returncode:
        return False, "Hysteria2 TLS certificate does not cover the configured domain."
    if cert_pub.returncode or key_pub.returncode or cert_pub.stdout.strip() != key_pub.stdout.strip():
        return False, "Hysteria2 TLS certificate and private key do not match."
    return True, ""


def status():
    binary = _binary()
    state = _state()
    config = _read_json(CONFIG_PATH, {}) or {}
    inbound = next(
        (item for item in config.get("inbounds", []) if isinstance(item, dict) and item.get("tag") == INBOUND_TAG),
        {},
    )
    port = int(inbound.get("listen_port") or state.get("port") or DEFAULT_PORT)
    users = inbound.get("users") if isinstance(inbound.get("users"), list) else []
    domain = str(state.get("domain") or get_setting("panel_domain", "") or "").strip()
    configured = bool(inbound.get("type") == "hysteria2" and state.get("domain"))
    service_active = _active() if binary and configured else False
    listener = _port_listener(port) if service_active else False
    cert_valid, cert_error = _certificate_status(domain) if configured else (False, "Hysteria2 is not configured.")
    warnings = []
    if not binary:
        warnings.append("sing-box is not installed.")
    if not configured:
        warnings.append("Hysteria2 has not been configured.")
    elif not cert_valid:
        warnings.append(cert_error)
    if configured and not service_active:
        warnings.append("makia-hysteria2.service is not active.")
    if service_active and not listener:
        warnings.append(f"No sing-box UDP listener was detected on port {port}.")
    if configured and not users:
        warnings.append("No Hysteria2 users configured; service remains stopped until the first user is created.")
    return {
        "installed": bool(binary),
        "binary": binary or "",
        "version": _version(binary) if binary else "",
        "configured": configured,
        "service": SERVICE,
        "service_active": service_active,
        "listener": listener,
        "ready": bool(binary and configured and service_active and listener and cert_valid),
        "certificate_valid": cert_valid,
        "certificate_error": cert_error,
        "domain": domain,
        "endpoint": domain,
        "port": port,
        "transport": "udp",
        "users_count": len(users),
        "warnings": warnings,
    }


def _version(binary):
    try:
        return _run([binary, "version"], timeout=8).splitlines()[0][:160]
    except Hysteria2Error:
        return ""


def _validate_name(name):
    name = str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,47}", name):
        raise Hysteria2Error("Username must be 3–48 characters using letters, numbers, dot, underscore or hyphen.")
    return name


def _validate_password(password):
    password = str(password or "")
    if not password:
        return secrets.token_urlsafe(24)
    if len(password) < 16 or len(password) > 128 or any(ord(ch) < 32 for ch in password):
        raise Hysteria2Error("Hysteria2 password must be 16–128 printable characters.")
    return password


def _backup_config():
    if not CONFIG_PATH.is_file():
        return ""
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BACKUP_ROOT, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUP_ROOT / f"makia-hysteria2-{stamp}-{secrets.token_hex(3)}.json"
    shutil.copy2(CONFIG_PATH, target)
    os.chmod(target, 0o600)
    return str(target)


def _write_config(config, restart=True):
    if not isinstance(config, dict):
        raise Hysteria2Error("Invalid Hysteria2 config.")
    binary = _binary()
    if not binary:
        raise Hysteria2Error("sing-box is not installed; run the Makia Hysteria2 setup script.")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".makia-hysteria2-", suffix=".json", dir=str(CONFIG_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o640)
        if os.geteuid() == 0:
            try:
                group = grp.getgrnam("sing-box")
                os.chown(temp_name, 0, group.gr_gid)
            except KeyError:
                raise Hysteria2Error("The sing-box service group is missing.")
        _run([binary, "check", "-c", temp_name], timeout=30)
        backup = _backup_config()
        os.replace(temp_name, CONFIG_PATH)
        os.chmod(CONFIG_PATH, 0o640)
        if os.geteuid() == 0:
            group = grp.getgrnam("sing-box")
            os.chown(CONFIG_PATH, 0, group.gr_gid)
        port = next(
            (int(item.get("listen_port")) for item in config.get("inbounds", [])
             if isinstance(item, dict) and item.get("tag") == INBOUND_TAG),
            DEFAULT_PORT,
        )
        if not restart:
            return {"backup": backup, "port": port}
        try:
            _run(["systemctl", "restart", SERVICE], timeout=45)
            _run(["systemctl", "enable", SERVICE], timeout=20)
            if not _active():
                raise Hysteria2Error("makia-hysteria2.service did not become active after the config update.")
            deadline = time.time() + 8
            while time.time() < deadline and not _port_listener(port):
                time.sleep(0.25)
            if not _port_listener(port):
                raise Hysteria2Error(f"sing-box did not bind UDP/{port} after restart.")
        except Exception as exc:
            if backup and Path(backup).is_file():
                shutil.copy2(backup, CONFIG_PATH)
                os.chmod(CONFIG_PATH, 0o640)
                if os.geteuid() == 0:
                    group = grp.getgrnam("sing-box")
                    os.chown(CONFIG_PATH, 0, group.gr_gid)
                subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, timeout=45, check=False)
            raise Hysteria2Error(f"Hysteria2 config update rolled back: {str(exc)[:400]}") from exc
        return {"backup": backup, "port": port}
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def share_link_for_user(name, user, domain, port):
    host = str(domain or "").strip()
    if not host:
        raise Hysteria2Error("A TLS domain is required for a Hysteria2 share link.")
    try:
        host = ipaddress.ip_address(host).compressed
        host_for_uri = f"[{host}]" if ":" in host else host
    except ValueError:
        host_for_uri = host.encode("idna").decode("ascii").lower()
    params = urllib.parse.urlencode({"sni": domain, "alpn": "h3"})
    password = urllib.parse.quote(str(user.get("password") or ""), safe="")
    return f"hysteria2://{password}@{host_for_uri}:{int(port)}/?{params}#{urllib.parse.quote(name, safe='')}"


def list_users():
    try:
        _, inbound = _load_config()
    except Hysteria2Error:
        return []
    return [{"name": str(item.get("name") or "")} for item in inbound.get("users", []) if isinstance(item, dict) and item.get("name")]


def get_user_credentials(name):
    name = _validate_name(name)
    _, inbound = _load_config()
    for item in inbound.get("users", []):
        if isinstance(item, dict) and item.get("name") == name:
            return {"name": name, "password": str(item.get("password") or "")}
    return None


def create_user(name, password=""):
    name = _validate_name(name)
    config, inbound = _load_config()
    users = list(inbound.get("users") or [])
    current = status()
    if not current.get("installed") or not current.get("configured") or not current.get("certificate_valid"):
        raise Hysteria2Error("Hysteria2 runtime or TLS certificate is not ready: " + " ".join(current.get("warnings") or []))
    if users and not current.get("ready"):
        raise Hysteria2Error("Existing Hysteria2 users are configured but the runtime is not healthy; repair diagnostics before changing users.")
    password = _validate_password(password)
    if any(str(item.get("name") or "").casefold() == name.casefold() for item in users if isinstance(item, dict)):
        raise Hysteria2Error("A Hysteria2 user with this name already exists.")
    user = {"name": name, "password": password}
    inbound["users"] = users + [user]
    applied = _write_config(config)
    state = _state()
    domain = str(state.get("domain") or current.get("domain") or "")
    port = int(inbound.get("listen_port") or current.get("port") or DEFAULT_PORT)
    return {
        "name": name,
        "password": password,
        "server": domain,
        "port": port,
        "share_link": share_link_for_user(name, user, domain, port),
        "backup": applied.get("backup") or "",
    }


def remove_user(name):
    name = _validate_name(name)
    config, inbound = _load_config()
    users = list(inbound.get("users") or [])
    remaining = [item for item in users if not (isinstance(item, dict) and item.get("name") == name)]
    if len(remaining) == len(users):
        raise Hysteria2Error("Hysteria2 user not found.")
    inbound["users"] = remaining
    if remaining:
        result = _write_config(config)
    else:
        was_active = _active()
        try:
            if was_active:
                _run(["systemctl", "stop", SERVICE], timeout=30)
            _run(["systemctl", "disable", SERVICE], timeout=20)
        except Hysteria2Error:
            if was_active:
                subprocess.run(["systemctl", "start", SERVICE], capture_output=True, timeout=30, check=False)
            raise
        try:
            result = _write_config(config, restart=False)
        except Exception:
            if was_active:
                subprocess.run(["systemctl", "enable", SERVICE], capture_output=True, timeout=20, check=False)
                subprocess.run(["systemctl", "start", SERVICE], capture_output=True, timeout=30, check=False)
            raise
    return {"ok": True, "name": name, "backup": result.get("backup") or ""}


def diagnostics():
    result = status()
    return {
        **result,
        "warnings": list(result.get("warnings") or []),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
    }
