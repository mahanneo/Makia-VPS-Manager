import base64
import hashlib
import os
import secrets
import time
import urllib.parse
from datetime import date, datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .config import BASE_DIR, COOKIE_NAME
from .db import (
    audit,
    clear_login_failures,
    connect,
    get_profile,
    login_rate_state,
    now,
    record_login_failure,
)
from .security import hash_password, read_session, verify_password
from . import access_ops

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

CLIENT_SESSION_COOKIE = "makia_client_session"
CLIENT_DEVICE_COOKIE = "makia_client_device"
CLIENT_ACTOR_PREFIX = "client:"
CLIENT_ACCESS_KINDS = {"ssh", "xray", "wireguard", "openvpn", "outline"}


def _enabled() -> bool:
    return (os.getenv("MAKIA_CLIENT_APP_ENABLED") or "0").strip().lower() in {"1", "true", "yes", "on"}


def _require_enabled():
    if not _enabled():
        raise HTTPException(404, "client app is disabled")


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "") or "unknown"


def _secure_cookie(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", "").lower() == "https" or request.url.scheme == "https"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64url_decode(value: str) -> bytes:
    raw = str(value or "").strip()
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _request_origin(request: Request) -> str:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",", 1)[0].strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",", 1)[0].strip()
    if proto not in {"http", "https"} or not host:
        raise HTTPException(400, "unable to determine control-plane origin")
    return f"{proto}://{host}"


def _agent_signature_message(grant: str, nonce: str, timestamp: int) -> bytes:
    return f"makia-agent-v1\n{grant}\n{nonce}\n{int(timestamp)}".encode("utf-8")


def _session_ttl_seconds() -> int:
    try:
        hours = int(os.getenv("MAKIA_CLIENT_APP_SESSION_HOURS") or "12")
    except ValueError:
        hours = 12
    return max(1, min(hours, 24 * 30)) * 3600


def _profile_expired(profile: dict | None) -> bool:
    if not profile:
        return False
    raw = str(profile.get("expire_date") or "").strip()
    if not raw:
        return False
    try:
        return date.fromisoformat(raw[:10]) < date.today()
    except ValueError:
        return False


def _effective_policy(account: dict) -> dict:
    profile_name = str(account.get("profile_username") or account.get("username") or "").strip()
    profile = get_profile(profile_name) if profile_name else None
    enabled = bool(account.get("active"))
    if profile:
        enabled = enabled and bool(profile.get("enabled"))
    return {
        "profile": profile,
        "profile_username": profile_name,
        "enabled": enabled,
        "expired": _profile_expired(profile),
        "device_limit": max(1, int((profile or {}).get("device_limit") or 1)),
        "session_limit": max(1, int((profile or {}).get("connection_limit") or 1)),
        "quota_mb": max(0, int((profile or {}).get("quota_mb") or 0)),
        "plan": str((profile or {}).get("plan") or ""),
        "expire_date": str((profile or {}).get("expire_date") or ""),
    }


def _account_by_username(username: str):
    with connect() as con:
        row = con.execute(
            "SELECT * FROM client_accounts WHERE username=? COLLATE NOCASE",
            (str(username or "").strip(),),
        ).fetchone()
        return dict(row) if row else None


def _account_by_id(account_id: int):
    with connect() as con:
        row = con.execute("SELECT * FROM client_accounts WHERE id=?", (int(account_id),)).fetchone()
        return dict(row) if row else None


