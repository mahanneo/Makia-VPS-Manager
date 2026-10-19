"""Native Windows client API: server-owned access, short-lived connector tickets.

Never returns VPN credentials to the desktop GUI. The existing one-use
/client/connector/redeem endpoint is the ONLY delivery owner.
"""
import os
import time
import urllib.parse
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import client_connector, client_portal, client_store
from .db import audit, clear_login_failures, login_rate_state, record_login_failure

router=APIRouter(prefix="/client/desktop",tags=["client-desktop"])
MAX_BODY=8192
DEFAULT_SESSION_TTL=12*3600
REMEMBER_SESSION_TTL=30*86400


def _native(request):
    client_portal._require_enabled()
    if request.headers.get("x-makia-desktop")!="1":
        raise HTTPException(status_code=403,detail="desktop client header required")
    if (request.headers.get("origin") or "").strip():
        raise HTTPException(status_code=403,detail="browser origins are not accepted by desktop API")
    if request.method=="POST" and request.headers.get("content-type","").split(";",1)[0].lower()!="application/json":
        raise HTTPException(status_code=415,detail="JSON required")
    secure=client_portal._secure_cookie(request)
    remote=request.client.host if request.client else ""
    if not secure and remote not in {"127.0.0.1","::1","testclient"}:
        raise HTTPException(status_code=403,detail="HTTPS required")


def _reply(value,status=200):
    response=JSONResponse(value,status_code=status)
    return client_portal._no_store(response)


async def _json(request):
    raw=await request.body()
    if len(raw)>MAX_BODY:
        raise HTTPException(status_code=413,detail="request too large")
    import json
    try:
        value=json.loads(raw)
        if not isinstance(value,dict):
            raise ValueError("JSON object required")
        return value
    except (ValueError,UnicodeDecodeError):
        raise HTTPException(status_code=400,detail="invalid JSON")


def _bearer(request):
    _native(request)
    raw=(request.headers.get("authorization") or "").strip()
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401,detail="desktop login required")
    token=raw[7:].strip()
    session=client_store.session_by_token(token,client_portal._ip(request))
    if not session:
        raise HTTPException(status_code=401,detail="desktop session invalid or expired")
    return session,token


@router.post("/login")
async def login(request:Request):
    _native(request)
    body=await _json(request)
    username=str(body.get("username") or "").strip()[:64]
    password=str(body.get("password") or "")
    device_key=str(body.get("device_key") or "").strip()[:256]
    remember=body.get("remember_device") is True
    label=str(body.get("device_label") or "Windows · Makia Desktop")[:120]
    if not username or not password or len(password)>512:
        raise HTTPException(status_code=400,detail="username and password required")
    ip=client_portal._ip(request) or "unknown"
    rate_key="client-desktop:"+ip
    now=int(time.time())
    state=login_rate_state(rate_key,now)
    if int(state.get("blocked_until") or 0)>now:
        raise HTTPException(status_code=429,detail="too many failed login attempts")
    account=client_store.verify_account_password(username,password)
    if not account:
        record_login_failure(rate_key,now,max_failures=6,window_seconds=900,block_seconds=900)
        audit("client:"+username,"desktop_login_failed",ip=ip)
        raise HTTPException(status_code=401,detail="username or password incorrect")
    available,reason=client_store.account_available(account,now)
    if not available:
        raise HTTPException(status_code=403,detail="account unavailable: "+reason)
    try:
        device,new_key=client_store.register_or_get_device(
            account["id"],device_key,label=label,platform="windows",
            user_agent=request.headers.get("user-agent",""),ip=ip,
        )
        token,expiry=client_store.create_session(
            account["id"],device["id"],ip,
            REMEMBER_SESSION_TTL if remember else DEFAULT_SESSION_TTL
        )
    except PermissionError:
        audit("client:"+account["username"],"desktop_login_device_denied",ip=ip)
        raise HTTPException(status_code=403,detail="device or concurrent session limit reached")
    clear_login_failures(rate_key)
    audit("client:"+account["username"],"desktop_login_success",target=str(device["id"]),
          detail="remember="+str(remember),ip=ip)
    snapshot=client_store.account_snapshot(account["id"]) or {}
    snapshot["current_device_id"]=device["id"]
    return _reply({"token":token,"expires_at":expiry,"remember_device":remember,
                   "device_key":new_key or device_key,"account":snapshot})


@router.get("/me")
def me(request:Request):
    session,_=_bearer(request)
    snapshot=client_store.account_snapshot(session["account_id"])
    if not snapshot:
        raise HTTPException(status_code=404,detail="account unavailable")
    snapshot["current_device_id"]=session["device_id"]
    snapshot["session_expires_at"]=session["expires_at"]
    return _reply(snapshot)


@router.get("/access")
def access(request:Request):
    session,_=_bearer(request)
    items=client_store.client_access_list(session["account_id"])
    # No configuration/private keys are returned by this endpoint.
    return _reply({"items":items})


@router.post("/ticket/{delivery_kind}/{delivery_id}")
async def ticket(delivery_kind:str,delivery_id:int,request:Request):
    session,_=_bearer(request)
    await _json(request)
    kind=str(delivery_kind or "").lower()
    try:
        if kind=="protocol":
            client_store.protocol_delivery(session["account_id"],delivery_id)
        elif kind=="artifact":
            client_store.artifact_delivery(session["account_id"],delivery_id,platform="windows")
        else:
            raise ValueError("unsupported delivery kind")
    except PermissionError:
        raise HTTPException(status_code=403,detail="profile is not available")
    except ValueError:
        raise HTTPException(status_code=404,detail="profile not found")
    try:
        origin=client_portal._public_origin(request)
    except ValueError as exc:
        raise HTTPException(status_code=503,detail=str(exc))
    parsed=urllib.parse.urlparse(origin)
    if parsed.scheme!="https" and parsed.hostname not in {"127.0.0.1","localhost","testserver"}:
        raise HTTPException(status_code=503,detail="public HTTPS Makia origin required")
    one=client_connector.issue_ticket(session["account_id"],session["device_id"],kind,delivery_id)
    audit("client:"+session["username"],"desktop_connector_ticket",
          target=f"{kind}:{delivery_id}",detail=f"ttl={one['ttl']}",ip=client_portal._ip(request))
    # A one-use launch URI carries NO VPN password, subscription secret or private key.
    url=("makia://connect?controller="+urllib.parse.quote(origin,safe="")+
         "&ticket="+urllib.parse.quote(one["ticket"],safe=""))
    return _reply({"launch_url":url,"expires_at":one["expires_at"],"ttl":one["ttl"]})


@router.post("/logout")
async def logout(request:Request):
    session,token=_bearer(request)
    await _json(request)
    client_store.revoke_session(token)
    audit("client:"+session["username"],"desktop_logout",
          target=str(session["device_id"]),ip=client_portal._ip(request))
    return _reply({"ok":True})
