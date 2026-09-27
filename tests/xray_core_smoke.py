import json
import os
import subprocess
import http.client
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app import protocol_ops


def make_test_certificate(root:Path):
    cert_path=root/"cert.pem"
    key_path=root/"key.pem"
    p=subprocess.run([
        "openssl","req","-x509","-newkey","rsa:2048","-nodes",
        "-keyout",str(key_path),"-out",str(cert_path),"-days","1",
        "-subj","/CN=test.example.com",
        "-addext","subjectAltName=DNS:test.example.com",
    ],text=True,capture_output=True,check=False)
    if p.returncode!=0:
        raise RuntimeError((p.stderr or p.stdout or "openssl certificate generation failed").strip())
    return cert_path,key_path


def main():
    binary=os.environ["XRAY_BIN"]
    version=protocol_ops._run([binary,"version"],timeout=10).splitlines()[0]
    print(version)
    assert "26.3.27" in version

    root=Path("/tmp/makia-xray-matrix")
    root.mkdir(parents=True,exist_ok=True)
    cert_path,key_path=make_test_certificate(root)
    original_tls=protocol_ops._xray_materialize_tls
    protocol_ops._xray_materialize_tls=lambda domain:(cert_path,key_path)
    try:
        data=protocol_ops._ensure_xray_stats(
            protocol_ops._xray_default_config(Path("/tmp/makia-xray-config.json"))
        )
        data["log"]["loglevel"]="debug"

        # VLESS + XHTTP + REALITY
        reality_stream,reality_meta=protocol_ops._build_xray_stream(
            binary,"vless","xhttp","reality","/makia","www.microsoft.com","www.microsoft.com:443",
        )
        data["inbounds"].append({
            "tag":"makia-ci-vless","listen":"127.0.0.1","port":21001,"protocol":"vless",
            "settings":{"clients":[{"id":str(uuid.uuid4()),"email":"ci-vless","level":0}],"decryption":"none"},
            "streamSettings":reality_stream,
            "sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"routeOnly":True},
        })

        # Default simple profile: exercise a real client handshake and routed HTTP request.
        simple_id=str(uuid.uuid4())
        simple_stream,simple_meta=protocol_ops._build_xray_stream(
            binary,"vless","tcp","reality","/","www.microsoft.com","www.microsoft.com:443",
        )
        data["inbounds"].append({
            "tag":"makia-ci-simple","listen":"127.0.0.1","port":21008,"protocol":"vless",
            "settings":{"clients":[{"id":simple_id,"email":"ci-simple","level":0,"flow":"xtls-rprx-vision"}],"decryption":"none"},
            "streamSettings":simple_stream,
        })

        # VMess + WebSocket
        vmess_stream,_=protocol_ops._build_xray_stream(binary,"vmess","ws","none","/vmess","","")
        data["inbounds"].append({
            "tag":"makia-ci-vmess","listen":"127.0.0.1","port":21002,"protocol":"vmess",
            "settings":{"clients":[{"id":str(uuid.uuid4()),"email":"ci-vmess","level":0}]},
            "streamSettings":vmess_stream,
        })

        # Trojan + TLS using a real generated certificate.
        trojan_stream,_=protocol_ops._build_xray_stream(binary,"trojan","tcp","tls","/","test.example.com","")
        data["inbounds"].append({
            "tag":"makia-ci-trojan","listen":"127.0.0.1","port":21003,"protocol":"trojan",
            "settings":{"clients":[{"password":"ci-trojan-secret","email":"ci-trojan","level":0}]},
            "streamSettings":trojan_stream,
        })

        # Shadowsocks
        ss_stream,_=protocol_ops._build_xray_stream(binary,"shadowsocks","tcp","none","/","","")
        data["inbounds"].append({
            "tag":"makia-ci-ss","listen":"127.0.0.1","port":21004,"protocol":"shadowsocks",
            "settings":{"method":"aes-128-gcm","password":"ci-shadow-secret","network":"tcp,udp"},
            "streamSettings":ss_stream,
        })

        # Hysteria2 + TLS
        data["inbounds"].append({
            "tag":"makia-ci-hysteria2","listen":"127.0.0.1","port":21005,"protocol":"hysteria",
            "settings":{"version":2,"users":[{"auth":"ci-hy2-secret","email":"ci-hy2","level":0}]},
            "streamSettings":{
                "method":"hysteria","security":"tls",
                "hysteriaSettings":{"version":2},
                "tlsSettings":{
                    "serverName":"test.example.com","alpn":["h3"],
                    "certificates":[{"certificateFile":str(cert_path),"keyFile":str(key_path)}],
                },
            },
        })

        # HTTP proxy.
        data["inbounds"].append({
            "tag":"makia-ci-http","listen":"127.0.0.1","port":21006,"protocol":"http",
            "settings":{"accounts":[{"user":"ci-http","pass":"ci-http-secret"}]},
            "streamSettings":{"method":"raw","security":"none"},
        })

        # SOCKS5 proxy.
        data["inbounds"].append({
            "tag":"makia-ci-socks","listen":"127.0.0.1","port":21007,"protocol":"socks",
            "settings":{"auth":"password","accounts":[{"user":"ci-socks","pass":"ci-socks-secret"}],"udp":True,"ip":"127.0.0.1"},
            "streamSettings":{"method":"raw","security":"none"},
        })

        target=protocol_ops._xray_temp_json_path(Path("/tmp/config.json"),"runtime-matrix")
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        try:
            protocol_ops._xray_test_config(binary,target)
            verify_simple_connection(binary,target,root,simple_id,simple_meta)
        finally:
            target.unlink(missing_ok=True)

        assert reality_meta["public_key"]
        assert reality_meta["short_id"]
        print("Xray 26.3.27 guided protocol matrix PASS: VLESS, VMess, Trojan, Shadowsocks, Hysteria2, HTTP, SOCKS5")
    finally:
        protocol_ops._xray_materialize_tls=original_tls


