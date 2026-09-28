import json
import os
import subprocess
import http.client
import ssl
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
    class Cover(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b"cover")
        def log_message(self,*args): pass
    cover=ThreadingHTTPServer(("127.0.0.1",0),Cover)
    cover_tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    cover_tls.load_cert_chain(str(cert_path),str(key_path))
    cover.socket=cover_tls.wrap_socket(cover.socket,server_side=True)
    cover_thread=threading.Thread(target=cover.serve_forever,daemon=True)
    cover_thread.start()
    original_tls=protocol_ops._xray_materialize_tls
    protocol_ops._xray_materialize_tls=lambda domain:(cert_path,key_path)
    try:
        validate_guided_matrix(binary,root,cert_path,key_path)
        validate_inbound_builder_profiles(binary,root,cert_path,key_path)
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
            binary,"vless","tcp","reality","/","test.example.com",f"127.0.0.1:{cover.server_port}",
        )
        data["inbounds"].append({
            "tag":"makia-ci-simple","listen":"127.0.0.1","port":21008,"protocol":"vless",
            "settings":{"clients":[{"id":simple_id,"email":"ci-simple","level":0,"flow":"xtls-rprx-vision"}],"decryption":"none"},
            "streamSettings":simple_stream,
        })

        # Manual/Expert profile: VLESS RAW with security=none.
        # This is intentionally allowed by Makia expert mode and must carry
        # real traffic, not merely pass JSON validation.
        manual_id=str(uuid.uuid4())
        manual_stream,_=protocol_ops._build_xray_stream(
            binary,"vless","tcp","none","/","","",
        )
        data["inbounds"].append({
            "tag":"makia-ci-manual-none","listen":"127.0.0.1","port":21009,"protocol":"vless",
            "settings":{"clients":[{"id":manual_id,"email":"ci-manual-none","level":0}],"decryption":"none"},
            "streamSettings":manual_stream,
        })

        # VMess + WebSocket
        vmess_stream,_=protocol_ops._build_xray_stream(binary,"vmess","ws","none","/vmess","","")
        data["inbounds"].append({
            "tag":"makia-ci-vmess","listen":"127.0.0.1","port":21002,"protocol":"vmess",
            "settings":{"clients":[{"id":str(uuid.uuid4()),"email":"ci-vmess","level":0}]},
            "streamSettings":vmess_stream,
        })

        # Additional guided transport/security combinations: the UI only
        # offers combinations that this exact Xray Core can validate.
        extra_profiles=[
            ("vless","grpc","reality","/grpc","www.microsoft.com","www.microsoft.com:443",21011),
            ("vless","ws","tls","/vless-ws","test.example.com","",21012),
            ("vless","httpupgrade","tls","/vless-up","test.example.com","",21013),
            ("vless","kcp","none","makia-kcp","","",21014),
            ("vmess","grpc","tls","/vm-grpc","test.example.com","",21015),
            ("vmess","xhttp","none","/vm-xhttp","","",21016),
        ]
        for idx,(proto,transport,security,path_value,sni,target_dest,port) in enumerate(extra_profiles):
            stream,_=protocol_ops._build_xray_stream(binary,proto,transport,security,path_value,sni,target_dest)
            cid=str(uuid.uuid4())
            settings={"clients":[{"id":cid,"email":f"ci-extra-{idx}","level":0}]}
            if proto=="vless":
                settings["decryption"]="none"
            data["inbounds"].append({
                "tag":f"makia-ci-extra-{idx}","listen":"127.0.0.1","port":port,"protocol":proto,
                "settings":settings,"streamSettings":stream,
            })

        # Trojan WebSocket/gRPC + TLS.
        for idx,transport in enumerate(("ws","grpc"),start=18):
            stream,_=protocol_ops._build_xray_stream(binary,"trojan",transport,"tls","/trojan","test.example.com","")
            data["inbounds"].append({
                "tag":f"makia-ci-trojan-{transport}","listen":"127.0.0.1","port":21000+idx,"protocol":"trojan",
                "settings":{"clients":[{"password":f"ci-trojan-{transport}","email":f"ci-trojan-{transport}","level":0}]},
                "streamSettings":stream,
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
            verify_manual_none_connection(binary,target,root,manual_id)
        finally:
            target.unlink(missing_ok=True)

        assert reality_meta["public_key"]
        assert reality_meta["short_id"]
        print("Xray 26.3.27 guided matrix PASS: VLESS RAW/WS/gRPC/HTTPUpgrade/XHTTP/mKCP; VMess WS/gRPC/XHTTP; Trojan TCP/WS/gRPC; Shadowsocks; Hysteria2; HTTP; SOCKS5")
    finally:
        cover.shutdown();cover.server_close()
        protocol_ops._xray_materialize_tls=original_tls



def validate_inbound_builder_profiles(binary,root,cert_path,key_path):
    """Validate the structured RC5 form fields against the pinned Xray Core."""
    cases=[
        ("vless","tcp","none",{
            "path":"/raw","header_type":"http","http_host":"example.com","http_path":"/raw",
            "tcp_fast_open":True,"tcp_no_delay":True,"domain_strategy":"UseIP",
            "sniffing_enabled":True,
        }),
        ("vless","ws","tls",{
            "path":"/ws","host":"test.example.com","heartbeat_period":10,
            "headers":{"X-Makia":"1"},"server_name":"test.example.com","alpn":"h2,http/1.1",
        }),
        ("vless","grpc","reality",{
            "service_name":"makia-grpc","authority":"test.example.com","multi_mode":True,
            "server_name":"www.microsoft.com","reality_dest":"www.microsoft.com:443",
            "fingerprint":"chrome","spider_x":"/",
        }),
        ("vless","xhttp","reality",{
            "path":"/xhttp","host":"test.example.com","xhttp_mode":"auto","x_padding_bytes":"100-1000",
            "server_name":"www.microsoft.com","reality_dest":"www.microsoft.com:443",
        }),
        ("vless","kcp","none",{
            "mtu":1350,"tti":20,"uplink_capacity":5,"downlink_capacity":20,
            "cwnd_multiplier":1,"max_sending_window":2097152,
        }),
        ("trojan","tcp","reality",{
            "server_name":"www.microsoft.com","reality_dest":"www.microsoft.com:443",
            "fingerprint":"chrome",
        }),
        ("shadowsocks","tcp","tls",{
            "server_name":"test.example.com","alpn":"h2,http/1.1",
        }),
    ]
    checked=[]
    for idx,(protocol,transport,security,options) in enumerate(cases):
        normalized_transport,normalized_security=protocol_ops._xray_builder_validate_combo(
            protocol,transport,security
        )
        stream,meta=protocol_ops._xray_builder_stream(
            binary,protocol,normalized_transport,normalized_security,options
        )
        credential=protocol_ops._xray_builder_credential(protocol)
        settings,_=protocol_ops._xray_builder_client(
            protocol,f"builder-{idx}",credential,
            "xtls-rprx-vision" if protocol=="vless" and transport=="tcp" and security=="reality" else "",
            "aes-128-gcm",
        )
        inbound={
            "tag":f"builder-{idx}","listen":"127.0.0.1","port":24000+idx,
            "protocol":"hysteria" if protocol=="hysteria2" else protocol,
            "settings":settings,"streamSettings":stream,
            "sniffing":protocol_ops._xray_builder_sniffing(options),
        }
        data=protocol_ops._xray_default_config(root/f"builder-{idx}.json")
        data["inbounds"]=[inbound]
        target=protocol_ops._xray_temp_json_path(root/f"builder-{idx}.json","builder-core")
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        try:
            protocol_ops._xray_test_config(binary,target)
        except Exception as exc:
            raise AssertionError(
                f"Xray 26.3.27 rejected inbound builder profile {protocol}/{transport}/{security}: {exc}"
            ) from exc
        finally:
            target.unlink(missing_ok=True)
        if security=="reality":
            assert meta.get("public_key") and meta.get("short_id")
        checked.append(f"{protocol}/{transport}/{security}")
    print("Xray Inbound Center structured options PASS: "+", ".join(checked))


def validate_guided_matrix(binary,root,cert_path,key_path):
    """Validate every guided transport/security pair against the pinned Core.

    The public compatibility table is intentionally broader than a Cartesian
    product for VLESS: REALITY is only valid with RAW, gRPC and XHTTP. Every
    pair the UI/backend can actually commit is syntax-checked by Xray 26.3.27.
    """
    expected={
        "vless":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["reality","tls","none"]},
        "vmess":{"transports":["tcp","ws","grpc","httpupgrade","xhttp","kcp"],"security":["none","tls"]},
        "trojan":{"transports":["tcp","ws","grpc","httpupgrade","xhttp"],"security":["tls"]},
        "shadowsocks":{"transports":["tcp"],"security":["none"]},
        "hysteria2":{"transports":["hysteria"],"security":["tls"]},
        "http":{"transports":["tcp"],"security":["none"]},
        "socks":{"transports":["tcp"],"security":["none"]},
    }
    assert protocol_ops.xray_guided_compatibility()==expected

    checked=[]
    rejected=[]
    port=23000
    for protocol,spec in expected.items():
        for transport in spec["transports"]:
            for security in spec["security"]:
                label=f"{protocol}/{transport}/{security}"
                if security=="reality" and transport not in {"tcp","grpc","xhttp"}:
                    try:
                        protocol_ops._validate_xray_guided_combo(protocol,transport,security)
                    except protocol_ops.ProtocolError:
                        rejected.append(label)
                        continue
                    raise AssertionError(f"guided matrix accepted invalid REALITY pair: {label}")

                normalized_transport,normalized_security=protocol_ops._validate_xray_guided_combo(
                    protocol,transport,security
                )
                data=protocol_ops._xray_default_config(root/f"matrix-{port}.json")
                cid=str(uuid.uuid4())

                if protocol=="hysteria2":
                    stream={
                        "method":"hysteria","security":"tls",
                        "hysteriaSettings":{"version":2},
                        "tlsSettings":{
                            "serverName":"test.example.com","alpn":["h3"],
                            "certificates":[{"certificateFile":str(cert_path),"keyFile":str(key_path)}],
                        },
                    }
                    inbound_protocol="hysteria"
                    settings={"version":2,"users":[{"auth":"matrix-hy2","email":f"matrix-{port}","level":0}]}
                elif protocol=="http":
                    stream={"method":"raw","security":"none"}
                    inbound_protocol="http"
                    settings={"accounts":[{"user":"matrix","pass":"matrix-secret"}]}
                elif protocol=="socks":
                    stream={"method":"raw","security":"none"}
                    inbound_protocol="socks"
                    settings={"auth":"password","accounts":[{"user":"matrix","pass":"matrix-secret"}],"udp":True,"ip":"127.0.0.1"}
                else:
                    sni="www.microsoft.com" if security=="reality" else ("test.example.com" if security=="tls" else "")
                    target="www.microsoft.com:443" if security=="reality" else ""
                    stream,_=protocol_ops._build_xray_stream(
                        binary,protocol,normalized_transport,normalized_security,
                        "/matrix",sni,target,
                    )
                    inbound_protocol=protocol
                    if protocol in {"vless","vmess"}:
                        client={"id":cid,"email":f"matrix-{port}","level":0}
                        settings={"clients":[client]}
                        if protocol=="vless":
                            settings["decryption"]="none"
                            if security=="reality" and stream.get("method")=="raw":
                                client["flow"]="xtls-rprx-vision"
                    elif protocol=="trojan":
                        settings={"clients":[{"password":"matrix-trojan","email":f"matrix-{port}","level":0}]}
                    elif protocol=="shadowsocks":
                        settings={"method":"aes-128-gcm","password":"matrix-shadow","network":"tcp,udp"}
                    else:
                        raise AssertionError(f"unhandled guided protocol: {protocol}")

                data["inbounds"]=[{
                    "tag":f"matrix-{port}",
                    "listen":"127.0.0.1",
                    "port":port,
                    "protocol":inbound_protocol,
                    "settings":settings,
                    "streamSettings":stream,
                }]
                target_path=protocol_ops._xray_temp_json_path(root/f"matrix-{port}.json","core")
                target_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                try:
                    protocol_ops._xray_test_config(binary,target_path)
                except Exception as exc:
                    raise AssertionError(f"Xray 26.3.27 rejected guided pair {label}: {exc}") from exc
                finally:
                    target_path.unlink(missing_ok=True)
                checked.append(label)
                port+=1

    assert set(rejected)=={
        "vless/ws/reality","vless/httpupgrade/reality","vless/kcp/reality",
    }
    print(f"Xray guided compatibility exhaustive PASS: {len(checked)} valid pairs; {len(rejected)} invalid REALITY pairs rejected")


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




def verify_manual_none_connection(binary,server_config,root,client_id):
    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"makia-vless-none-connected")
        def log_message(self,*args): pass

    target=ThreadingHTTPServer(("127.0.0.1",0),Target)
    thread=threading.Thread(target=target.serve_forever,daemon=True)
    thread.start()
    client_config=root/"client-none.json"
    client_config.write_text(json.dumps({
        "log":{"loglevel":"debug"},
        "inbounds":[{"listen":"127.0.0.1","port":21020,"protocol":"http","settings":{}}],
        "outbounds":[{"protocol":"vless","settings":{"vnext":[{
            "address":"127.0.0.1","port":21009,
            "users":[{"id":client_id,"encryption":"none"}],
        }]},"streamSettings":{"method":"raw","security":"none"}}],
    }),encoding="utf-8")
    protocol_ops._xray_test_config(binary,client_config)
    server_log=root/"server-none.log"
    client_log=root/"client-none.log"
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
                        conn=http.client.HTTPConnection("127.0.0.1",21020,timeout=2)
                        conn.request("GET",f"http://127.0.0.1:{target.server_port}/")
                        response=conn.getresponse()
                        body=response.read()
                        conn.close()
                        if response.status==200 and body==b"makia-vless-none-connected":
                            print("VLESS RAW security=none client handshake and traffic PASS")
                            return
                        error=f"HTTP {response.status}: {body[:100]!r}"
                    except (OSError,http.client.HTTPException) as exc:
                        error=str(exc)
                    time.sleep(.25)
                raise AssertionError(f"VLESS none traffic failed: {error}; server={server_log.read_text()[-1500:]}; client={client_log.read_text()[-1500:]}")
            finally:
                client.terminate();server.terminate()
                client.wait(timeout=5);server.wait(timeout=5)
    finally:
        target.shutdown();target.server_close()


if __name__=="__main__":
    main()
