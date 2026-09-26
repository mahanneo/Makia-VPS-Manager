from pathlib import Path
from datetime import date, datetime, timedelta
import time, io, base64, secrets, string, urllib.request, urllib.parse, json, os, stat, re, ipaddress, threading
import pyotp, qrcode
import qrcode.image.svg
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from .config import APP_NAME, VERSION, COOKIE_NAME, ALLOWED_SERVICES, DATA_DIR, SECRET_PATH
from .db import init_db, connect, audit, upsert_profile, all_profiles, delete_profile, metrics_since, get_admin_2fa, set_admin_totp_secret, set_admin_totp_enabled, clear_admin_totp, create_api_token, list_api_tokens, revoke_api_token, verify_api_token, create_node, list_nodes, revoke_node, node_by_token, update_node_heartbeat, get_setting, set_setting, all_settings, create_protocol_client, list_protocol_clients, get_protocol_client, update_protocol_client_state, delete_protocol_client, reset_protocol_traffic, protocol_client_by_subscription, login_rate_state, record_login_failure, clear_login_failures, upsert_access_artifact, list_access_artifacts, get_access_artifact_by_key, delete_access_artifact_by_key, create_support_request, list_support_requests, update_support_request_delivery, create_support_grant, consume_support_grant, support_grant_by_id, list_support_grants, revoke_support_grant
from .security import verify_password, make_session, read_session, hash_password, make_preauth, read_preauth
from . import system_ops, protocol_ops, panel_ops, access_ops, license_ops

BASE=Path(__file__).resolve().parent
app=FastAPI(title=APP_NAME,version=VERSION,docs_url=None,redoc_url=None)
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
templates=Jinja2Templates(directory=BASE/"templates")

@app.middleware("http")
async def security_headers(request:Request,call_next):
    allowed_raw=(os.getenv("MAKIA_ADMIN_ALLOWED_CIDRS") or "").strip()
    public_path=(
        request.url.path=="/healthz" or
        request.url.path=="/help/connect" or
        request.url.path in {"/support/login","/support/logout"} or
        request.url.path.startswith("/static/") or
        request.url.path.startswith("/sub/") or
        request.url.path.startswith("/client/") or
        request.url.path=="/api/node/heartbeat"
    )
    support_override=False
    raw_actor=read_session(request.cookies.get(COOKIE_NAME))
    if raw_actor and raw_actor.startswith("support:"):
        parts=raw_actor.split(":")
        if len(parts)==3:
            try:
                grant=support_grant_by_id(int(parts[1]))
                support_override=bool(grant and grant.get("active") and grant.get("scope")==parts[2])
            except Exception:
                support_override=False
    if allowed_raw and not public_path and not support_override:
        try:
            client_ip=ipaddress.ip_address((request.client.host if request.client else "").strip())
            networks=[ipaddress.ip_network(x.strip(),strict=False) for x in allowed_raw.split(",") if x.strip()]
            if not networks or not any(client_ip in network for network in networks):
                return PlainTextResponse("Makia admin access is not allowed from this network.",status_code=403)
        except ValueError:
            return PlainTextResponse("Makia admin network policy is invalid.",status_code=503)
    response=await call_next(request)
    response.headers.setdefault("X-Frame-Options","DENY")
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("Referrer-Policy","no-referrer")
    response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy","same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy","same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'; "
        "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api/") or request.url.path in {"/","/login","/login/2fa"}:
        response.headers["Cache-Control"]="no-store"
    if request.headers.get("x-forwarded-proto","").lower()=="https" or request.url.scheme=="https":
        response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
    return response

_LICENSE_SYNC_STARTED=False

def _sync_license_lease_once():
    code=(get_setting("license_code","") or "").strip()
    if not code:
        return {"required":False}
    try:
        local=license_ops.verify_license(code)
    except license_ops.LicenseError as exc:
        set_setting("license_lease_error",str(exc))
        return {"required":False,"error":str(exc)}
    if not local.get("online_required"):
        set_setting("license_lease_code","")
        set_setting("license_lease_error","")
        return {"required":False}
    try:
        result=license_ops.fetch_online_lease(code)
        lease_code=result.get("lease_code") or ""
        if lease_code:
            set_setting("license_lease_code",lease_code)
        replacement=result.get("replacement_license_code") or ""
        if replacement and replacement!=code:
            verified=license_ops.verify_license(replacement)
            if verified["installation_id"]==local["installation_id"] and verified["license_id"]==local["license_id"]:
                set_setting("license_code",replacement)
                code=replacement
        set_setting("license_lease_checked_at",int(time.time()))
        set_setting("license_lease_error","")
        return result
    except Exception as exc:
        set_setting("license_lease_checked_at",int(time.time()))
        set_setting("license_lease_error",str(exc)[:500])
        return {"required":True,"error":str(exc)}

def _license_sync_loop():
    while True:
        try: _sync_license_lease_once()
        except Exception: pass
        time.sleep(900)

@app.on_event("startup")
def startup():
    global _LICENSE_SYNC_STARTED
    init_db()
    if get_setting("ui_generation","")!="glass-v1":
        set_setting("theme","glass")
        set_setting("ui_generation","glass-v1")
    if not _LICENSE_SYNC_STARTED and os.getenv("MAKIA_DISABLE_LICENSE_SYNC","0")!="1":
        threading.Thread(target=_license_sync_loop,name="makia-license-sync",daemon=True).start()
        _LICENSE_SYNC_STARTED=True

def current_user(request:Request):
    actor=read_session(request.cookies.get(COOKIE_NAME))
    if not actor:
        return None
    if actor.startswith("support:"):
        parts=actor.split(":")
        if len(parts)!=3:
            return None
        try: grant=support_grant_by_id(int(parts[1]))
        except Exception: grant=None
        if not grant or not grant.get("active") or grant.get("scope")!=parts[2]:
            return None
    return actor

def is_support_actor(actor):
    return bool(str(actor or "").startswith("support:"))

def support_actor_scope(actor):
    parts=str(actor or "").split(":")
    return parts[2] if len(parts)==3 and parts[0]=="support" else ""

def require_user(request:Request):
    user=current_user(request)
    if not user: raise HTTPException(status_code=401,detail="authentication required")
    return user

def require_local_admin(request:Request):
    actor=require_user(request)
    if is_support_actor(actor):
        raise HTTPException(status_code=403,detail="local administrator confirmation required")
    return actor

def _support_operator_mutation_allowed(request:Request)->bool:
    if request.method.upper()!="POST":
        return False
    path=request.url.path
    if re.fullmatch(r"/api/services/[^/]+/(start|stop|restart)",path):
        return True
    return path in {
        "/api/protocols/xray/repair",
        "/api/protocols/openvpn/repair",
        "/api/protocols/wireguard/repair",
        "/api/support/requests",
    }

def require_mutation(request:Request):
    user=require_user(request)
    if is_support_actor(user):
        if support_actor_scope(user)!="operator":
            raise HTTPException(status_code=403,detail="remote support session is read-only")
        if not _support_operator_mutation_allowed(request):
            raise HTTPException(status_code=403,detail="remote support operator is limited to approved runtime repair actions")
    if request.headers.get("x-makia-request")!="1":
        raise HTTPException(status_code=403,detail="invalid management request")
    origin=(request.headers.get("origin") or "").strip()
    if origin:
        parsed=urllib.parse.urlparse(origin)
        request_host=(request.headers.get("host") or request.url.netloc or "").lower()
        if parsed.netloc.lower()!=request_host:
            raise HTTPException(status_code=403,detail="cross-origin management request blocked")
    fetch_site=(request.headers.get("sec-fetch-site") or "").lower()
    if fetch_site and fetch_site not in {"same-origin","none"}:
        raise HTTPException(status_code=403,detail="cross-site management request blocked")
    return user

def license_snapshot():
    state=license_ops.license_status(
        get_setting("license_code",""),
        get_setting("license_lease_code",""),
    )
    state["lease_last_checked_at"]=int(get_setting("license_lease_checked_at",0) or 0)
    state["lease_sync_error"]=get_setting("license_lease_error","") or ""
    return state

def license_feature_enabled(feature:str)->bool:
    return str(feature or "").lower() in set(license_snapshot().get("features") or [])

def assert_license_feature(feature:str):
    if not license_feature_enabled(feature):
        state=license_snapshot()
        raise HTTPException(
            status_code=403,
            detail={
                "code":"license_required",
                "feature":feature,
                "tier":state.get("tier","community"),
                "installation_id":state.get("installation_id",""),
                "message":"این قابلیت نیاز به دسترسی Full دارد."
            }
        )

def require_feature(request:Request,feature:str,mutation:bool=False):
    actor=require_mutation(request) if mutation else require_user(request)
    assert_license_feature(feature)
    return actor

def require_access_kind(request:Request,kind:str,mutation:bool=False):
    kind=str(kind or "").lower()
    if kind=="ssh":
        return require_mutation(request) if mutation else require_user(request)
    feature={"xray":"xray","wireguard":"wireguard","openvpn":"openvpn"}.get(kind)
    if not feature:
        raise HTTPException(404,"unknown access type")
    return require_feature(request,feature,mutation)

def support_snapshot():
    username=(os.getenv("MAKIA_SUPPORT_TELEGRAM") or "").strip().lstrip("@")
    webhook=(os.getenv("MAKIA_SUPPORT_WEBHOOK_URL") or "").strip()
    webhook_token=(os.getenv("MAKIA_SUPPORT_WEBHOOK_TOKEN") or "").strip()
    return {
        "telegram_username":username,
        "telegram_url":f"https://t.me/{username}" if username else "",
        "webhook_enabled":bool(webhook),
        "control_plane_connected":bool(webhook and webhook_token),
        "admin_network_restricted":bool((os.getenv("MAKIA_ADMIN_ALLOWED_CIDRS") or "").strip()),
    }

def ip(request:Request): return request.client.host if request.client else None

def public_origin(request:Request):
    domain=(get_setting("panel_domain","") or "").strip()
    host=domain or request.url.netloc or request.url.hostname or "server"
    forwarded=request.headers.get("x-forwarded-proto","").lower()
    scheme="https" if forwarded=="https" or (domain and panel_ops.domain_status(domain).get("certificate")) else "http"
    return f"{scheme}://{host}"

def public_host(request:Request):
    return (get_setting("panel_domain","") or request.url.hostname or "server").strip()


def _setting_int(key,default,minimum=None,maximum=None):
    try: value=int(get_setting(key,default))
    except Exception: value=int(default)
    if minimum is not None: value=max(int(minimum),value)
    if maximum is not None: value=min(int(maximum),value)
    return value

def _setting_bool(key,default=False):
    raw=str(get_setting(key,"1" if default else "0")).strip().lower()
    return raw in {"1","true","yes","on"}

