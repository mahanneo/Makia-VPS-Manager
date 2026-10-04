#!/usr/bin/env python3
import argparse, base64, ctypes, json, os, re, signal, socket, subprocess, sys, tempfile, time
import urllib.parse, urllib.request
from pathlib import Path

APP="Makia Client Connector"
ROOT=Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())/"Makia"/"Connector"
STATE=ROOT/"state.json"
PROFILE=ROOT/"active.json"
LOG=ROOT/"connector.log"

def log(msg):
    ROOT.mkdir(parents=True,exist_ok=True)
    with LOG.open("a",encoding="utf-8") as f:f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+str(msg)+"\n")

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
    if u.scheme=="https" and u.netloc:return True
    if os.environ.get("MAKIA_ALLOW_HTTP")=="1" and u.scheme=="http" and u.hostname in {"127.0.0.1","localhost"}:return True
    return False

def redeem(controller,ticket):
    if not controller_ok(controller):raise RuntimeError("Controller must use HTTPS")
    data=json.dumps({"ticket":ticket}).encode()
    req=urllib.request.Request(controller.rstrip("/")+"/client/connector/redeem",data=data,headers={"Content-Type":"application/json","User-Agent":"MakiaClientConnector/1.4"},method="POST")
    with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode())

def transport(q):
    typ=(q.get("type") or [""])[0].lower()
    if typ=="ws":
        return {"type":"ws","path":(q.get("path") or [""])[0],"headers":{"Host":(q.get("host") or [""])[0]}} if (q.get("host") or [""])[0] else {"type":"ws","path":(q.get("path") or [""])[0]}
    if typ=="grpc":return {"type":"grpc","service_name":(q.get("serviceName") or q.get("service_name") or [""])[0]}
    if typ=="httpupgrade":return {"type":"httpupgrade","path":(q.get("path") or ["/"])[0],"host":(q.get("host") or [""])[0]}
    if typ in {"http","h2"}:return {"type":"http","path":(q.get("path") or ["/"])[0],"host":[(q.get("host") or [""])[0]] if (q.get("host") or [""])[0] else []}
    return None

def tls_for(q,host):
    sec=(q.get("security") or [""])[0].lower()
    if sec not in {"tls","reality"}:return None
    out={"enabled":True,"server_name":(q.get("sni") or [host])[0]}
    fp=(q.get("fp") or [""])[0]
    if fp:out["utls"]={"enabled":True,"fingerprint":fp}
    if sec=="reality":
        out["reality"]={"enabled":True,"public_key":(q.get("pbk") or q.get("publicKey") or [""])[0],"short_id":(q.get("sid") or q.get("shortId") or [""])[0]}
    return out

