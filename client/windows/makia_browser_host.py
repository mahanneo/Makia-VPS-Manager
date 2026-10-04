#!/usr/bin/env python3
import base64
import ctypes
from ctypes import wintypes
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import makia_client_connector as connector

HOST_VERSION="1.4.0"
ROOT=Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())/"Makia"/"BrowserHost"
PROFILE=ROOT/"profile.json"
LOG=ROOT/"browser-host.log"
MAX_MESSAGE=256*1024

# Chromium Native Messaging on Windows requires raw binary stdio framing.
if os.name=="nt":
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)


class DATA_BLOB(ctypes.Structure):
    _fields_=[("cbData",wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_byte))]


def log(message):
    ROOT.mkdir(parents=True,exist_ok=True)
    with LOG.open("a",encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+str(message)+"\n")


def _dpapi(data,protect=True):
    if os.name!="nt":
        raise RuntimeError("Makia Browser Host is supported on Windows")
    raw=bytes(data)
    buf=ctypes.create_string_buffer(raw)
    inp=DATA_BLOB(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)))
    out=DATA_BLOB()
    if protect:
        ok=ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(inp),"Makia Browser Host",None,None,None,0,ctypes.byref(out)
        )
    else:
        ok=ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)
        )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.pbData,out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def seal(value):
    return base64.b64encode(_dpapi(str(value).encode("utf-8"),True)).decode("ascii")


def open_sealed(value):
    return _dpapi(base64.b64decode(str(value or "")),False).decode("utf-8")


def save_profile(controller,token,expires_at):
    if not connector.controller_ok(controller):
        raise RuntimeError("Controller must use HTTPS")
    ROOT.mkdir(parents=True,exist_ok=True)
    data={
        "controller":str(controller).rstrip("/"),
        "token_enc":seal(token),
        "expires_at":int(expires_at or 0),
        "version":HOST_VERSION,
    }
    PROFILE.write_text(json.dumps(data,separators=(",",":")),encoding="utf-8")
    try:
        os.chmod(PROFILE,0o600)
    except OSError:
        pass


def clear_profile():
    try:
        PROFILE.unlink()
    except OSError:
        pass


def load_profile(required=True):
    if not PROFILE.exists():
        if required:
            raise RuntimeError("Browser extension is not paired")
        return None
    try:
        data=json.loads(PROFILE.read_text(encoding="utf-8"))
        data["token"]=open_sealed(data.pop("token_enc"))
        if int(data.get("expires_at") or 0)<=int(time.time()):
            clear_profile()
            raise RuntimeError("Browser pairing session expired; pair again")
        if not connector.controller_ok(data.get("controller")):
            raise RuntimeError("Stored controller is invalid")
        return data
    except Exception:
        if required:
            raise
        return None


