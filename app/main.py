from pathlib import Path
from datetime import date, datetime, timedelta
import time, io, base64, secrets, string, urllib.request, urllib.parse, json, os, stat, re, ipaddress, socket
import pyotp, qrcode
import qrcode.image.svg
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from .config import APP_NAME, VERSION, COOKIE_NAME, ALLOWED_SERVICES, DATA_DIR, SECRET_PATH
from .db import init_db, connect, audit, upsert_profile, all_profiles, delete_profile, metrics_since, get_admin_2fa, set_admin_totp_secret, set_admin_totp_enabled, clear_admin_totp, create_api_token, list_api_tokens, revoke_api_token, verify_api_token, create_node, list_nodes, revoke_node, node_by_token, update_node_heartbeat, get_setting, set_setting, all_settings, create_protocol_client, list_protocol_clients, get_protocol_client, update_protocol_client_state, replace_protocol_client_identity, delete_protocol_client, reset_protocol_traffic, protocol_client_by_subscription, login_rate_state, record_login_failure, clear_login_failures, upsert_access_artifact, list_access_artifacts, get_access_artifact_by_key, delete_access_artifact_by_key, create_support_request, list_support_requests, update_support_request_delivery, create_support_grant, consume_support_grant, support_grant_by_id, list_support_grants, revoke_support_grant, create_service_plan, list_service_plans, get_service_plan, update_service_plan, delete_service_plan, add_notification_event, list_notification_events, mark_notification_delivered
from .security import verify_password, make_session, read_session, hash_password, make_preauth, read_preauth
from . import system_ops, protocol_ops, panel_ops, access_ops, integration_ops

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
        request.url.path.startswith("/access/") or
        request.url.path=="/integrations/telegram/webhook" or
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

@app.on_event("startup")
def startup():
    init_db()
    if get_setting("ui_generation","")!="glass-v1":
        set_setting("theme","glass")
        set_setting("ui_generation","glass-v1")

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

def require_capability(request:Request,_feature:str,mutation:bool=False):
    """All installed capabilities are available to authenticated administrators."""
    return require_mutation(request) if mutation else require_user(request)

def require_access_kind(request:Request,kind:str,mutation:bool=False):
    kind=str(kind or "").lower()
    if kind=="ssh":
        return require_mutation(request) if mutation else require_user(request)
    feature={"xray":"xray","wireguard":"wireguard","openvpn":"openvpn","outline":"outline"}.get(kind)
    if not feature:
        raise HTTPException(404,"unknown access type")
    return require_capability(request,feature,mutation)

def support_snapshot():
    username=(os.getenv("MAKIA_SUPPORT_TELEGRAM") or "").strip().lstrip("@")
    webhook=(os.getenv("MAKIA_SUPPORT_WEBHOOK_URL") or "").strip()
    webhook_token=(os.getenv("MAKIA_SUPPORT_WEBHOOK_TOKEN") or "").strip()
    return {
        "telegram_username":username,
        "telegram_url":f"https://t.me/{username}" if username else "",
        "webhook_enabled":bool(webhook),
        "webhook_authenticated":bool(webhook and webhook_token),
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
            "xray_transport":get_setting("default_xray_transport","tcp"),
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
    meta=dict(metadata or {})
    existing=get_access_artifact_by_key(str(kind),str(external_key))
    if existing:
        try:
            old_meta=json.loads(existing.get("metadata_json") or "{}")
        except (TypeError,ValueError):
            old_meta={}
        if old_meta.get("public_token") and not meta.get("public_token"):
            meta["public_token"]=old_meta["public_token"]
    meta.setdefault("public_token",secrets.token_urlsafe(24))
    return upsert_access_artifact(
        kind,external_key,display_name,protocol,payload.get("native_filename",""),
        access_ops.seal_payload(payload),
        json.dumps(meta,ensure_ascii=False,separators=(",",":"))
    )

def _artifact_public_meta(artifact):
    try:
        return json.loads((artifact or {}).get("metadata_json") or "{}")
    except (TypeError,ValueError):
        return {}

def _ensure_artifact_public_token(kind,key):
    artifact=get_access_artifact_by_key(str(kind),str(key))
    if not artifact:
        return None,""
    meta=_artifact_public_meta(artifact)
    token=str(meta.get("public_token") or "").strip()
    if token:
        return artifact,token
    token=secrets.token_urlsafe(24)
    meta["public_token"]=token
    payload=access_ops.open_payload(artifact["payload_enc"])
    upsert_access_artifact(
        artifact["kind"],artifact["external_key"],artifact["display_name"],artifact.get("protocol") or "",
        artifact.get("native_filename") or payload.get("native_filename",""),
        artifact["payload_enc"],json.dumps(meta,ensure_ascii=False,separators=(",",":"))
    )
    return get_access_artifact_by_key(str(kind),str(key)),token

def _artifact_by_public_token(token):
    raw=str(token or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}",raw):
        return None
    for item in list_access_artifacts():
        meta=_artifact_public_meta(item)
        if secrets.compare_digest(str(meta.get("public_token") or ""),raw):
            return get_access_artifact_by_key(item["kind"],item["external_key"])
    return None

def _portal_language(request:Request):
    requested=(request.query_params.get("lang") or "").strip().lower()
    if requested in {"fa","en"}:
        return requested
    current=str(get_setting("language","fa") or "fa").lower()
    return current if current in {"fa","en"} else "fa"

def _portal_device(request:Request):
    ua=(request.headers.get("user-agent") or "").lower()
    if "android" in ua:return {"id":"android","label":"Android"}
    if "iphone" in ua or "ipad" in ua:return {"id":"ios","label":"iPhone / iPad"}
    if "windows" in ua:return {"id":"windows","label":"Windows"}
    if "macintosh" in ua or "mac os" in ua:return {"id":"macos","label":"macOS"}
    if "linux" in ua:return {"id":"linux","label":"Linux"}
    return {"id":"other","label":"Device"}

def _portal_one_tap(kind,share_text,download_url):
    share=str(share_text or "").strip()
    if kind in {"xray","outline"}:
        scheme=urllib.parse.urlsplit(share).scheme.lower()
        if scheme in {"vless","vmess","trojan","ss","hysteria2","hy2","socks"}:
            return share
    if kind in {"wireguard","openvpn"}:
        return download_url
    return ""


def _public_access_state(kind,key):
    if kind in {"xray","outline"}:
        try: row=get_protocol_client(int(key))
        except Exception: row=None
        if not row:
            return {"active":False,"reason":"not_found","usage":None}
        snap=_subscription_snapshot(row)
        active=bool(snap.get("enabled") and not snap.get("expired") and not snap.get("quota_exhausted"))
        reason="active" if active else ("expired" if snap.get("expired") else "quota" if snap.get("quota_exhausted") else "disabled")
        return {"active":active,"reason":reason,"usage":snap}
    return {"active":True,"reason":"active","usage":None}

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
    """Return a name that is free across all first-class access engines.

    The create wizard is protocol-agnostic at step 1, so a name that is only
    free in Linux can still collide with Xray, Outline, WireGuard or OpenVPN.
    Keep one global suggestion pool to prevent the UI from proposing a value
    that another engine already owns.
    """
    used={str(u.get("username") or "") for u in system_ops.ssh_users()}
    used.update(str(row.get("name") or "") for row in list_protocol_clients())
    try: used.update(str(row.get("name") or "") for row in protocol_ops.list_wireguard_peers())
    except Exception: pass
    try: used.update(str(row.get("name") or "") for row in protocol_ops.list_openvpn_clients())
    except Exception: pass
    used={name for name in used if name}
    for i in range(1,10000):
        name=f"user{i:03d}"
        if name not in used:
            return name
    while True:
        name="user"+secrets.token_hex(3)
        if name not in used:
            return name

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
        "theme":get_setting("theme","glass"),"density":get_setting("density","comfortable"),
        "current_username":current_user(request) or "admin"
    })

@app.get("/help/connect",response_class=HTMLResponse)
def connection_help(request:Request):
    response=templates.TemplateResponse("client_guide.html",{
        "request":request,"app_name":APP_NAME,"version":VERSION,
        "language":get_setting("language","fa"),"panel_domain":get_setting("panel_domain",""),
    })
    response.headers["Cache-Control"]="public, max-age=300"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

@app.get("/support/login",response_class=HTMLResponse)
def support_login_page(request:Request):
    if current_user(request): return RedirectResponse("/",302)
    return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":None})

@app.post("/support/login")
def support_login(request:Request,code:str=Form(...)):
    remote_ip=ip(request) or "unknown"
    state=login_rate_state("support:"+remote_ip,int(time.time()))
    if int(state.get("blocked_until") or 0)>int(time.time()):
        return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":("تلاش‌های ناموفق زیاد بوده است؛ کمی بعد دوباره امتحان کنید." if get_setting("language","fa")!="en" else "Too many failed attempts. Try again later.")},status_code=429)
    grant=consume_support_grant(code)
    if not grant:
        state=record_login_failure("support:"+remote_ip,int(time.time()),max_failures=5,window_seconds=900,block_seconds=900)
        audit("remote-support","support_login_failed",detail=f"failures={state['failures']}",ip=remote_ip)
        return templates.TemplateResponse("support_login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":("کد پشتیبانی نامعتبر، استفاده‌شده یا منقضی است." if get_setting("language","fa")!="en" else "The support code is invalid, already used or expired.")},status_code=401)
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
    return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":None})