def _device_platform(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "android" in ua:
        return "Android"
    if "iphone" in ua or "ipad" in ua:
        return "iOS"
    if "windows" in ua:
        return "Windows"
    if "mac os" in ua or "macintosh" in ua:
        return "macOS"
    if "linux" in ua:
        return "Linux"
    return "Browser"


def _ensure_device_cookie(request: Request, response):
    token = (request.cookies.get(CLIENT_DEVICE_COOKIE) or "").strip()
    if not token.startswith("mkd_") or len(token) < 24:
        token = "mkd_" + secrets.token_urlsafe(24)
        response.set_cookie(
            CLIENT_DEVICE_COOKIE,
            token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=_secure_cookie(request),
            samesite="strict",
            path="/client-app",
        )
    return token


def _client_session(request: Request, touch: bool = True):
    token = (request.cookies.get(CLIENT_SESSION_COOKIE) or "").strip()
    if not token:
        return None
    token_hash = _token_hash(token)
    now_ts = int(time.time())
    with connect() as con:
        row = con.execute(
            """SELECT s.*,a.username,a.display_name,a.profile_username,a.active AS account_active,
                      d.device_hash,d.label AS device_label,d.platform,d.active AS device_active,
                      d.public_key,d.agent_paired_at,d.agent_version,d.agent_platform
               FROM client_sessions s
               JOIN client_accounts a ON a.id=s.account_id
               JOIN client_devices d ON d.id=s.device_id
               WHERE s.token_hash=? AND s.revoked_at=0 AND s.expires_at>?""",
            (token_hash, now_ts),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        account = {
            "id": data["account_id"],
            "username": data["username"],
            "display_name": data["display_name"],
            "profile_username": data["profile_username"],
            "active": data["account_active"],
        }
        policy = _effective_policy(account)
        if not data.get("device_active") or not policy["enabled"] or policy["expired"]:
            con.execute("UPDATE client_sessions SET revoked_at=? WHERE id=?", (now_ts, data["id"]))
            return None
        if touch:
            con.execute(
                "UPDATE client_sessions SET last_seen_at=? WHERE id=?",
                (now(), data["id"]),
            )
            con.execute(
                "UPDATE client_devices SET last_seen_at=?,last_ip=? WHERE id=?",
                (now(), _client_ip(request), data["device_id"]),
            )
        data["policy"] = policy
        return data


def _require_client(request: Request):
    _require_enabled()
    session = _client_session(request)
    if not session:
        raise HTTPException(401, "client session required")
    return session


def _require_admin(request: Request):
    _require_enabled()
    actor = read_session(request.cookies.get(COOKIE_NAME))
    if not actor or str(actor).startswith("support:"):
        raise HTTPException(401, "admin session required")
    with connect() as con:
        row = con.execute("SELECT username FROM admins WHERE username=? AND active=1", (actor,)).fetchone()
    if not row:
        raise HTTPException(401, "admin session required")
    return str(actor)


def _list_bindings(account_id: int):
    with connect() as con:
        rows = con.execute(
            """SELECT b.id,b.kind,b.external_key,b.active,b.created_at,
                      a.display_name,a.protocol,a.native_filename,a.updated_at
               FROM client_access_bindings b
               LEFT JOIN access_artifacts a
                 ON a.kind=b.kind AND a.external_key=b.external_key
               WHERE b.account_id=? AND b.active=1
               ORDER BY b.id ASC""",
            (int(account_id),),
        ).fetchall()
        return [
            {
                **dict(row),
                "available": bool(row["display_name"]),
            }
            for row in rows
        ]


def _list_devices(account_id: int):
    with connect() as con:
        rows = con.execute(
            """SELECT id,label,platform,first_seen_at,last_seen_at,last_ip,active
               FROM client_devices WHERE account_id=? ORDER BY last_seen_at DESC""",
            (int(account_id),),
        ).fetchall()
        return [dict(row) for row in rows]


@router.get("/client-app/login", response_class=HTMLResponse)
def client_login_page(request: Request):
    _require_enabled()
    if _client_session(request, touch=False):
        return RedirectResponse("/client-app/", 302)
    response = templates.TemplateResponse(
        "client_app_login.html",
        {"request": request, "error": None},
    )
    _ensure_device_cookie(request, response)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/client-app/login")
def client_login(request: Request, username: str = Form(...), password: str = Form(...)):
    _require_enabled()
    remote_ip = _client_ip(request)
    rate_key = "client:" + remote_ip
    now_ts = int(time.time())
    rate = login_rate_state(rate_key, now_ts)
    if int(rate.get("blocked_until") or 0) > now_ts:
        wait = max(1, int(rate["blocked_until"]) - now_ts)
        response = templates.TemplateResponse(
            "client_app_login.html",
            {"request": request, "error": f"Too many attempts. Try again in {max(1, wait // 60)} minute(s)."},
            status_code=429,
        )
        _ensure_device_cookie(request, response)
        return response

    account = _account_by_username(username)
    if not account or not verify_password(password, str(account.get("password_hash") or "")):
        record_login_failure(rate_key, now_ts)
        audit(CLIENT_ACTOR_PREFIX + (username or "unknown"), "client_login_failed", ip=remote_ip)
        response = templates.TemplateResponse(
            "client_app_login.html",
            {"request": request, "error": "Username or password is incorrect."},
            status_code=401,
        )
        _ensure_device_cookie(request, response)
        return response

    policy = _effective_policy(account)
    if not policy["enabled"] or policy["expired"]:
        audit(CLIENT_ACTOR_PREFIX + account["username"], "client_login_blocked_policy", ip=remote_ip)
        response = templates.TemplateResponse(
            "client_app_login.html",
            {"request": request, "error": "This subscription is not active."},
            status_code=403,
        )
        _ensure_device_cookie(request, response)
        return response

    response = RedirectResponse("/client-app/", 302)
    device_token = _ensure_device_cookie(request, response)
    device_hash = _token_hash(device_token)
    user_agent = (request.headers.get("user-agent") or "")[:500]
    platform = _device_platform(user_agent)
    ts = now()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        device = con.execute(
            "SELECT * FROM client_devices WHERE account_id=? AND device_hash=?",
            (account["id"], device_hash),
        ).fetchone()
        if not device:
            active_devices = con.execute(
                "SELECT COUNT(*) AS n FROM client_devices WHERE account_id=? AND active=1",
                (account["id"],),
            ).fetchone()["n"]
            if int(active_devices) >= policy["device_limit"]:
                response = templates.TemplateResponse(
                    "client_app_login.html",
                    {"request": request, "error": "Device limit reached. Remove an old device before signing in here."},
                    status_code=403,
                )
                _ensure_device_cookie(request, response)
                return response
            cur = con.execute(
                """INSERT INTO client_devices
                   (account_id,device_hash,label,platform,first_seen_at,last_seen_at,last_ip,active)
                   VALUES(?,?,?,?,?,?,?,1)""",
                (account["id"], device_hash, platform, platform, ts, ts, remote_ip),
            )
            device_id = int(cur.lastrowid)
        else:
            device_id = int(device["id"])
            if not int(device["active"]):
                raise HTTPException(403, "this device is revoked")
            con.execute(
                "UPDATE client_devices SET last_seen_at=?,last_ip=?,platform=? WHERE id=?",
                (ts, remote_ip, platform, device_id),
            )

        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND device_id=? AND revoked_at=0",
            (now_ts, account["id"], device_id),
        )
        active_sessions = con.execute(
            "SELECT COUNT(*) AS n FROM client_sessions WHERE account_id=? AND revoked_at=0 AND expires_at>?",
            (account["id"], now_ts),
        ).fetchone()["n"]
        if int(active_sessions) >= policy["session_limit"]:
            response = templates.TemplateResponse(
                "client_app_login.html",
                {"request": request, "error": "Concurrent session limit reached."},
                status_code=403,
            )
            _ensure_device_cookie(request, response)
            return response

        token = "mkc_" + secrets.token_urlsafe(36)
        expires_at = now_ts + _session_ttl_seconds()
        cur = con.execute(
            """INSERT INTO client_sessions
               (account_id,device_id,token_hash,created_at,last_seen_at,expires_at,revoked_at,ip,user_agent)
               VALUES(?,?,?,?,?,?,0,?,?)""",
            (account["id"], device_id, _token_hash(token), ts, ts, expires_at, remote_ip, user_agent),
        )

    clear_login_failures(rate_key)
    response.set_cookie(
        CLIENT_SESSION_COOKIE,
        token,
        max_age=max(60, expires_at - now_ts),
        httponly=True,
        secure=_secure_cookie(request),
        samesite="strict",
        path="/client-app",
    )
    audit(CLIENT_ACTOR_PREFIX + account["username"], "client_login_success", str(cur.lastrowid), ip=remote_ip)
    return response


@router.post("/client-app/logout")
def client_logout(request: Request):
    _require_enabled()
    token = (request.cookies.get(CLIENT_SESSION_COOKIE) or "").strip()
    session = _client_session(request, touch=False)
    if token:
        with connect() as con:
            con.execute(
                "UPDATE client_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at=0",
                (int(time.time()), _token_hash(token)),
            )
    if session:
        audit(CLIENT_ACTOR_PREFIX + session["username"], "client_logout", ip=_client_ip(request))
    response = RedirectResponse("/client-app/login", 302)
    response.delete_cookie(CLIENT_SESSION_COOKIE, path="/client-app")
    return response


@router.get("/client-app/", response_class=HTMLResponse)
def client_dashboard(request: Request):
    _require_enabled()
    session = _client_session(request)
    if not session:
        return RedirectResponse("/client-app/login", 302)
    account = _account_by_id(session["account_id"])
    policy = _effective_policy(account)
    bindings = _list_bindings(account["id"])
    devices = _list_devices(account["id"])
    response = templates.TemplateResponse(
        "client_app.html",
        {
            "request": request,
            "account": account,
            "policy": policy,
            "bindings": bindings,
            "devices": devices,
            "session": session,
        },
    )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@router.get("/client-app/api/me")
def client_me(request: Request):
    session = _require_client(request)
    account = _account_by_id(session["account_id"])
    return {
        "account": {
            "username": account["username"],
            "display_name": account.get("display_name") or account["username"],
        },
        "policy": _effective_policy(account),
        "device": {
            "id": session["device_id"],
            "label": session.get("device_label") or session.get("platform") or "Browser",
            "platform": session.get("platform") or "Browser",
        },
        "access": _list_bindings(account["id"]),
    }


@router.get("/client-app/manifest.webmanifest")
def client_manifest():
    _require_enabled()
    return JSONResponse(
        {
            "name": "Makia Client",
            "short_name": "Makia",
            "start_url": "/client-app/",
            "scope": "/client-app/",
            "display": "standalone",
            "background_color": "#07111f",
            "theme_color": "#0b1628",
            "icons": [
                {
                    "src": "/static/client-app-icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        },
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/client-app/sw.js")
def client_service_worker():
    _require_enabled()
    response = FileResponse(
        BASE_DIR / "app" / "static" / "client-app-sw.js",
        media_type="application/javascript",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/client-app/"
    return response


class AgentPairRequest(BaseModel):
    pairing_token: str = Field(min_length=24, max_length=256)
    public_key: str = Field(min_length=40, max_length=128)
    agent_version: str = Field(default="", max_length=64)
    platform: str = Field(default="windows", max_length=64)


class AgentRedeemRequest(BaseModel):
    grant: str = Field(min_length=24, max_length=256)
    nonce: str = Field(min_length=12, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    timestamp: int
    signature: str = Field(min_length=40, max_length=256)


class ClientAccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(default="", max_length=120)
    profile_username: str = Field(default="", max_length=128)


class ClientAccountPassword(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class ClientBindingCreate(BaseModel):
    kind: str = Field(min_length=2, max_length=24)
    external_key: str = Field(min_length=1, max_length=256)


@router.post("/client-app/api/agent/pairing-grant")
def client_agent_pairing_grant(request: Request):
    session = _require_client(request)
    account = _account_by_id(session["account_id"])
    if not account:
        raise HTTPException(404, "client account not found")
    token = "mkp_" + secrets.token_urlsafe(36)
    now_ts = int(time.time())
    expires_at = now_ts + 300
    with connect() as con:
        con.execute(
            "DELETE FROM client_agent_pairing_grants WHERE used_at>0 OR expires_at<?",
            (now_ts - 300,),
        )
        con.execute(
            """INSERT INTO client_agent_pairing_grants
               (account_id,device_id,token_hash,expires_at,used_at,created_at)
               VALUES(?,?,?,?,0,?)""",
            (session["account_id"], session["device_id"], _token_hash(token), expires_at, now()),
        )
    origin = _request_origin(request)
    deep_link = (
        "makia://pair?server="
        + urllib.parse.quote(origin, safe="")
        + "&token="
        + urllib.parse.quote(token, safe="")
    )
    audit(CLIENT_ACTOR_PREFIX + account["username"], "client_agent_pairing_grant", f"device={session['device_id']}", ip=_client_ip(request))
    return {"deep_link": deep_link, "expires_in": 300, "paired": bool(session.get("public_key"))}


@router.post("/api/client-agent/pair")
def client_agent_pair(payload: AgentPairRequest, request: Request):
    _require_enabled()
    now_ts = int(time.time())
    try:
        public_raw = _b64url_decode(payload.public_key)
        if len(public_raw) != 32:
            raise ValueError("invalid public key length")
        Ed25519PublicKey.from_public_bytes(public_raw)
    except Exception as exc:
        raise HTTPException(400, "invalid Ed25519 public key") from exc

    token_hash = _token_hash(payload.pairing_token)
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            """SELECT g.id,g.account_id,g.device_id,g.expires_at,g.used_at,
                      a.username,a.profile_username,a.active AS account_active,
                      d.active AS device_active
               FROM client_agent_pairing_grants g
               JOIN client_accounts a ON a.id=g.account_id
               JOIN client_devices d ON d.id=g.device_id
               WHERE g.token_hash=?""",
            (token_hash,),
        ).fetchone()
        if not row or int(row["used_at"] or 0) or int(row["expires_at"] or 0) < now_ts:
            raise HTTPException(410, "pairing grant is invalid or expired")
        account = {
            "id": row["account_id"],
            "username": row["username"],
            "profile_username": row["profile_username"],
            "active": row["account_active"],
        }
        policy = _effective_policy(account)
        if not row["device_active"] or not policy["enabled"] or policy["expired"]:
            raise HTTPException(403, "client device or subscription is inactive")
        normalized = _b64url_encode(public_raw)
        con.execute(
            """UPDATE client_devices
               SET public_key=?,agent_paired_at=?,agent_version=?,agent_platform=?,last_seen_at=?,last_ip=?
               WHERE id=? AND account_id=?""",
            (
                normalized,
                now(),
                payload.agent_version.strip(),
                payload.platform.strip(),
                now(),
                _client_ip(request),
                row["device_id"],
                row["account_id"],
            ),
        )
        con.execute(
            "UPDATE client_agent_pairing_grants SET used_at=? WHERE id=? AND used_at=0",
            (now_ts, row["id"]),
        )
    audit(CLIENT_ACTOR_PREFIX + row["username"], "client_agent_paired", f"device={row['device_id']}", ip=_client_ip(request))
    return {
        "ok": True,
        "device_id": row["device_id"],
        "account": row["username"],
        "key_type": "ed25519",
    }


@router.post("/client-app/api/access/{binding_id}/grant")
def client_agent_action_grant(binding_id: int, request: Request):
    session = _require_client(request)
    if not session.get("public_key"):
        raise HTTPException(409, "Makia Agent is not paired with this device")
    with connect() as con:
        binding = con.execute(
            """SELECT b.id,b.account_id,b.kind,b.external_key,a.display_name,a.protocol
               FROM client_access_bindings b
               JOIN access_artifacts a ON a.kind=b.kind AND a.external_key=b.external_key
               WHERE b.id=? AND b.account_id=? AND b.active=1""",
            (int(binding_id), int(session["account_id"])),
        ).fetchone()
        if not binding:
            raise HTTPException(404, "assigned access not found")
        # Phase B enables only the Windows WireGuard adapter. Other protocols
        # stay metadata-only until their native adapters pass independent UAT.
        if str(binding["kind"] or "").lower() != "wireguard":
            raise HTTPException(409, "native adapter for this access is not enabled yet")
        token = "mkg_" + secrets.token_urlsafe(36)
        now_ts = int(time.time())
        expires_at = now_ts + 60
        con.execute(
            "DELETE FROM client_agent_action_grants WHERE redeemed_at>0 OR expires_at<?",
            (now_ts - 300,),
        )
        con.execute(
            """INSERT INTO client_agent_action_grants
               (account_id,device_id,binding_id,action,token_hash,expires_at,redeemed_at,created_at)
               VALUES(?,?,?,?,?,?,0,?)""",
            (
                session["account_id"],
                session["device_id"],
                int(binding_id),
                "connect",
                _token_hash(token),
                expires_at,
                now(),
            ),
        )
    origin = _request_origin(request)
    deep_link = (
        "makia://connect?server="
        + urllib.parse.quote(origin, safe="")
        + "&grant="
        + urllib.parse.quote(token, safe="")
    )
    audit(
        CLIENT_ACTOR_PREFIX + session["username"],
        "client_agent_connect_grant",
        f"{binding['kind']}:{binding['external_key']}",
        f"device={session['device_id']}",
        ip=_client_ip(request),
    )
    return {
        "deep_link": deep_link,
        "expires_in": 60,
        "access": {
            "binding_id": int(binding["id"]),
            "kind": binding["kind"],
            "protocol": binding["protocol"],
            "name": binding["display_name"],
        },
    }


@router.post("/api/client-agent/redeem")
def client_agent_redeem(payload: AgentRedeemRequest, request: Request):
    _require_enabled()
    now_ts = int(time.time())
    if abs(now_ts - int(payload.timestamp)) > 90:
        raise HTTPException(400, "agent signature timestamp is outside the allowed window")
    try:
        signature = _b64url_decode(payload.signature)
        if len(signature) != 64:
            raise ValueError("invalid signature length")
    except Exception as exc:
        raise HTTPException(400, "invalid agent signature encoding") from exc

    token_hash = _token_hash(payload.grant)
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            """SELECT g.id AS grant_id,g.account_id,g.device_id,g.binding_id,g.action,g.expires_at,g.redeemed_at,
                      d.public_key,d.active AS device_active,
                      b.kind,b.external_key,b.active AS binding_active,
                      ar.display_name,ar.protocol,ar.native_filename,ar.payload_enc,
                      a.username,a.profile_username,a.active AS account_active
               FROM client_agent_action_grants g
               JOIN client_devices d ON d.id=g.device_id AND d.account_id=g.account_id
               JOIN client_access_bindings b ON b.id=g.binding_id AND b.account_id=g.account_id
               JOIN access_artifacts ar ON ar.kind=b.kind AND ar.external_key=b.external_key
               JOIN client_accounts a ON a.id=g.account_id
               WHERE g.token_hash=?""",
            (token_hash,),
        ).fetchone()
        if not row or int(row["redeemed_at"] or 0) or int(row["expires_at"] or 0) < now_ts:
            raise HTTPException(410, "agent grant is invalid, expired, or already used")
        if not row["device_active"] or not row["binding_active"] or not row["public_key"]:
            raise HTTPException(403, "agent device or assigned access is inactive")
        account = {
            "id": row["account_id"],
            "username": row["username"],
            "profile_username": row["profile_username"],
            "active": row["account_active"],
        }
        policy = _effective_policy(account)
        if not policy["enabled"] or policy["expired"]:
            raise HTTPException(403, "subscription is inactive")

        try:
            public_raw = _b64url_decode(row["public_key"])
            public_key = Ed25519PublicKey.from_public_bytes(public_raw)
            public_key.verify(
                signature,
                _agent_signature_message(payload.grant, payload.nonce, payload.timestamp),
            )
        except (ValueError, InvalidSignature) as exc:
            raise HTTPException(403, "agent signature verification failed") from exc

        changed = con.execute(
            "UPDATE client_agent_action_grants SET redeemed_at=? WHERE id=? AND redeemed_at=0",
            (now_ts, row["grant_id"]),
        ).rowcount
        if changed != 1:
            raise HTTPException(409, "agent grant was already redeemed")
        artifact = dict(row)

    try:
        opened = access_ops.open_payload(artifact["payload_enc"])
    except access_ops.AccessPackageError as exc:
        raise HTTPException(500, "assigned access payload is unavailable") from exc

    files = opened.get("files") or {}
    native_name = str(opened.get("native_filename") or artifact.get("native_filename") or "")
    native_data = files.get(native_name) if native_name else None
    if isinstance(native_data, str):
        native_data = native_data.encode("utf-8")
    native_b64 = base64.b64encode(bytes(native_data)).decode("ascii") if native_data is not None else ""

    audit(
        CLIENT_ACTOR_PREFIX + artifact["username"],
        "client_agent_grant_redeemed",
        f"{artifact['kind']}:{artifact['external_key']}",
        f"device={artifact['device_id']}",
        ip=_client_ip(request),
    )
    return {
        "ok": True,
        "action": artifact["action"],
        "access": {
            "kind": artifact["kind"],
            "protocol": artifact["protocol"],
            "name": artifact["display_name"],
            "native_filename": native_name,
            "native_content_b64": native_b64,
            "primary_text": str(opened.get("primary_text") or ""),
            "share_text": str(opened.get("share_text") or ""),
            "share_type": str(opened.get("share_type") or ""),
            "summary": opened.get("summary") or {},
        },
        "grant": {
            "redeemed_at": now_ts,
            "one_time": True,
        },
    }


@router.get("/api/client-app/admin/accounts")
def client_admin_accounts(request: Request):
    _require_admin(request)
    with connect() as con:
        rows = con.execute(
            """SELECT a.*,
                      (SELECT COUNT(*) FROM client_devices d WHERE d.account_id=a.id AND d.active=1) AS active_devices,
                      (SELECT COUNT(*) FROM client_sessions s WHERE s.account_id=a.id AND s.revoked_at=0 AND s.expires_at>?) AS active_sessions
               FROM client_accounts a ORDER BY a.id DESC""",
            (int(time.time()),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item.pop("password_hash", None)
        item["policy"] = _effective_policy(item)
        result.append(item)
    return result


@router.post("/api/client-app/admin/accounts")
def client_admin_account_create(payload: ClientAccountCreate, request: Request):
    actor = _require_admin(request)
    username = payload.username.strip()
    profile_username = (payload.profile_username or username).strip()
    ts = now()
    try:
        with connect() as con:
            cur = con.execute(
                """INSERT INTO client_accounts
                   (username,password_hash,display_name,profile_username,active,created_at,updated_at)
                   VALUES(?,?,?,?,1,?,?)""",
                (username, hash_password(payload.password), payload.display_name.strip(), profile_username, ts, ts),
            )
            account_id = int(cur.lastrowid)
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(409, "client username already exists")
        raise
    audit(actor, "client_account_create", username, f"id={account_id}")
    return {"id": account_id, "username": username, "profile_username": profile_username}


@router.post("/api/client-app/admin/accounts/{account_id}/password")
def client_admin_password(account_id: int, payload: ClientAccountPassword, request: Request):
    actor = _require_admin(request)
    account = _account_by_id(account_id)
    if not account:
        raise HTTPException(404, "client account not found")
    with connect() as con:
        con.execute(
            "UPDATE client_accounts SET password_hash=?,updated_at=? WHERE id=?",
            (hash_password(payload.password), now(), int(account_id)),
        )
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND revoked_at=0",
            (int(time.time()), int(account_id)),
        )
    audit(actor, "client_account_password_reset", account["username"])
    return {"ok": True}


@router.post("/api/client-app/admin/accounts/{account_id}/bindings")
def client_admin_binding(account_id: int, payload: ClientBindingCreate, request: Request):
    actor = _require_admin(request)
    account = _account_by_id(account_id)
    if not account:
        raise HTTPException(404, "client account not found")
    kind = payload.kind.strip().lower()
    if kind not in CLIENT_ACCESS_KINDS:
        raise HTTPException(400, "unsupported access kind")
    key = payload.external_key.strip()
    with connect() as con:
        artifact = con.execute(
            "SELECT id FROM access_artifacts WHERE kind=? AND external_key=?",
            (kind, key),
        ).fetchone()
        if not artifact:
            raise HTTPException(404, "access artifact not found")
        con.execute(
            """INSERT INTO client_access_bindings(account_id,kind,external_key,active,created_at)
               VALUES(?,?,?,1,?)
               ON CONFLICT(account_id,kind,external_key) DO UPDATE SET active=1""",
            (int(account_id), kind, key, now()),
        )
    audit(actor, "client_access_bind", account["username"], f"{kind}:{key}")
    return {"ok": True, "kind": kind, "external_key": key}


@router.delete("/api/client-app/admin/accounts/{account_id}/bindings/{binding_id}")
def client_admin_binding_delete(account_id: int, binding_id: int, request: Request):
    actor = _require_admin(request)
    account = _account_by_id(account_id)
    if not account:
        raise HTTPException(404, "client account not found")
    with connect() as con:
        row = con.execute(
            "SELECT * FROM client_access_bindings WHERE id=? AND account_id=?",
            (int(binding_id), int(account_id)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "binding not found")
        con.execute("UPDATE client_access_bindings SET active=0 WHERE id=?", (int(binding_id),))
    audit(actor, "client_access_unbind", account["username"], f"{row['kind']}:{row['external_key']}")
    return {"ok": True}


@router.post("/api/client-app/admin/accounts/{account_id}/devices/{device_id}/revoke")
def client_admin_device_revoke(account_id: int, device_id: int, request: Request):
    actor = _require_admin(request)
    account = _account_by_id(account_id)
    if not account:
        raise HTTPException(404, "client account not found")
    now_ts = int(time.time())
    with connect() as con:
        row = con.execute(
            "SELECT id FROM client_devices WHERE id=? AND account_id=?",
            (int(device_id), int(account_id)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "device not found")
        con.execute("UPDATE client_devices SET active=0 WHERE id=?", (int(device_id),))
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND device_id=? AND revoked_at=0",
            (now_ts, int(account_id), int(device_id)),
        )
    audit(actor, "client_device_revoke", account["username"], f"device={device_id}")
    return {"ok": True}
