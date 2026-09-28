import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from . import access_ops


class IntegrationError(RuntimeError):
    pass


def seal_secret(value:dict)->str:
    return access_ops.seal_payload(value or {})


def open_secret(token:str)->dict:
    if not token:
        return {}
    return access_ops.open_payload(token)


def _json_request(url,method="GET",body=None,headers=None,timeout=15,context=None):
    data=None
    merged={"Accept":"application/json"}
    if headers:
        merged.update(headers)
    if body is not None:
        data=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        merged.setdefault("Content-Type","application/json")
    req=urllib.request.Request(url,data=data,headers=merged,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout,context=context) as response:
            raw=response.read()
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {"raw":raw.decode("utf-8","replace")}
    except Exception as exc:
        detail=str(exc)
        if hasattr(exc,"read"):
            try:
                detail=(exc.read() or b"").decode("utf-8","replace")[:1000] or detail
            except Exception:
                pass
        raise IntegrationError(detail[:1200]) from exc


def cloudflare_record(token,zone_id,name):
    token=str(token or "").strip()
    zone_id=str(zone_id or "").strip()
    name=str(name or "").strip().lower().rstrip(".")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,80}",zone_id):
        raise IntegrationError("invalid Cloudflare zone id")
    if not token or len(token)<20:
        raise IntegrationError("Cloudflare API token is missing")
    if not name or "." not in name:
        raise IntegrationError("a fully-qualified DNS record name is required")
    q=urllib.parse.urlencode({"type":"A","name":name})
    url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?{q}"
    result=_json_request(url,headers={"Authorization":"Bearer "+token})
    if not result.get("success"):
        raise IntegrationError("Cloudflare DNS lookup failed")
    rows=result.get("result") or []
    return rows[0] if rows else None


def cloudflare_update_a(token,zone_id,name,ipv4,ttl=60):
    try:
        socket.inet_aton(str(ipv4))
    except OSError as exc:
        raise IntegrationError("invalid IPv4 address") from exc
    record=cloudflare_record(token,zone_id,name)
    body={"type":"A","name":str(name).strip().lower().rstrip("."),"content":str(ipv4),"ttl":max(60,min(int(ttl or 60),86400)),"proxied":False}
    base=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    if record:
        result=_json_request(base+"/"+urllib.parse.quote(str(record.get("id") or ""),safe=""),method="PUT",body=body,headers={"Authorization":"Bearer "+token})
        action="updated"
    else:
        result=_json_request(base,method="POST",body=body,headers={"Authorization":"Bearer "+token})
        action="created"
    if not result.get("success"):
        raise IntegrationError("Cloudflare DNS update failed")
    out=result.get("result") or {}
    return {"action":action,"id":out.get("id"),"name":out.get("name"),"content":out.get("content"),"proxied":out.get("proxied"),"ttl":out.get("ttl")}


def telegram_send(bot_token,chat_id,text):
    token=str(bot_token or "").strip()
    chat=str(chat_id or "").strip()
    if not re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}",token):
        raise IntegrationError("invalid Telegram bot token")
    if not re.fullmatch(r"-?\d{5,30}",chat):
        raise IntegrationError("invalid Telegram chat id")
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    result=_json_request(url,method="POST",body={
        "chat_id":chat,
        "text":str(text or "")[:3900],
        "disable_web_page_preview":True,
    })
    if not result.get("ok"):
        raise IntegrationError("Telegram sendMessage failed")
    return result.get("result") or {}


def telegram_set_webhook(bot_token,url,secret_token):
    token=str(bot_token or "").strip()
    hook=str(url or "").strip()
    secret=str(secret_token or "").strip()
    if not hook.startswith("https://"):
        raise IntegrationError("Telegram webhook requires HTTPS")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}",secret):
        raise IntegrationError("invalid Telegram webhook secret")
    result=_json_request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        method="POST",
        body={"url":hook,"secret_token":secret,"allowed_updates":["message"]},
    )
    if not result.get("ok"):
        raise IntegrationError("Telegram setWebhook failed")
    return result


def _outline_access_file(path="/opt/outline/access.txt"):
    p=Path(path)
    if not p.is_file():
        return {}
    values={}
    try:
        for line in p.read_text(encoding="utf-8",errors="ignore").splitlines():
            if ":" not in line:
                continue
            key,value=line.split(":",1)
            if key in {"apiUrl","certSha256"}:
                values[key]=value.strip()
    except OSError as exc:
        raise IntegrationError(str(exc)) from exc
    return values


def outline_config():
    values=_outline_access_file()
    api_url=values.get("apiUrl","")
    fingerprint=re.sub(r"[^0-9A-Fa-f]","",values.get("certSha256","")).upper()
    return {"api_url":api_url.rstrip("/"),"cert_sha256":fingerprint}


def _outline_local_url(api_url):
    parsed=urllib.parse.urlsplit(api_url)
    if parsed.scheme!="https" or not parsed.hostname:
        raise IntegrationError("Outline apiUrl must use HTTPS")
    port=parsed.port or 443
    host="127.0.0.1"
    path=parsed.path.rstrip("/")
    return urllib.parse.urlunsplit(("https",f"{host}:{port}",path,"",""))