@app.post("/login")
def login(request:Request,username:str=Form(...),password:str=Form(...)):
    remote_ip=ip(request) or "unknown"
    now_ts=int(time.time())
    rate=login_rate_state(remote_ip,now_ts)
    if int(rate.get("blocked_until") or 0)>now_ts:
        wait=max(1,int(rate["blocked_until"])-now_ts)
        audit(username or "unknown","login_rate_limited",detail=f"retry_after={wait}",ip=remote_ip)
        return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":(f"تلاش‌های ناموفق زیاد بوده است. {max(1,wait//60)} دقیقه دیگر دوباره امتحان کنید." if get_setting("language","fa")!="en" else f"Too many failed attempts. Try again in {max(1,wait//60)} minute(s).")},status_code=429)
    with connect() as con:
        row=con.execute("SELECT * FROM admins WHERE username=? AND active=1",(username,)).fetchone()
    if not row or not verify_password(password,row["password_hash"]):
        state=record_login_failure(remote_ip,now_ts)
        audit(username or "unknown","login_failed",detail=f"failures={state['failures']}",ip=remote_ip)
        return templates.TemplateResponse("login.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"error":("نام کاربری یا رمز عبور صحیح نیست." if get_setting("language","fa")!="en" else "Invalid username or password.")},status_code=401)
    clear_login_failures(remote_ip)
    twofa=get_admin_2fa(username)
    if twofa and twofa.get("totp_enabled"):
        audit(username,"login_password_success_2fa_required",ip=ip(request))
        return templates.TemplateResponse("login_2fa.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"token":make_preauth(username),"error":None})
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
        return templates.TemplateResponse("login_2fa.html",{"request":request,"app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),"token":token,"error":("کد تایید صحیح نیست." if get_setting("language","fa")!="en" else "The verification code is invalid.")},status_code=401)
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
    body={
        "product":APP_NAME,
        "version":VERSION,
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
        "request_text":f"Makia Support Request\nVersion: {VERSION}\nDomain: {body['domain'] or '-'}\nSubject: {body['subject']}\n\n{body['message']}",
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
    endpoint:str|None=Field(default=None,max_length=255)
    endpoint_mode:str="auto"
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

class ServicePlanPayload(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    protocol_kind:str=Field(default="xray",max_length=24)
    config:dict=Field(default_factory=dict)
    price_label:str=Field(default="",max_length=80)
    active:bool=True

def _validate_service_plan(payload:ServicePlanPayload):
    kind=str(payload.protocol_kind or "").lower()
    allowed={"ssh","xray","wireguard","openvpn","outline"}
    if kind not in allowed:
        raise HTTPException(400,"unsupported plan protocol")
    cfg=dict(payload.config or {})
    numeric={
        "expire_days":(0,3650),"quota_gb":(0,100000),"ip_limit":(1,50),
        "device_limit":(1,50),"connection_limit":(1,50),"reset_days":(0,3650),
    }
    for key,(low,high) in numeric.items():
        if key in cfg:
            try:value=float(cfg[key])
            except Exception:raise HTTPException(400,f"invalid plan field: {key}")
            if value<low or value>high:
                raise HTTPException(400,f"plan field out of range: {key}")
    enforceable={
        "ssh":{"expire_days","device_limit","connection_limit"},
        "xray":{"expire_days","quota_gb","ip_limit","reset_days"},
        "outline":{"expire_days","quota_gb"},
        "wireguard":set(),
        "openvpn":set(),
    }[kind]
    for key in set(numeric)-enforceable:
        cfg.pop(key,None)
    return kind,cfg

@app.get("/api/plans")
def service_plans_get(request:Request,active_only:bool=False):
    require_user(request)
    return list_service_plans(active_only)

@app.post("/api/plans")
def service_plans_create(payload:ServicePlanPayload,request:Request):
    actor=require_mutation(request)
    kind,cfg=_validate_service_plan(payload)
    try:
        plan_id=create_service_plan(payload.name,kind,cfg,payload.price_label,payload.active)
    except Exception as exc:
        raise HTTPException(400,str(exc))
    audit(actor,"plan_create",str(plan_id),f"{payload.name}; {kind}",ip(request))
    return get_service_plan(plan_id)

@app.put("/api/plans/{plan_id}")
def service_plans_update(plan_id:int,payload:ServicePlanPayload,request:Request):
    actor=require_mutation(request)
    if not get_service_plan(plan_id):
        raise HTTPException(404,"plan not found")
    kind,cfg=_validate_service_plan(payload)
    update_service_plan(plan_id,payload.name,kind,cfg,payload.price_label,payload.active)
    audit(actor,"plan_update",str(plan_id),f"{payload.name}; {kind}",ip(request))
    return get_service_plan(plan_id)

@app.delete("/api/plans/{plan_id}")
def service_plans_delete(plan_id:int,request:Request):
    actor=require_mutation(request)
    if not get_service_plan(plan_id):
        raise HTTPException(404,"plan not found")
    delete_service_plan(plan_id)
    audit(actor,"plan_delete",str(plan_id),ip=ip(request))
    return {"ok":True}


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
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint or public_host(request),payload.endpoint_mode,direct=True,check_aaaa=True)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    try:
        system_ops.create_ssh_user(payload.username,password,payload.expire_date)
        upsert_profile(payload.username,payload.plan,payload.note,payload.expire_date,payload.connection_limit,payload.quota_mb,1,payload.device_limit,payload.renewal_days)
        delivery=access_ops.ssh_payload(endpoint,payload.username,password,22,ssh_npv_options(payload.username))
        artifact_id=artifact_save("ssh",payload.username,payload.username,"ssh",delivery,{
            "expire_date":payload.expire_date or "","plan":payload.plan or "",
            "connection_limit":payload.connection_limit,"device_limit":payload.device_limit,
            "endpoint":endpoint,"endpoint_mode":payload.endpoint_mode
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
        previous=get_access_artifact_by_key("ssh",username)
        try: previous_meta=json.loads(previous.get("metadata_json") or "{}") if previous else {}
        except (TypeError,ValueError): previous_meta={}
        selected_host=previous_meta.get("endpoint") or public_host(request)
        delivery=access_ops.ssh_payload(selected_host,username,payload.password,22,ssh_npv_options(username))
        artifact_save("ssh",username,username,"ssh",delivery,{
            "expire_date":None if payload.clear_expire else (payload.expire_date or ""),
            "plan":payload.plan or "","connection_limit":payload.connection_limit,"device_limit":payload.device_limit,
            "endpoint":selected_host,"endpoint_mode":previous_meta.get("endpoint_mode","auto")
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
    result=protocol_ops.catalog()
    try:outline=integration_ops.outline_status()
    except Exception as exc:outline={"installed":False,"container_active":False,"api_ok":False,"error":str(exc)[:300]}
    result["outline"]=outline
    result.setdefault("capabilities",[]).append({
        "id":"outline","engine":"outline","available":bool(outline.get("installed") and outline.get("api_ok")),
        "installed":bool(outline.get("installed")),"mode":"managed"
    })
    return result

@app.get("/api/protocols/modes")
def protocol_modes_get(request:Request):
    require_user(request)
    return protocol_ops.protocol_modes()

class IKEv2Bootstrap(BaseModel):
    domain:str=Field(min_length=3,max_length=253)
    cidr:str=Field(default="10.77.0.0/24",max_length=64)
    dns:str=Field(default="1.1.1.1",max_length=64)

@app.post("/api/protocols/ikev2/bootstrap")
def ikev2_bootstrap(payload:IKEv2Bootstrap,request:Request):
    actor=require_mutation(request)
    try:
        result=protocol_ops.bootstrap_ikev2(payload.domain,payload.cidr,payload.dns)
    except protocol_ops.ProtocolError as e:
        audit(actor,"ikev2_bootstrap_failed","ikev2",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"ikev2_bootstrap","ikev2",f"domain={payload.domain}; cidr={payload.cidr}",ip=ip(request))
    return result

class IKEv2UserCreate(BaseModel):
    name:str=Field(min_length=3,max_length=48)
    password:str=Field(default="",max_length=128)

@app.post("/api/protocols/ikev2/users")
def ikev2_user_create(payload:IKEv2UserCreate,request:Request):
    actor=require_mutation(request)
    try:
        result=protocol_ops.create_ikev2_user(payload.name,payload.password or None)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"ikev2_user_create",payload.name,ip=ip(request))
    return result

@app.get("/api/protocols/ikev2/users")
def ikev2_users_get(request:Request):
    require_user(request)
    return {"users":protocol_ops.list_ikev2_users()}

@app.delete("/api/protocols/ikev2/users/{name}")
def ikev2_user_delete(name:str,request:Request):
    actor=require_mutation(request)
    try:
        result=protocol_ops.remove_ikev2_user(name)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"ikev2_user_delete",name,ip=ip(request))
    return result

class OpenVPNTCPFallback(BaseModel):
    port:int=Field(default=8443,ge=1,le=65535)

@app.post("/api/protocols/openvpn/tcp-fallback")
def openvpn_tcp_fallback(payload:OpenVPNTCPFallback,request:Request):
    actor=require_capability(request,"openvpn",True)
    try:
        result=protocol_ops.ensure_openvpn_tcp_fallback(payload.port)
    except protocol_ops.ProtocolError as e:
        audit(actor,"openvpn_tcp_fallback_failed","openvpn",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"openvpn_tcp_fallback","openvpn",f"port={payload.port}",ip=ip(request))
    return result

class StealthBootstrap(BaseModel):
    domain:str=Field(min_length=3,max_length=253)
    port:int=Field(default=9443,ge=1,le=65535)

@app.post("/api/protocols/stealth/bootstrap")
def stealth_bootstrap(payload:StealthBootstrap,request:Request):
    actor=require_mutation(request)
    try:
        result=protocol_ops.bootstrap_stealth(payload.domain,payload.port)
    except protocol_ops.ProtocolError as e:
        audit(actor,"stealth_bootstrap_failed","stealth",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"stealth_bootstrap","stealth",f"domain={payload.domain}; port={payload.port}",ip=ip(request))
    return result

class WStunnelBootstrap(BaseModel):
    domain:str=Field(min_length=3,max_length=253)
    port:int=Field(default=8444,ge=1,le=65535)
    path_prefix:str=Field(default="",max_length=96)

@app.post("/api/protocols/wstunnel/bootstrap")
def wstunnel_bootstrap(payload:WStunnelBootstrap,request:Request):
    actor=require_mutation(request)
    try:
        result=protocol_ops.bootstrap_wstunnel(payload.domain,payload.port,payload.path_prefix or None)
    except protocol_ops.ProtocolError as e:
        audit(actor,"wstunnel_bootstrap_failed","wstunnel",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"wstunnel_bootstrap","wstunnel",f"domain={payload.domain}; port={payload.port}",ip=ip(request))
    return result

class XrayInboundBuilderPayload(BaseModel):
    protocol:str
    port:int=Field(ge=1,le=65535)
    remark:str=Field(min_length=1,max_length=80)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    listen:str=Field(default="0.0.0.0",max_length=80)
    transport:str="tcp"
    security:str="none"
    flow:str=""
    credential:str=Field(default="",max_length=128)
    shadowsocks_method:str="aes-128-gcm"
    quota_gb:float=Field(default=0,ge=0,le=100000)
    expire_days:int=Field(default=0,ge=0,le=3650)
    ip_limit:int=Field(default=1,ge=1,le=50)
    reset_days:int=Field(default=0,ge=0,le=3650)
    options:dict=Field(default_factory=dict)


@app.get("/api/protocols/xray/inbound-capabilities")
def xray_inbound_capabilities(request:Request):
    require_capability(request,"xray")
    caps=protocol_ops.xray_inbound_builder_capabilities()
    # Presets are enriched with actual host port readiness so selecting a
    # profile does not blindly collide with Nginx, OpenVPN, WireGuard or
    # another Xray listener. This is advisory; create/apply still performs
    # the authoritative runtime validation and rollback.
    for preset in caps.get("presets") or []:
        transport_proto="udp" if preset.get("requires_udp") else "tcp"
        states=[]
        for raw_port in preset.get("ports") or []:
            port=int(raw_port)
            occupied=protocol_ops._port_transport_in_use(port,transport_proto)
            states.append({
                "port":port,"transport":transport_proto,"occupied":occupied,
                "owner":protocol_ops._port_owner_label(port,transport_proto) if occupied else "",
            })
        preset["port_state"]=states
        preset["suggested_port"]=next((x["port"] for x in states if not x["occupied"]),None)
    return caps


@app.post("/api/protocols/xray/inbounds")
def xray_inbound_create(payload:XrayInboundBuilderPayload,request:Request):
    actor=require_capability(request,"xray",True)
    if any(row.get("engine")=="xray" and row.get("name")==payload.name for row in list_protocol_clients()):
        raise HTTPException(400,"Xray client name must be unique because traffic accounting uses the client email/name identity")
    client_id=None
    result=None
    try:
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode)
        spec=payload.model_dump()
        spec["endpoint"]=endpoint
        result=protocol_ops.create_xray_full_inbound(spec)
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
            "flow":payload.flow,"subscription_id":sub_id,
            "endpoint":endpoint,"endpoint_mode":payload.endpoint_mode,
            "builder":"inbound-center-v1","remark":payload.remark,
            "reality_public_key":(result.get("reality") or {}).get("public_key",""),
            "reality_short_id":(result.get("reality") or {}).get("short_id",""),
        })
    except protocol_ops.ProtocolError as exc:
        raise HTTPException(400,str(exc))
    except Exception:
        if client_id is not None:
            try:
                delete_access_artifact_by_key("xray",str(client_id))
                delete_protocol_client(client_id)
            except Exception:
                pass
        if result and result.get("tag"):
            try:protocol_ops.remove_xray_inbound(result["tag"])
            except Exception:pass
        raise
    qr=qrcode.make(result["share_link"],image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO();qr.save(buf)
    result["qr"]="data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode()
    result["client_id"]=client_id
    result["artifact_id"]=artifact_id
    result["subscription_id"]=sub_id
    result["quota_bytes"]=quota_bytes
    result["expire_at"]=expire_at
    result["ip_limit"]=payload.ip_limit
    result["reset_days"]=payload.reset_days
    audit(
        actor,"xray_inbound_builder_create",result["tag"],
        f"protocol={payload.protocol}; transport={payload.transport}; security={payload.security}; port={payload.port}",
        ip(request)
    )
    return result


class XrayInboundClientCreate(BaseModel):
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    credential:str=Field(default="",max_length=128)
    flow:str=""
    quota_gb:float=Field(default=0,ge=0,le=100000)
    expire_days:int=Field(default=0,ge=0,le=3650)
    ip_limit:int=Field(default=1,ge=1,le=50)
    reset_days:int=Field(default=0,ge=0,le=3650)


@app.post("/api/protocols/xray/inbounds/{inbound_tag}/clients")
def xray_inbound_client_create(inbound_tag:str,payload:XrayInboundClientCreate,request:Request):
    actor=require_capability(request,"xray",True)
    if any(row.get("engine")=="xray" and row.get("name")==payload.name for row in list_protocol_clients()):
        raise HTTPException(400,"Xray client name must be globally unique because accounting uses the email/name identity")
    client_id=None
    result=None
    try:
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode)
        result=protocol_ops.add_xray_client_to_inbound(
            inbound_tag,payload.name,endpoint,payload.credential,payload.flow
        )
        quota_bytes=int(payload.quota_gb*1024*1024*1024)
        expire_at=int(time.time()+payload.expire_days*86400) if payload.expire_days else 0
        client_id=create_protocol_client(
            payload.name,"xray",result["protocol"],result["tag"],result["credential"],result["share_link"],
            quota_bytes,expire_at,payload.ip_limit,payload.reset_days
        )
        row=get_protocol_client(client_id)
        sub_id=(row or {}).get("subscription_id") or ""
        origin=public_origin(request)
        subscription_settings=operator_settings_snapshot()["subscription"]
        sub_format=subscription_settings["default_format"]
        delivery=access_ops.xray_payload(
            payload.name,result["protocol"],result["share_link"],
            f"{origin}/sub/{sub_id}?format={sub_format}" if sub_id and subscription_settings["enabled"] else "",
            f"{origin}/client/{sub_id}" if sub_id and subscription_settings["client_page_enabled"] else ""
        )
        artifact_id=artifact_save("xray",str(client_id),payload.name,result["protocol"],delivery,{
            "client_id":client_id,"inbound_tag":result["tag"],"port":result["port"],
            "transport":result.get("transport",""),"security":result.get("security",""),
            "flow":payload.flow,"subscription_id":sub_id,
            "endpoint":endpoint,"endpoint_mode":payload.endpoint_mode,
            "builder":"inbound-client-v1",
            "reality_public_key":(result.get("reality") or {}).get("public_key",""),
            "reality_short_id":(result.get("reality") or {}).get("short_id",""),
        })
    except protocol_ops.ProtocolError as exc:
        raise HTTPException(400,str(exc))
    except Exception:
        if result and result.get("tag") and payload.name:
            try:protocol_ops.remove_xray_client_from_inbound(result["tag"],payload.name)
            except Exception:pass
        if client_id is not None:
            try:
                delete_access_artifact_by_key("xray",str(client_id))
                delete_protocol_client(client_id)
            except Exception:
                pass
        raise
    qr=qrcode.make(result["share_link"],image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO();qr.save(buf)
    result["qr"]="data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode()
    result["client_id"]=client_id
    result["artifact_id"]=artifact_id
    result["subscription_id"]=sub_id
    result["quota_bytes"]=quota_bytes
    result["expire_at"]=expire_at
    result["ip_limit"]=payload.ip_limit
    result["reset_days"]=payload.reset_days
    audit(actor,"xray_inbound_client_create",result["tag"],f"name={payload.name}; protocol={result['protocol']}",ip=ip(request))
    return result


class XrayQuickInbound(BaseModel):
    protocol:str
    port:int=Field(ge=1,le=65535)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    transport:str="tcp"
    security:str="none"
    path_value:str=Field(default="/",max_length=255)
    server_name:str=Field(default="",max_length=255)
    reality_dest:str=Field(default="",max_length=255)
    quota_gb:float=Field(default=0,ge=0,le=100000)
    expire_days:int=Field(default=0,ge=0,le=3650)
    ip_limit:int=Field(default=1,ge=1,le=50)
    reset_days:int=Field(default=0,ge=0,le=3650)
    manual:bool=False

@app.post("/api/protocols/xray/quick-inbound")
def xray_quick_inbound(payload:XrayQuickInbound,request:Request):
    actor=require_capability(request,"xray",True)
    if any(row.get("engine")=="xray" and row.get("name")==payload.name for row in list_protocol_clients()):
        raise HTTPException(400,"Xray client name must be unique because traffic accounting uses the client email/name identity")
    try:
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode)
        result=protocol_ops.create_xray_inbound(
            payload.protocol,payload.port,payload.name,endpoint,
            payload.transport,payload.security,payload.path_value,payload.server_name,payload.reality_dest,
            manual=payload.manual
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
        "transport":result.get("transport",""),"security":result.get("security",""),"manual":bool(payload.manual),
        "subscription_id":sub_id,"endpoint":endpoint,"endpoint_mode":payload.endpoint_mode
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
        "app_name":APP_NAME,"version":VERSION,"language":get_setting("language","fa"),
        "profile_qr":profile_qr,"subscription_qr":subscription_qr,"subscription_url":sub_url,
        "subscription_enabled":subscription_settings["enabled"],
        "guide_url":f"{origin}/help/connect#xray",
    })
    response.headers["Cache-Control"]="no-store, private"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

@app.get("/api/protocol-clients")
def protocol_clients_get(request:Request,engine:str=""):
    require_capability(request,"xray")
    engine_filter=str(engine or "").strip().lower()
    if engine_filter not in {"","xray","outline"}:
        raise HTTPException(400,"unsupported protocol client engine")
    rows=[]
    now_ts=int(time.time())
    for item in list_protocol_clients():
        if engine_filter and str(item.get("engine") or "").lower()!=engine_filter:
            continue
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
    actor=require_capability(request,"xray",True)
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
    actor=require_capability(request,"xray",True)
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
    require_capability(request,"xray")
    try: return protocol_ops.read_xray_config()
    except protocol_ops.ProtocolError as e: raise HTTPException(400,str(e))

class XrayConfigPayload(BaseModel):
    config:dict

@app.post("/api/protocols/xray/config/validate")
def xray_config_validate(payload:XrayConfigPayload,request:Request):
    require_capability(request,"xray",True)
    try: return protocol_ops.validate_xray_config(payload.config)
    except protocol_ops.ProtocolError as e: raise HTTPException(400,str(e))

@app.put("/api/protocols/xray/config")
def xray_config_apply(payload:XrayConfigPayload,request:Request):
    actor=require_capability(request,"xray",True)
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
    actor=require_capability(request,"xray",True)
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
    try:
        result=protocol_ops.install_component(payload.component)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"protocol_install",payload.component,ip=ip(request))
    return result

@app.get("/api/protocols/xray/diagnostics")
def xray_diagnostics_get(request:Request):
    require_capability(request,"xray")
    return protocol_ops.xray_diagnostics()

@app.post("/api/protocols/xray/repair")
def xray_repair(request:Request):
    actor=require_capability(request,"xray",True)
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
    actor=require_capability(request,"wireguard",True)
    try:
        result=protocol_ops.bootstrap_wireguard(payload.port,payload.cidr,mtu=payload.mtu)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"wireguard_bootstrap","wg0",f"port={payload.port}; cidr={payload.cidr}; mtu={payload.mtu}",ip(request))
    return result

@app.get("/api/protocols/wireguard/diagnostics")
def wireguard_diagnostics_get(request:Request,endpoint:str="",known_working_ipv4:str=""):
    require_capability(request,"wireguard")
    target=(endpoint or public_host(request)).strip()
    try:
        diagnostics=protocol_ops.wireguard_endpoint_diagnostics(target)
        if known_working_ipv4:
            try:
                expected=ipaddress.IPv4Address(known_working_ipv4.strip()).compressed
            except ipaddress.AddressValueError as exc:
                raise HTTPException(400,"Known working IP must be an IPv4 address") from exc
            diagnostics["known_working_ipv4"]=expected
            if not diagnostics["endpoint_is_ip"] and expected not in diagnostics["resolved_ipv4"]:
                diagnostics["endpoint_ok"]=False
                diagnostics["ok"]=False
                diagnostics["warnings"].insert(0,f"رکورد A دامنه به IP شناخته‌شده و سالم ({expected}) اشاره نمی‌کند.")
        return diagnostics
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))

class WireGuardEndpointUpdate(BaseModel):
    endpoint:str=Field(min_length=1,max_length=255)

@app.post("/api/access/wireguard/{key}/endpoint")
def wireguard_endpoint_update(key:str,payload:WireGuardEndpointUpdate,request:Request):
    actor=require_capability(request,"wireguard",True)
    require_local_admin(request)
    artifact=get_access_artifact_by_key("wireguard",key)
    if not artifact:
        raise HTTPException(409,"Client private key is not retained; reissue this legacy peer")
    try:
        profile=access_ops.open_payload(artifact["payload_enc"])
        metadata=json.loads(artifact.get("metadata_json") or "{}")
        active=next((p for p in protocol_ops.list_wireguard_peers() if p["name"]==key),None)
        if not active or not metadata.get("public_key") or active["public_key"]!=metadata["public_key"]:
            raise HTTPException(409,"Stored profile does not match the active peer")
        endpoint=protocol_ops._validate_endpoint_host(payload.endpoint,"WireGuard endpoint")
        diagnostics=protocol_ops.wireguard_endpoint_diagnostics(endpoint)
        if not diagnostics["endpoint_ok"]:
            raise HTTPException(409,"WireGuard domain/IP is not ready: "+"; ".join(diagnostics["warnings"]))
        previous_endpoint=re.search(r"(?m)^Endpoint[ \t]*=[ \t]*([^\s:]+):\d+[ \t]*$",profile["primary_text"])
        if previous_endpoint and not diagnostics["endpoint_is_ip"]:
            try: old_ipv4=ipaddress.IPv4Address(previous_endpoint.group(1)).compressed
            except ipaddress.AddressValueError: old_ipv4=""
            if old_ipv4 and old_ipv4 not in diagnostics["resolved_ipv4"]:
                raise HTTPException(409,f"Domain A record does not match the previous working IPv4 ({old_ipv4})")
        updated=access_ops.wireguard_replace_endpoint(profile["primary_text"],protocol_ops._uri_host(endpoint))
        refreshed=access_ops.wireguard_payload(key,updated,metadata.get("address"))
        metadata["endpoint"]=endpoint
        artifact_save("wireguard",key,artifact["display_name"],"wireguard",refreshed,metadata)
    except (access_ops.AccessPackageError,KeyError,ValueError,TypeError) as exc:
        raise HTTPException(409,"Stored WireGuard profile cannot be updated: "+str(exc)) from exc
    audit(actor,"wireguard_endpoint_update",key,f"endpoint={endpoint}",ip(request))
    return {"ok":True,"endpoint":endpoint,"diagnostics":diagnostics}

@app.post("/api/protocols/wireguard/repair")
def wireguard_repair(request:Request):
    actor=require_capability(request,"wireguard",True)
    try:
        result=protocol_ops.repair_wireguard_runtime()
    except protocol_ops.ProtocolError as e:
        audit(actor,"wireguard_repair_failed","wg0",str(e)[:500],ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"wireguard_repair","wg0",f"backup={result.get('backup')}",ip(request))
    return result

class WireGuardPeerState(BaseModel):
    enabled:bool

@app.post("/api/access/wireguard/{key}/state")
def wireguard_peer_state(key:str,payload:WireGuardPeerState,request:Request):
    actor=require_capability(request,"wireguard",True)
    try:
        peer=protocol_ops.set_wireguard_peer_enabled(key,payload.enabled)
    except protocol_ops.ProtocolError as exc:
        raise HTTPException(400,str(exc)) from exc
    audit(actor,"wireguard_peer_state",key,f"enabled={peer['enabled']}",ip(request))
    return {"ok":True,"name":key,"enabled":peer["enabled"]}

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
    endpoint_mode:str="auto"
    dns:str=Field(default="1.1.1.1",max_length=64)
    mtu:int=Field(default=1280,ge=576,le=1500)
    keepalive:int=Field(default=15,ge=0,le=3600)
    allowed_ips:str=Field(default="0.0.0.0/0",max_length=255)

@app.post("/api/protocols/wireguard/peers")
def wireguard_peer_create(payload:WireGuardPeer,request:Request):
    actor=require_capability(request,"wireguard",True)
    try:
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode,direct=True)
        result=protocol_ops.create_wireguard_peer(payload.name,endpoint,dns=payload.dns,mtu=payload.mtu,keepalive=payload.keepalive,allowed_ips=payload.allowed_ips)
        result["diagnostics"]=protocol_ops.wireguard_endpoint_diagnostics(endpoint)
        try:
            delivery=access_ops.wireguard_payload(payload.name,result["config"],result.get("address"))
            artifact_id=artifact_save("wireguard",payload.name,payload.name,"wireguard",delivery,{
                "public_key":result.get("public_key",""),"address":result.get("address",""),"interface":"wg0",
                "endpoint":result.get("endpoint",""),"endpoint_mode":payload.endpoint_mode,
                "port":result.get("port"),"dns":result.get("dns",""),
                "mtu":result.get("mtu"),"keepalive":result.get("keepalive"),"allowed_ips":result.get("allowed_ips","")
            })
        except Exception:
            try: protocol_ops.remove_wireguard_peer(result["public_key"])
            except protocol_ops.ProtocolError as cleanup_exc:
                raise protocol_ops.ProtocolError(
                    f"WireGuard export save failed and peer cleanup failed; inspect {result['public_key']}: {cleanup_exc}"
                ) from cleanup_exc
            raise
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
    actor=require_capability(request,"openvpn",True)
    try:
        result=protocol_ops.bootstrap_openvpn(payload.port,payload.proto)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))
    audit(actor,"openvpn_bootstrap","server",f"port={payload.port}; proto={payload.proto}",ip(request))
    return result

