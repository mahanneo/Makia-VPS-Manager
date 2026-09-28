from __future__ import annotations

from pathlib import Path
import hashlib, json, os, re, shutil, socket, subprocess, time, urllib.parse, urllib.request


class GrowthError(RuntimeError):
    pass


def _json_request(url,method="GET",headers=None,payload=None,timeout=20):
    data=None
    hdr={"Accept":"application/json","User-Agent":"Makia-VPS-Manager"}
    hdr.update(headers or {})
    if payload is not None:
        data=json.dumps(payload,separators=(",",":")).encode("utf-8")
        hdr["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=hdr,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            raw=response.read()
    except Exception as exc:
        raise GrowthError(str(exc)) from exc
    try:return json.loads(raw.decode("utf-8") or "{}")
    except Exception as exc:raise GrowthError("remote API returned invalid JSON") from exc


def cloudflare_zone(token,domain):
    domain=str(domain or "").strip().lower().rstrip(".")
    token=str(token or "").strip()
    if not token or not domain:raise GrowthError("Cloudflare token and domain are required")
    parts=domain.split(".")
    candidates=[".".join(parts[i:]) for i in range(max(0,len(parts)-2),len(parts))]
    headers={"Authorization":f"Bearer {token}"}
    for candidate in candidates:
        data=_json_request("https://api.cloudflare.com/client/v4/zones?name="+urllib.parse.quote(candidate),headers=headers)
        result=data.get("result") or []
        if data.get("success") and result:
            return result[0]
    raise GrowthError("Cloudflare zone was not found for this domain")


def cloudflare_record_status(token,hostname):
    zone=cloudflare_zone(token,hostname)
    headers={"Authorization":f"Bearer {token}"}
    url=f"https://api.cloudflare.com/client/v4/zones/{zone['id']}/dns_records?type=A&name="+urllib.parse.quote(hostname)
    data=_json_request(url,headers=headers)
    rows=data.get("result") or []
    record=rows[0] if rows else None
    return {
        "zone_id":zone.get("id"),"zone_name":zone.get("name"),
        "record_id":record.get("id") if record else "",
        "name":hostname,"content":record.get("content") if record else "",
        "proxied":bool(record.get("proxied")) if record else False,
        "ttl":record.get("ttl") if record else None,
        "exists":bool(record),
    }


def cloudflare_update_a(token,hostname,ip,ttl=120,proxied=False):
    try:socket.inet_aton(str(ip))
    except OSError as exc:raise GrowthError("new VPS IP must be valid IPv4") from exc
    zone=cloudflare_zone(token,hostname)
    headers={"Authorization":f"Bearer {token}"}
    base=f"https://api.cloudflare.com/client/v4/zones/{zone['id']}/dns_records"
    current=cloudflare_record_status(token,hostname)
    payload={"type":"A","name":hostname,"content":str(ip),"ttl":int(ttl or 120),"proxied":bool(proxied)}
    if current.get("record_id"):
        data=_json_request(base+"/"+current["record_id"],"PUT",headers,payload)
    else:
        data=_json_request(base,"POST",headers,payload)
    if not data.get("success"):
        raise GrowthError("Cloudflare rejected the DNS update")
    result=data.get("result") or {}
    return {"zone":zone.get("name"),"record_id":result.get("id"),"name":hostname,"content":result.get("content"),"proxied":bool(result.get("proxied"))}


def telegram_send(bot_token,chat_id,text):
    token=str(bot_token or "").strip(); chat=str(chat_id or "").strip()
    if not token or not chat:raise GrowthError("Telegram bot token and chat ID are required")
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    data=_json_request(url,"POST",payload={"chat_id":chat,"text":str(text)[:4000],"disable_web_page_preview":True})
    if not data.get("ok"):raise GrowthError("Telegram sendMessage failed")
    return data.get("result") or {}


def telegram_updates(bot_token,offset=0,timeout=10):
    token=str(bot_token or "").strip()
    if not token:return []
    url=f"https://api.telegram.org/bot{token}/getUpdates?timeout={int(timeout)}&offset={int(offset or 0)}&allowed_updates=%5B%22message%22%5D"
    data=_json_request(url,timeout=max(15,int(timeout)+5))
    if not data.get("ok"):raise GrowthError("Telegram getUpdates failed")
    return data.get("result") or []


def backup_remote_upload(path,config):
    source=Path(path)
    if not source.is_file():raise GrowthError("backup file does not exist")
    cfg=dict(config or {})
    remote_type=str(cfg.get("type") or "local").lower()
    if remote_type=="local":
        dest=Path(str(cfg.get("path") or "/var/backups/makia-remote"))
        dest.mkdir(parents=True,exist_ok=True,mode=0o700)
        out=dest/source.name
        shutil.copy2(source,out)
        return {"remote_type":"local","target":str(out),"sha256":sha256_file(out)}
    if remote_type!="sftp":
        raise GrowthError("remote backup type must be local or sftp")
    host=str(cfg.get("host") or "").strip()
    user=str(cfg.get("user") or "").strip()
    port=int(cfg.get("port") or 22)
    remote_path=str(cfg.get("path") or "~/makia-backups").strip()
    identity=str(cfg.get("identity_file") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",user):raise GrowthError("invalid SFTP username")
    if not host or any(ch.isspace() for ch in host):raise GrowthError("invalid SFTP host")
    if not 1<=port<=65535:raise GrowthError("invalid SFTP port")
    if not identity or not Path(identity).is_file():raise GrowthError("SFTP identity_file must exist on this VPS")
    if not shutil.which("ssh") or not shutil.which("scp"):raise GrowthError("OpenSSH client tools are not installed")
    base=["-i",identity,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=accept-new"]
    target=f"{user}@{host}"
    mk=["ssh","-i",identity,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=accept-new",target,"mkdir","-p",remote_path]
    p=subprocess.run(mk,text=True,capture_output=True,timeout=30)
    if p.returncode!=0:raise GrowthError((p.stderr or p.stdout or "remote mkdir failed").strip()[:500])
    cmd=["scp",*base,str(source),f"{target}:{remote_path.rstrip('/')}/{source.name}"]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=300)
    if p.returncode!=0:raise GrowthError((p.stderr or p.stdout or "SFTP upload failed").strip()[:500])
    remote_file=remote_path.rstrip("/")+"/"+source.name
    verify=["ssh","-i",identity,"-p",str(port),"-o","BatchMode=yes",target,"sha256sum",remote_file]
    p=subprocess.run(verify,text=True,capture_output=True,timeout=30)
    digest=(p.stdout or "").strip().split()[0] if p.returncode==0 else ""
    local=sha256_file(source)
    if digest and digest!=local:raise GrowthError("remote SHA256 mismatch")
    return {"remote_type":"sftp","target":f"{target}:{remote_file}","sha256":local,"verified":bool(digest)}


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def detect_public_ipv4():
    for url in ("https://api.ipify.org","https://ifconfig.me/ip"):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Makia-VPS-Manager"})
            with urllib.request.urlopen(req,timeout=6) as resp:
                value=resp.read().decode().strip()
            socket.inet_aton(value)
            return value
        except Exception:
            continue
    return ""


def ping_latency(host):
    if not host or not shutil.which("ping"):return None
    p=subprocess.run(["ping","-c","1","-W","2",str(host)],text=True,capture_output=True,timeout=4)
    if p.returncode!=0:return None
    m=re.search(r"time[=<]([0-9.]+)\s*ms",p.stdout or "")
    return float(m.group(1)) if m else None