def operator_settings_snapshot():
    return {
        "session_max_age_minutes":_setting_int("session_max_age_minutes",720,5,43200),
        "delivery":{
            "profile_prefix":get_setting("delivery_profile_prefix","Makia"),
            "npv_enabled":_setting_bool("delivery_npv_enabled",True),
            "npv_dns_mode":get_setting("delivery_npv_dns_mode","UDP"),
            "npv_udpgw_port":_setting_int("delivery_npv_udpgw_port",7300,1,65535),
            "npv_transparent_dns":_setting_bool("delivery_npv_transparent_dns",False),
            "show_qr":_setting_bool("delivery_show_qr",True),
        },
        "subscription":{
            "enabled":_setting_bool("subscription_enabled",True),
            "client_page_enabled":_setting_bool("subscription_client_page_enabled",True),
            "default_format":get_setting("subscription_default_format","base64"),
        },
        "defaults":{
            "ssh_password_mode":get_setting("default_ssh_password_mode","pin6"),
            "ssh_expire_days":_setting_int("default_ssh_expire_days",30,0,3650),
            "ssh_sessions":_setting_int("default_ssh_sessions",1,1,50),
            "ssh_devices":_setting_int("default_ssh_devices",1,1,50),
            "xray_protocol":get_setting("default_xray_protocol","vless"),
            "xray_port":_setting_int("default_xray_port",2087,1,65535),
            "xray_transport":get_setting("default_xray_transport","xhttp"),
            "xray_security":get_setting("default_xray_security","reality"),
            "xray_path":get_setting("default_xray_path","/makia"),
            "xray_sni":get_setting("default_xray_sni","www.microsoft.com"),
            "xray_reality_target":get_setting("default_xray_reality_target","www.microsoft.com:443"),
            "xray_quota_gb":_setting_int("default_xray_quota_gb",50,0,100000),
            "xray_expire_days":_setting_int("default_xray_expire_days",30,0,3650),
            "xray_ip_limit":_setting_int("default_xray_ip_limit",1,1,50),
            "xray_reset_days":_setting_int("default_xray_reset_days",30,0,3650),
            "wireguard_dns":get_setting("default_wireguard_dns","1.1.1.1"),
            "wireguard_port":_setting_int("default_wireguard_port",443,1,65535),
            "wireguard_mtu":_setting_int("default_wireguard_mtu",1280,576,1500),
            "wireguard_keepalive":_setting_int("default_wireguard_keepalive",15,0,3600),
            "wireguard_allowed_ips":get_setting("default_wireguard_allowed_ips","0.0.0.0/0"),
            "wireguard_cidr":get_setting("default_wireguard_cidr","10.66.66.1/24"),
            "openvpn_port":_setting_int("default_openvpn_port",1194,1,65535),
            "openvpn_proto":get_setting("default_openvpn_proto","udp"),
        }
    }

def ssh_npv_options(username):
    settings=operator_settings_snapshot()["delivery"]
    return {
        "enabled":settings["npv_enabled"],
        "remarks":f"{settings['profile_prefix']} {username}".strip(),
        "dns_mode":settings["npv_dns_mode"],
        "udpgw_port":settings["npv_udpgw_port"],
        "transparent_dns":settings["npv_transparent_dns"],
    }

def artifact_save(kind,external_key,display_name,protocol,payload,metadata=None):
    return upsert_access_artifact(
        kind,external_key,display_name,protocol,payload.get("native_filename",""),
        access_ops.seal_payload(payload),
        json.dumps(metadata or {},ensure_ascii=False,separators=(",",":"))
    )

def bearer(request:Request):
    auth=request.headers.get("authorization","")
    if auth.lower().startswith("bearer "):
        return auth.split(" ",1)[1].strip()
    return None

def require_api_scope(request:Request,scope:str):
    token=bearer(request)
    if not token:
        raise HTTPException(status_code=401,detail="bearer token required")
    identity=verify_api_token(token,scope)
    if not identity:
        raise HTTPException(status_code=403,detail="invalid token or scope")
    return identity

def days_left(expire_date):
    if not expire_date: return None
    try: return (date.fromisoformat(str(expire_date))-date.today()).days
    except Exception: return None


def generate_user_secret(mode:str="strong"):
    mode=(mode or "strong").lower()
    if mode=="pin4":
        return "".join(secrets.choice(string.digits) for _ in range(4))
    if mode=="pin6":
        return "".join(secrets.choice(string.digits) for _ in range(6))
    if mode=="easy8":
        alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(8))
    if mode=="strong":
        alphabet="ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%"
        return "".join(secrets.choice(alphabet) for _ in range(14))
    raise HTTPException(400,"unknown password mode")

def suggested_username():
    used={u["username"] for u in system_ops.ssh_users()}
    for i in range(1,10000):
        name=f"user{i:03d}"
        if name not in used:
            return name
    return "user"+secrets.token_hex(2)

def account_rows():
    profiles=all_profiles()
    sessions=system_ops.online_sessions()
    counts={}
    for s in sessions: counts[s["username"]]=counts.get(s["username"],0)+1
    rows=[]
    for u in system_ops.ssh_users():
        p=profiles.get(u["username"],{})
        left=days_left(p.get("expire_date"))
        rows.append({
            **u,
            "plan":p.get("plan",""),
            "note":p.get("note",""),
            "expire_date":p.get("expire_date"),
            "days_left":left,
            "connection_limit":int(p.get("connection_limit",1) or 1),
            "device_limit":int(p.get("device_limit",1) or 1),
            "quota_mb":int(p.get("quota_mb",0) or 0),
            "renewal_days":int(p.get("renewal_days",0) or 0),
            "online_ips":sorted({s.get("remote") for s in sessions if s.get("username")==u["username"] and s.get("remote")}),
            "enabled":bool(p.get("enabled",1)),
            "online":counts.get(u["username"],0),
            "expired":left is not None and left<0,
        })
    return rows

@app.get("/",response_class=HTMLResponse)
def root(request:Request):
    if not current_user(request): return RedirectResponse("/login",302)
    return templates.TemplateResponse("dashboard.html",{
        "request":request,"app_name":APP_NAME,"version":VERSION,
        "language":get_setting("language","fa"),"panel_domain":get_setting("panel_domain",""),
        "theme":get_setting("theme","glass"),"density":get_setting("density","comfortable")
    })

@app.get("/help/connect",response_class=HTMLResponse)
def connection_help(request:Request):
    response=templates.TemplateResponse("client_guide.html",{
        "request":request,"app_name":APP_NAME,"version":VERSION,
        "panel_domain":get_setting("panel_domain",""),
    })
    response.headers["Cache-Control"]="public, max-age=300"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

@app.get("/support/login",response_class=HTMLResponse)
def support_login_page(request:Request):
    if current_user(request): return RedirectResponse("/",302)
    return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":None})

@app.post("/support/login")
def support_login(request:Request,code:str=Form(...)):
    remote_ip=ip(request) or "unknown"
    state=login_rate_state("support:"+remote_ip,int(time.time()))
    if int(state.get("blocked_until") or 0)>int(time.time()):
        return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":"تلاش‌های ناموفق زیاد بوده است؛ کمی بعد دوباره امتحان کنید."},status_code=429)
    grant=consume_support_grant(code)
    if not grant:
        state=record_login_failure("support:"+remote_ip,int(time.time()),max_failures=5,window_seconds=900,block_seconds=900)
        audit("remote-support","support_login_failed",detail=f"failures={state['failures']}",ip=remote_ip)
        return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":"کد پشتیبانی نامعتبر، استفاده‌شده یا منقضی است."},status_code=401)
    clear_login_failures("support:"+remote_ip)
    actor=f"support:{grant['id']}:{grant['scope']}"
    ttl=max(60,int(grant["expires_at"])-int(time.time()))
    audit(actor,"support_login_success",str(grant["id"]),f"scope={grant['scope']}",ip=remote_ip)
    response=RedirectResponse("/",302)
    secure_cookie=request.headers.get("x-forwarded-proto","").lower()=="https"
    response.set_cookie(COOKIE_NAME,make_session(actor,ttl),httponly=True,secure=secure_cookie,samesite="strict",max_age=ttl)
    return response

@app.post("/support/logout")
def support_logout(request:Request):
    actor=current_user(request)
    if actor and is_support_actor(actor): audit(actor,"support_logout",ip=ip(request))
    response=RedirectResponse("/support/login",302)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/login",response_class=HTMLResponse)
def login_page(request:Request):
    return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":None})

