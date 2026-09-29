import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.parse
from pathlib import Path

ACCESS_CONFIG=Path("/opt/outline/access.txt")
INSTALL_HELPER="/usr/local/sbin/makia-install-outline"


class OutlineError(RuntimeError):
    pass


def _read_access_config():
    if not ACCESS_CONFIG.is_file():
        return {}
    data={}
    for line in ACCESS_CONFIG.read_text(encoding="utf-8",errors="ignore").splitlines():
        if ":" not in line:continue
        key,value=line.split(":",1)
        if key in {"apiUrl","certSha256"}:data[key]=value.strip()
    if not data.get("apiUrl") or not data.get("certSha256"):
        return {}
    return data


def installed():
    return bool(_read_access_config())


def docker_ready():
    docker=shutil.which("docker")
    if not docker:return False
    try:
        p=subprocess.run([docker,"info"],text=True,capture_output=True,timeout=10,check=False)
        return p.returncode==0
    except Exception:return False


def status():
    cfg=_read_access_config()
    container=False
    if shutil.which("docker"):
        try:
            p=subprocess.run(["docker","inspect","-f","{{.State.Running}}","shadowbox"],text=True,capture_output=True,timeout=10,check=False)
            container=p.returncode==0 and (p.stdout or "").strip()=="true"
        except Exception:container=False
    out={
        "installed":bool(cfg),"docker_ready":docker_ready(),"container_active":container,
        "api_configured":bool(cfg.get("apiUrl")),"api_reachable":False,
        "keys":0,"server":None,
        "install_command":"sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade" if not shutil.which("docker") else "",
    }
    if cfg and container:
        try:
            keys=list_keys()
            out["api_reachable"]=True
            out["keys"]=len(keys)
            try:out["server"]=_request("GET","/server")
            except Exception:out["server"]=None
        except Exception as exc:
            out["error"]=str(exc)
    return out


def setup(hostname="",keys_port=0):
    if installed():
        return status()
    helper=Path(INSTALL_HELPER)
    if not helper.is_file():
        raise OutlineError("Outline installer helper is missing; run sudo makia-upgrade")
    if not docker_ready():
        raise OutlineError("Docker host dependency is not ready. Run: sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade")
    args=[str(helper)]
    host=str(hostname or "").strip()
    if host:
        if len(host)>255 or not re.fullmatch(r"[A-Za-z0-9_.:-]+",host):
            raise OutlineError("invalid Outline hostname")
        args+=["--hostname",host]
    if keys_port:
        port=int(keys_port)
        if not 1<=port<=65535:raise OutlineError("invalid Outline keys port")
        args+=["--keys-port",str(port)]
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=600,check=False)
    except Exception as exc:
        raise OutlineError(str(exc)) from exc
    if p.returncode!=0:
        raise OutlineError((p.stderr or p.stdout or "Outline installation failed").strip()[-1800:])
    if not installed():
        raise OutlineError("Outline installer finished but access.txt was not created")
    return status()


def _api_parts():
    cfg=_read_access_config()
    if not cfg:raise OutlineError("Outline server is not installed")
    parsed=urllib.parse.urlsplit(cfg["apiUrl"])
    if parsed.scheme!="https" or not parsed.hostname:
        raise OutlineError("invalid Outline management API URL")
    expected=re.sub(r"[^0-9A-Fa-f]","",cfg["certSha256"]).lower()
    if len(expected)!=64:raise OutlineError("invalid Outline certificate fingerprint")
    return parsed,expected


def _request(method,suffix,payload=None,form=None,timeout=20):
    parsed,expected=_api_parts()
    ctx=ssl._create_unverified_context()
    conn=http.client.HTTPSConnection(parsed.hostname,parsed.port or 443,context=ctx,timeout=timeout)
    try:
        conn.connect()
        cert=conn.sock.getpeercert(binary_form=True)
        actual=hashlib.sha256(cert).hexdigest().lower()
        if not hmac_compare(actual,expected):
            raise OutlineError("Outline API certificate fingerprint mismatch")
        base=parsed.path.rstrip("/")
        path=base+"/"+str(suffix or "").lstrip("/")
        headers={"Accept":"application/json"}
        body=None
        if payload is not None:
            body=json.dumps(payload,separators=(",",":")).encode("utf-8")
            headers["Content-Type"]="application/json"
        elif form is not None:
            boundary="----makiaoutline"+os.urandom(8).hex()
            parts=[]
            for key,value in form.items():
                parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
            parts.append(f"--{boundary}--\r\n".encode())
            body=b"".join(parts)
            headers["Content-Type"]=f"multipart/form-data; boundary={boundary}"
        conn.request(method.upper(),path,body=body,headers=headers)
        res=conn.getresponse()
        raw=res.read(2_000_000)
        if res.status>=400:
            raise OutlineError(f"Outline API {res.status}: {raw.decode('utf-8',errors='ignore')[:1000]}")
        if not raw:return {}
        try:return json.loads(raw.decode("utf-8"))
        except Exception:return {"raw":raw.decode("utf-8",errors="ignore")}
    finally:
        conn.close()


def hmac_compare(a,b):
    import hmac
    return hmac.compare_digest(str(a),str(b))


def list_keys():
    data=_request("GET","/access-keys/")
    rows=data.get("accessKeys") if isinstance(data,dict) else None
    return rows if isinstance(rows,list) else []


def get_key(key_id):
    return _request("GET",f"/access-keys/{int(key_id)}")


def create_key(name="",limit_bytes=0):
    key=_request("POST","/access-keys")
    key_id=key.get("id")
    if key_id is None:raise OutlineError("Outline did not return an access key id")
    if name:
        rename_key(key_id,name)
        key=get_key(key_id)
    if int(limit_bytes or 0)>0:
        set_data_limit(key_id,int(limit_bytes))
        key=get_key(key_id)
    return key


def rename_key(key_id,name):
    name=str(name or "").strip()
    if not name or len(name)>80:raise OutlineError("Outline key name is required and must be <= 80 characters")
    _request("PUT",f"/access-keys/{int(key_id)}/name",form={"name":name})
    return get_key(key_id)


def delete_key(key_id):
    _request("DELETE",f"/access-keys/{int(key_id)}")
    return {"ok":True,"id":str(key_id)}


def set_data_limit(key_id,bytes_limit):
    value=max(0,int(bytes_limit or 0))
    if value<=0:
        _request("DELETE",f"/access-keys/{int(key_id)}/data-limit")
    else:
        _request("PUT",f"/access-keys/{int(key_id)}/data-limit",payload={"limit":{"bytes":value}})
    return {"ok":True,"id":str(key_id),"bytes":value}
