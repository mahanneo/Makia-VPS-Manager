import json
import os
import time
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import client_store
from .config import APP_NAME, VERSION
from .db import audit, clear_login_failures, login_rate_state, record_login_failure

BASE=Path(__file__).resolve().parent
templates=Jinja2Templates(directory=BASE/"templates")
router=APIRouter()

CLIENT_SESSION_COOKIE="makia_client_session"
CLIENT_DEVICE_COOKIE="makia_client_device"
CLIENT_SESSION_TTL=12*60*60
CLIENT_DEVICE_TTL=365*24*60*60


def enabled():
    return str(os.getenv("MAKIA_CLIENT_PORTAL_ENABLED","0")).strip().lower() in {"1","true","yes","on"}


def _require_enabled():
    if not enabled():
        raise HTTPException(status_code=404,detail="client portal is disabled")


def _ip(request):
    forwarded=(request.headers.get("x-forwarded-for") or "").split(",",1)[0].strip()
    if forwarded:
        return forwarded[:96]
    return (request.client.host if request.client else "")[:96]


def _secure_cookie(request):
    return request.headers.get("x-forwarded-proto","").lower()=="https" or request.url.scheme=="https"


def _session(request):
    if not enabled():
        return None
    return client_store.session_by_token(request.cookies.get(CLIENT_SESSION_COOKIE),_ip(request))


def _require_session(request):
    session=_session(request)
    if not session:
        raise HTTPException(status_code=401,detail="client authentication required")
    return session


def _require_mutation(request):
    session=_require_session(request)
    if request.headers.get("x-makia-client")!="1":
        raise HTTPException(status_code=403,detail="invalid client request")
    origin=(request.headers.get("origin") or "").strip()
    if origin:
        parsed=urllib.parse.urlparse(origin)
        request_host=(request.headers.get("host") or request.url.netloc or "").lower()
        if parsed.netloc.lower()!=request_host:
            raise HTTPException(status_code=403,detail="cross-origin client request blocked")
    fetch_site=(request.headers.get("sec-fetch-site") or "").lower()
    if fetch_site and fetch_site not in {"same-origin","none"}:
        raise HTTPException(status_code=403,detail="cross-site client request blocked")
    return session


def _no_store(response):
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response


@router.get("/client/")
def client_root(request:Request):
    _require_enabled()
    if _session(request):
        return _no_store(RedirectResponse("/client/app",302))
    return _no_store(RedirectResponse("/client/login",302))


@router.get("/client/login",response_class=HTMLResponse)
def client_login_page(request:Request):
    _require_enabled()
    if _session(request):
        return RedirectResponse("/client/app",302)
    response=templates.TemplateResponse(
        "client_login.html",
        {"request":request,"app_name":APP_NAME,"version":VERSION,"error":None},
    )
    return _no_store(response)


@router.post("/client/login",response_class=HTMLResponse)
def client_login(
    request:Request,
    username:str=Form(...),
    password:str=Form(...),
    device_label:str=Form(""),
):
    _require_enabled()
    remote_ip=_ip(request) or "unknown"
    rate_key="client:"+remote_ip
    now_ts=int(time.time())
    state=login_rate_state(rate_key,now_ts)
    if int(state.get("blocked_until") or 0)>now_ts:
        wait=max(1,int(state["blocked_until"])-now_ts)
        return _no_store(templates.TemplateResponse(
            "client_login.html",
            {
                "request":request,"app_name":APP_NAME,"version":VERSION,
                "error":f"تلاش‌های ناموفق زیاد بوده است. حدود {max(1,wait//60)} دقیقه بعد دوباره امتحان کنید.",
            },
            status_code=429,
        ))
    account=client_store.verify_account_password(username,password)
    if not account:
        state=record_login_failure(rate_key,now_ts,max_failures=6,window_seconds=900,block_seconds=900)
        audit("client:"+str(username or "unknown"),"client_login_failed",detail=f"failures={state['failures']}",ip=remote_ip)
        return _no_store(templates.TemplateResponse(
            "client_login.html",
            {"request":request,"app_name":APP_NAME,"version":VERSION,"error":"نام کاربری یا رمز عبور صحیح نیست."},
            status_code=401,
        ))
    ok,reason=client_store.account_available(account,now_ts)
    if not ok:
        audit("client:"+account["username"],"client_login_denied",detail=reason,ip=remote_ip)
        message={
            "expired":"اشتراک شما منقضی شده است.",
            "quota":"حجم اشتراک شما به پایان رسیده است.",
            "disabled":"حساب کاربری غیرفعال است.",
        }.get(reason,"دسترسی حساب در حال حاضر فعال نیست.")
        return _no_store(templates.TemplateResponse(
            "client_login.html",
            {"request":request,"app_name":APP_NAME,"version":VERSION,"error":message},
            status_code=403,
        ))
    try:
        device,device_key=client_store.register_or_get_device(
            account["id"],
            request.cookies.get(CLIENT_DEVICE_COOKIE),
            label=device_label or "Web / PWA",
            platform="web",
            user_agent=request.headers.get("user-agent",""),
            ip=remote_ip,
        )
        token,expires_at=client_store.create_session(account["id"],device["id"],remote_ip,CLIENT_SESSION_TTL)
    except PermissionError as exc:
        audit("client:"+account["username"],"client_login_device_denied",detail=str(exc),ip=remote_ip)
        message="سقف دستگاه یا اتصال همزمان این اشتراک پر شده است."
        return _no_store(templates.TemplateResponse(
            "client_login.html",
            {"request":request,"app_name":APP_NAME,"version":VERSION,"error":message},
            status_code=403,
        ))
    clear_login_failures(rate_key)
    audit("client:"+account["username"],"client_login_success",target=str(device["id"]),ip=remote_ip)
    response=RedirectResponse("/client/app",302)
    secure=_secure_cookie(request)
    response.set_cookie(
        CLIENT_SESSION_COOKIE,token,httponly=True,secure=secure,samesite="strict",
        max_age=max(300,expires_at-int(time.time())),path="/client",
    )
    if device_key:
        response.set_cookie(
            CLIENT_DEVICE_COOKIE,device_key,httponly=True,secure=secure,samesite="strict",
            max_age=CLIENT_DEVICE_TTL,path="/client",
        )
    return _no_store(response)


