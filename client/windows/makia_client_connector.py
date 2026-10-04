#!/usr/bin/env python3
import argparse, base64, ctypes, json, os, re, socket, struct, subprocess, sys, tempfile, time
import urllib.parse, urllib.request
from pathlib import Path

APP="Makia Client Connector"
ROOT=Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())/"Makia"/"Connector"
STATE=ROOT/"state.json"
PROFILE=ROOT/"active.json"
BROWSER_STATE=ROOT/"browser-state.json"
BROWSER_PROFILE=ROOT/"browser-active.json"
LOG=ROOT/"connector.log"

def log(msg):
    ROOT.mkdir(parents=True,exist_ok=True)
    with LOG.open("a",encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+str(msg)+"\n")

def show_error(message):
    if os.name!="nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(0,str(message),APP,0x10)
    except Exception:
        pass

def b64decode_loose(value):
    raw=str(value or "").strip()
    raw += "="*((4-len(raw)%4)%4)
    return base64.urlsafe_b64decode(raw.encode()).decode("utf-8")

def controller_ok(url):
    u=urllib.parse.urlparse(url)
    if u.scheme=="https" and u.netloc:
        return True
    if os.environ.get("MAKIA_ALLOW_HTTP")=="1" and u.scheme=="http" and u.hostname in {"127.0.0.1","localhost"}:
        return True
    return False

def redeem(controller,ticket):
    if not controller_ok(controller):
        raise RuntimeError("Controller must use HTTPS")
    data=json.dumps({"ticket":ticket}).encode()
    req=urllib.request.Request(
        controller.rstrip("/")+"/client/connector/redeem",
        data=data,
        headers={"Content-Type":"application/json","User-Agent":"MakiaClientConnector/1.4.1"},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=15) as r:
        return json.loads(r.read().decode())

def transport(q):
    typ=(q.get("type") or [""])[0].lower()
    if typ=="ws":
        host=(q.get("host") or [""])[0]
        out={"type":"ws","path":(q.get("path") or [""])[0]}
        if host:
            out["headers"]={"Host":host}
        return out
    if typ=="grpc":
        return {"type":"grpc","service_name":(q.get("serviceName") or q.get("service_name") or [""])[0]}
    if typ=="httpupgrade":
        return {"type":"httpupgrade","path":(q.get("path") or ["/"])[0],"host":(q.get("host") or [""])[0]}
    if typ in {"http","h2"}:
        host=(q.get("host") or [""])[0]
        return {"type":"http","path":(q.get("path") or ["/"])[0],"host":[host] if host else []}
    return None

def tls_for(q,host):
    sec=(q.get("security") or [""])[0].lower()
    if sec not in {"tls","reality"}:
        return None
    out={"enabled":True,"server_name":(q.get("sni") or [host])[0]}
    fp=(q.get("fp") or [""])[0]
    if fp:
        out["utls"]={"enabled":True,"fingerprint":fp}
    if sec=="reality":
        out["reality"]={
            "enabled":True,
            "public_key":(q.get("pbk") or q.get("publicKey") or [""])[0],
            "short_id":(q.get("sid") or q.get("shortId") or [""])[0],
        }
    return out