@app.get("/api/protocols/openvpn/diagnostics")
def openvpn_diagnostics_get(request:Request,endpoint:str=""):
    require_capability(request,"openvpn")
    target=(endpoint or public_host(request)).strip()
    try:
        return protocol_ops.openvpn_endpoint_diagnostics(target)
    except protocol_ops.ProtocolError as e:
        raise HTTPException(400,str(e))

@app.post("/api/protocols/openvpn/repair")
def openvpn_repair(request:Request):
    actor=require_capability(request,"openvpn",True)
    try:
        result=protocol_ops.repair_openvpn_ipv4_runtime()
    except protocol_ops.ProtocolError as e:
        audit(actor,"openvpn_repair_failed","openvpn",str(e)[:500],ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"openvpn_repair","openvpn",f"backup={result.get('backup')}",ip(request))
    return result

class OpenVPNConfigure(BaseModel):
    port:int=Field(default=1194,ge=1,le=65535)
    proto:str="udp"
    dns_servers:list[str]=Field(default_factory=lambda:["1.1.1.1","8.8.8.8"])
    keepalive_ping:int=Field(default=10,ge=1,le=3600)
    keepalive_timeout:int=Field(default=120,ge=10,le=7200)
    redirect_gateway:bool=True
    client_to_client:bool=False