def http_json(method,controller,path,body=None,token=None):
    if not connector.controller_ok(controller):
        raise RuntimeError("Controller must use HTTPS")
    headers={"Accept":"application/json","User-Agent":"MakiaBrowserHost/1.4"}
    data=None
    if body is not None:
        data=json.dumps(body,separators=(",",":")).encode("utf-8")
        headers["Content-Type"]="application/json"
    if token:
        headers["Authorization"]="Bearer "+str(token)
    req=urllib.request.Request(controller.rstrip("/")+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode("utf-8","replace")
        try:
            detail=json.loads(raw).get("detail") or raw
        except Exception:
            detail=raw
        raise RuntimeError(str(detail or ("HTTP "+str(exc.code))))


def pair(controller,code):
    result=http_json("POST",controller,"/client/browser/redeem",{"code":str(code or "").strip()})
    token=str(result.get("token") or "")
    if not token:
        raise RuntimeError("Pairing response did not include a session token")
    save_profile(controller,token,result.get("expires_at"))
    return {"paired":True,"expires_at":int(result.get("expires_at") or 0)}


def auth_request(method,path,body=None):
    profile=load_profile(True)
    try:
        return http_json(method,profile["controller"],path,body,profile["token"])
    except RuntimeError as exc:
        if "authentication" in str(exc).lower() or "expired" in str(exc).lower():
            clear_profile()
        raise


def connector_state():
    if not connector.STATE.exists():
        return {"connected":False,"scope":"","proxy_port":0}
    try:
        state=json.loads(connector.STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"connected":False,"scope":"","proxy_port":0}
    state["connected"]=True
    pid=int(state.get("pid") or 0)
    if pid and os.name=="nt":
        cp=subprocess.run(
            ["tasklist","/FI","PID eq "+str(pid)],
            capture_output=True,text=True,timeout=5,check=False,
        )
        if str(pid) not in (cp.stdout or ""):
            state["connected"]=False
    return state


def _connector_exe():
    here=Path(sys.executable).resolve().parent
    exe=here/"MakiaClientConnector.exe"
    if not exe.is_file():
        raise RuntimeError("MakiaClientConnector.exe is missing")
    return str(exe)


def wait_connector_state(scope=None,connected=True,timeout=12):
    deadline=time.time()+max(1,float(timeout))
    last=None
    while time.time()<deadline:
        last=connector_state()
        if connected:
            if last.get("connected") and (not scope or last.get("scope")==scope):
                return last
        elif not last.get("connected"):
            return last
        time.sleep(0.25)
    return last or {"connected":False,"scope":""}


def run_elevated(args,expect_scope=None,expect_disconnect=False):
    if os.name!="nt":
        raise RuntimeError("Device VPN is supported on Windows")
    params=subprocess.list2cmdline([str(x) for x in args])
    rc=ctypes.windll.shell32.ShellExecuteW(None,"runas",_connector_exe(),params,None,1)
    if int(rc)<=32:
        raise RuntimeError("Unable to start elevated Makia Connector")
    state=wait_connector_state(
        scope=expect_scope,
        connected=not expect_disconnect,
        timeout=15,
    )
    if expect_disconnect:
        if state.get("connected"):
            raise RuntimeError("Makia Connector did not stop the active tunnel")
        return {"connected":False,"scope":"","uac":True}
    if not state.get("connected") or (expect_scope and state.get("scope")!=expect_scope):
        raise RuntimeError("Makia Connector did not confirm the requested tunnel")
    state["uac"]=True
    return state


def connect_access(kind,delivery_id,mode):
    kind=str(kind or "").lower()
    if kind not in {"protocol","artifact"}:
        raise RuntimeError("Unsupported access kind")
    mode=str(mode or "browser").lower()
    if mode not in {"browser","device"}:
        raise RuntimeError("Unsupported connection mode")
    ticket=auth_request("POST","/client/browser/connect/"+kind+"/"+str(int(delivery_id))+"/ticket",{})
    launch=str(ticket.get("launch_url") or "")
    if not launch.startswith("makia://connect?"):
        raise RuntimeError("Invalid connector launch response")
    if mode=="browser":
        state=connector_state()
        if state.get("connected") and state.get("scope")=="device":
            raise RuntimeError("Disconnect Device VPN before starting Browser Only mode")
        result=connector.handle_uri(launch,browser_only=True)
        result["scope"]="browser"
        return result
    return run_elevated([launch],expect_scope="device")


def disconnect():
    state=connector_state()
    if not state.get("connected"):
        return {"connected":False,"stopped":False}
    if state.get("scope")=="browser":
        result=connector.stop_current()
        result["connected"]=False
        return result
    return run_elevated(["--disconnect"],expect_disconnect=True)


def logout():
    profile=load_profile(False)
    if profile:
        try:
            http_json("POST",profile["controller"],"/client/browser/logout",{},profile["token"])
        except Exception as exc:
            log("logout remote: "+str(exc))
    clear_profile()
    return {"paired":False}


def handle(message):
    action=str((message or {}).get("action") or "").lower()
    if action=="health":
        return {"ok":True,"version":HOST_VERSION,"paired":bool(load_profile(False))}
    if action=="pair":
        return pair(str(message.get("controller") or ""),str(message.get("code") or ""))
    if action=="me":
        return auth_request("GET","/client/browser/me")
    if action=="protocols":
        return auth_request("GET","/client/browser/protocols")
    if action=="status":
        state=connector_state()
        state["paired"]=bool(load_profile(False))
        state["host_version"]=HOST_VERSION
        return state
    if action=="connect":
        return connect_access(message.get("kind"),message.get("id"),message.get("mode"))
    if action=="disconnect":
        return disconnect()
    if action=="logout":
        return logout()
    raise RuntimeError("Unsupported Makia Browser Host action")


def read_message():
    raw=sys.stdin.buffer.read(4)
    if not raw:
        return None
    if len(raw)!=4:
        raise RuntimeError("Invalid native message header")
    length=struct.unpack("=I",raw)[0]
    if length<2 or length>MAX_MESSAGE:
        raise RuntimeError("Native message size is invalid")
    payload=sys.stdin.buffer.read(length)
    if len(payload)!=length:
        raise RuntimeError("Native message was truncated")
    return json.loads(payload.decode("utf-8"))


def write_message(payload):
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I",len(raw)))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def main():
    while True:
        try:
            message=read_message()
            if message is None:
                return 0
            result=handle(message)
            write_message({"ok":True,"result":result})
        except Exception as exc:
            log(type(exc).__name__+": "+str(exc))
            try:
                write_message({"ok":False,"error":str(exc)})
            except Exception:
                return 2


if __name__=="__main__":
    raise SystemExit(main())