@router.post("/client/logout")
def client_logout(request:Request):
    _require_enabled()
    session=_session(request)
    token=request.cookies.get(CLIENT_SESSION_COOKIE)
    if token:
        client_store.revoke_session(token)
    if session:
        audit("client:"+session["username"],"client_logout",target=str(session["device_id"]),ip=_ip(request))
    response=RedirectResponse("/client/login",302)
    response.delete_cookie(CLIENT_SESSION_COOKIE,path="/client")
    return _no_store(response)


@router.get("/client/app",response_class=HTMLResponse)
def client_app(request:Request):
    _require_enabled()
    session=_session(request)
    if not session:
        return RedirectResponse("/client/login",302)
    response=templates.TemplateResponse(
        "client_app.html",
        {
            "request":request,"app_name":APP_NAME,"version":VERSION,
            "username":session["username"],"display_name":session.get("display_name") or session["username"],
        },
    )
    return _no_store(response)


@router.get("/client/api/me")
def client_me(request:Request):
    session=_require_session(request)
    snapshot=client_store.account_snapshot(session["account_id"])
    if not snapshot:
        raise HTTPException(status_code=404,detail="account not found")
    snapshot["current_device_id"]=session["device_id"]
    snapshot["session_expires_at"]=session["expires_at"]
    return _no_store(JSONResponse(snapshot))


@router.get("/client/api/protocols")
def client_protocols(request:Request):
    session=_require_session(request)
    return _no_store(JSONResponse({
        "items":client_store.list_protocols(session["account_id"],include_secrets=False)
    }))


@router.post("/client/api/protocols/{protocol_client_id}/delivery")
def client_protocol_delivery(protocol_client_id:int,request:Request):
    session=_require_mutation(request)
    try:
        item=client_store.protocol_delivery(session["account_id"],protocol_client_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403,detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=404,detail="protocol binding not found")
    audit(
        "client:"+session["username"],"client_protocol_delivery",
        target=str(protocol_client_id),detail=str(item.get("protocol") or ""),ip=_ip(request),
    )
    return _no_store(JSONResponse(item))


@router.get("/client/api/devices")
def client_devices(request:Request):
    session=_require_session(request)
    return _no_store(JSONResponse({
        "current_device_id":session["device_id"],
        "items":client_store.list_devices(session["account_id"]),
    }))


@router.post("/client/api/devices/{device_id}/revoke")
def client_device_revoke(device_id:int,request:Request):
    session=_require_mutation(request)
    if int(device_id)==int(session["device_id"]):
        raise HTTPException(status_code=400,detail="current device cannot revoke itself")
    client_store.revoke_device(session["account_id"],device_id)
    audit("client:"+session["username"],"client_device_revoke",target=str(device_id),ip=_ip(request))
    return {"ok":True}


@router.get("/client/manifest.webmanifest")
def client_manifest(request:Request):
    _require_enabled()
    manifest={
        "name":"Makia Client",
        "short_name":"Makia",
        "start_url":"/client/",
        "scope":"/client/",
        "display":"standalone",
        "background_color":"#07111f",
        "theme_color":"#07111f",
        "description":"Makia secure client access portal",
        "icons":[
            {"src":"/static/client-icon.svg","sizes":"any","type":"image/svg+xml","purpose":"any maskable"}
        ],
    }
    response=JSONResponse(manifest,media_type="application/manifest+json")
    response.headers["Cache-Control"]="public, max-age=3600"
    return response


@router.get("/client/sw.js")
def client_service_worker(request:Request):
    _require_enabled()
    response=FileResponse(BASE/"static"/"client-sw.js",media_type="application/javascript")
    response.headers["Cache-Control"]="no-cache"
    response.headers["Service-Worker-Allowed"]="/client/"
    return response