@app.post("/api/protocols/openvpn/configure")
def openvpn_configure(payload:OpenVPNConfigure,request:Request):
    actor=require_capability(request,"openvpn",True)
    try:
        result=protocol_ops.reconfigure_openvpn_server(
            payload.port,payload.proto,payload.dns_servers,
            payload.keepalive_ping,payload.keepalive_timeout,
            payload.redirect_gateway,payload.client_to_client,
        )
    except protocol_ops.ProtocolError as e:
        audit(actor,"openvpn_configure_failed","openvpn",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    runtime=result.get("runtime") or {}
    set_setting("default_openvpn_port",int(runtime.get("port") or payload.port))
    set_setting("default_openvpn_proto","tcp" if str(runtime.get("proto") or payload.proto).startswith("tcp") else "udp")
    audit(actor,"openvpn_configure","openvpn",f"port={runtime.get('port')}; proto={runtime.get('proto')}",ip=ip(request))
    return result

class OpenVPNClient(BaseModel):
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    port:int=Field(default=1194,ge=1,le=65535)
    proto:str="udp"

@app.post("/api/protocols/openvpn/clients")
def openvpn_client_create(payload:OpenVPNClient,request:Request):
    actor=require_capability(request,"openvpn",True)
    try:
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode,direct=True)
        result=protocol_ops.create_openvpn_client(payload.name,endpoint,payload.port,payload.proto)
        result["diagnostics"]=protocol_ops.openvpn_endpoint_diagnostics(endpoint)
        delivery=access_ops.openvpn_payload(payload.name,result["config"])
        artifact_id=artifact_save("openvpn",payload.name,payload.name,"openvpn",delivery,{
            "endpoint":endpoint,"endpoint_mode":payload.endpoint_mode,
            "port":payload.port,"transport":payload.proto
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
    if kind=="outline":
        try: row=get_protocol_client(int(key))
        except Exception: row=None
        if not row or row.get("engine")!="outline":
            raise HTTPException(404,"Outline client not found")
        payload=access_ops.outline_payload(
            row["name"],row.get("share_link") or "",row.get("inbound_tag") or "",row.get("quota_bytes") or 0
        )
        artifact_save("outline",str(row["id"]),row["name"],"outline",payload,{
            "client_id":row["id"],"outline_key_id":row.get("inbound_tag") or "",
        })
        return payload,get_access_artifact_by_key("outline",str(row["id"]))
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
        # Modern OpenVPN artifacts retain the explicitly selected endpoint.
        # Only those profiles are safe to regenerate from current server
        # runtime (for example after UDP/TCP or port reconfiguration). Legacy
        # payloads have no provenance metadata, so preserve them byte-for-byte
        # instead of guessing an endpoint or requiring a newer DB table.
        try:
            artifact=get_access_artifact_by_key("openvpn",str(key))
        except Exception:
            artifact=None
        if artifact:
            endpoint=""
            try:
                endpoint=str(json.loads(artifact.get("metadata_json") or "{}").get("endpoint") or "")
            except (TypeError,ValueError):
                endpoint=""
            endpoint=endpoint or public_host(request)
            try:
                rendered=protocol_ops.render_openvpn_client(str(key),endpoint)
                result=access_ops.openvpn_payload(str(key),rendered["config"])
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
    if kind in {"ssh","xray","wireguard","openvpn","outline"}:
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
    def saved_endpoint(artifact):
        if not artifact:return ""
        try:return str(json.loads(artifact.get("metadata_json") or "{}").get("endpoint") or "")
        except (TypeError,ValueError):return ""

    for item in account_rows():
        key=item["username"]
        art=artifacts.get(("ssh",key))
        rows.append({
            "id":f"ssh:{key}","kind":"ssh","key":key,"name":key,"protocol":"ssh",
            "status":"expired" if item.get("expired") else ("active" if item.get("enabled") else "disabled"),
            "online":item.get("online",0),"device_limit":item.get("device_limit",1),
            "connection_limit":item.get("connection_limit",1),"expire_date":item.get("expire_date"),
            "plan":item.get("plan",""),"can_export":bool(art),"artifact_id":art["id"] if art else None,
            "legacy":not bool(art),"endpoint":saved_endpoint(art)
        })

    protocol_rows=protocol_clients_get(request)
    for item in protocol_rows:
        engine=str(item.get("engine") or "xray").lower()
        if engine not in {"xray","outline"}:
            continue
        kind=engine
        key=str(item["id"])
        art=artifacts.get((kind,key))
        rows.append({
            "id":f"{kind}:{key}","kind":kind,"key":key,"name":item["name"],"protocol":item["protocol"],
            "status":"expired" if item.get("expired") else ("active" if item.get("enabled") else "disabled"),
            "online":item.get("online_ip_count",0) if kind=="xray" else None,"device_limit":item.get("ip_limit",1),
            "quota_bytes":item.get("quota_bytes",0),"used_bytes":item.get("usage",{}).get("total",0),
            "expire_at":item.get("expire_at",0),"can_export":True,
            "artifact_id":art["id"] if art else None,"subscription_id":item.get("subscription_id","") if kind=="xray" else "",
            "legacy":not bool(art),"endpoint":saved_endpoint(art)
        })

    known_wg={a["external_key"] for a in artifacts.values() if a["kind"]=="wireguard"}
    wg_runtime={p["public_key"]:p for p in protocol_ops._wireguard_peer_runtime()}
    for peer in protocol_ops.list_wireguard_peers():
        key=peer["name"]
        art=artifacts.get(("wireguard",key))
        try: wg_meta=json.loads(art["metadata_json"]) if art else {}
        except (ValueError,TypeError): wg_meta={}
        rows.append({
            "id":f"wireguard:{key}","kind":"wireguard","key":key,"name":key,"protocol":"wireguard",
            "status":"active" if peer.get("enabled",True) else "disabled","online":None,"device_limit":1,"can_export":bool(art),
            "artifact_id":art["id"] if art else None,"legacy":not bool(art),
            "public_key":peer.get("public_key",""),"address":peer.get("allowed_ips",""),
            "endpoint":wg_meta.get("endpoint",""),"enabled":peer.get("enabled",True),
            "handshake_age":wg_runtime.get(peer["public_key"],{}).get("handshake_age"),
            "rx":wg_runtime.get(peer["public_key"],{}).get("rx",0),
            "tx":wg_runtime.get(peer["public_key"],{}).get("tx",0)
        })

    known_ovpn={a["external_key"] for a in artifacts.values() if a["kind"]=="openvpn"}
    for client in protocol_ops.list_openvpn_clients():
        key=client["name"]
        art=artifacts.get(("openvpn",key))
        rows.append({
            "id":f"openvpn:{key}","kind":"openvpn","key":key,"name":key,"protocol":"openvpn",
            "status":"active","online":None,"device_limit":1,"can_export":True,
            "artifact_id":art["id"] if art else None,"legacy":not bool(art),
            "endpoint":saved_endpoint(art)
        })

    order={"ssh":0,"xray":1,"outline":2,"wireguard":3,"openvpn":4}
    rows.sort(key=lambda x:(order.get(x["kind"],9),str(x["name"]).lower()))
    return rows


@app.get("/api/access/{kind}/{key}/portal")
def access_portal_link(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    require_local_admin(request)
    artifact,token=_ensure_artifact_public_token(kind,key)
    if not artifact or not token:
        payload,_=_resolve_access_payload(kind,key,request)
        artifact=get_access_artifact_by_key(kind,key)
        if not artifact:
            raise HTTPException(404,"access artifact not available")
        artifact,token=_ensure_artifact_public_token(kind,key)
    return {
        "url":f"{public_origin(request)}/access/{token}",
        "token":token,
        "language":get_setting("language","fa"),
    }



@app.post("/api/access/{kind}/{key}/portal/rotate")
def access_portal_rotate(kind:str,key:str,request:Request):
    actor=require_access_kind(request,kind,True)
    require_local_admin(request)
    artifact=get_access_artifact_by_key(kind,key)
    if not artifact:
        _resolve_access_payload(kind,key,request)
        artifact=get_access_artifact_by_key(kind,key)
    if not artifact:
        raise HTTPException(404,"access artifact not available")
    meta=_artifact_public_meta(artifact)
    token=secrets.token_urlsafe(24)
    meta["public_token"]=token
    upsert_access_artifact(
        artifact["kind"],artifact["external_key"],artifact["display_name"],artifact.get("protocol") or "",
        artifact.get("native_filename") or "",artifact["payload_enc"],
        json.dumps(meta,ensure_ascii=False,separators=(",",":"))
    )
    audit(actor,"access_portal_rotate",f"{kind}:{key}",ip=ip(request))
    return {"url":f"{public_origin(request)}/access/{token}","token":token}


@app.get("/access/{token}",response_class=HTMLResponse)
def public_access_portal(token:str,request:Request):
    artifact=_artifact_by_public_token(token)
    if not artifact:
        raise HTTPException(404,"access link not found")
    kind=str(artifact.get("kind") or "")
    key=str(artifact.get("external_key") or "")
    try:
        payload=access_ops.open_payload(artifact["payload_enc"])
        payload=_current_delivery_payload(kind,key,payload,request)
    except access_ops.AccessPackageError as exc:
        raise HTTPException(404,str(exc))
    state=_public_access_state(kind,key)
    if kind in {"xray","outline"} and not state.get("active"):
        share_text=""
    else:
        share_text=str(payload.get("share_text") or payload.get("primary_text") or "")
    lang=_portal_language(request)
    summary=dict(payload.get("summary") or {})
    files=payload.get("files") or {}
    native_filename=payload.get("native_filename") or ""
    has_native=bool(native_filename and native_filename in files)
    public_files=[]
    for filename,data in files.items():
        safe_name=str(filename)
        if "/" in safe_name or "\\" in safe_name or safe_name.endswith("-qr.svg"):
            continue
        public_files.append({
            "name":safe_name,
            "size":len(data.encode("utf-8") if isinstance(data,str) else bytes(data)),
            "url":f"/access/{token}/files/{urllib.parse.quote(safe_name,safe='')}",
        })
    qr=""
    if share_text and kind in {"xray","wireguard","ssh","outline"}:
        qr="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(share_text)).decode("ascii")
    guide_kind="xray" if kind=="xray" else kind
    protocol=str(artifact.get("protocol") or summary.get("protocol") or kind)
    portal_url=f"{public_origin(request)}/access/{token}"
    response=templates.TemplateResponse("access_portal.html",{
        "request":request,"app_name":APP_NAME,"version":VERSION,
        "lang":lang,"dir":"rtl" if lang=="fa" else "ltr",
        "kind":kind,"key":key,"name":artifact.get("display_name") or key,
        "protocol":protocol,"summary":summary,"state":state,
        "share_text":share_text,"qr":qr,"has_native":has_native,
        "native_filename":native_filename,"public_files":public_files,
        "details_text":str(payload.get("primary_text") or "") if kind=="ssh" else "",
        "portal_url":portal_url,
        "device":_portal_device(request),
        "guide_url":f"{public_origin(request)}/help/connect#{guide_kind}",
        "download_url":f"/access/{token}/download",
        "qr_url":f"/access/{token}/qr.svg" if qr else "",
        "one_tap_url":_portal_one_tap(kind,share_text,f"/access/{token}/download") if state.get("active") else "",
    })
    response.headers["Cache-Control"]="no-store, private"
    response.headers["Pragma"]="no-cache"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["X-Robots-Tag"]="noindex, nofollow, noarchive"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response


@app.get("/access/{token}/download")
def public_access_download(token:str,request:Request):
    artifact=_artifact_by_public_token(token)
    if not artifact:
        raise HTTPException(404,"access link not found")
    kind=str(artifact.get("kind") or "")
    key=str(artifact.get("external_key") or "")
    state=_public_access_state(kind,key)
    if kind in {"xray","outline"} and not state.get("active"):
        raise HTTPException(410,"access is no longer active")
    payload=access_ops.open_payload(artifact["payload_enc"])
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
    safe=access_ops.safe_filename(filename)
    return Response(content=bytes(data),media_type=media,headers={
        "Content-Disposition":f'attachment; filename="{safe}"',
        "Cache-Control":"no-store, private","Pragma":"no-cache",
        "Referrer-Policy":"no-referrer","X-Robots-Tag":"noindex, nofollow, noarchive",
        "X-Content-Type-Options":"nosniff",
    })



@app.get("/access/{token}/files/{filename}")
def public_access_file(token:str,filename:str,request:Request):
    artifact=_artifact_by_public_token(token)
    if not artifact:
        raise HTTPException(404,"access link not found")
    kind=str(artifact.get("kind") or "")
    key=str(artifact.get("external_key") or "")
    state=_public_access_state(kind,key)
    if kind in {"xray","outline"} and not state.get("active"):
        raise HTTPException(410,"access is no longer active")
    payload=access_ops.open_payload(artifact["payload_enc"])
    payload=_current_delivery_payload(kind,key,payload,request)
    files=payload.get("files") or {}
    requested=str(filename or "")
    if "/" in requested or "\\" in requested or requested not in files:
        raise HTTPException(404,"file not found")
    data=files[requested]
    if isinstance(data,str):data=data.encode("utf-8")
    media="application/octet-stream"
    if requested.endswith((".txt",".conf",".json")):media="text/plain; charset=utf-8"
    elif requested.endswith(".ovpn"):media="application/x-openvpn-profile"
    elif requested.endswith(".svg"):media="image/svg+xml"
    return Response(content=bytes(data),media_type=media,headers={
        "Content-Disposition":f'attachment; filename="{access_ops.safe_filename(requested)}"',
        "Cache-Control":"no-store, private","Pragma":"no-cache",
        "Referrer-Policy":"no-referrer","X-Robots-Tag":"noindex, nofollow, noarchive",
        "X-Content-Type-Options":"nosniff",
    })


@app.get("/access/{token}/qr.svg")
def public_access_qr(token:str,request:Request):
    artifact=_artifact_by_public_token(token)
    if not artifact:
        raise HTTPException(404,"access link not found")
    kind=str(artifact.get("kind") or "")
    key=str(artifact.get("external_key") or "")
    state=_public_access_state(kind,key)
    if kind in {"xray","outline"} and not state.get("active"):
        raise HTTPException(410,"access is no longer active")
    payload=access_ops.open_payload(artifact["payload_enc"])
    payload=_current_delivery_payload(kind,key,payload,request)
    if kind not in {"xray","wireguard","ssh","outline"}:
        raise HTTPException(404,"QR is not available for this access type")
    share=str(payload.get("share_text") or payload.get("primary_text") or "")
    if not share:
        raise HTTPException(404,"QR is not available for this access type")
    return Response(content=access_ops.make_qr_svg(share),media_type="image/svg+xml",headers={
        "Cache-Control":"no-store, private","Pragma":"no-cache",
        "Referrer-Policy":"no-referrer","X-Robots-Tag":"noindex, nofollow, noarchive",
        "X-Content-Type-Options":"nosniff",
    })


@app.get("/api/access/{kind}/{key}/share")
def access_share(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    require_local_admin(request)
    if kind not in {"ssh","xray","wireguard","outline"}:
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
    if kind not in {"ssh","xray","wireguard","outline"}:
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
    require_capability(request,"subscriptions")
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

def _delete_outline_managed_client(row):
    """Revoke one Makia-managed Outline credential and then remove local state.

    If the Management API is reachable and the runtime key is already absent,
    local cleanup is still safe. If the API itself is unreachable, keep local
    state so an administrator can retry instead of silently losing the ability
    to revoke a still-live credential later.
    """
    if not row or row.get("engine")!="outline":
        raise HTTPException(404,"Outline client not found")
    client_id=int(row.get("id") or 0)
    outline_key_id=str(row.get("inbound_tag") or "").strip()
    if not outline_key_id:
        raise HTTPException(409,"Outline runtime key id is missing")
    try:
        runtime_keys=integration_ops.outline_list_keys()
    except integration_ops.IntegrationError as exc:
        raise HTTPException(400,str(exc))
    runtime_present=any(str(item.get("id") or "")==outline_key_id for item in runtime_keys)
    if runtime_present:
        try:
            integration_ops.outline_delete_key(outline_key_id)
        except integration_ops.IntegrationError as exc:
            raise HTTPException(400,str(exc))
    delete_access_artifact_by_key("outline",str(client_id))
    delete_protocol_client(client_id)
    return {"ok":True,"client_id":client_id,"outline_key_id":outline_key_id,"runtime_removed":runtime_present}


@app.delete("/api/access/{kind}/{key}")
def access_revoke(kind:str,key:str,request:Request):
    actor=require_access_kind(request,kind,True)
    result={"ok":True}
    try:
        if kind=="ssh":
            system_ops.delete_user(key); delete_profile(key); delete_access_artifact_by_key("ssh",key)
        elif kind=="xray":
            row=get_protocol_client(int(key))
            if not row or row.get("engine")!="xray": raise HTTPException(404,"Xray client not found")
            siblings=[
                item for item in list_protocol_clients()
                if item.get("engine")=="xray"
                and item.get("inbound_tag")==row.get("inbound_tag")
                and int(item.get("id") or 0)!=int(key)
            ]
            if siblings:
                protocol_ops.remove_xray_client_from_inbound(row["inbound_tag"],row["name"])
            else:
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
        elif kind=="outline":
            try: row=get_protocol_client(int(key))
            except Exception: row=None
            result=_delete_outline_managed_client(row)
        else:
            raise HTTPException(404,"unsupported access kind")
    except (system_ops.OperationError,protocol_ops.ProtocolError) as e:
        raise HTTPException(400,str(e))
    audit(actor,"access_revoke",f"{kind}:{key}",ip=ip(request))
    return result

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
    try: result=system_ops.create_backup(str(DATA_DIR),VERSION)
    except system_ops.OperationError as e: raise HTTPException(400,str(e))
    audit(actor,"backup_create",result["name"],ip=ip(request))
    return result

@app.get("/api/backups/migration-readiness")
def backup_migration_readiness(request:Request):
    require_local_admin(request)
    domain=(get_setting("panel_domain","") or "").strip()
    domain_based=0
    ip_based=0
    unknown=0
    examples=[]
    for artifact in list_access_artifacts():
        endpoint=""
        try:
            endpoint=str(json.loads(artifact.get("metadata_json") or "{}").get("endpoint") or "").strip()
        except Exception:
            endpoint=""
        if not endpoint:
            unknown+=1
            continue
        host=endpoint.strip("[]")
        try:
            ipaddress.ip_address(host)
            ip_based+=1
            if len(examples)<5:
                examples.append({"kind":artifact.get("kind"),"name":artifact.get("name"),"endpoint":endpoint})
        except ValueError:
            domain_based+=1
    return {
        "panel_domain":domain,
        "domain_configured":bool(domain),
        "domain_based":domain_based,
        "ip_based":ip_based,
        "unknown":unknown,
        "ip_examples":examples,
        "same_config_cutover_ready":bool(domain and ip_based==0),
        "cloudflare_note":"VPN/SSH records that carry raw traffic must be DNS only; Cloudflare orange-cloud proxy does not proxy raw WireGuard/OpenVPN/SSH.",
        "restore_command":"sudo makia-restore-portable /root/makia-full-migration.zip --apply",
    }

class PortableBackupRequest(BaseModel):
    password:str=Field(min_length=10,max_length=128)

class MigrationRestoreApply(BaseModel):
    password:str=Field(min_length=10,max_length=128)

@app.post("/api/backups/portable")
def backup_portable(payload:PortableBackupRequest,request:Request):
    require_local_admin(request)
    actor=require_capability(request,"portable_migration",True)
    try:
        files=system_ops.portable_migration_files(
            str(DATA_DIR),
            list(all_profiles().keys()),
            panel_domain=get_setting("panel_domain",""),
            version=VERSION,
        )
        blob=access_ops.protected_zip(files,payload.password)
        access_ops.verify_protected_zip(blob,payload.password,"manifest.json")
        manifest=json.loads(files["manifest.json"].decode("utf-8"))
        saved=system_ops.save_full_migration_backup(blob,VERSION,manifest)
    except (system_ops.OperationError,access_ops.AccessPackageError,OSError,ValueError) as e:
        raise HTTPException(400,str(e))
    filename=saved["name"]
    audit(actor,"full_migration_backup_export",filename,f"files={len(files)}; sha256={saved['sha256']}",ip(request))
    return Response(content=blob,media_type="application/zip",headers={
        "Content-Disposition":f'attachment; filename="{filename}"',
        "Cache-Control":"no-store, private",
        "X-Content-Type-Options":"nosniff",
        "X-Makia-Backup-SHA256":saved["sha256"],
    })

@app.get("/api/backups/{name}/download")
def backup_download(name:str,request:Request):
    actor=require_local_admin(request)
    try:
        path=system_ops.backup_download_path(name)
    except system_ops.OperationError as e:
        raise HTTPException(404,str(e))
    if not path.name.endswith(".zip"):
        raise HTTPException(409,"Quick Backup is host-local only. Build a password-protected Full Migration Backup for download.")
    audit(actor,"backup_download",name,ip=ip(request))
    media="application/zip"
    return FileResponse(
        path,media_type=media,filename=path.name,
        headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"},
    )


@app.post("/api/backups/restore/verify")
async def backup_restore_verify(request:Request,bundle:UploadFile=File(...),password:str=Form(...)):
    actor=require_local_admin(request)
    require_mutation(request)
    if len(password)<10:
        raise HTTPException(400,"Migration password must be at least 10 characters")
    max_bytes=512*1024*1024
    blob=await bundle.read(max_bytes+1)
    if len(blob)>max_bytes:
        raise HTTPException(413,"Migration bundle exceeds the 512 MiB upload limit")
    try:
        result=system_ops.stage_migration_restore(blob,password,VERSION)
    except system_ops.OperationError as e:
        audit(actor,"migration_restore_verify_failed",bundle.filename or "upload",str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"migration_restore_verified",result["job_id"],f"sha256={result['sha256']}",ip=ip(request))
    result["cutover_instruction"]=(
        f"Cloudflare A record: {result['panel_domain']} → NEW_VPS_IP"
        if result.get("panel_domain") else
        "Configure a stable domain before cutover if unchanged client configs are required."
    )
    return result


@app.post("/api/backups/restore/{job_id}/apply")
def backup_restore_apply(job_id:str,payload:MigrationRestoreApply,request:Request):
    actor=require_local_admin(request)
    require_mutation(request)
    try:
        status=system_ops.migration_restore_status(job_id)
    except system_ops.OperationError as e:
        raise HTTPException(404,str(e))
    if status.get("state") not in {"verified","failed"}:
        raise HTTPException(409,f"Restore job is already {status.get('state')}")
    unit=f"makia-migration-restore@{job_id}.service"
    try:
        system_ops.arm_migration_restore(job_id,payload.password,VERSION)
        system_ops._run(["systemctl","start","--no-block",unit],timeout=15)
    except system_ops.OperationError as e:
        system_ops.discard_migration_restore_password(job_id)
        audit(actor,"migration_restore_start_failed",job_id,str(e)[:500],ip=ip(request))
        raise HTTPException(400,str(e))
    audit(actor,"migration_restore_started",job_id,ip=ip(request))
    return {
        "ok":True,"job_id":job_id,"state":"starting",
        "note":"Restore runs in a separate root systemd unit so the job survives the Makia service restart.",
    }


@app.get("/api/backups/restore/{job_id}/status")
def backup_restore_status(job_id:str,request:Request):
    require_local_admin(request)
    try:
        status=system_ops.migration_restore_status(job_id)
    except system_ops.OperationError as e:
        raise HTTPException(404,str(e))
    domain=str(status.get("panel_domain") or "")
    if domain:
        status["cutover_instruction"]=f"Cloudflare A record: {domain} → NEW_VPS_IP"
        resolved=[]
        try:
            resolved=sorted({
                item[4][0] for item in socket.getaddrinfo(domain,443,socket.AF_INET,socket.SOCK_STREAM)
                if item and item[4]
            })
        except OSError:
            resolved=[]
        local=sorted(set(protocol_ops._local_ipv4_candidates()))
        status["dns_propagation"]={
            "resolved_ipv4":resolved,
            "vps_ipv4":local,
            "points_to_this_vps":bool(set(resolved)&set(local)),
            "note":"For raw VPN/SSH transports the Cloudflare record must be DNS only.",
        }
    status["ip_based_warning"]="Profiles containing the old literal VPS IP cannot be preserved by DNS cutover and must be re-exported."
    return status



class OutlineInstallPayload(BaseModel):
    hostname:str=Field(default="",max_length=255)
    keys_port:int=Field(default=0,ge=0,le=65535)

class OutlineKeyCreate(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    quota_gb:float=Field(default=0,ge=0,le=100000)
    expire_days:int=Field(default=0,ge=0,le=3650)

@app.get("/api/protocols/outline/status")
def outline_status_get(request:Request):
    require_capability(request,"outline")
    return integration_ops.outline_status()

@app.post("/api/protocols/outline/install")
def outline_install(payload:OutlineInstallPayload,request:Request):
    """Return the root setup command; package installation never runs inside the hardened web service."""
    actor=require_local_admin(request)
    require_mutation(request)
    try:
        command=integration_ops.outline_install_command(payload.hostname,payload.keys_port)
    except integration_ops.IntegrationError as exc:
        raise HTTPException(400,str(exc))
    status=integration_ops.outline_status()
    if status.get("api_ok"):
        return {"ok":True,"already_ready":True,"status":status,"command":""}
    audit(actor,"outline_install_command","outline",f"keys_port={payload.keys_port}",ip(request))
    docker_ready=bool(status.get("docker"))
    return {
        "ok":False,"already_ready":False,"requires_root":True,
        "requires_dependency":not docker_ready,
        "dependency_command":"sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade" if not docker_ready else "",
        "command":command,
        "note":"Run the host preparation command first when Docker is missing, then run the pinned Outline installer command. Makia intentionally does not run APT/Docker installers inside the hardened web service.",
        "status":status,
    }

@app.get("/api/protocols/outline/keys")
def outline_keys_get(request:Request):
    require_capability(request,"outline")
    try:
        keys=integration_ops.outline_list_keys()
    except integration_ops.IntegrationError as exc:
        raise HTTPException(400,str(exc))
    try:metrics=integration_ops.outline_transfer_metrics()
    except integration_ops.IntegrationError:metrics={}
    managed={str(row.get("inbound_tag") or ""):row for row in list_protocol_clients() if row.get("engine")=="outline"}
    rows=[]
    for item in keys:
        key_id=str(item.get("id") or "")
        row=managed.get(key_id)
        enriched={**item,"usage_bytes":int(metrics.get(key_id,0) or 0),"managed":row}
        if row:
            enriched["quota_bytes"]=int(row.get("quota_bytes") or 0)
            enriched["expire_at"]=int(row.get("expire_at") or 0)
            enriched["enabled"]=bool(row.get("enabled"))
        rows.append(enriched)
    return rows

@app.post("/api/protocols/outline/keys")
def outline_key_create(payload:OutlineKeyCreate,request:Request):
    actor=require_capability(request,"outline",True)
    quota_bytes=int(payload.quota_gb*1024*1024*1024)
    expire_at=int(time.time()+payload.expire_days*86400) if payload.expire_days else 0
    created=None
    client_id=None
    try:
        created=integration_ops.outline_create_key(payload.name,quota_bytes)
        key_id=str(created.get("id") or "")
        access_url=str(created.get("accessUrl") or "")
        client_id=create_protocol_client(
            payload.name,"outline","outline",key_id,key_id,access_url,
            quota_bytes,expire_at,1,0
        )
        delivery=access_ops.outline_payload(payload.name,access_url,key_id,quota_bytes)
        artifact_id=artifact_save("outline",str(client_id),payload.name,"outline",delivery,{
            "client_id":client_id,"outline_key_id":key_id,"quota_bytes":quota_bytes
        })
    except (integration_ops.IntegrationError,Exception) as exc:
        if created and created.get("id"):
            try:integration_ops.outline_delete_key(created["id"])
            except Exception:pass
        if client_id:
            try:delete_protocol_client(client_id)
            except Exception:pass
        if isinstance(exc,HTTPException):raise
        raise HTTPException(400,str(exc))
    audit(actor,"outline_key_create",str(created.get("id") or ""),f"name={payload.name}; quota={quota_bytes}; expire_at={expire_at}",ip(request))
    qr="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(created["accessUrl"])).decode("ascii")
    return {
        "id":created.get("id"),"name":payload.name,"access_url":created.get("accessUrl"),
        "client_id":client_id,"artifact_id":artifact_id,"quota_bytes":quota_bytes,
        "expire_at":expire_at,"qr":qr
    }

@app.delete("/api/protocols/outline/keys/{key_id}")
def outline_key_delete(key_id:str,request:Request):
    actor=require_capability(request,"outline",True)
    row=next((x for x in list_protocol_clients() if x.get("engine")=="outline" and str(x.get("inbound_tag"))==str(key_id)),None)
    if row:
        result=_delete_outline_managed_client(row)
    else:
        try:
            result=integration_ops.outline_delete_key(key_id)
        except integration_ops.IntegrationError as exc:
            raise HTTPException(400,str(exc))
    audit(actor,"outline_key_delete",key_id,ip=ip(request))
    return result


class OutlineQuotaUpdate(BaseModel):
    quota_gb:float=Field(default=0,ge=0,le=100000)


def _outline_reissue_managed_client(row,quota_bytes=None):
    if not row or row.get("engine")!="outline":
        raise RuntimeError("Outline client not found")
    quota=int(row.get("quota_bytes") or 0) if quota_bytes is None else max(0,int(quota_bytes))
    old_id=str(row.get("inbound_tag") or "")
    old_credential=str(row.get("credential") or "")
    old_share=str(row.get("share_link") or "")
    created=None
    try:
        created=integration_ops.outline_create_key(row["name"],quota)
        new_id=str(created.get("id") or "")
        access_url=str(created.get("accessUrl") or "")
        if not new_id or not access_url.startswith("ss://"):
            raise RuntimeError("Outline did not return a valid replacement access key")
        replace_protocol_client_identity(row["id"],new_id,new_id,access_url)
        update_protocol_client_state(row["id"],True,quota,int(row.get("expire_at") or 0),None,None)
        delivery=access_ops.outline_payload(row["name"],access_url,new_id,quota)
        artifact_save("outline",str(row["id"]),row["name"],"outline",delivery,{
            "client_id":row["id"],"outline_key_id":new_id,"quota_bytes":quota
        })
    except Exception:
        if created and created.get("id"):
            try:integration_ops.outline_delete_key(created["id"])
            except Exception:pass
        try:
            replace_protocol_client_identity(row["id"],old_id,old_credential,old_share)
            update_protocol_client_state(
                row["id"],bool(row.get("enabled")),int(row.get("quota_bytes") or 0),
                int(row.get("expire_at") or 0),None,None
            )
        except Exception:pass
        raise
    cleanup_error=""
    if old_id and old_id!=new_id and bool(row.get("enabled")):
        try:integration_ops.outline_delete_key(old_id)
        except Exception as exc:cleanup_error=str(exc)[:200]
    return {
        "client_id":row["id"],"outline_key_id":new_id,"access_url":access_url,
        "quota_bytes":quota,"cleanup_warning":cleanup_error,
    }


@app.post("/api/protocols/outline/clients/{client_id}/reissue")
def outline_client_reissue(client_id:int,request:Request):
    actor=require_capability(request,"outline",True)
    row=get_protocol_client(client_id)
    if not row or row.get("engine")!="outline":
        raise HTTPException(404,"Outline client not found")
    try:result=_outline_reissue_managed_client(row)
    except Exception as exc:raise HTTPException(400,str(exc))
    audit(actor,"outline_key_reissue",str(client_id),f"outline_key_id={result['outline_key_id']}",ip(request))
    return result


@app.put("/api/protocols/outline/clients/{client_id}/quota")
def outline_client_quota(client_id:int,payload:OutlineQuotaUpdate,request:Request):
    actor=require_capability(request,"outline",True)
    row=get_protocol_client(client_id)
    if not row or row.get("engine")!="outline":
        raise HTTPException(404,"Outline client not found")
    quota_bytes=int(payload.quota_gb*1024*1024*1024)
    if bool(row.get("enabled")):
        try:integration_ops.outline_set_limit(str(row.get("inbound_tag") or ""),quota_bytes)
        except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
    update_protocol_client_state(client_id,None,quota_bytes,None,None,None)
    artifact=get_access_artifact_by_key("outline",str(client_id))
    if artifact:
        try:
            current=access_ops.open_payload(artifact["payload_enc"])
            access_url=str(current.get("share_text") or current.get("primary_text") or row.get("share_link") or "")
            delivery=access_ops.outline_payload(row["name"],access_url,str(row.get("inbound_tag") or ""),quota_bytes)
            artifact_save("outline",str(client_id),row["name"],"outline",delivery,{
                "client_id":client_id,"outline_key_id":str(row.get("inbound_tag") or ""),"quota_bytes":quota_bytes
            })
        except Exception:pass
    audit(actor,"outline_quota_update",str(client_id),f"quota_bytes={quota_bytes}",ip(request))
    return {"ok":True,"client_id":client_id,"quota_bytes":quota_bytes}


class ManagedBulkItem(BaseModel):
    kind:str
    key:str

class ManagedBulkAction(BaseModel):
    items:list[ManagedBulkItem]=Field(min_length=1,max_length=200)
    action:str
    days:int=Field(default=0,ge=0,le=3650)
    quota_add_gb:float=Field(default=0,ge=0,le=100000)

def _renew_managed_item(kind,key,days,quota_add_gb,actor,request):
    now_ts=int(time.time())
    if kind=="ssh":
        profile=all_profiles().get(key)
        if not profile:
            raise RuntimeError("SSH profile not found")
        base=date.today()
        raw=profile.get("expire_date")
        if raw:
            try:
                d=date.fromisoformat(str(raw))
                if d>base:base=d
            except Exception:pass
        expire=(base+timedelta(days=max(1,days))).isoformat()
        system_ops.update_ssh_user(key,expire=expire)
        upsert_profile(
            key,profile.get("plan",""),profile.get("note",""),expire,
            profile.get("connection_limit",1),profile.get("quota_mb",0),1,
            profile.get("device_limit",1),profile.get("renewal_days",0)
        )
        try:system_ops.lock_user(key,False)
        except Exception:pass
        return {"kind":kind,"key":key,"expire_date":expire}
    if kind in {"xray","outline"}:
        try:row=get_protocol_client(int(key))
        except Exception:row=None
        if not row or row.get("engine")!=kind:
            raise RuntimeError(f"{kind} client not found")
        base=max(now_ts,int(row.get("expire_at") or 0))
        expire_at=base+max(1,days)*86400
        quota=int(row.get("quota_bytes") or 0)+int(float(quota_add_gb or 0)*1024*1024*1024)
        if kind=="xray":
            if not row.get("enabled"):
                protocol_ops.enable_xray_client(row["inbound_tag"],row["name"],row["protocol"],row["credential"])
            update_protocol_client_state(row["id"],True,quota,expire_at,None,None)
        else:
            key_id=str(row.get("inbound_tag") or "")
            if row.get("enabled"):
                integration_ops.outline_set_limit(key_id,quota)
                update_protocol_client_state(row["id"],True,quota,expire_at,None,None)
            else:
                # Expired/revoked Outline access has no pause state. Renewal rotates
                # the runtime credential and keeps the same Makia managed-client identity.
                result=_outline_reissue_managed_client(row,quota)
                key_id=result["outline_key_id"]
                update_protocol_client_state(row["id"],True,quota,expire_at,None,None)
            return {"kind":kind,"key":key,"expire_at":expire_at,"quota_bytes":quota,"outline_key_id":key_id}
        return {"kind":kind,"key":key,"expire_at":expire_at,"quota_bytes":quota}
    raise RuntimeError("renew is not enforceable for this access type")

@app.post("/api/access/bulk")
def managed_bulk_action(payload:ManagedBulkAction,request:Request):
    actor=require_mutation(request)
    if payload.action not in {"renew","enable","disable"}:
        raise HTTPException(400,"unsupported bulk action")
    if payload.action=="renew" and payload.days<1:
        raise HTTPException(400,"renewal days must be at least 1")
    done=[];failed=[]
    for item in payload.items:
        kind=str(item.kind or "").lower()
        key=str(item.key or "")
        try:
            if payload.action=="renew":
                result=_renew_managed_item(kind,key,payload.days,payload.quota_add_gb,actor,request)
            elif kind=="ssh":
                system_ops.lock_user(key,payload.action=="disable")
                p=all_profiles().get(key,{})
                upsert_profile(key,p.get("plan",""),p.get("note",""),p.get("expire_date"),p.get("connection_limit",1),p.get("quota_mb",0),1 if payload.action=="enable" else 0,p.get("device_limit",1),p.get("renewal_days",0))
                result={"kind":kind,"key":key}
            elif kind=="xray":
                row=get_protocol_client(int(key))
                if not row:raise RuntimeError("client not found")
                if payload.action=="enable":
                    protocol_ops.enable_xray_client(row["inbound_tag"],row["name"],row["protocol"],row["credential"])
                else:
                    protocol_ops.disable_xray_client(row["inbound_tag"],row["name"])
                update_protocol_client_state(row["id"],payload.action=="enable",None,None,None,None)
                result={"kind":kind,"key":key}
            elif kind=="outline":
                row=get_protocol_client(int(key))
                if not row or row.get("engine")!="outline":raise RuntimeError("client not found")
                if payload.action=="disable":
                    integration_ops.outline_delete_key(row["inbound_tag"])
                    update_protocol_client_state(row["id"],False,None,None,None,None)
                else:
                    raise RuntimeError("disabled Outline keys must be renewed/reissued")
                result={"kind":kind,"key":key}
            else:
                raise RuntimeError("bulk enable/disable is not supported for this access type")
            done.append(result)
        except Exception as exc:
            failed.append({"kind":kind,"key":key,"error":str(exc)[:200]})
    audit(actor,f"access_bulk_{payload.action}",str(len(done)),f"failed={len(failed)}; days={payload.days}; quota_add_gb={payload.quota_add_gb}",ip(request))
    return {"done":done,"failed":failed}


def _expiry_snapshot(days=30):
    horizon=max(0,min(int(days),3650))
    today=date.today()
    now_ts=int(time.time())
    rows=[]
    for username,p in all_profiles().items():
        raw=p.get("expire_date")
        if not raw:continue
        try:d=date.fromisoformat(str(raw))
        except Exception:continue
        left=(d-today).days
        if left<=horizon:
            rows.append({"kind":"ssh","key":username,"name":username,"protocol":"ssh","days_left":left,"expire_date":str(raw),"expired":left<0,"renew_supported":True})
    for row in list_protocol_clients():
        expire_at=int(row.get("expire_at") or 0)
        if not expire_at:continue
        left=(expire_at-now_ts)//86400
        if left<=horizon:
            rows.append({
                "kind":row.get("engine"),"key":str(row.get("id")),"name":row.get("name"),"protocol":row.get("protocol"),
                "days_left":left,"expire_at":expire_at,"expired":expire_at<now_ts,"renew_supported":row.get("engine") in {"xray","outline"},
                "enabled":bool(row.get("enabled"))
            })
    rows.sort(key=lambda x:x.get("days_left",999999))
    return {"days":horizon,"count":len(rows),"expired":sum(1 for x in rows if x.get("expired")),"rows":rows}

@app.get("/api/expiry")
def expiry_center(request:Request,days:int=30):
    require_user(request)
    return _expiry_snapshot(days)


@app.get("/api/notifications")
def notifications_get(request:Request):
    require_user(request)
    events=list_notification_events(100)
    expiry=_expiry_snapshot(7)
    stale=[]
    now=time.time()
    for node in list_nodes():
        seen=node.get("last_seen_at")
        age=None
        if seen:
            try:age=max(0,int(now-datetime.fromisoformat(str(seen)).timestamp()))
            except Exception:age=None
        if node.get("active") and (age is None or age>180):
            stale.append({"id":node.get("id"),"name":node.get("name"),"age":age})
    return {
        "events":events,
        "summary":{"expiring_7d":expiry["count"],"expired":expiry["expired"],"nodes_offline":len(stale)},
        "nodes_offline":stale,
    }


@app.get("/api/diagnostics/access/{kind}/{key}")
def access_diagnostics(kind:str,key:str,request:Request):
    require_access_kind(request,kind)
    checks=[]
    def add(name,ok,detail=""):
        checks.append({"name":name,"ok":bool(ok),"detail":str(detail or "")[:500]})
    artifact=get_access_artifact_by_key(kind,key)
    add("artifact",bool(artifact),"encrypted delivery artifact available" if artifact else "delivery artifact missing")
    payload=None
    if artifact:
        try:
            payload=access_ops.open_payload(artifact["payload_enc"])
            add("artifact_decrypt",True,"payload decrypt PASS")
        except Exception as exc:add("artifact_decrypt",False,exc)
    state=_public_access_state(kind,key)
    add("policy_active",state.get("active"),state.get("reason"))
    if payload:
        files=payload.get("files") or {}
        add("native_file",bool(payload.get("native_filename") in files),payload.get("native_filename") or "none")
        share=str(payload.get("share_text") or "")
        add("share_payload",bool(share) if kind in {"xray","wireguard","ssh","outline"} else True,"available" if share else "not applicable")
    endpoint=""
    meta=_artifact_public_meta(artifact) if artifact else {}
    endpoint=str(meta.get("endpoint") or "")
    if endpoint:
        try:
            resolved=sorted({x[4][0] for x in socket.getaddrinfo(endpoint,None,socket.AF_INET)})
            add("endpoint_dns",bool(resolved),", ".join(resolved))
        except Exception as exc:add("endpoint_dns",False,exc)
    if kind=="xray":
        try:
            row=get_protocol_client(int(key))
            diag=protocol_ops.xray_diagnostics()
            add("xray_service",bool(diag.get("service_active")),diag.get("journal") or "")
            if row:
                config=protocol_ops.read_xray_config()
                inbound=next((x for x in config.get("inbounds",[]) if x.get("tag")==row.get("inbound_tag")),None)
                add("inbound",bool(inbound),row.get("inbound_tag"))
                if inbound:add("listener",protocol_ops._listener_present(int(inbound.get("port") or 0),"udp" if (inbound.get("streamSettings") or {}).get("method") in {"mkcp","hysteria"} else "tcp"),str(inbound.get("port")))
        except Exception as exc:add("xray_runtime",False,exc)
    elif kind=="wireguard":
        try:
            d=protocol_ops.wireguard_endpoint_diagnostics(endpoint or public_host(request))
            add("wireguard_runtime",bool(d.get("runtime_ok")),"; ".join(d.get("warnings") or []))
        except Exception as exc:add("wireguard_runtime",False,exc)
    elif kind=="openvpn":
        try:
            d=protocol_ops.openvpn_endpoint_diagnostics(endpoint or public_host(request))
            add("openvpn_runtime",bool(d.get("service_active") and d.get("listener")),"; ".join(d.get("warnings") or []))
        except Exception as exc:add("openvpn_runtime",False,exc)
    elif kind=="outline":
        try:
            d=integration_ops.outline_status()
            add("outline_api",bool(d.get("api_ok")),d.get("error") or f"{d.get('key_count',0)} keys")
        except Exception as exc:add("outline_api",False,exc)
    return {"kind":kind,"key":key,"ok":all(x["ok"] for x in checks),"checks":checks,"state":state}



class BackupSchedulePayload(BaseModel):
    enabled:bool=True
    frequency_hours:int=Field(default=24,ge=1,le=168)
    keep_local:int=Field(default=7,ge=1,le=50)
    password:str=Field(default="",max_length=128)
    remote_enabled:bool=False
    remote_host:str=Field(default="",max_length=255)
    remote_user:str=Field(default="",max_length=32)
    remote_path:str=Field(default="/var/backups/makia",max_length=240)
    remote_port:int=Field(default=22,ge=1,le=65535)
    remote_key_path:str=Field(default="",max_length=240)

def _backup_schedule_snapshot():
    try:cfg=json.loads(get_setting("backup_schedule_json","{}") or "{}")
    except Exception:cfg={}
    try:status=json.loads(get_setting("backup_schedule_status","{}") or "{}")
    except Exception:status={}
    return {
        "enabled":bool(cfg.get("enabled",False)),
        "frequency_hours":int(cfg.get("frequency_hours") or 24),
        "keep_local":int(cfg.get("keep_local") or 7),
        "remote":cfg.get("remote") or {},
        "has_password":bool(get_setting("backup_schedule_secret","")),
        "last_run":int(get_setting("backup_schedule_last_run","0") or 0),
        "status":status,
    }

@app.get("/api/backups/schedule")
def backup_schedule_get(request:Request):
    require_local_admin(request)
    return _backup_schedule_snapshot()

@app.put("/api/backups/schedule")
def backup_schedule_put(payload:BackupSchedulePayload,request:Request):
    actor=require_local_admin(request);require_mutation(request)
    if payload.enabled and not payload.password and not get_setting("backup_schedule_secret",""):
        raise HTTPException(400,"set a Full Migration backup password before enabling scheduled backups")
    remote={
        "enabled":bool(payload.remote_enabled),
        "host":payload.remote_host.strip(),
        "user":payload.remote_user.strip(),
        "path":payload.remote_path.strip(),
        "port":payload.remote_port,
        "key_path":payload.remote_key_path.strip(),
    }
    if remote["enabled"]:
        # Validate without transmitting a file.
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,255}",remote["host"]):
            raise HTTPException(400,"invalid remote backup host")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}",remote["user"]):
            raise HTTPException(400,"invalid remote backup user")
        if remote["key_path"] and not Path(remote["key_path"]).is_file():
            raise HTTPException(400,"remote backup SSH key does not exist")
    cfg={"enabled":payload.enabled,"frequency_hours":payload.frequency_hours,"keep_local":payload.keep_local,"remote":remote}
    set_setting("backup_schedule_json",json.dumps(cfg,ensure_ascii=False,separators=(",",":")))
    if payload.password:
        if len(payload.password)<10:raise HTTPException(400,"backup password must be at least 10 characters")
        set_setting("backup_schedule_secret",integration_ops.seal_secret({"password":payload.password}))
    audit(actor,"backup_schedule_update","scheduler",f"enabled={payload.enabled}; remote={payload.remote_enabled}",ip(request))
    return _backup_schedule_snapshot()

@app.post("/api/backups/schedule/run")
def backup_schedule_run(request:Request):
    actor=require_local_admin(request);require_mutation(request)
    try:
        from . import scheduled_backup
        result=scheduled_backup.run_once(True)
    except Exception as exc:
        raise HTTPException(400,str(exc))
    audit(actor,"backup_schedule_run",result.get("name","manual"),ip=ip(request))
    return result


class CloudflareIntegrationPayload(BaseModel):
    api_token:str=Field(default="",max_length=256)
    zone_id:str=Field(default="",max_length=80)
    record_name:str=Field(default="",max_length=253)
    ttl:int=Field(default=60,ge=60,le=86400)

class CloudflareCutoverPayload(BaseModel):
    ipv4:str=Field(min_length=7,max_length=64)

def _cloudflare_snapshot():
    return {
        "configured":bool(get_setting("cloudflare_secret","") and get_setting("cloudflare_zone_id","") and get_setting("cloudflare_record_name","")),
        "zone_id":get_setting("cloudflare_zone_id",""),
        "record_name":get_setting("cloudflare_record_name",""),
        "ttl":_setting_int("cloudflare_ttl",60,60,86400),
    }

@app.get("/api/integrations/cloudflare")
def cloudflare_get(request:Request):
    require_local_admin(request)
    return _cloudflare_snapshot()

@app.put("/api/integrations/cloudflare")
def cloudflare_put(payload:CloudflareIntegrationPayload,request:Request):
    actor=require_local_admin(request);require_mutation(request)
    zone=payload.zone_id.strip();name=payload.record_name.strip().lower().rstrip(".")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,80}",zone):raise HTTPException(400,"invalid Cloudflare zone id")
    if not name or "." not in name:raise HTTPException(400,"invalid Cloudflare A-record name")
    if payload.api_token:
        if len(payload.api_token)<20:raise HTTPException(400,"invalid Cloudflare API token")
        set_setting("cloudflare_secret",integration_ops.seal_secret({"api_token":payload.api_token.strip()}))
    elif not get_setting("cloudflare_secret",""):
        raise HTTPException(400,"Cloudflare API token is required")
    set_setting("cloudflare_zone_id",zone);set_setting("cloudflare_record_name",name);set_setting("cloudflare_ttl",payload.ttl)
    audit(actor,"cloudflare_settings_update",name,ip=ip(request))
    return _cloudflare_snapshot()

def _cloudflare_token():
    secret=get_setting("cloudflare_secret","")
    if not secret:return ""
    try:return str(integration_ops.open_secret(secret).get("api_token") or "")
    except Exception:return ""

@app.post("/api/integrations/cloudflare/test")
def cloudflare_test(request:Request):
    require_local_admin(request);require_mutation(request)
    cfg=_cloudflare_snapshot()
    try:record=integration_ops.cloudflare_record(_cloudflare_token(),cfg["zone_id"],cfg["record_name"])
    except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
    return {"ok":True,"record":record,"dns_only":None if not record else not bool(record.get("proxied"))}

@app.post("/api/integrations/cloudflare/cutover")
def cloudflare_cutover(payload:CloudflareCutoverPayload,request:Request):
    actor=require_local_admin(request);require_mutation(request)
    cfg=_cloudflare_snapshot()
    if not cfg["configured"]:raise HTTPException(409,"Cloudflare integration is not configured")
    try:
        result=integration_ops.cloudflare_update_a(_cloudflare_token(),cfg["zone_id"],cfg["record_name"],payload.ipv4,cfg["ttl"])
    except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
    audit(actor,"cloudflare_dns_cutover",cfg["record_name"],f"ipv4={payload.ipv4}; dns_only=true",ip(request))
    resolved=[]
    try:resolved=sorted({x[4][0] for x in socket.getaddrinfo(cfg["record_name"],443,socket.AF_INET,socket.SOCK_STREAM)})
    except OSError:pass
    return {"ok":True,"record":result,"resolved_ipv4":resolved,"propagated":payload.ipv4 in resolved}


class TelegramIntegrationPayload(BaseModel):
    bot_token:str=Field(default="",max_length=256)
    chat_id:str=Field(default="",max_length=40)
    enable_webhook:bool=False

def _telegram_snapshot():
    return {
        "configured":bool(get_setting("telegram_secret","") and get_setting("telegram_chat_id","")),
        "chat_id":get_setting("telegram_chat_id",""),
        "webhook_enabled":_setting_bool("telegram_webhook_enabled",False),
    }

def _telegram_token():
    raw=get_setting("telegram_secret","")
    if not raw:return ""
    try:return str(integration_ops.open_secret(raw).get("bot_token") or "")
    except Exception:return ""

@app.get("/api/integrations/telegram")
def telegram_get(request:Request):
    require_local_admin(request)
    return _telegram_snapshot()

@app.put("/api/integrations/telegram")
def telegram_put(payload:TelegramIntegrationPayload,request:Request):
    actor=require_local_admin(request);require_mutation(request)
    chat=payload.chat_id.strip()
    if not re.fullmatch(r"-?\d{5,30}",chat):raise HTTPException(400,"invalid Telegram chat id")
    if payload.bot_token:
        token=payload.bot_token.strip()
        if not re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}",token):
            raise HTTPException(400,"invalid Telegram bot token")
        set_setting("telegram_secret",integration_ops.seal_secret({"bot_token":token}))
    elif not get_setting("telegram_secret",""):
        raise HTTPException(400,"Telegram bot token is required")
    set_setting("telegram_chat_id",chat)
    if payload.enable_webhook:
        domain=(get_setting("panel_domain","") or "").strip()
        if not domain:raise HTTPException(409,"HTTPS panel domain is required for Telegram webhook")
        secret=get_setting("telegram_webhook_secret","") or secrets.token_urlsafe(32)
        set_setting("telegram_webhook_secret",secret)
        try:integration_ops.telegram_set_webhook(_telegram_token(),f"https://{domain}/integrations/telegram/webhook",secret)
        except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
        set_setting("telegram_webhook_enabled","1")
    elif _setting_bool("telegram_webhook_enabled",False):
        try:integration_ops.telegram_delete_webhook(_telegram_token())
        except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
        set_setting("telegram_webhook_enabled","0")
    audit(actor,"telegram_settings_update","telegram",f"webhook={payload.enable_webhook}",ip(request))
    return _telegram_snapshot()

@app.post("/api/integrations/telegram/test")
def telegram_test(request:Request):
    require_local_admin(request);require_mutation(request)
    try:result=integration_ops.telegram_send(_telegram_token(),get_setting("telegram_chat_id",""),f"✅ Makia {VERSION}\nTelegram integration is working.")
    except integration_ops.IntegrationError as exc:raise HTTPException(400,str(exc))
    return {"ok":True,"message_id":result.get("message_id")}

@app.post("/integrations/telegram/webhook")
async def telegram_webhook(request:Request):
    secret=str(get_setting("telegram_webhook_secret","") or "")
    received=str(request.headers.get("x-telegram-bot-api-secret-token") or "")
    if not secret or not secrets.compare_digest(secret,received):
        raise HTTPException(403,"invalid webhook secret")
    try:payload=await request.json()
    except Exception:raise HTTPException(400,"invalid update")
    message=payload.get("message") or {}
    chat=str((message.get("chat") or {}).get("id") or "")
    configured=str(get_setting("telegram_chat_id","") or "")
    if not chat or chat!=configured:
        return {"ok":True}
    text=str(message.get("text") or "").strip().split()[0].lower()
    response=""
    if text in {"/status","/start"}:
        m=system_ops.metrics();stack=protocol_ops.catalog()
        response=f"Makia {VERSION}\nCPU {m['cpu']:.0f}% · RAM {m['memory']:.0f}% · Disk {m['disk']:.0f}%\nXray: {'UP' if stack.get('xray',{}).get('service_active') else 'DOWN'}\nWG: {'UP' if stack.get('wireguard',{}).get('service_active') else 'DOWN'}\nOpenVPN: {'UP' if stack.get('openvpn',{}).get('service_active') else 'DOWN'}"
    elif text=="/expiry":
        expiry=_expiry_snapshot(7)
        response=f"Expiring/expired in 7 days: {expiry['count']}\nExpired: {expiry['expired']}"
    elif text=="/backup":
        rows=system_ops.backup_list()
        latest=rows[0] if rows else None
        schedule=_backup_schedule_snapshot()
        if latest:
            response=(
                f"Latest backup: {latest.get('name')}\n"
                f"Type: {latest.get('type')} · Encrypted: {'yes' if latest.get('encrypted') else 'no'}\n"
                f"Scheduled backup: {'ON' if schedule.get('enabled') else 'OFF'}"
            )
        else:
            response=f"No backups found.\nScheduled backup: {'ON' if schedule.get('enabled') else 'OFF'}"
    else:
        response="Commands: /status /expiry /backup"
    try:integration_ops.telegram_send(_telegram_token(),configured,response)
    except Exception:pass
    return {"ok":True}


@app.get("/api/disaster-recovery/summary")
def disaster_recovery_summary(request:Request):
    require_local_admin(request)
    readiness=backup_migration_readiness(request)
    cf=_cloudflare_snapshot()
    backups=system_ops.backup_list()
    full=next((x for x in backups if x.get("type")=="full_migration"),None)
    return {
        "readiness":readiness,"cloudflare":cf,"latest_full_backup":full,
        "steps":[
            "preflight","full_backup","install_destination","verify_bundle",
            "restore","runtime_verification","dns_cutover","client_uat"
        ],
        "stable_config_cutover":bool(readiness.get("same_config_cutover_ready")),
    }


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
    rows=[]
    for row in list_protocol_clients():
        snap=_subscription_snapshot(row)
        snap.pop("share_link",None)
        rows.append(snap)
    return rows

@app.get("/api/v1/nodes")
def api_v1_nodes(request:Request):
    require_api_scope(request,"nodes:read")
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
    public_ip:str=Field(default="",max_length=64)
    region:str=Field(default="",max_length=80)
    users:int=Field(default=0,ge=0,le=1000000)
    online_users:int=Field(default=0,ge=0,le=1000000)
    traffic_bytes:int=Field(default=0,ge=0)
    services:dict=Field(default_factory=dict)
    last_error:str=Field(default="",max_length=500)

@app.get("/api/nodes")
def nodes_get(request:Request):
    require_capability(request,"nodes")
    return list_nodes()

@app.post("/api/nodes")
def nodes_create(payload:NodeCreate,request:Request):
    actor=require_capability(request,"nodes",True)
    result=create_node(payload.name)
    audit(actor,"node_create",payload.name,ip=ip(request))
    return result

@app.post("/api/nodes/{node_id}/revoke")
def nodes_revoke(node_id:int,request:Request):
    actor=require_capability(request,"nodes",True)
    revoke_node(node_id)
    audit(actor,"node_revoke",str(node_id),ip=ip(request))
    return {"ok":True}

@app.post("/api/node/heartbeat")
def node_heartbeat(payload:NodeHeartbeat,request:Request):
    token=bearer(request)
    node=node_by_token(token or "")
    if not node:
        raise HTTPException(403,"invalid node token")
    update_node_heartbeat(
        node["id"],payload.hostname,payload.version,payload.cpu,payload.memory,payload.disk,
        payload.public_ip,payload.region,payload.users,payload.online_users,payload.traffic_bytes,payload.services,payload.last_error
    )
    return {"ok":True,"node_id":node["id"],"server_time":int(time.time())}

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
    xray_transport:str="tcp"
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
    allowed_transports={"tcp","ws","grpc","httpupgrade","xhttp","kcp","hysteria"}
    allowed_security={"none","tls","reality"}
    dns_mode=(payload.npv_dns_mode or "UDP").upper()
    if dns_mode not in {"UDP","TCP"}: raise HTTPException(400,"NPV DNS mode must be UDP or TCP")
    if payload.ssh_password_mode not in allowed_modes: raise HTTPException(400,"invalid SSH password mode")
    if payload.xray_protocol not in allowed_protocols: raise HTTPException(400,"invalid Xray protocol")
    if payload.xray_transport not in allowed_transports: raise HTTPException(400,"invalid Xray transport")
    if payload.xray_security not in allowed_security: raise HTTPException(400,"invalid Xray security")
    try:
        normalized_xray_transport,normalized_xray_security=protocol_ops._validate_xray_guided_combo(
            payload.xray_protocol,payload.xray_transport,payload.xray_security
        )
    except protocol_ops.ProtocolError as exc:
        raise HTTPException(400,str(exc)) from exc
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
        "default_xray_transport":normalized_xray_transport,
        "default_xray_security":normalized_xray_security,
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