@app.post("/login")
def login(request:Request,username:str=Form(...),password:str=Form(...)):
    remote_ip=ip(request) or "unknown"
    now_ts=int(time.time())
    rate=login_rate_state(remote_ip,now_ts)
    if int(rate.get("blocked_until") or 0)>now_ts:
        wait=max(1,int(rate["blocked_until"])-now_ts)
        audit(username or "unknown","login_rate_limited",detail=f"retry_after={wait}",ip=remote_ip)
        return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":f"تلاش‌های ناموفق زیاد بوده است. {max(1,wait//60)} دقیقه دیگر دوباره امتحان کنید."},status_code=429)
    with connect() as con:
        row=con.execute("SELECT * FROM admins WHERE username=? AND active=1",(username,)).fetchone()
    if not row or not verify_password(password,row["password_hash"]):
        state=record_login_failure(remote_ip,now_ts)
        audit(username or "unknown","login_failed",detail=f"failures={state['failures']}",ip=remote_ip)
        return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"error":"نام کاربری یا رمز عبور صحیح نیست."},status_code=401)
    clear_login_failures(remote_ip)
    twofa=get_admin_2fa(username)
    if twofa and twofa.get("totp_enabled"):
        audit(username,"login_password_success_2fa_required",ip=ip(request))
        return templates.TemplateResponse("login_2fa.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"token":make_preauth(username),"error":None})
    audit(username,"login_success",ip=ip(request))
    r=RedirectResponse("/",302)
    secure_cookie=request.headers.get("x-forwarded-proto","").lower()=="https"
    session_age=_setting_int("session_max_age_minutes",720,5,43200)*60
    r.set_cookie(COOKIE_NAME,make_session(username,session_age),httponly=True,secure=secure_cookie,samesite="strict",max_age=session_age)
    return r

@app.post("/login/2fa")
def login_2fa(request:Request,token:str=Form(...),code:str=Form(...)):
    username=read_preauth(token)
    if not username:
        return RedirectResponse("/login",302)
    state=get_admin_2fa(username)
    valid=bool(state and state.get("totp_enabled") and state.get("totp_secret") and pyotp.TOTP(state["totp_secret"]).verify(code.strip(),valid_window=1))
    if not valid:
        audit(username,"login_2fa_failed",ip=ip(request))
        return templates.TemplateResponse("login_2fa.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"token":token,"error":"کد تایید صحیح نیست."},status_code=401)
    audit(username,"login_success_2fa",ip=ip(request))
    r=RedirectResponse("/",302)
    secure_cookie=request.headers.get("x-forwarded-proto","").lower()=="https"
    session_age=_setting_int("session_max_age_minutes",720,5,43200)*60
    r.set_cookie(COOKIE_NAME,make_session(username,session_age),httponly=True,secure=secure_cookie,samesite="strict",max_age=session_age)
    return r

@app.post("/logout")
def logout(request:Request):
    user=current_user(request)
    if user: audit(user,"logout",ip=ip(request))
    r=RedirectResponse("/login",302); r.delete_cookie(COOKIE_NAME); return r

class LicenseActivation(BaseModel):
    code:str=Field(min_length=20,max_length=8192)

@app.get("/api/license/status")
def license_status_api(request:Request):
    require_user(request)
    return {**license_snapshot(),"support":support_snapshot()}

@app.post("/api/license/sync")
def license_sync(request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    result=_sync_license_lease_once()
    audit(actor,"license_sync","license",str(result.get("lease",{}).get("status") or result.get("error") or "offline")[:200],ip(request))
    return {**license_snapshot(),"support":support_snapshot()}

@app.post("/api/license/activate")
def license_activate(payload:LicenseActivation,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    try:
        verified=license_ops.verify_license(payload.code)
    except license_ops.LicenseError as exc:
        audit(actor,"license_activation_failed","license",str(exc),ip(request))
        raise HTTPException(400,str(exc))
    set_setting("license_code",payload.code.strip())
    set_setting("license_lease_code","")
    set_setting("license_lease_error","")
    if verified.get("online_required"):
        _sync_license_lease_once()
    audit(actor,"license_activated",verified.get("license_id") or "full",f"tier={verified.get('tier')}; customer={verified.get('customer')}; online={verified.get('online_required')}",ip(request))
    return {**license_snapshot(),"support":support_snapshot()}

@app.delete("/api/license")
def license_remove(request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    set_setting("license_code","")
    set_setting("license_lease_code","")
    set_setting("license_lease_error","")
    audit(actor,"license_removed","license",ip=ip(request))
    return {**license_snapshot(),"support":support_snapshot()}

class SupportRequestCreate(BaseModel):
    subject:str=Field(min_length=3,max_length=160)
    message:str=Field(min_length=3,max_length=5000)

def _deliver_support_request(payload:dict):
    url=(os.getenv("MAKIA_SUPPORT_WEBHOOK_URL") or "").strip()
    if not url:
        return {"delivered":False,"status":"local","remote_ticket_id":""}
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" or not parsed.netloc:
        return {"delivered":False,"status":"invalid_webhook","remote_ticket_id":""}
    webhook_token=(os.getenv("MAKIA_SUPPORT_WEBHOOK_TOKEN") or "").strip()
    headers={"Content-Type":"application/json","User-Agent":f"Makia/{VERSION}"}
    if webhook_token:
        headers["Authorization"]="Bearer "+webhook_token
    req=urllib.request.Request(
        url,
        data=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req,timeout=8) as response:
            body=response.read(4096).decode("utf-8","replace")
            remote=""
            try:
                obj=json.loads(body or "{}")
                remote=str(obj.get("ticket_id") or obj.get("id") or "")
            except Exception:
                remote=""
            ok=200<=int(response.status)<300
            return {"delivered":ok,"status":"webhook" if ok else f"http_{response.status}","remote_ticket_id":remote}
    except Exception:
        return {"delivered":False,"status":"delivery_failed","remote_ticket_id":""}

@app.get("/api/support/requests")
def support_requests_get(request:Request):
    require_user(request)
    return {"items":list_support_requests(100),"support":support_snapshot()}

@app.post("/api/support/requests")
def support_requests_create(payload:SupportRequestCreate,request:Request):
    actor=require_mutation(request)
    license_state=license_snapshot()
    body={
        "product":APP_NAME,
        "version":VERSION,
        "installation_id":license_state.get("installation_id"),
        "tier":license_state.get("tier"),
        "domain":get_setting("panel_domain",""),
        "subject":payload.subject.strip(),
        "message":payload.message.strip(),
    }
    local_id=create_support_request(payload.subject,payload.message)
    delivery=_deliver_support_request(body)
    update_support_request_delivery(local_id,delivery["status"],delivery.get("remote_ticket_id",""))
    audit(actor,"support_request_create",str(local_id),f"delivery={delivery['status']}",ip(request))
    return {
        "ok":True,"id":local_id,**delivery,
        "request_text":f"Makia Support Request\nInstallation: {body['installation_id']}\nVersion: {VERSION}\nDomain: {body['domain'] or '-'}\nTier: {body['tier']}\nSubject: {body['subject']}\n\n{body['message']}",
        "support":support_snapshot()
    }

class SupportGrantCreate(BaseModel):
    minutes:int=Field(default=30,ge=5,le=120)
    scope:str=Field(default="operator",pattern="^(readonly|operator)$")

@app.get("/api/support/grants")
def support_grants_get(request:Request):
    require_local_admin(request)
    return {"items":list_support_grants(20)}

@app.post("/api/support/grants")
def support_grants_create(payload:SupportGrantCreate,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    grant=create_support_grant(actor,payload.minutes,payload.scope)
    audit(actor,"support_grant_create",str(grant["id"]),f"scope={grant['scope']}; expires_at={grant['expires_at']}",ip(request))
    return {**grant,"login_url":f"{public_origin(request)}/support/login"}

@app.delete("/api/support/grants/{grant_id}")
def support_grants_revoke(grant_id:int,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    result=revoke_support_grant(grant_id)
    audit(actor,"support_grant_revoke",str(grant_id),ip=ip(request))
    return result

@app.get("/api/session/context")
def session_context(request:Request):
    actor=require_user(request)
    return {
        "actor":actor,
        "remote_support":is_support_actor(actor),
        "support_scope":support_actor_scope(actor),
    }

@app.get("/api/overview")
def overview(request:Request):
    require_user(request)
    services=[]
    for name in ALLOWED_SERVICES:
        try: services.append(system_ops.service_status(name))
        except Exception: services.append({"name":name,"label":ALLOWED_SERVICES[name],"active":False,"state":"error"})
    sessions=system_ops.online_sessions()
    accounts=account_rows()
    expiring=sum(1 for a in accounts if a["days_left"] is not None and 0<=a["days_left"]<=7)
    violations=sum(1 for a in accounts if a["online"]>a["connection_limit"])
    return {
        "version":VERSION,
        "metrics":system_ops.metrics(),
        "services":services,
        "users":len(accounts),
        "online_sessions":len(sessions),
        "online_users":len({s["username"] for s in sessions}),
        "expiring_soon":expiring,
        "limit_violations":violations,
        "sessions":sessions[:25],
        "license":license_snapshot(),
    }

@app.get("/api/metrics/history")
def metric_history(request:Request,hours:int=24):
    require_user(request)
    hours=max(1,min(hours,168))
    return metrics_since(int(time.time())-hours*3600)

@app.get("/api/accounts")
def accounts(request:Request):
    require_user(request)
    return account_rows()

class AccountCreate(BaseModel):
    username:str
    password:str|None=Field(default=None,min_length=4,max_length=128)
    password_mode:str="manual"
    expire_date:str|None=None
    plan:str=""
    note:str=""
    connection_limit:int=Field(default=1,ge=1,le=50)
    device_limit:int=Field(default=1,ge=1,le=50)
    quota_mb:int=Field(default=0,ge=0,le=10_000_000)
    renewal_days:int=Field(default=0,ge=0,le=3650)

@app.get("/api/accounts/new-defaults")
def account_new_defaults(request:Request):
    require_user(request)
    return {
        "username":suggested_username(),
        "password_modes":["pin4","pin6","easy8","strong"],
        "recommended_mode":"pin6",
        "expiry_presets":[1,7,30,60,90],
    }

@app.get("/api/accounts/generate-secret")
def account_generate_secret(request:Request,mode:str="strong"):
    require_user(request)
    return {"mode":mode,"secret":generate_user_secret(mode)}

@app.post("/api/accounts")
def create_account(payload:AccountCreate,request:Request):
    actor=require_mutation(request)
    generated=False
    password=payload.password
    if payload.password_mode!="manual":
        password=generate_user_secret(payload.password_mode)
        generated=True
    if not password:
        raise HTTPException(400,"password is required")
    try:
        system_ops.create_ssh_user(payload.username,password,payload.expire_date)
        upsert_profile(payload.username,payload.plan,payload.note,payload.expire_date,payload.connection_limit,payload.quota_mb,1,payload.device_limit,payload.renewal_days)
        delivery=access_ops.ssh_payload(public_host(request),payload.username,password,22,ssh_npv_options(payload.username))
        artifact_id=artifact_save("ssh",payload.username,payload.username,"ssh",delivery,{
            "expire_date":payload.expire_date or "","plan":payload.plan or "",
            "connection_limit":payload.connection_limit,"device_limit":payload.device_limit
        })
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,"account_create",payload.username,f"plan={payload.plan}; limit={payload.connection_limit}; quota_mb={payload.quota_mb}; password_mode={payload.password_mode}",ip(request))
    return {"ok":True,"username":payload.username,"password":password if generated else None,"generated":generated,"artifact_id":artifact_id}

class AccountUpdate(BaseModel):
    password:str|None=Field(default=None,min_length=4,max_length=128)
    expire_date:str|None=None
    clear_expire:bool=False
    plan:str=""
    note:str=""
    connection_limit:int=Field(default=1,ge=1,le=50)
    device_limit:int=Field(default=1,ge=1,le=50)
    quota_mb:int=Field(default=0,ge=0,le=10_000_000)
    renewal_days:int=Field(default=0,ge=0,le=3650)
    enabled:bool=True

@app.put("/api/accounts/{username}")
def update_account(username:str,payload:AccountUpdate,request:Request):
    actor=require_mutation(request)
    try:
        system_ops.update_ssh_user(username,payload.password,payload.expire_date,payload.clear_expire)
        system_ops.lock_user(username,not payload.enabled)
        upsert_profile(username,payload.plan,payload.note,None if payload.clear_expire else payload.expire_date,payload.connection_limit,payload.quota_mb,1 if payload.enabled else 0,payload.device_limit,payload.renewal_days)
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    if payload.password:
        delivery=access_ops.ssh_payload(public_host(request),username,payload.password,22,ssh_npv_options(username))
        artifact_save("ssh",username,username,"ssh",delivery,{
            "expire_date":None if payload.clear_expire else (payload.expire_date or ""),
            "plan":payload.plan or "","connection_limit":payload.connection_limit,"device_limit":payload.device_limit
        })
    audit(actor,"account_update",username,f"enabled={payload.enabled}; limit={payload.connection_limit}; quota_mb={payload.quota_mb}",ip(request))
    return {"ok":True}

@app.post("/api/accounts/{username}/{action}")
def account_action(username:str,action:str,request:Request):
    actor=require_mutation(request)
    try:
        if action=="lock":
            result=system_ops.lock_user(username,True)
            p=next((a for a in account_rows() if a["username"]==username),None)
            if p: upsert_profile(username,p["plan"],p["note"],p["expire_date"],p["connection_limit"],p["quota_mb"],0,p.get("device_limit",1),p.get("renewal_days",0))
        elif action=="unlock":
            result=system_ops.lock_user(username,False)
            p=next((a for a in account_rows() if a["username"]==username),None)
            if p: upsert_profile(username,p["plan"],p["note"],p["expire_date"],p["connection_limit"],p["quota_mb"],1,p.get("device_limit",1),p.get("renewal_days",0))
        elif action=="disconnect":
            targets=[s for s in system_ops.online_sessions() if s["username"]==username and s["tty"]]
            for s in targets:
                try: system_ops.disconnect_session(s["tty"])
                except system_ops.OperationError: pass
            result={"username":username,"disconnected":len(targets)}
        elif action=="delete":
            result=system_ops.delete_user(username); delete_profile(username); delete_access_artifact_by_key("ssh",username)
        else: raise HTTPException(404,"unknown action")
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,f"account_{action}",username,ip=ip(request))
    return result

class BulkAccountAction(BaseModel):
    usernames:list[str]=Field(min_length=1,max_length=200)
    action:str
    days:int=Field(default=0,ge=0,le=3650)

@app.post("/api/accounts/bulk")
def bulk_account_action(payload:BulkAccountAction,request:Request):
    actor=require_mutation(request)
    if payload.action not in {"lock","unlock","disconnect","extend"}:
        raise HTTPException(400,"bulk action not allowed")
    if payload.action=="extend" and payload.days<1:
        raise HTTPException(400,"days must be at least 1")
    profiles=all_profiles()
    done=[]; failed=[]
    for username in payload.usernames:
        try:
            system_ops.validate_username(username)
            if payload.action=="lock":
                system_ops.lock_user(username,True)
            elif payload.action=="unlock":
                system_ops.lock_user(username,False)
            elif payload.action=="extend":
                p=profiles.get(username,{})
                base=date.today()
                if p.get("expire_date"):
                    try:
                        current=date.fromisoformat(str(p.get("expire_date")))
                        if current>base: base=current
                    except Exception:
                        pass
                new_expire=(base+timedelta(days=payload.days)).isoformat()
                system_ops.update_ssh_user(username,expire=new_expire)
                upsert_profile(username,p.get("plan",""),p.get("note",""),new_expire,p.get("connection_limit",1),p.get("quota_mb",0),p.get("enabled",1),p.get("device_limit",1),p.get("renewal_days",0))
            else:
                for s in [x for x in system_ops.online_sessions() if x["username"]==username and x["tty"]]:
                    try: system_ops.disconnect_session(s["tty"])
                    except system_ops.OperationError: pass
            done.append(username)
        except Exception as exc:
            failed.append({"username":username,"error":str(exc)[:160]})
    audit(actor,f"accounts_bulk_{payload.action}",",".join(done[:30]),f"done={len(done)}; failed={len(failed)}; days={payload.days}",ip(request))
    return {"done":done,"failed":failed}

@app.get("/api/sessions")
def sessions(request:Request):
    require_user(request)
    return system_ops.online_sessions()

class SessionDisconnect(BaseModel):
    tty:str
    username:str|None=None

@app.post("/api/sessions/disconnect")
def session_disconnect(payload:SessionDisconnect,request:Request):
    actor=require_mutation(request)
    try: result=system_ops.disconnect_session(payload.tty)
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,"session_disconnect",payload.username or payload.tty,payload.tty,ip(request))
    return result

@app.post("/api/services/{name}/{action}")
def service(name:str,action:str,request:Request):
    actor=require_mutation(request)
    feature={"xray":"xray","openvpn-server@server":"openvpn","wg-quick@wg0":"wireguard"}.get(name)
    if feature:
        assert_license_feature(feature)
    elif name not in {"ssh","nginx","fail2ban","makia-policy-enforcer","makia-metrics-sampler","makia-protocol-traffic"}:
        assert_license_feature("advanced_services")
    try: result=system_ops.service_action(name,action)
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,f"service_{action}",name,ip=ip(request))
    return result

@app.get("/api/security")
def security(request:Request):
    require_user(request)
    return system_ops.security_status()

@app.get("/api/protocols")
def protocols(request:Request):
    require_user(request)
    return protocol_ops.catalog()

class XrayQuickInbound(BaseModel):
    protocol:str
    port:int=Field(ge=1,le=65535)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    transport:str="tcp"
    security:str="none"
    path_value:str=Field(default="/",max_length=255)
    server_name:str=Field(default="",max_length=255)
    reality_dest:str=Field(default="",max_length=255)
    quota_gb:float=Field(default=0,ge=0,le=100000)
    expire_days:int=Field(default=0,ge=0,le=3650)
    ip_limit:int=Field(default=1,ge=1,le=50)
    reset_days:int=Field(default=0,ge=0,le=3650)

@app.post("/api/protocols/xray/quick-inbound")
def xray_quick_inbound(payload:XrayQuickInbound,request:Request):
    actor=require_feature(request,"xray",True)
    if any(row.get("engine")=="xray" and row.get("name")==payload.name for row in list_protocol_clients()):
        raise HTTPException(400,"Xray client name must be unique because traffic accounting uses the client email/name identity")
    try:
        result=protocol_ops.create_xray_inbound(
            payload.protocol,payload.port,payload.name,payload.endpoint,
            payload.transport,payload.security,payload.path_value,payload.server_name,payload.reality_dest
        )
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    qr=qrcode.make(result["share_link"],image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO(); qr.save(buf)
    result["qr"]="data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode()
    quota_bytes=int(payload.quota_gb*1024*1024*1024)
    expire_at=int(time.time()+payload.expire_days*86400) if payload.expire_days else 0
    client_id=create_protocol_client(
        payload.name,"xray",payload.protocol,result["tag"],result["credential"],result["share_link"],
        quota_bytes,expire_at,payload.ip_limit,payload.reset_days
    )
    client_row=get_protocol_client(client_id)
    sub_id=(client_row or {}).get("subscription_id") or ""
    origin=public_origin(request)
    subscription_settings=operator_settings_snapshot()["subscription"]
    sub_format=subscription_settings["default_format"]
    delivery=access_ops.xray_payload(
        payload.name,payload.protocol,result["share_link"],
        f"{origin}/sub/{sub_id}?format={sub_format}" if sub_id and subscription_settings["enabled"] else "",
        f"{origin}/client/{sub_id}" if sub_id and subscription_settings["client_page_enabled"] else ""
    )
    artifact_id=artifact_save("xray",str(client_id),payload.name,payload.protocol,delivery,{
        "client_id":client_id,"inbound_tag":result["tag"],"port":payload.port,
        "transport":result.get("transport",""),"security":result.get("security",""),
        "subscription_id":sub_id
    })
    result["client_id"]=client_id
    result["artifact_id"]=artifact_id
    result["subscription_id"]=sub_id
    result["quota_bytes"]=quota_bytes
    result["expire_at"]=expire_at
    result["ip_limit"]=payload.ip_limit
    result["reset_days"]=payload.reset_days
    audit(actor,"xray_quick_inbound",result["tag"],f"protocol={payload.protocol}; port={payload.port}; quota={quota_bytes}; ip_limit={payload.ip_limit}",ip(request))
    return result

def _subscription_snapshot(row):
    usage={"uplink":0,"downlink":0,"total":0,"available":False}
    if row.get("engine")=="xray" and row.get("protocol") in {"vless","vmess","trojan","hysteria2"} and row.get("enabled"):
        try: usage=protocol_ops.xray_client_traffic(row["name"])
        except Exception: pass
    stored_up=int(row.get("used_up_bytes") or 0)
    stored_down=int(row.get("used_down_bytes") or 0)
    total_up=stored_up+int(usage.get("uplink") or 0)
    total_down=stored_down+int(usage.get("downlink") or 0)
    quota=int(row.get("quota_bytes") or 0)
    expire_at=int(row.get("expire_at") or 0)
    used=total_up+total_down
    expired=bool(expire_at and expire_at<int(time.time()))
    quota_exhausted=bool(quota and used>=quota)
    return {
        "id":row.get("id"),"name":row.get("name"),"protocol":row.get("protocol"),
        "enabled":bool(row.get("enabled")),"share_link":row.get("share_link") or "",
        "quota_bytes":quota,"used_up_bytes":total_up,"used_down_bytes":total_down,
        "used_bytes":used,"remaining_bytes":max(0,quota-used) if quota else None,
        "expire_at":expire_at,"expired":expired,"quota_exhausted":quota_exhausted,
        "ip_limit":int(row.get("ip_limit") or 1),
        "reset_days":int(row.get("reset_days") or 0),
    }

@app.get("/sub/{subscription_id}")
def subscription_get(subscription_id:str,format:str="base64"):
    if not operator_settings_snapshot()["subscription"]["enabled"]:
        raise HTTPException(404,"subscription delivery is disabled")
    row=protocol_client_by_subscription(subscription_id)
    if not row:
        raise HTTPException(404,"subscription not found")
    snap=_subscription_snapshot(row)
    if not snap.get("enabled") or snap.get("expired") or snap.get("quota_exhausted"):
        raise HTTPException(403,"subscription is inactive")
    link=(row.get("share_link") or "").strip()
    if not link:
        raise HTTPException(404,"subscription is empty")
    if format=="raw":
        return PlainTextResponse(link+"\n",media_type="text/plain; charset=utf-8",headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})
    if format=="json":
        return JSONResponse(snap,headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})
    if format not in {"base64","b64"}:
        raise HTTPException(400,"supported formats: base64, raw, json")
    encoded=base64.b64encode((link+"\n").encode()).decode()
    return PlainTextResponse(encoded+"\n",media_type="text/plain; charset=utf-8",headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})

@app.get("/client/{subscription_id}",response_class=HTMLResponse)
def subscription_page(subscription_id:str,request:Request):
    subscription_settings=operator_settings_snapshot()["subscription"]
    if not subscription_settings["client_page_enabled"]:
        raise HTTPException(404,"client page is disabled")
    row=protocol_client_by_subscription(subscription_id)
    if not row:
        raise HTTPException(404,"subscription not found")
    snap=_subscription_snapshot(row)
    link=(row.get("share_link") or "").strip()
    origin=public_origin(request)
    sub_url=f"{origin}/sub/{subscription_id}?format={subscription_settings['default_format']}" if subscription_settings["enabled"] else ""
    profile_qr=""
    subscription_qr=""
    if link:
        profile_qr="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(link)).decode("ascii")
    if sub_url:
        subscription_qr="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(sub_url)).decode("ascii")
    response=templates.TemplateResponse("subscription.html",{
        "request":request,"client":snap,"subscription_id":subscription_id,
        "app_name":APP_NAME,"version":VERSION,
        "profile_qr":profile_qr,"subscription_qr":subscription_qr,"subscription_url":sub_url,
        "subscription_enabled":subscription_settings["enabled"],
        "guide_url":f"{origin}/help/connect#xray",
    })
    response.headers["Cache-Control"]="no-store, private"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

@app.get("/api/protocol-clients")
def protocol_clients_get(request:Request):
    require_feature(request,"xray")
    rows=[]
    now_ts=int(time.time())
    for item in list_protocol_clients():
        usage={"uplink":0,"downlink":0,"total":0,"available":False,"error":None}
        if item.get("engine")=="xray" and item.get("protocol") in {"vless","vmess","trojan","hysteria2"} and item.get("enabled"):
            try: usage=protocol_ops.xray_client_traffic(item["name"])
            except Exception as exc: usage={"uplink":0,"downlink":0,"total":0,"available":False,"error":str(exc)[:160]}
        stored_up=int(item.get("used_up_bytes") or 0)
        stored_down=int(item.get("used_down_bytes") or 0)
        cumulative={
            "uplink":stored_up+int(usage.get("uplink") or 0),
            "downlink":stored_down+int(usage.get("downlink") or 0),
            "total":stored_up+stored_down+int(usage.get("total") or 0),
            "available":bool(usage.get("available") or stored_up or stored_down),
            "error":usage.get("error"),
        }
        online={"available":False,"ips":[],"error":None}
        if item.get("engine")=="xray" and item.get("enabled"):
            try: online=protocol_ops.xray_client_online_ips(item["name"])
            except Exception as exc: online={"available":False,"ips":[],"error":str(exc)[:160]}
        quota=int(item.get("quota_bytes") or 0)
        expire_at=int(item.get("expire_at") or 0)
        ip_limit=max(1,int(item.get("ip_limit") or 1))
        accounting_supported=item.get("protocol") in {"vless","vmess","trojan","hysteria2"}
        rows.append({
            **item,
            "accounting_supported":accounting_supported,
            "usage":cumulative,
            "online":online,
            "online_ip_count":len(online.get("ips") or []),
            "ip_violation":bool(online.get("available") and len(online.get("ips") or [])>ip_limit),
            "quota_percent":round((cumulative["total"]/quota)*100,1) if quota else 0,
            "expired":bool(expire_at and expire_at<now_ts),
            "days_left":max(0,(expire_at-now_ts)//86400) if expire_at and expire_at>=now_ts else (0 if expire_at else None),
        })
    return rows

class ProtocolClientPolicy(BaseModel):
    quota_gb:float|None=Field(default=None,ge=0,le=100000)
    expire_days:int|None=Field(default=None,ge=0,le=3650)
    ip_limit:int|None=Field(default=None,ge=1,le=50)
    reset_days:int|None=Field(default=None,ge=0,le=3650)
    enabled:bool|None=None

@app.put("/api/protocol-clients/{client_id}")
def protocol_client_update(client_id:int,payload:ProtocolClientPolicy,request:Request):
    actor=require_feature(request,"xray",True)
    row=get_protocol_client(client_id)
    if not row: raise HTTPException(404,"client not found")
    quota_bytes=int(payload.quota_gb*1024*1024*1024) if payload.quota_gb is not None else None
    expire_at=int(time.time()+payload.expire_days*86400) if payload.expire_days is not None and payload.expire_days>0 else (0 if payload.expire_days==0 else None)

    if payload.enabled is not None and bool(payload.enabled)!=bool(row.get("enabled")):
        if row.get("engine")=="xray" and row.get("protocol") in {"vless","vmess","trojan","hysteria2","http","socks"}:
            try:
                if payload.enabled:
                    protocol_ops.enable_xray_client(row["inbound_tag"],row["name"],row["protocol"],row["credential"])
                else:
                    protocol_ops.disable_xray_client(row["inbound_tag"],row["name"])
            except protocol_ops.ProtocolError as e:
                raise HTTPException(400,str(e))

    update_protocol_client_state(client_id,payload.enabled,quota_bytes,expire_at,payload.ip_limit,payload.reset_days)
    audit(actor,"protocol_client_update",str(client_id),f"enabled={payload.enabled}; reset_days={payload.reset_days}",ip(request))
    return {"ok":True}

@app.post("/api/protocol-clients/{client_id}/reset-traffic")
def protocol_client_reset_traffic(client_id:int,request:Request):
    actor=require_feature(request,"xray",True)
    row=get_protocol_client(client_id)
    if not row: raise HTTPException(404,"client not found")
    if row.get("engine")!="xray":
        raise HTTPException(400,"traffic reset is only available for Xray clients in this release")
    try:
        result=protocol_ops.reset_xray_client_traffic(row["name"])
        reset_protocol_traffic(client_id)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"protocol_client_reset_traffic",str(client_id),ip=ip(request))
    return {"ok":True,"xray":result}

@app.get("/api/protocols/xray/config")
def xray_config_get(request:Request):
    require_feature(request,"xray")
    try: return protocol_ops.read_xray_config()
    except protocol_ops.ProtocolError as e: raise HTTPException(400,str(e))

class XrayConfigPayload(BaseModel):
    config:dict

@app.post("/api/protocols/xray/config/validate")
def xray_config_validate(payload:XrayConfigPayload,request:Request):
    require_feature(request,"xray",True)
    try: return protocol_ops.validate_xray_config(payload.config)
    except protocol_ops.ProtocolError as e: raise HTTPException(400,str(e))

@app.put("/api/protocols/xray/config")
def xray_config_apply(payload:XrayConfigPayload,request:Request):
    actor=require_feature(request,"xray",True)
    try: result=protocol_ops.apply_xray_config(payload.config)
    except protocol_ops.ProtocolError as e: raise HTTPException(400,str(e))
    audit(actor,"xray_config_apply",result.get("path"),f"backup={result.get('backup')}",ip(request))
    return result

class XrayTunnelCreate(BaseModel):
    listen_port:int=Field(ge=1,le=65535)
    target_host:str=Field(min_length=1,max_length=255)
    target_port:int=Field(ge=1,le=65535)
    network:str="tcp,udp"
    name:str=Field(default="tunnel",min_length=1,max_length=48)

@app.post("/api/protocols/xray/tunnels")
def xray_tunnel_create(payload:XrayTunnelCreate,request:Request):
    actor=require_feature(request,"xray",True)
    try:
        result=protocol_ops.create_xray_tunnel(payload.listen_port,payload.target_host,payload.target_port,payload.network,payload.name)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"xray_tunnel_create",result["tag"],f"{payload.listen_port}->{payload.target_host}:{payload.target_port}/{payload.network}",ip(request))
    return result