def _outline_verify_fingerprint(api_url,expected):
    expected=re.sub(r"[^0-9A-Fa-f]","",str(expected or "")).upper()
    if len(expected)!=64:
        raise IntegrationError("Outline certificate fingerprint is missing or invalid")
    parsed=urllib.parse.urlsplit(api_url)
    port=parsed.port or 443
    context=ssl._create_unverified_context()
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=8) as raw:
            with context.wrap_socket(raw,server_hostname=parsed.hostname or "localhost") as tls:
                actual=hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest().upper()
    except OSError as exc:
        raise IntegrationError(f"Outline API TLS connection failed: {exc}") from exc
    if actual!=expected:
        raise IntegrationError("Outline API certificate fingerprint mismatch")
    return True


def _outline_request(path,method="GET",body=None):
    cfg=outline_config()
    api_url=cfg.get("api_url") or ""
    if not api_url:
        raise IntegrationError("Outline Server is not configured on this VPS")
    _outline_verify_fingerprint(api_url,cfg.get("cert_sha256"))
    base=_outline_local_url(api_url)
    url=base+"/"+str(path or "").lstrip("/")
    return _json_request(url,method=method,body=body,context=ssl._create_unverified_context(),timeout=20)


def outline_status():
    cfg=outline_config()
    docker=bool(subprocess.run(["sh","-c","command -v docker >/dev/null 2>&1"],capture_output=True).returncode==0)
    container=False
    if docker:
        p=subprocess.run(["docker","inspect","-f","{{.State.Running}}","shadowbox"],text=True,capture_output=True,timeout=8,check=False)
        container=p.returncode==0 and (p.stdout or "").strip().lower()=="true"
    keys=[]
    api_ok=False
    error=""
    if cfg.get("api_url"):
        try:
            response=_outline_request("/access-keys/")
            keys=response.get("accessKeys") or []
            api_ok=True
        except Exception as exc:
            error=str(exc)
    return {
        "installed":bool(cfg.get("api_url")),
        "docker":docker,
        "container_active":container,
        "api_ok":api_ok,
        "keys":keys,
        "key_count":len(keys),
        "api_url_configured":bool(cfg.get("api_url")),
        "error":error[:500],
    }


def outline_transfer_metrics():
    """Return cumulative transfer bytes by access-key id.

    Outline's Manager API exposes /metrics/transfer with
    bytesTransferredByUserId. Treat absence as unavailable rather than guessing.
    """
    result=_outline_request("/metrics/transfer")
    values=result.get("bytesTransferredByUserId") or {}
    if not isinstance(values,dict):
        raise IntegrationError("Outline transfer metrics response is invalid")
    out={}
    for key,value in values.items():
        try:out[str(key)]=max(0,int(value or 0))
        except Exception:continue
    return out


def outline_list_keys():
    result=_outline_request("/access-keys/")
    return result.get("accessKeys") or []


def outline_create_key(name,data_limit_bytes=0):
    name=str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_. -]{1,80}",name):
        raise IntegrationError("Outline key name contains unsupported characters")
    body={"name":name}
    if int(data_limit_bytes or 0)>0:
        body["dataLimit"]={"bytes":int(data_limit_bytes)}
    try:
        created=_outline_request("/access-keys",method="POST",body=body)
    except IntegrationError:
        created=_outline_request("/access-keys",method="POST")
        key_id=str(created.get("id") or "")
        if not key_id:
            raise
        # Older compatible Outline versions expose rename / data-limit as separate calls.
        _outline_request(f"/access-keys/{urllib.parse.quote(key_id,safe='')}/name",method="PUT",body={"name":name})
        if int(data_limit_bytes or 0)>0:
            _outline_request(
                f"/access-keys/{urllib.parse.quote(key_id,safe='')}/data-limit",
                method="PUT",body={"limit":{"bytes":int(data_limit_bytes)}},
            )
        created=_outline_request(f"/access-keys/{urllib.parse.quote(key_id,safe='')}")
    if not created.get("accessUrl"):
        raise IntegrationError("Outline did not return an accessUrl")
    return created


def outline_delete_key(key_id):
    key=str(key_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}",key):
        raise IntegrationError("invalid Outline key id")
    _outline_request(f"/access-keys/{urllib.parse.quote(key,safe='')}",method="DELETE")
    return {"removed":True,"id":key}


def outline_set_limit(key_id,bytes_limit):
    key=str(key_id or "").strip()
    if int(bytes_limit or 0)<=0:
        _outline_request(f"/access-keys/{urllib.parse.quote(key,safe='')}/data-limit",method="DELETE")
        return {"id":key,"limit_bytes":0}
    _outline_request(
        f"/access-keys/{urllib.parse.quote(key,safe='')}/data-limit",
        method="PUT",body={"limit":{"bytes":int(bytes_limit)}},
    )
    return {"id":key,"limit_bytes":int(bytes_limit)}


def outline_install_command(hostname="",keys_port=0):
    host=str(hostname or "").strip()
    port=int(keys_port or 0)
    if host and not re.fullmatch(r"[A-Za-z0-9.:-]{1,255}",host):
        raise IntegrationError("invalid Outline hostname")
    args=["sudo","/usr/local/sbin/makia-install-outline"]
    if host:
        args+=["--hostname",host]
    if port:
        if not 1<=port<=65535:
            raise IntegrationError("invalid Outline keys port")
        args+=["--keys-port",str(port)]
    return " ".join(args)