def parse_vless_or_trojan(uri):
    u=urllib.parse.urlparse(uri)
    q=urllib.parse.parse_qs(u.query)
    if u.scheme=="vless":
        out={"type":"vless","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"uuid":urllib.parse.unquote(u.username or "")}
        flow=(q.get("flow") or [""])[0]
        if flow:
            out["flow"]=flow
    else:
        out={"type":"trojan","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"password":urllib.parse.unquote(u.username or "")}
    tls=tls_for(q,u.hostname or "")
    if tls:
        out["tls"]=tls
    tr=transport(q)
    if tr:
        out["transport"]=tr
    return out

def parse_hy2(uri):
    u=urllib.parse.urlparse(uri)
    q=urllib.parse.parse_qs(u.query)
    out={"type":"hysteria2","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"password":urllib.parse.unquote(u.username or "")}
    out["tls"]={
        "enabled":True,
        "server_name":(q.get("sni") or [u.hostname or ""])[0],
        "insecure":(q.get("insecure") or ["0"])[0] in {"1","true"},
    }
    obfs=(q.get("obfs") or [""])[0]
    obfs_pass=(q.get("obfs-password") or q.get("obfs_password") or [""])[0]
    if obfs:
        out["obfs"]={"type":obfs,"password":obfs_pass}
    return out

def parse_vmess(uri):
    obj=json.loads(b64decode_loose(uri.split("://",1)[1]))
    out={
        "type":"vmess","tag":"proxy","server":obj["add"],"server_port":int(obj.get("port") or 443),
        "uuid":obj["id"],"security":obj.get("scy") or "auto","alter_id":int(obj.get("aid") or 0),
    }
    if str(obj.get("tls") or "").lower() in {"tls","reality"}:
        q={
            "security":[str(obj.get("tls"))],"sni":[str(obj.get("sni") or obj.get("host") or obj["add"])],
            "fp":[str(obj.get("fp") or "")],"pbk":[str(obj.get("pbk") or "")],"sid":[str(obj.get("sid") or "")],
        }
        out["tls"]=tls_for(q,obj["add"])
    typ=str(obj.get("net") or "")
    if typ:
        q={"type":[typ],"path":[str(obj.get("path") or "")],"host":[str(obj.get("host") or "")],"serviceName":[str(obj.get("path") or "")]}
        tr=transport(q)
        if tr:
            out["transport"]=tr
    return out

def parse_ss(uri):
    raw=uri.split("://",1)[1].split("#",1)[0]
    if "@" not in raw:
        raw=b64decode_loose(raw)
    auth,server=raw.rsplit("@",1)
    if ":" not in auth:
        auth=b64decode_loose(auth)
    method,password=auth.split(":",1)
    if server.startswith("["):
        host,port=server.rsplit("]:",1)
        host=host[1:]
    else:
        host,port=server.rsplit(":",1)
    return {
        "type":"shadowsocks","tag":"proxy","server":host,
        "server_port":int(port.split("?",1)[0]),"method":method,"password":urllib.parse.unquote(password),
    }

def parse_npvt_ssh(uri):
    obj=json.loads(b64decode_loose(uri.split("://",1)[1]))
    return {
        "type":"ssh","tag":"proxy","server":obj["sshHost"],"server_port":int(obj.get("sshPort") or 22),
        "user":obj.get("sshUsername") or "root","password":obj.get("sshPassword") or "",
    }

def outbound_from_share(uri):
    scheme=urllib.parse.urlparse(uri).scheme.lower()
    if scheme in {"vless","trojan"}:
        return parse_vless_or_trojan(uri)
    if scheme in {"hysteria2","hy2"}:
        return parse_hy2(uri)
    if scheme=="vmess":
        return parse_vmess(uri)
    if scheme=="ss":
        return parse_ss(uri)
    if scheme=="npvt-ssh":
        return parse_npvt_ssh(uri)
    raise RuntimeError("Unsupported direct-connect scheme: "+scheme)

def find_free_local_port():
    for port in range(2080,2100):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1",port))
                return port
            except OSError:
                pass
    raise RuntimeError("No local Makia browser proxy port is available")

def singbox_config(outbound,connection_mode="device",proxy_port=0):
    if connection_mode=="browser":
        if not proxy_port:
            raise RuntimeError("Browser proxy port is required")
        inbounds=[{
            "type":"mixed","tag":"browser-in","listen":"127.0.0.1",
            "listen_port":int(proxy_port),"set_system_proxy":False,
        }]
    else:
        inbounds=[{
            "type":"tun","tag":"tun-in","interface_name":"Makia","address":["172.19.0.1/30"],
            "mtu":1400,"auto_route":True,"strict_route":True,
        }]
    return {
        "log":{"level":"info","timestamp":True},
        "inbounds":inbounds,
        "outbounds":[outbound,{"type":"direct","tag":"direct"}],
        "route":{"auto_detect_interface":True,"final":"proxy"},
    }

def find_binary(names):
    here=Path(sys.executable).resolve().parent
    candidates=[]
    for n in names:
        candidates += [here/n,ROOT/n]
        for folder in os.environ.get("PATH","").split(os.pathsep):
            if folder:
                candidates.append(Path(folder)/n)
    for p in candidates:
        if p.is_file():
            return str(p)
    return None

def _state_paths(connection_mode):
    return (BROWSER_STATE,BROWSER_PROFILE) if connection_mode=="browser" else (STATE,PROFILE)

def stop_current(connection_mode="device"):
    state_path,profile_path=_state_paths(connection_mode)
    if not state_path.exists():
        return {"ok":True,"stopped":False,"connection_mode":connection_mode}
    try:
        state=json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state={}
    try:
        if state.get("mode")=="process":
            pid=int(state.get("pid") or 0)
            if pid:
                subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,timeout=10,check=False)
        elif state.get("mode")=="wireguard" and connection_mode!="browser":
            exe=find_binary(["wireguard.exe"])
            if exe and state.get("tunnel"):
                subprocess.run([exe,"/uninstalltunnelservice",state["tunnel"]],capture_output=True,timeout=20,check=False)
    finally:
        for p in [profile_path,state_path]:
            try:
                p.unlink()
            except OSError:
                pass
    return {"ok":True,"stopped":True,"connection_mode":connection_mode}

def start_process(cmd):
    flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    return p.pid

def connect_delivery(d,dry_run=False,connection_mode="device"):
    engine=str(d.get("engine") or "").lower()
    share=str(d.get("share_link") or "")
    state_path,profile_path=_state_paths(connection_mode)
    stop_current(connection_mode)
    ROOT.mkdir(parents=True,exist_ok=True)
    if connection_mode=="browser" and engine in {"wireguard","openvpn"}:
        raise RuntimeError("This profile requires Full Device / Import mode")
    if engine=="wireguard":
        raw=base64.b64decode(d.get("native_base64") or "") if d.get("native_base64") else share.encode()
        name=re.sub(r"[^A-Za-z0-9_-]+","-",Path(d.get("native_filename") or "makia.conf").stem)[:40] or "makia"
        path=ROOT/(name+".conf")
        path.write_bytes(raw)
        exe=find_binary(["wireguard.exe"])
        if dry_run:
            return {"ok":True,"mode":"wireguard","binary":bool(exe),"profile":str(path)}
        if not exe:
            raise RuntimeError("WireGuard for Windows is not installed")
        cp=subprocess.run([exe,"/installtunnelservice",str(path)],capture_output=True,text=True,timeout=30,check=False)
        if cp.returncode!=0:
            raise RuntimeError((cp.stderr or cp.stdout or "WireGuard failed")[-500:])
        state_path.write_text(json.dumps({"mode":"wireguard","tunnel":name,"connection_mode":"device"}),encoding="utf-8")
        return {"ok":True,"mode":"wireguard","connected":True,"connection_mode":"device"}
    if engine=="openvpn":
        raw=base64.b64decode(d.get("native_base64") or "")
        if not raw:
            raise RuntimeError("OpenVPN profile missing")
        path=ROOT/"makia.ovpn"
        path.write_bytes(raw)
        exe=find_binary(["openvpn.exe"])
        if dry_run:
            return {"ok":True,"mode":"openvpn","binary":bool(exe),"profile":str(path)}
        if not exe:
            raise RuntimeError("OpenVPN Connect/OpenVPN binary is not installed")
        pid=start_process([exe,"--config",str(path)])
        state_path.write_text(json.dumps({"mode":"process","pid":pid,"engine":"openvpn","connection_mode":"device"}),encoding="utf-8")
        return {"ok":True,"mode":"openvpn","connected":True,"connection_mode":"device"}
    outbound=outbound_from_share(share)
    proxy_port=find_free_local_port() if connection_mode=="browser" else 0
    cfg=singbox_config(outbound,connection_mode,proxy_port)
    profile_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
    exe=find_binary(["sing-box.exe"])
    if dry_run:
        return {
            "ok":True,"mode":"sing-box","binary":bool(exe),"outbound":outbound["type"],
            "profile":str(profile_path),"connection_mode":connection_mode,"proxy_port":proxy_port,
        }
    if not exe:
        raise RuntimeError("Makia sing-box runtime is missing")
    check=subprocess.run([exe,"check","-c",str(profile_path)],capture_output=True,text=True,timeout=15,check=False)
    if check.returncode!=0:
        raise RuntimeError((check.stderr or check.stdout or "sing-box config rejected")[-800:])
    pid=start_process([exe,"run","-c",str(profile_path)])
    time.sleep(1)
    if subprocess.run(["tasklist","/FI",f"PID eq {pid}"],capture_output=True,text=True,timeout=5).stdout.find(str(pid))<0:
        raise RuntimeError("sing-box exited during startup")
    state={
        "mode":"process","pid":pid,"engine":outbound["type"],
        "connection_mode":connection_mode,"proxy_port":proxy_port,
    }
    state_path.write_text(json.dumps(state),encoding="utf-8")
    return {
        "ok":True,"mode":"sing-box","protocol":outbound["type"],"connected":True,
        "connection_mode":connection_mode,"proxy_port":proxy_port,
    }

def handle_uri(uri,dry_run=False):
    u=urllib.parse.urlparse(uri)
    if u.scheme.lower()!="makia":
        raise RuntimeError("Invalid Makia URI")
    action=(u.netloc or u.path.strip("/")).lower()
    if action=="disconnect":
        return stop_current("device")
    if action!="connect":
        raise RuntimeError("Unknown Makia action")
    q=urllib.parse.parse_qs(u.query)
    controller=(q.get("controller") or [""])[0]
    ticket=(q.get("ticket") or [""])[0]
    if not ticket:
        raise RuntimeError("Missing connector ticket")
    delivery=redeem(controller,ticket)
    return connect_delivery(delivery,dry_run=dry_run,connection_mode="device")

def native_read():
    raw=sys.stdin.buffer.read(4)
    if len(raw)!=4:
        raise RuntimeError("Native message header missing")
    size=struct.unpack("<I",raw)[0]
    if size<2 or size>1024*1024:
        raise RuntimeError("Native message size is invalid")
    data=sys.stdin.buffer.read(size)
    if len(data)!=size:
        raise RuntimeError("Native message body is incomplete")
    return json.loads(data.decode("utf-8"))

def native_write(payload):
    data=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I",len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def browser_status():
    if not BROWSER_STATE.exists():
        return {"ok":True,"connected":False,"connection_mode":"browser"}
    try:
        state=json.loads(BROWSER_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"ok":True,"connected":False,"connection_mode":"browser"}
    return {
        "ok":True,"connected":bool(state.get("pid")),"connection_mode":"browser",
        "protocol":state.get("engine") or "","proxy_port":int(state.get("proxy_port") or 0),
    }

def handle_native_message(message):
    action=str((message or {}).get("action") or "").lower()
    if action=="status":
        return browser_status()
    if action=="disconnect":
        return stop_current("browser")
    if action=="connect":
        controller=str(message.get("controller") or "")
        ticket=str(message.get("ticket") or "")
        if not ticket:
            raise RuntimeError("Missing connector ticket")
        delivery=redeem(controller,ticket)
        return connect_delivery(delivery,dry_run=False,connection_mode="browser")
    raise RuntimeError("Unknown native host action")

def main():
    ap=argparse.ArgumentParser(prog="MakiaClientConnector")
    ap.add_argument("uri",nargs="?")
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--disconnect",action="store_true")
    ap.add_argument("--status",action="store_true")
    ap.add_argument("--native-host",action="store_true")
    ap.add_argument("--browser-disconnect",action="store_true")
    args=ap.parse_args()
    browser_host_binary=Path(sys.executable).stem.lower()=="makiabrowserhost"
    try:
        if args.native_host or browser_host_binary:
            native_write(handle_native_message(native_read()))
            return 0
        if args.browser_disconnect:
            result=stop_current("browser")
        elif args.disconnect:
            result=stop_current("device")
        elif args.status:
            result=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"connected":False}
        elif args.uri:
            result=handle_uri(args.uri,args.dry_run)
        else:
            raise RuntimeError("Makia URI is required")
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as exc:
        message=str(exc)
        log(type(exc).__name__+": "+message)
        if args.native_host or browser_host_binary:
            try:
                native_write({"ok":False,"error":message})
            except Exception:
                pass
        else:
            if args.uri and not args.dry_run:
                show_error(message+"\n\nLog: "+str(LOG))
            print(json.dumps({"ok":False,"error":message},ensure_ascii=False))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