class ProtocolInstall(BaseModel):
    component:str

@app.post("/api/protocols/install")
def protocol_install(payload:ProtocolInstall,request:Request):
    actor=require_mutation(request)
    component=str(payload.component or "").lower()
    feature={"xray":"xray","wireguard":"wireguard","openvpn":"openvpn"}.get(component,"advanced_services")
    assert_license_feature(feature)
    try:
        result=protocol_ops.install_component(payload.component)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"protocol_install",payload.component,ip=ip(request))
    return result

@app.get("/api/protocols/xray/diagnostics")
def xray_diagnostics_get(request:Request):
    require_feature(request,"xray")
    return protocol_ops.xray_diagnostics()

@app.post("/api/protocols/xray/repair")
def xray_repair(request:Request):
    actor=require_feature(request,"xray",True)
    try:
        result=protocol_ops.repair_xray_runtime()
    except protocol_ops.ProtocolError as e:
        audit(actor,"xray_repair_failed","xray",str(e)[:500],ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"xray_repair","xray",f"backup={result.get('backup')}",ip(request))
    return result

class WireGuardBootstrap(BaseModel):
    port:int=Field(default=443,ge=1,le=65535)
    cidr:str="10.66.66.1/24"
    mtu:int=Field(default=1280,ge=576,le=1500)