def parse_vless_or_trojan(uri):
    u=urllib.parse.urlparse(uri);q=urllib.parse.parse_qs(u.query)
    if u.scheme=="vless":
        out={"type":"vless","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"uuid":urllib.parse.unquote(u.username or "")}
        flow=(q.get("flow") or [""])[0]
        if flow:out["flow"]=flow
    else:
        out={"type":"trojan","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"password":urllib.parse.unquote(u.username or "")}
    t=tls_for(q,u.hostname or "")
    if t:out["tls"]=t
    tr=transport(q)
    if tr:out["transport"]=tr
    return out

def parse_hy2(uri):
    u=urllib.parse.urlparse(uri);q=urllib.parse.parse_qs(u.query)
    out={"type":"hysteria2","tag":"proxy","server":u.hostname,"server_port":u.port or 443,"password":urllib.parse.unquote(u.username or "")}
    out["tls"]={"enabled":True,"server_name":(q.get("sni") or [u.hostname or ""])[0],"insecure":(q.get("insecure") or ["0"])[0] in {"1","true"}}
    obfs=(q.get("obfs") or [""])[0];obfs_pass=(q.get("obfs-password") or q.get("obfs_password") or [""])[0]
    if obfs:out["obfs"]={"type":obfs,"password":obfs_pass}
    return out

def parse_vmess(uri):
    obj=json.loads(b64decode_loose(uri.split("://",1)[1]))
    out={"type":"vmess","tag":"proxy","server":obj["add"],"server_port":int(obj.get("port") or 443),"uuid":obj["id"],"security":obj.get("scy") or "auto","alter_id":int(obj.get("aid") or 0)}
    if str(obj.get("tls") or "").lower() in {"tls","reality"}:
        q={"security":[str(obj.get("tls"))],"sni":[str(obj.get("sni") or obj.get("host") or obj["add"])],"fp":[str(obj.get("fp") or "")],"pbk":[str(obj.get("pbk") or "")],"sid":[str(obj.get("sid") or "")]}
        out["tls"]=tls_for(q,obj["add"])
    typ=str(obj.get("net") or "")
    if typ:
        q={"type":[typ],"path":[str(obj.get("path") or "")],"host":[str(obj.get("host") or "")],"serviceName":[str(obj.get("path") or "")]}
        tr=transport(q)
        if tr:out["transport"]=tr
    return out

def parse_ss(uri):
    raw=uri.split("://",1)[1].split("#",1)[0]
    if "@" not in raw:
        raw=b64decode_loose(raw)
    auth,server=raw.rsplit("@",1)
    if ":" not in auth:auth=b64decode_loose(auth)
    method,password=auth.split(":",1)
    if server.startswith("["):
        host,port=server.rsplit("]:",1);host=host[1:]
    else:host,port=server.rsplit(":",1)
    return {"type":"shadowsocks","tag":"proxy","server":host,"server_port":int(port.split("?",1)[0]),"method":method,"password":urllib.parse.unquote(password)}

def parse_npvt_ssh(uri):
    obj=json.loads(b64decode_loose(uri.split("://",1)[1]))
    return {"type":"ssh","tag":"proxy","server":obj["sshHost"],"server_port":int(obj.get("sshPort") or 22),"user":obj.get("sshUsername") or "root","password":obj.get("sshPassword") or ""}

def outbound_from_share(uri):
    scheme=urllib.parse.urlparse(uri).scheme.lower()
    if scheme in {"vless","trojan"}:return parse_vless_or_trojan(uri)
    if scheme in {"hysteria2","hy2"}:return parse_hy2(uri)
    if scheme=="vmess":return parse_vmess(uri)
    if scheme=="ss":return parse_ss(uri)
    if scheme=="npvt-ssh":return parse_npvt_ssh(uri)
    raise RuntimeError("Unsupported direct-connect scheme: "+scheme)

def singbox_config(outbound):
    return {
      "log":{"level":"info","timestamp":True},
      "inbounds":[{"type":"tun","tag":"tun-in","interface_name":"Makia","address":["172.19.0.1/30"],"mtu":1400,"auto_route":True,"strict_route":True}],
      "outbounds":[outbound,{"type":"direct","tag":"direct"}],
      "route":{"auto_detect_interface":True,"final":"proxy"}
    }

def free_loopback_port():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1",0))
        return int(sock.getsockname()[1])

def singbox_browser_config(outbound,port):
    return {
      "log":{"level":"info","timestamp":True},
      "inbounds":[{
          "type":"mixed","tag":"browser-in","listen":"127.0.0.1",
          "listen_port":int(port),"set_system_proxy":False
      }],
      "outbounds":[outbound,{"type":"direct","tag":"direct"}],
      "route":{"auto_detect_interface":True,"final":"proxy"}
    }

def find_binary(names):
    here=Path(sys.executable).resolve().parent
    candidates=[]
    for n in names:
        candidates += [here/n,ROOT/n]
        p=os.environ.get("PATH","")
        for folder in p.split(os.pathsep):
            if folder:candidates.append(Path(folder)/n)
    for p in candidates:
        if p.is_file():return str(p)
    return None

def stop_current():
    if not STATE.exists():return {"ok":True,"stopped":False}
    try:state=json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:state={}
    mode=state.get("mode")
    try:
        if mode=="process":
            pid=int(state.get("pid") or 0)
            if pid:
                subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,timeout=10,check=False)
        elif mode=="wireguard":
            exe=find_binary(["wireguard.exe"])
            if exe and state.get("tunnel"):subprocess.run([exe,"/uninstalltunnelservice",state["tunnel"]],capture_output=True,timeout=20,check=False)
    finally:
        for p in [PROFILE,STATE]:
            try:p.unlink()
            except OSError:pass
    return {"ok":True,"stopped":True}

def start_process(cmd):
    flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    return p.pid

def connect_delivery(d,browser_only=False,dry_run=False):
    if not isinstance(d,dict):
        raise RuntimeError("Invalid connector delivery payload")
    engine=str(d.get("engine") or "").lower();share=str(d.get("share_link") or "")
    stop_current();ROOT.mkdir(parents=True,exist_ok=True)
    if browser_only and engine in {"wireguard","openvpn"}:
        raise RuntimeError("WireGuard and OpenVPN require Device VPN mode")
    if engine=="wireguard":
        raw=base64.b64decode(d.get("native_base64") or "") if d.get("native_base64") else share.encode()
        name=re.sub(r"[^A-Za-z0-9_-]+","-",Path(d.get("native_filename") or "makia.conf").stem)[:40] or "makia"
        path=ROOT/(name+".conf");path.write_bytes(raw)
        exe=find_binary(["wireguard.exe"])
        if dry_run:return {"mode":"wireguard","binary":bool(exe),"profile":str(path),"scope":"device"}
        if not exe:raise RuntimeError("WireGuard for Windows is not installed")
        cp=subprocess.run([exe,"/installtunnelservice",str(path)],capture_output=True,text=True,timeout=30,check=False)
        if cp.returncode!=0:raise RuntimeError((cp.stderr or cp.stdout or "WireGuard failed")[-500:])
        STATE.write_text(json.dumps({"mode":"wireguard","tunnel":name,"scope":"device"}),encoding="utf-8")
        return {"mode":"wireguard","connected":True,"scope":"device"}
    if engine=="openvpn":
        raw=base64.b64decode(d.get("native_base64") or "")
        if not raw:raise RuntimeError("OpenVPN profile missing")
        path=ROOT/"makia.ovpn";path.write_bytes(raw)
        exe=find_binary(["openvpn.exe"])
        if dry_run:return {"mode":"openvpn","binary":bool(exe),"profile":str(path),"scope":"device"}
        if not exe:raise RuntimeError("OpenVPN Connect/OpenVPN binary is not installed")
        pid=start_process([exe,"--config",str(path)])
        STATE.write_text(json.dumps({"mode":"process","pid":pid,"engine":"openvpn","scope":"device"}),encoding="utf-8")
        return {"mode":"openvpn","connected":True,"scope":"device"}
    if not share:
        raise RuntimeError("Connector delivery does not contain a supported share link")
    outbound=outbound_from_share(share)
    proxy_port=free_loopback_port() if browser_only else 0
    cfg=singbox_browser_config(outbound,proxy_port) if browser_only else singbox_config(outbound)
    PROFILE.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
    exe=find_binary(["sing-box.exe"])
    if dry_run:
        out={"mode":"sing-box","binary":bool(exe),"outbound":outbound["type"],"profile":str(PROFILE),"scope":"browser" if browser_only else "device"}
        if browser_only:out["proxy_port"]=proxy_port
        return out
    if not exe:raise RuntimeError("Makia sing-box runtime is missing")
    check=subprocess.run([exe,"check","-c",str(PROFILE)],capture_output=True,text=True,timeout=15,check=False)
    if check.returncode!=0:raise RuntimeError((check.stderr or check.stdout or "sing-box config rejected")[-800:])
    pid=start_process([exe,"run","-c",str(PROFILE)])
    time.sleep(1)
    if subprocess.run(["tasklist","/FI",f"PID eq {pid}"],capture_output=True,text=True,timeout=5).stdout.find(str(pid))<0:
        raise RuntimeError("sing-box exited during startup")
    scope="browser" if browser_only else "device"
    state={"mode":"process","pid":pid,"engine":outbound["type"],"scope":scope}
    if browser_only:state["proxy_port"]=proxy_port
    STATE.write_text(json.dumps(state),encoding="utf-8")
    result={"mode":"sing-box","protocol":outbound["type"],"connected":True,"scope":scope}
    if browser_only:result["proxy_port"]=proxy_port
    return result

def handle_uri(uri,dry_run=False,browser_only=False):
    u=urllib.parse.urlparse(uri)
    if u.scheme.lower()!="makia":raise RuntimeError("Invalid Makia URI")
    action=(u.netloc or u.path.strip("/")).lower()
    if action=="disconnect":return stop_current()
    if action!="connect":raise RuntimeError("Unknown Makia action")
    q=urllib.parse.parse_qs(u.query);controller=(q.get("controller") or [""])[0];ticket=(q.get("ticket") or [""])[0]
    if not ticket:raise RuntimeError("Missing connector ticket")
    delivery=redeem(controller,ticket)
    return connect_delivery(delivery,browser_only=browser_only,dry_run=dry_run)

def main():
    ap=argparse.ArgumentParser(prog="MakiaClientConnector")
    ap.add_argument("uri",nargs="?")
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--disconnect",action="store_true")
    ap.add_argument("--status",action="store_true")
    args=ap.parse_args()
    try:
        if args.disconnect:result=stop_current()
        elif args.status:
            result=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"connected":False}
        elif args.uri:result=handle_uri(args.uri,args.dry_run)
        else:raise RuntimeError("Makia URI is required")
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as exc:
        message=str(exc)
        log(type(exc).__name__+": "+message)
        if args.uri and not args.dry_run:
            show_error(message+"\n\nLog: "+str(LOG))
        print(json.dumps({"ok":False,"error":message},ensure_ascii=False))
        return 2

if __name__=="__main__":raise SystemExit(main())