def verify_simple_connection(binary,server_config,root,client_id,meta):
    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"makia-vless-reality-connected")
        def log_message(self,*args): pass

    target=ThreadingHTTPServer(("127.0.0.1",0),Target)
    thread=threading.Thread(target=target.serve_forever,daemon=True)
    thread.start()
    client_config=root/"client.json"
    client_config.write_text(json.dumps({
        "log":{"loglevel":"debug"},
        "inbounds":[{"listen":"127.0.0.1","port":21010,"protocol":"http","settings":{}}],
        "outbounds":[{"protocol":"vless","settings":{"vnext":[{
            "address":"127.0.0.1","port":21008,
            "users":[{"id":client_id,"encryption":"none","flow":"xtls-rprx-vision"}],
        }]},"streamSettings":{"method":"raw","security":"reality","realitySettings":{
            "serverName":meta["server_name"],"fingerprint":"chrome",
            "password":meta["public_key"],"shortId":meta["short_id"],
        }}}],
    }),encoding="utf-8")
    protocol_ops._xray_test_config(binary,client_config)
    server_log=root/"server.log"
    client_log=root/"client.log"
    try:
        with server_log.open("w") as srv_log,client_log.open("w") as cli_log:
            server=subprocess.Popen([binary,"run","-config",str(server_config)],stdout=srv_log,stderr=subprocess.STDOUT)
            client=subprocess.Popen([binary,"run","-config",str(client_config)],stdout=cli_log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+12
                error=None
                while time.monotonic()<deadline:
                    if server.poll() is not None or client.poll() is not None:
                        break
                    try:
                        conn=http.client.HTTPConnection("127.0.0.1",21010,timeout=2)
                        conn.request("GET",f"http://127.0.0.1:{target.server_port}/")
                        response=conn.getresponse()
                        body=response.read()
                        conn.close()
                        if response.status==200 and body==b"makia-vless-reality-connected":
                            print("VLESS RAW REALITY client handshake and traffic PASS")
                            return
                        error=f"HTTP {response.status}: {body[:100]!r}"
                    except (OSError,http.client.HTTPException) as exc:
                        error=str(exc)
                    time.sleep(.25)
                raise AssertionError(f"VLESS client traffic failed: {error}; server={server_log.read_text()[-1500:]}; client={client_log.read_text()[-1500:]}")
            finally:
                client.terminate();server.terminate()
                client.wait(timeout=5);server.wait(timeout=5)
    finally:
        target.shutdown();target.server_close()


if __name__=="__main__":
    main()