@app.post("/api/protocols/wireguard/bootstrap")
def wireguard_bootstrap(payload:WireGuardBootstrap,request:Request):
    actor=require_feature(request,"wireguard",True)
    try:
        result=protocol_ops.bootstrap_wireguard(payload.port,payload.cidr,mtu=payload.mtu)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"wireguard_bootstrap","wg0",f"port={payload.port}; cidr={payload.cidr}; mtu={payload.mtu}",ip(request))
    return result

@app.get("/api/protocols/wireguard/diagnostics")
def wireguard_diagnostics_get(request:Request,endpoint:str=""):
    require_feature(request,"wireguard")
    target=(endpoint or public_host(request)).strip()
    try:
        return protocol_ops.wireguard_endpoint_diagnostics(target)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))

@app.post("/api/protocols/wireguard/repair")
def wireguard_repair(request:Request):
    actor=require_feature(request,"wireguard",True)
    try:
        result=protocol_ops.repair_wireguard_runtime()
    except protocol_ops.ProtocolError as e:
        audit(actor,"wireguard_repair_failed","wg0",str(e)[:500],ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"wireguard_repair","wg0",f"backup={result.get('backup')}",ip(request))
    return result

@app.get("/api/protocols/endpoint-matrix")
def protocol_endpoint_matrix_get(request:Request,endpoint:str=""):
    require_user(request)
    target=(endpoint or public_host(request)).strip()
    try:
        return protocol_ops.protocol_endpoint_matrix(target)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))

class WireGuardPeer(BaseModel):
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    dns:str=Field(default="1.1.1.1",max_length=64)
    mtu:int=Field(default=1280,ge=576,le=1500)
    keepalive:int=Field(default=15,ge=0,le=3600)
    allowed_ips:str=Field(default="0.0.0.0/0",max_length=255)

@app.post("/api/protocols/wireguard/peers")
def wireguard_peer_create(payload:WireGuardPeer,request:Request):
    actor=require_feature(request,"wireguard",True)
    try:
        result=protocol_ops.create_wireguard_peer(payload.name,payload.endpoint,dns=payload.dns,mtu=payload.mtu,keepalive=payload.keepalive,allowed_ips=payload.allowed_ips)
        result["diagnostics"]=protocol_ops.wireguard_endpoint_diagnostics(payload.endpoint)
        delivery=access_ops.wireguard_payload(payload.name,result["config"],result.get("address"))
        artifact_id=artifact_save("wireguard",payload.name,payload.name,"wireguard",delivery,{
            "public_key":result.get("public_key",""),"address":result.get("address",""),"interface":"wg0",
            "endpoint":result.get("endpoint",""),"port":result.get("port"),"dns":result.get("dns",""),
            "mtu":result.get("mtu"),"keepalive":result.get("keepalive"),"allowed_ips":result.get("allowed_ips","")
        })
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    result["artifact_id"]=artifact_id
    audit(actor,"wireguard_peer_create",payload.name,ip=ip(request))
    return result

class OpenVPNBootstrap(BaseModel):
    port:int=Field(default=1194,ge=1,le=65535)
    proto:str="udp"

@app.post("/api/protocols/openvpn/bootstrap")
def openvpn_bootstrap(payload:OpenVPNBootstrap,request:Request):
    actor=require_feature(request,"openvpn",True)
    try:
        result=protocol_ops.bootstrap_openvpn(payload.port,payload.proto)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"openvpn_bootstrap","server",f"port={payload.port}; proto={payload.proto}",ip(request))
    return result

@app.get("/api/protocols/openvpn/diagnostics")
def openvpn_diagnostics_get(request:Request,endpoint:str=""):
    require_feature(request,"openvpn")
    target=(endpoint or public_host(request)).strip()
    try:
        return protocol_ops.openvpn_endpoint_diagnostics(target)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))

@app.post("/api/protocols/openvpn/repair")
def openvpn_repair(request:Request):
    actor=require_feature(request,"openvpn",True)
    try:
        result=protocol_ops.repair_openvpn_ipv4_runtime()
    except protocol_ops.ProtocolError as e:
        audit(actor,"openvpn_repair_failed","openvpn",str(e)[:500],ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"openvpn_repair","openvpn",f"backup={result.get('backup')}",ip(request))
    return result

class OpenVPNClient(BaseModel):
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    port:int=Field(default=1194,ge=1,le=65535)
    proto:str="udp"

@app.post("/api/protocols/openvpn/clients")
def openvpn_client_create(payload:OpenVPNClient,request:Request):
    actor=require_feature(request,"openvpn",True)
    try:
        result=protocol_ops.create_openvpn_client(payload.name,payload.endpoint,payload.port,payload.proto)
        result["diagnostics"]=protocol_ops.openvpn_endpoint_diagnostics(payload.endpoint)
        delivery=access_ops.openvpn_payload(payload.name,result["config"])
        artifact_id=artifact_save("openvpn",payload.name,payload.name,"openvpn",delivery,{
            "endpoint":payload.endpoint,"port":payload.port,"transport":payload.proto
        })
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    result["artifact_id"]=artifact_id
    audit(actor,"openvpn_client_create",payload.name,ip=ip(request))
    return result

class AccessPackageRequest(BaseModel):
    password:str=Field(min_length=4,max_length=128)

def _resolve_access_payload(kind,key,request):
    artifact=get_access_artifact_by_key(kind,key)
    if artifact:
        try:
            return access_ops.open_payload(artifact["payload_enc"]),artifact
        except access_ops.AccessPackageError as e:
            raise HTTPException(500,str(e))
    if kind=="xray":
        try: row=get_protocol_client(int(key))
        except Exception: row=None
        if not row:
            raise HTTPException(404,"Xray client not found")
        sub_id=row.get("subscription_id") or ""
        origin=public_origin(request)
        subscription_settings=operator_settings_snapshot()["subscription"]
        payload=access_ops.xray_payload(
            row["name"],row["protocol"],row.get("share_link") or "",
            f"{origin}/sub/{sub_id}?format={subscription_settings['default_format']}" if sub_id and subscription_settings["enabled"] else "",
            f"{origin}/client/{sub_id}" if sub_id and subscription_settings["client_page_enabled"] else ""
        )
        artifact_id=artifact_save("xray",str(row["id"]),row["name"],row["protocol"],payload,{
            "client_id":row["id"],"inbound_tag":row.get("inbound_tag",""),"subscription_id":sub_id
        })
        artifact=get_access_artifact_by_key("xray",str(row["id"]))
        return payload,artifact
    if kind=="openvpn":
        try:
            rendered=protocol_ops.render_openvpn_client(key,public_host(request))
        except protocol_ops.ProtocolError as e:
            raise HTTPException(409,str(e))
        payload=access_ops.openvpn_payload(key,rendered["config"])
        artifact_save("openvpn",key,key,"openvpn",payload,{
            "endpoint":public_host(request),"port":rendered.get("port",1194),"transport":rendered.get("proto","udp")
        })
        return payload,get_access_artifact_by_key("openvpn",key)
    if kind=="wireguard":
        raise HTTPException(409,"legacy WireGuard peer has no recoverable client private key; reissue this peer to create a new exportable config")
    if kind=="ssh":
        raise HTTPException(409,"SSH password was not retained for this legacy account; set a new password once to enable encrypted exports")
    raise HTTPException(404,"access entry not found")

def _current_delivery_payload(kind,key,payload,request):
    """Rebuild delivery-facing files from current settings without mutating service credentials."""
    result=payload
    if kind=="ssh":
        summary=dict(payload.get("summary") or {})
        credentials=(payload.get("files") or {}).get("credentials.txt",b"")
        if isinstance(credentials,bytes):
            credentials=credentials.decode("utf-8","replace")
        match=re.search(r"(?m)^Password:\s*(.+)$",str(credentials))
        password=match.group(1).strip() if match else ""
        username=summary.get("username") or key
        if password and summary.get("host") and username:
            result=access_ops.ssh_payload(
                summary["host"],username,password,int(summary.get("port") or 22),ssh_npv_options(username)
            )
    elif kind=="openvpn":
        try:
            rendered=protocol_ops.render_openvpn_client(key,public_host(request))
            result=access_ops.openvpn_payload(key,rendered["config"])
        except protocol_ops.ProtocolError:
            result=payload
    elif kind=="xray":
        try: row=get_protocol_client(int(key))
        except Exception: row=None
        if row and row.get("share_link"):
            subscription_settings=operator_settings_snapshot()["subscription"]
            sid=row.get("subscription_id") or ""
            origin=public_origin(request)
            result=access_ops.xray_payload(
                row["name"],row["protocol"],row.get("share_link") or "",
                f"{origin}/sub/{sid}?format={subscription_settings['default_format']}" if sid and subscription_settings["enabled"] else "",
                f"{origin}/client/{sid}" if sid and subscription_settings["client_page_enabled"] else ""
            )
    # Older encrypted artifacts predate the bundled Persian guide. Add it at
    # delivery time without changing any credential or native configuration.
    if kind in {"ssh","xray","wireguard","openvpn"}:
        result=dict(result)
        files=dict(result.get("files") or {})
        protocol=""
        if kind=="xray":
            try:
                protocol=(get_protocol_client(int(key)) or {}).get("protocol") or ""
            except Exception:
                protocol=""
        files.setdefault("connection-guide-fa.txt",access_ops.client_guide_text(kind,protocol).encode("utf-8"))
        result["files"]=files
    return result

@app.get("/api/access")
def access_entries(request:Request):
    require_user(request)
    artifacts={(a["kind"],a["external_key"]):a for a in list_access_artifacts()}
    rows=[]

    for item in account_rows():
        key=item["username"]
        art=artifacts.get(("ssh",key))
        rows.append({
            "id":f"ssh:{key}","kind":"ssh","key":key,"name":key,"protocol":"ssh",
            "status":"expired" if item.get("expired") else ("active" if item.get("enabled") else "disabled"),
            "online":item.get("online",0),"device_limit":item.get("device_limit",1),
            "connection_limit":item.get("connection_limit",1),"expire_date":item.get("expire_date"),
            "plan":item.get("plan",""),"can_export":bool(art),"artifact_id":art["id"] if art else None,
            "legacy":not bool(art)
        })

    protocol_rows=protocol_clients_get(request) if license_feature_enabled("xray") else []
    for item in protocol_rows:
        key=str(item["id"])
        art=artifacts.get(("xray",key))
        rows.append({
            "id":f"xray:{key}","kind":"xray","key":key,"name":item["name"],"protocol":item["protocol"],
            "status":"expired" if item.get("expired") else ("active" if item.get("enabled") else "disabled"),
            "online":item.get("online_ip_count",0),"device_limit":item.get("ip_limit",1),
            "quota_bytes":item.get("quota_bytes",0),"used_bytes":item.get("usage",{}).get("total",0),
            "expire_at":item.get("expire_at",0),"can_export":True,
            "artifact_id":art["id"] if art else None,"subscription_id":item.get("subscription_id",""),
            "legacy":not bool(art)
        })

    known_wg={a["external_key"] for a in artifacts.values() if a["kind"]=="wireguard"}
    for peer in (protocol_ops.list_wireguard_peers() if license_feature_enabled("wireguard") else []):
        key=peer["name"]
        art=artifacts.get(("wireguard",key))
        rows.append({
            "id":f"wireguard:{key}","kind":"wireguard","key":key,"name":key,"protocol":"wireguard",
            "status":"active","online":None,"device_limit":1,"can_export":bool(art),
            "artifact_id":art["id"] if art else None,"legacy":not bool(art),
            "public_key":peer.get("public_key",""),"address":peer.get("allowed_ips","")
        })

    known_ovpn={a["external_key"] for a in artifacts.values() if a["kind"]=="openvpn"}
    for client in (protocol_ops.list_openvpn_clients() if license_feature_enabled("openvpn") else []):
        key=client["name"]
        art=artifacts.get(("openvpn",key))
        rows.append({
            "id":f"openvpn:{key}","kind":"openvpn","key":key,"name":key,"protocol":"openvpn",
            "status":"active","online":None,"device_limit":1,"can_export":True,
            "artifact_id":art["id"] if art else None,"legacy":not bool(art)
        })

    order={"ssh":0,"xray":1,"wireguard":2,"openvpn":3}
    rows.sort(key=lambda x:(order.get(x["kind"],9),str(x["name"]).lower()))
    return rows

@app.get("/api/access/{kind}/{key}/share")
def access_share(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    require_local_admin(request)
    if kind not in {"ssh","xray","wireguard"}:
        raise HTTPException(404,"share view is not available for this access type")
    if kind=="ssh" and not operator_settings_snapshot()["delivery"]["npv_enabled"]:
        raise HTTPException(409,"NPV SSH delivery is disabled in Settings")
    payload,artifact=_resolve_access_payload(kind,key,request)
    payload=_current_delivery_payload(kind,key,payload,request)
    share=str(payload.get("share_text") or payload.get("primary_text") or "")
    if not share: raise HTTPException(404,"share content is not available")
    qr=access_ops.make_qr_svg(share)
    summary=dict(payload.get("summary") or {})
    connection={}
    if kind=="xray":
        try: xray_row=get_protocol_client(int(key))
        except Exception: xray_row=None
        connection=access_ops.describe_xray_share(share,(xray_row or {}).get("protocol") or summary.get("protocol"))
        subscription_settings=operator_settings_snapshot()["subscription"]
        if xray_row and xray_row.get("subscription_id"):
            sid=xray_row["subscription_id"]
            summary["subscription_url"]=f"{public_origin(request)}/sub/{sid}?format={subscription_settings['default_format']}" if subscription_settings["enabled"] else ""
            summary["client_url"]=f"{public_origin(request)}/client/{sid}" if subscription_settings["client_page_enabled"] else ""
    summary["guide_url"]=f"{public_origin(request)}/help/connect#{'xray' if kind=='xray' else 'wireguard' if kind=='wireguard' else 'ssh'}"
    subscription=str(summary.get("subscription_url") or "")
    subscription_qr=""
    if subscription:
        subscription_qr="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(subscription)).decode("ascii")
    return JSONResponse({
        "kind":kind,"key":key,"share_type":payload.get("share_type") or kind,
        "share_text":share,
        "qr":"data:image/svg+xml;base64,"+base64.b64encode(qr).decode("ascii"),
        "subscription_url":subscription,
        "subscription_qr":subscription_qr,
        "summary":summary,
        "connection":connection,
        "artifact_id":artifact.get("id") if artifact else None,
    },headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})

@app.get("/api/access/{kind}/{key}/qr.svg")
def access_qr(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    if kind not in {"ssh","xray","wireguard"}:
        raise HTTPException(404,"QR is not available for this access type")
    if kind=="ssh" and not operator_settings_snapshot()["delivery"]["npv_enabled"]:
        raise HTTPException(409,"NPV SSH delivery is disabled in Settings")
    payload,_=_resolve_access_payload(kind,key,request)
    payload=_current_delivery_payload(kind,key,payload,request)
    share=str(payload.get("share_text") or payload.get("primary_text") or "")
    if not share: raise HTTPException(404,"QR content is not available")
    return Response(content=access_ops.make_qr_svg(share),media_type="image/svg+xml",headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})

@app.get("/api/access/xray/{key}/subscription-qr.svg")
def access_subscription_qr(key:str,request:Request):
    require_feature(request,"subscriptions")
    require_local_admin(request)
    subscription_settings=operator_settings_snapshot()["subscription"]
    if not subscription_settings["enabled"]:
        raise HTTPException(409,"subscription delivery is disabled in Settings")
    try: row=get_protocol_client(int(key))
    except Exception: row=None
    if not row or not row.get("subscription_id"):
        raise HTTPException(404,"Xray subscription not found")
    url=f"{public_origin(request)}/sub/{row['subscription_id']}?format={subscription_settings['default_format']}"
    return Response(content=access_ops.make_qr_svg(url),media_type="image/svg+xml",headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})

@app.get("/api/access/{kind}/{key}/manifest")
def access_manifest(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    payload,artifact=_resolve_access_payload(kind,key,request)
    payload=_current_delivery_payload(kind,key,payload,request)
    files=payload.get("files") or {}
    return {
        "kind":kind,
        "key":key,
        "native_filename":payload.get("native_filename") or "",
        "files":[{"name":str(name),"size":len(data.encode("utf-8") if isinstance(data,str) else bytes(data))} for name,data in files.items()],
        "protected_package":bool(files),
        "artifact_id":artifact.get("id") if artifact else None,
    }

@app.get("/api/access/{kind}/{key}/native")
def access_native(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    require_local_admin(request)
    payload,_=_resolve_access_payload(kind,key,request)
    payload=_current_delivery_payload(kind,key,payload,request)
    filename=payload.get("native_filename") or "makia-access.txt"
    files=payload.get("files") or {}
    data=files.get(filename)
    if data is None:
        data=(payload.get("primary_text") or "").encode("utf-8")
    if isinstance(data,str): data=data.encode("utf-8")
    media="application/octet-stream"
    if filename.endswith((".txt",".conf",".json")): media="text/plain; charset=utf-8"
    elif filename.endswith(".ovpn"): media="application/x-openvpn-profile"
    audit(current_user(request),"access_native_export",f"{kind}:{key}",filename,ip(request))
    safe=access_ops.safe_filename(filename)
    return Response(content=bytes(data),media_type=media,headers={
        "Content-Disposition":f'attachment; filename="{safe}"',
        "Cache-Control":"no-store, private",
        "X-Content-Type-Options":"nosniff",
    })

@app.post("/api/access/{kind}/{key}/package")
def access_package(kind:str,key:str,payload:AccessPackageRequest,request:Request):
    require_local_admin(request)
    actor=require_access_kind(request,kind,True)
    assert_license_feature("protected_delivery")
    access,_=_resolve_access_payload(kind,key,request)
    access=_current_delivery_payload(kind,key,access,request)
    try:
        content=access_ops.protected_zip(access.get("files") or {},payload.password)
    except access_ops.AccessPackageError as e:
        raise HTTPException(400,str(e))
    try:
        access_ops.verify_protected_zip(content,payload.password)
    except access_ops.AccessPackageError as e:
        raise HTTPException(500,str(e))
    filename=access_ops.safe_filename(f"makia-{kind}-{key}.zip")
    audit(actor,"access_protected_export",f"{kind}:{key}",filename,ip(request))
    return Response(content=content,media_type="application/zip",headers={
        "Content-Disposition":f'attachment; filename="{filename}"',
        "Cache-Control":"no-store, private",
        "X-Content-Type-Options":"nosniff",
    })

@app.delete("/api/access/{kind}/{key}")
def access_revoke(kind:str,key:str,request:Request):
    actor=require_access_kind(request,kind,True)
    try:
        if kind=="ssh":
            system_ops.delete_user(key); delete_profile(key); delete_access_artifact_by_key("ssh",key)
        elif kind=="xray":
            row=get_protocol_client(int(key))
            if not row: raise HTTPException(404,"Xray client not found")
            protocol_ops.remove_xray_inbound(row["inbound_tag"])
            delete_protocol_client(int(key)); delete_access_artifact_by_key("xray",key)
        elif kind=="wireguard":
            artifact=get_access_artifact_by_key("wireguard",key)
            public_key=""
            if artifact:
                try:
                    meta=json.loads(artifact.get("metadata_json") or "{}")
                    public_key=meta.get("public_key","")
                except Exception: pass
            if not public_key:
                match=next((p for p in protocol_ops.list_wireguard_peers() if p.get("name")==key),None)
                public_key=(match or {}).get("public_key","")
            if not public_key: raise HTTPException(404,"WireGuard peer not found")
            protocol_ops.remove_wireguard_peer(public_key)
            delete_access_artifact_by_key("wireguard",key)
        elif kind=="openvpn":
            protocol_ops.revoke_openvpn_client(key)
            delete_access_artifact_by_key("openvpn",key)
        else:
            raise HTTPException(404,"unsupported access kind")
    except (system_ops.OperationError,protocol_ops.ProtocolError) as e:
        raise HTTPException(400,str(e))
    audit(actor,"access_revoke",f"{kind}:{key}",ip=ip(request))
    return {"ok":True}

@app.get("/api/diagnostics/self-test")
def diagnostics_self_test(request:Request):
    require_user(request)
    checks=[]
    def add(name,ok,detail="",level="ok"):
        checks.append({"name":name,"ok":bool(ok),"detail":str(detail)[:500],"level":level if not ok else "ok"})

    try:
        with connect() as con:
            value=con.execute("SELECT 1 AS ok").fetchone()["ok"]
        add("database",value==1,"SQLite query succeeded")
    except Exception as exc:
        add("database",False,exc,"error")

    try:
        mode=stat.S_IMODE(os.stat(SECRET_PATH).st_mode) if SECRET_PATH.exists() else None
        add("server_secret",SECRET_PATH.exists() and mode==0o600,f"mode={oct(mode) if mode is not None else 'missing'}","error")
    except Exception as exc:
        add("server_secret",False,exc,"error")

    try:
        probe={"native_filename":"probe.txt","files":{"probe.txt":b"makia-self-test"},"summary":{"kind":"probe"}}
        token=access_ops.seal_payload(probe)
        reopened=access_ops.open_payload(token)
        add("artifact_crypto",reopened["files"]["probe.txt"]==b"makia-self-test","Fernet round-trip")
    except Exception as exc:
        add("artifact_crypto",False,exc,"error")

    try:
        z=access_ops.protected_zip({"probe.txt":b"makia-self-test"},"582941")
        verified=access_ops.verify_protected_zip(z,"582941","probe.txt")
        add("protected_zip",verified.get("ok") and verified.get("sample_size")==15,f"{len(z)} bytes AES archive")
    except Exception as exc:
        add("protected_zip",False,exc,"error")

    with connect() as con:
        artifact_rows=[dict(r) for r in con.execute("SELECT kind,external_key,payload_enc FROM access_artifacts ORDER BY id").fetchall()]
    broken=[]
    for row in artifact_rows:
        try:
            access_ops.open_payload(row["payload_enc"])
        except Exception as exc:
            broken.append(f"{row.get('kind')}:{row.get('external_key')}:{str(exc)[:80]}")
    add("stored_artifacts",not broken,f"{len(artifact_rows)} checked"+(f"; broken={'; '.join(broken[:3])}" if broken else ""),"error")

    for service_name,label in ALLOWED_SERVICES.items():
        try:
            status=system_ops.service_status(service_name)
            installed=status.get("state") not in {"not-found","unknown"}
            if installed:
                add(f"service:{service_name}",bool(status.get("active")),f"{label}: {status.get('state')}","warn")
        except Exception as exc:
            add(f"service:{service_name}",False,exc,"warn")

    try:
        stack=protocol_ops.catalog()
        add("protocol_catalog",True,f"{sum(1 for x in stack.get('capabilities',[]) if x.get('available'))} capabilities available")
    except Exception as exc:
        add("protocol_catalog",False,exc,"error")

    try:
        xdiag=protocol_ops.xray_diagnostics()
        if xdiag.get("installed"):
            add("xray_core_version",bool(xdiag.get("validated_version")),xdiag.get("version") or "unknown","warn")
            add("xray_config_root",bool(xdiag.get("root_validation")),xdiag.get("root_error") or "Xray core validation PASS","error")
            add("xray_config_service_user",bool(xdiag.get("service_validation")),xdiag.get("service_error") or f"readable by {xdiag.get('service_user')}","error")
            add("xray_runtime",bool(xdiag.get("service_active")),"active" if xdiag.get("service_active") else (xdiag.get("journal") or "service inactive")[-420:],"error")
            add("xray_cert_sync_hook",bool(xdiag.get("cert_sync_hook")),"Certbot deploy hook installed" if xdiag.get("cert_sync_hook") else "Xray TLS renewal hook missing","warn")
    except Exception as exc:
        add("xray_runtime_diagnostics",False,exc,"warn")

    try:
        panel_domain=get_setting("panel_domain","").strip()
        if panel_domain:
            domain_health=panel_ops.domain_status(panel_domain)
            if domain_health.get("certificate"):
                days=domain_health.get("certificate_days_left")
                add("panel_tls_expiry",days is not None and int(days)>14,f"{days} days remaining" if days is not None else "certificate expiry unavailable","warn")
    except Exception as exc:
        add("panel_tls_expiry",False,exc,"warn")

    try:
        ovpn=protocol_ops.openvpn_status()
        if ovpn.get("installed") and ovpn.get("config"):
            diag=protocol_ops.openvpn_endpoint_diagnostics(public_host(request))
            add("openvpn_runtime",bool(diag.get("service_active") and diag.get("listener")),f"{diag.get('proto')}:{diag.get('port')} · listener={diag.get('listener')}","error")
            if not diag.get("endpoint_is_ip"):
                add("openvpn_domain",bool(diag.get("resolved_ipv4")) and diag.get("dns_matches_server") is not False,"; ".join(diag.get("warnings") or []) or "Domain A record points to this VPS","warn")
    except Exception as exc:
        add("openvpn_runtime",False,exc,"warn")

    critical=[x for x in checks if not x["ok"] and x["level"]=="error"]
    warnings=[x for x in checks if not x["ok"] and x["level"]=="warn"]
    return {
        "ok":not critical,
        "version":VERSION,
        "checks":checks,
        "critical":len(critical),
        "warnings":len(warnings),
        "summary":"PASS" if not critical else "FAIL",
    }

@app.get("/api/backups")
def backups(request:Request):
    require_user(request)
    return system_ops.backup_list()

@app.post("/api/backups")
def backup_create(request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    try: result=system_ops.create_backup(str(DATA_DIR))
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,"backup_create",result["name"],ip=ip(request))
    return result

class PortableBackupRequest(BaseModel):
    password:str=Field(min_length=10,max_length=128)

@app.post("/api/backups/portable")
def backup_portable(payload:PortableBackupRequest,request:Request):
    require_local_admin(request)
    actor=require_feature(request,"portable_migration",True)
    try:
        files=system_ops.portable_migration_files(
            str(DATA_DIR),
            list(all_profiles().keys()),
            panel_domain=get_setting("panel_domain",""),
            version=VERSION,
        )
        blob=access_ops.protected_zip(files,payload.password)
        access_ops.verify_protected_zip(blob,payload.password,"manifest.json")
    except (system_ops.OperationError,access_ops.AccessPackageError) as e:
        raise HTTPException(400,str(e))
    filename=f"makia-portable-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    audit(actor,"portable_backup_export",filename,f"files={len(files)}",ip(request))
    return Response(content=blob,media_type="application/zip",headers={
        "Content-Disposition":f'attachment; filename="{filename}"',
        "Cache-Control":"no-store, private",
        "X-Content-Type-Options":"nosniff",
    })

@app.get("/api/audit")
def audit_list(request:Request,limit:int=100):
    require_user(request); limit=max(1,min(limit,500))
    with connect() as con: rows=con.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    return [dict(r) for r in rows]

class PasswordChange(BaseModel):
    current_password:str
    new_password:str=Field(min_length=12,max_length=128)

@app.post("/api/admin/password")
def change_password(payload:PasswordChange,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    with connect() as con:
        row=con.execute("SELECT * FROM admins WHERE username=?",(actor,)).fetchone()
        if not row or not verify_password(payload.current_password,row["password_hash"]): raise HTTPException(400,"current password is incorrect")
        con.execute("UPDATE admins SET password_hash=? WHERE username=?",(hash_password(payload.new_password),actor))
    audit(actor,"admin_password_change",actor,ip=ip(request))
    return {"ok":True}

@app.get("/api/v1/status")
def api_v1_status(request:Request):
    require_api_scope(request,"status:read")
    return {"product":APP_NAME,"version":VERSION,"metrics":system_ops.metrics(),"sessions":len(system_ops.online_sessions())}

@app.get("/api/v1/accounts")
def api_v1_accounts(request:Request):
    require_api_scope(request,"accounts:read")
    return account_rows()

@app.get("/api/v1/protocol-clients")
def api_v1_protocol_clients(request:Request):
    require_api_scope(request,"protocols:read")
    assert_license_feature("xray")
    rows=[]
    for row in list_protocol_clients():
        snap=_subscription_snapshot(row)
        snap.pop("share_link",None)
        rows.append(snap)
    return rows

@app.get("/api/v1/nodes")
def api_v1_nodes(request:Request):
    require_api_scope(request,"nodes:read")
    assert_license_feature("nodes")
    return list_nodes()

class APITokenCreate(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    scopes:list[str]=Field(default_factory=lambda:["status:read"])

@app.get("/api/admin/tokens")
def admin_tokens(request:Request):
    require_local_admin(request)
    return list_api_tokens()

@app.post("/api/admin/tokens")
def admin_token_create(payload:APITokenCreate,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    allowed={"status:read","accounts:read","protocols:read","nodes:read"}
    scopes=[x for x in payload.scopes if x in allowed]
    if not scopes:
        raise HTTPException(400,"at least one valid scope is required")
    result=create_api_token(payload.name,scopes)
    audit(actor,"api_token_create",payload.name,",".join(scopes),ip(request))
    return result

@app.post("/api/admin/tokens/{token_id}/revoke")
def admin_token_revoke(token_id:int,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    revoke_api_token(token_id)
    audit(actor,"api_token_revoke",str(token_id),ip=ip(request))
    return {"ok":True}

class NodeCreate(BaseModel):
    name:str=Field(min_length=1,max_length=80)

class NodeHeartbeat(BaseModel):
    hostname:str=Field(min_length=1,max_length=255)
    version:str=Field(default="",max_length=80)
    cpu:float=Field(ge=0,le=100)
    memory:float=Field(ge=0,le=100)
    disk:float=Field(ge=0,le=100)

@app.get("/api/nodes")
def nodes_get(request:Request):
    require_feature(request,"nodes")
    return list_nodes()

@app.post("/api/nodes")
def nodes_create(payload:NodeCreate,request:Request):
    actor=require_feature(request,"nodes",True)
    result=create_node(payload.name)
    audit(actor,"node_create",payload.name,ip=ip(request))
    return result

@app.post("/api/nodes/{node_id}/revoke")
def nodes_revoke(node_id:int,request:Request):
    actor=require_feature(request,"nodes",True)
    revoke_node(node_id)
    audit(actor,"node_revoke",str(node_id),ip=ip(request))
    return {"ok":True}

@app.post("/api/node/heartbeat")
def node_heartbeat(payload:NodeHeartbeat,request:Request):
    token=bearer(request)
    node=node_by_token(token or "")
    if not node:
        raise HTTPException(403,"invalid node token")
    update_node_heartbeat(node["id"],payload.hostname,payload.version,payload.cpu,payload.memory,payload.disk)
    return {"ok":True,"node_id":node["id"]}

class GeneralSettings(BaseModel):
    language:str="fa"
    panel_domain:str=""
    theme:str="glass"
    density:str="comfortable"

@app.get("/api/settings/general")
def general_settings_get(request:Request):
    require_user(request)
    data=all_settings()
    domain=data.get("panel_domain","")
    return {
        "language":data.get("language","fa"),
        "panel_domain":domain,
        "theme":data.get("theme","glass"),
        "density":data.get("density","comfortable"),
        "domain_status":panel_ops.domain_status(domain or None),
    }

@app.put("/api/settings/general")
def general_settings_put(payload:GeneralSettings,request:Request):
    actor=require_mutation(request)
    language=payload.language if payload.language in {"fa","en"} else "fa"
    theme=payload.theme if payload.theme in {"glass","midnight","amoled","graphite"} else "glass"
    density=payload.density if payload.density in {"comfortable","compact"} else "comfortable"
    domain=(payload.panel_domain or "").strip().lower()
    if domain:
        try: domain=panel_ops.validate_domain(domain)
        except panel_ops.PanelOperationError as e: raise HTTPException(400,str(e))
    set_setting("language",language)
    set_setting("panel_domain",domain)
    set_setting("theme",theme)
    set_setting("density",density)
    audit(actor,"general_settings_update",domain or "none",f"language={language}; theme={theme}; density={density}",ip(request))
    return {"ok":True,"language":language,"panel_domain":domain,"theme":theme,"density":density}


class OperatorSettings(BaseModel):
    session_max_age_minutes:int=Field(default=720,ge=5,le=43200)
    profile_prefix:str=Field(default="Makia",max_length=40)
    npv_enabled:bool=True
    npv_dns_mode:str="UDP"
    npv_udpgw_port:int=Field(default=7300,ge=1,le=65535)
    npv_transparent_dns:bool=False
    show_qr:bool=True
    ssh_password_mode:str="pin6"
    ssh_expire_days:int=Field(default=30,ge=0,le=3650)
    ssh_sessions:int=Field(default=1,ge=1,le=50)
    ssh_devices:int=Field(default=1,ge=1,le=50)
    xray_protocol:str="vless"
    xray_port:int=Field(default=2087,ge=1,le=65535)
    xray_transport:str="xhttp"
    xray_security:str="reality"
    xray_path:str=Field(default="/makia",max_length=256)
    xray_sni:str=Field(default="www.microsoft.com",max_length=253)
    xray_reality_target:str=Field(default="www.microsoft.com:443",max_length=300)
    xray_quota_gb:int=Field(default=50,ge=0,le=100000)
    xray_expire_days:int=Field(default=30,ge=0,le=3650)
    xray_ip_limit:int=Field(default=1,ge=1,le=50)
    xray_reset_days:int=Field(default=30,ge=0,le=3650)
    wireguard_dns:str=Field(default="1.1.1.1",max_length=64)
    wireguard_port:int=Field(default=443,ge=1,le=65535)
    wireguard_mtu:int=Field(default=1280,ge=576,le=1500)
    wireguard_keepalive:int=Field(default=15,ge=0,le=3600)
    wireguard_allowed_ips:str=Field(default="0.0.0.0/0",max_length=255)
    wireguard_cidr:str=Field(default="10.66.66.1/24",max_length=64)
    openvpn_port:int=Field(default=1194,ge=1,le=65535)
    openvpn_proto:str="udp"
    subscription_enabled:bool=True
    subscription_client_page_enabled:bool=True
    subscription_default_format:str="base64"

@app.get("/api/settings/operator")
def operator_settings_get(request:Request):
    require_user(request)
    return operator_settings_snapshot()

@app.put("/api/settings/operator")
def operator_settings_put(payload:OperatorSettings,request:Request):
    actor=require_mutation(request)
    allowed_modes={"pin4","pin6","easy8","strong"}
    allowed_protocols={"vless","vmess","trojan","shadowsocks","hysteria2","http","socks"}
    allowed_transports={"tcp","ws","grpc","httpupgrade","xhttp","kcp"}
    allowed_security={"none","tls","reality"}
    dns_mode=(payload.npv_dns_mode or "UDP").upper()
    if dns_mode not in {"UDP","TCP"}: raise HTTPException(400,"NPV DNS mode must be UDP or TCP")
    if payload.ssh_password_mode not in allowed_modes: raise HTTPException(400,"invalid SSH password mode")
    if payload.xray_protocol not in allowed_protocols: raise HTTPException(400,"invalid Xray protocol")
    if payload.xray_transport not in allowed_transports: raise HTTPException(400,"invalid Xray transport")
    if payload.xray_security not in allowed_security: raise HTTPException(400,"invalid Xray security")
    if payload.openvpn_proto not in {"udp","tcp"}: raise HTTPException(400,"OpenVPN proto must be udp or tcp")
    if payload.subscription_default_format not in {"base64","raw"}: raise HTTPException(400,"subscription format must be base64 or raw")
    try:
        wg_allowed_ips=protocol_ops._validate_wireguard_allowed_ips(payload.wireguard_allowed_ips)
        protocol_ops._validate_wireguard_mtu(payload.wireguard_mtu)
        protocol_ops._validate_keepalive(payload.wireguard_keepalive)
        wg_cidr=ipaddress.ip_interface(payload.wireguard_cidr)
        if wg_cidr.version!=4:
            raise ValueError("WireGuard tunnel CIDR must be IPv4 in this release")
    except Exception as exc:
        raise HTTPException(400,str(exc))
    values={
        "session_max_age_minutes":payload.session_max_age_minutes,
        "delivery_profile_prefix":payload.profile_prefix.strip() or "Makia",
        "delivery_npv_enabled":1 if payload.npv_enabled else 0,
        "delivery_npv_dns_mode":dns_mode,
        "delivery_npv_udpgw_port":payload.npv_udpgw_port,
        "delivery_npv_transparent_dns":1 if payload.npv_transparent_dns else 0,
        "delivery_show_qr":1 if payload.show_qr else 0,
        "default_ssh_password_mode":payload.ssh_password_mode,
        "default_ssh_expire_days":payload.ssh_expire_days,
        "default_ssh_sessions":payload.ssh_sessions,
        "default_ssh_devices":payload.ssh_devices,
        "default_xray_protocol":payload.xray_protocol,
        "default_xray_port":payload.xray_port,
        "default_xray_transport":payload.xray_transport,
        "default_xray_security":payload.xray_security,
        "default_xray_path":payload.xray_path or "/",
        "default_xray_sni":payload.xray_sni.strip(),
        "default_xray_reality_target":payload.xray_reality_target.strip(),
        "default_xray_quota_gb":payload.xray_quota_gb,
        "default_xray_expire_days":payload.xray_expire_days,
        "default_xray_ip_limit":payload.xray_ip_limit,
        "default_xray_reset_days":payload.xray_reset_days,
        "default_wireguard_dns":payload.wireguard_dns.strip() or "1.1.1.1",
        "default_wireguard_port":payload.wireguard_port,
        "default_wireguard_mtu":payload.wireguard_mtu,
        "default_wireguard_keepalive":payload.wireguard_keepalive,
        "default_wireguard_allowed_ips":wg_allowed_ips,
        "default_wireguard_cidr":payload.wireguard_cidr.strip(),
        "default_openvpn_port":payload.openvpn_port,
        "default_openvpn_proto":payload.openvpn_proto,
        "subscription_enabled":1 if payload.subscription_enabled else 0,
        "subscription_client_page_enabled":1 if payload.subscription_client_page_enabled else 0,
        "subscription_default_format":payload.subscription_default_format,
    }
    for key,value in values.items(): set_setting(key,value)
    audit(actor,"operator_settings_update","settings",f"session={payload.session_max_age_minutes}; npv={payload.npv_enabled}; xray={payload.xray_protocol}/{payload.xray_transport}/{payload.xray_security}",ip(request))
    return operator_settings_snapshot()

class DomainApply(BaseModel):
    domain:str=Field(min_length=3,max_length=253)

@app.post("/api/settings/domain/apply")
def domain_apply(payload:DomainApply,request:Request):
    actor=require_mutation(request)
    try: result=panel_ops.apply_domain(payload.domain)
    except panel_ops.PanelOperationError as e: raise HTTPException(400,str(e))
    set_setting("panel_domain",result["domain"])
    audit(actor,"domain_apply",result["domain"],ip=ip(request))
    return result

class CertificateIssue(BaseModel):
    domain:str=Field(min_length=3,max_length=253)
    email:str=Field(min_length=5,max_length=254)

@app.post("/api/settings/domain/certificate")
def certificate_issue(payload:CertificateIssue,request:Request):
    actor=require_mutation(request)
    try: result=panel_ops.issue_certificate(payload.domain,payload.email)
    except panel_ops.PanelOperationError as e: raise HTTPException(400,str(e))
    set_setting("panel_domain",result["domain"])
    audit(actor,"certificate_issue",result["domain"],ip=ip(request))
    return result

@app.get("/api/admin/2fa/status")
def twofa_status(request:Request):
    actor=require_local_admin(request)
    state=get_admin_2fa(actor) or {}
    return {"enabled":bool(state.get("totp_enabled")),"configured":bool(state.get("totp_secret"))}

@app.post("/api/admin/2fa/setup")
def twofa_setup(request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    secret=pyotp.random_base32()
    set_admin_totp_secret(actor,secret)
    uri=pyotp.TOTP(secret).provisioning_uri(name=actor,issuer_name="Makia VPS Manager")
    qr=qrcode.make(uri,image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO(); qr.save(buf)
    qr_data="data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode()
    audit(actor,"admin_2fa_setup",actor,ip=ip(request))
    return {"secret":secret,"uri":uri,"qr":qr_data}

class TwoFACode(BaseModel):
    code:str

@app.post("/api/admin/2fa/enable")
def twofa_enable(payload:TwoFACode,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    state=get_admin_2fa(actor)
    if not state or not state.get("totp_secret") or not pyotp.TOTP(state["totp_secret"]).verify(payload.code.strip(),valid_window=1):
        raise HTTPException(400,"invalid authenticator code")
    set_admin_totp_enabled(actor,True)
    audit(actor,"admin_2fa_enable",actor,ip=ip(request))
    return {"ok":True}

class TwoFADisable(BaseModel):
    password:str
    code:str

@app.post("/api/admin/2fa/disable")
def twofa_disable(payload:TwoFADisable,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    with connect() as con:
        row=con.execute("SELECT password_hash FROM admins WHERE username=?",(actor,)).fetchone()
    state=get_admin_2fa(actor)
    if not row or not verify_password(payload.password,row["password_hash"]):
        raise HTTPException(400,"current password is incorrect")
    if state and state.get("totp_enabled") and (not state.get("totp_secret") or not pyotp.TOTP(state["totp_secret"]).verify(payload.code.strip(),valid_window=1)):
        raise HTTPException(400,"invalid authenticator code")
    clear_admin_totp(actor)
    audit(actor,"admin_2fa_disable",actor,ip=ip(request))
    return {"ok":True}

@app.get("/api/update/status")
def update_status(request:Request):
    require_user(request)
    latest=None
    error=None
    try:
        req=urllib.request.Request(
            "https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/VERSION",
            headers={"User-Agent":"Makia-VPS-Manager"}
        )
        with urllib.request.urlopen(req,timeout=4) as resp:
            latest=resp.read(64).decode("utf-8","replace").strip()
    except Exception as exc:
        error=str(exc)[:160]
    return {"current":VERSION,"latest":latest,"update_available":bool(latest and latest!=VERSION),"error":error}

@app.get("/healthz")
def healthz(): return {"ok":True,"version":VERSION,"product":APP_NAME}
