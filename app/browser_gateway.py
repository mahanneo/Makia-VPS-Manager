import argparse
import asyncio
import base64
import ipaddress
import json
import logging
import os
import socket
import ssl
import time
import urllib.parse
from pathlib import Path

from . import browser_gateway_store
from .db import get_setting


LOG=logging.getLogger("makia.browser_gateway")
HEADER_LIMIT=65536
IDLE_TIMEOUT=300
USAGE_FLUSH_BYTES=262144
ALLOWED_CONNECT_PORTS={80,443}
MAX_CONNECTIONS=max(32,min(int(os.getenv("MAKIA_BROWSER_GATEWAY_MAX_CONNECTIONS","512") or 512),4096))


class ProxyError(Exception):
    pass


class QuotaExceeded(ProxyError):
    pass


def _env_bool(name,default=True):
    raw=str(os.getenv(name,"1" if default else "0")).strip().lower()
    return raw in {"1","true","yes","on"}


def gateway_config():
    host=str(os.getenv("MAKIA_BROWSER_GATEWAY_HOST","") or get_setting("panel_domain","") or "").strip().lower().rstrip(".")
    port=int(os.getenv("MAKIA_BROWSER_GATEWAY_PORT","8445") or 8445)
    bind=str(os.getenv("MAKIA_BROWSER_GATEWAY_BIND","0.0.0.0") or "0.0.0.0").strip()
    enabled=_env_bool("MAKIA_BROWSER_GATEWAY_ENABLED",True)
    cert=str(os.getenv("MAKIA_BROWSER_GATEWAY_CERT","") or "").strip()
    key=str(os.getenv("MAKIA_BROWSER_GATEWAY_KEY","") or "").strip()
    if host and not cert:
        cert=f"/etc/letsencrypt/live/{host}/fullchain.pem"
    if host and not key:
        key=f"/etc/letsencrypt/live/{host}/privkey.pem"
    return {
        "enabled":enabled,
        "host":host,
        "port":port,
        "bind":bind,
        "cert":cert,
        "key":key,
        "max_connections":MAX_CONNECTIONS,
    }


def validate_config(config=None,require_files=True):
    cfg=dict(config or gateway_config())
    if not cfg["enabled"]:
        raise ProxyError("browser gateway is disabled")
    host=cfg["host"]
    if not host or len(host)>253 or any(ch.isspace() for ch in host):
        raise ProxyError("browser gateway requires a valid panel/domain hostname")
    if not (1<=int(cfg["port"])<=65535):
        raise ProxyError("browser gateway port is invalid")
    if require_files:
        if not Path(cfg["cert"]).is_file():
            raise ProxyError(f"browser gateway certificate missing: {cfg['cert']}")
        if not Path(cfg["key"]).is_file():
            raise ProxyError(f"browser gateway private key missing: {cfg['key']}")
    return cfg


def tls_context(cfg):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.options |= getattr(ssl,"OP_NO_COMPRESSION",0)
    ctx.load_cert_chain(cfg["cert"],cfg["key"])
    return ctx


def _parse_basic(value):
    raw=str(value or "")
    if not raw.lower().startswith("basic "):
        return None,None
    try:
        decoded=base64.b64decode(raw.split(" ",1)[1].strip(),validate=True).decode("utf-8")
    except Exception:
        return None,None
    if ":" not in decoded:
        return None,None
    return tuple(decoded.split(":",1))


def _split_authority(value,default_port):
    raw=str(value or "").strip()
    if not raw:
        raise ProxyError("missing proxy target")
    if raw.startswith("["):
        end=raw.find("]")
        if end<0:
            raise ProxyError("invalid IPv6 target")
        host=raw[1:end]
        rest=raw[end+1:]
        if rest.startswith(":"):
            port=int(rest[1:])
        elif rest:
            raise ProxyError("invalid IPv6 target")
        else:
            port=default_port
        return host,port
    if raw.count(":")==1:
        host,port_text=raw.rsplit(":",1)
        try:
            return host,int(port_text)
        except ValueError:
            raise ProxyError("invalid target port")
    return raw,default_port


def _valid_hostname(host):
    host=str(host or "").strip().rstrip(".")
    if not host or len(host)>253 or any(c in host for c in "\x00/\\ @"):
        return False
    try:
        host.encode("idna")
    except UnicodeError:
        return False
    return True


async def _resolve_public(host,port):
    if not _valid_hostname(host):
        raise ProxyError("invalid target host")
    try:
        literal=ipaddress.ip_address(host)
        if not literal.is_global:
            raise ProxyError("private/reserved proxy targets are blocked")
        family=socket.AF_INET6 if literal.version==6 else socket.AF_INET
        return str(literal),family
    except ValueError:
        pass

    loop=asyncio.get_running_loop()
    try:
        infos=await loop.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ProxyError("target DNS resolution failed") from exc
    candidates=[]
    for family,_,_,_,sockaddr in infos:
        ip=sockaddr[0]
        try:
            addr=ipaddress.ip_address(ip)
        except ValueError:
            continue
        if not addr.is_global:
            raise ProxyError("private/reserved proxy targets are blocked")
        candidates.append((ip,family))
    if not candidates:
        raise ProxyError("target has no public address")
    return candidates[0]


async def _open_public(host,port):
    port=int(port)
    if port not in ALLOWED_CONNECT_PORTS:
        raise ProxyError("proxy target port is not allowed")
    ip,family=await _resolve_public(host,port)
    try:
        return await asyncio.wait_for(
            asyncio.open_connection(ip,port,family=family),
            timeout=15,
        )
    except (OSError,asyncio.TimeoutError) as exc:
        raise ProxyError("target connection failed") from exc


class UsageMeter:
    def __init__(self,session_id):
        self.session_id=int(session_id)
        self.up=0
        self.down=0
        self.pending=0
        self.last_flush=time.monotonic()

    def add(self,direction,count):
        count=max(0,int(count or 0))
        if direction=="up":
            self.up+=count
        else:
            self.down+=count
        self.pending+=count

    def should_flush(self):
        return self.pending>=USAGE_FLUSH_BYTES or (self.pending and time.monotonic()-self.last_flush>=5)

    def flush(self):
        if not self.up and not self.down:
            return True
        up,down=self.up,self.down
        self.up=self.down=self.pending=0
        self.last_flush=time.monotonic()
        return browser_gateway_store.add_usage(self.session_id,up,down)


async def _relay(src,dst,meter,direction):
    while True:
        try:
            data=await asyncio.wait_for(src.read(65536),timeout=IDLE_TIMEOUT)
        except asyncio.TimeoutError:
            break
        if not data:
            break
        dst.write(data)
        await dst.drain()
        meter.add(direction,len(data))
        if meter.should_flush() and not meter.flush():
            raise QuotaExceeded("browser VPN quota/availability ended")


async def _tunnel(client_reader,client_writer,remote_reader,remote_writer,meter):
    tasks=[
        asyncio.create_task(_relay(client_reader,remote_writer,meter,"up")),
        asyncio.create_task(_relay(remote_reader,client_writer,meter,"down")),
    ]
    done,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        try:
            task.result()
        except (asyncio.CancelledError,ConnectionError,OSError):
            pass
    for task in pending:
        try:
            await task
        except (asyncio.CancelledError,ConnectionError,OSError):
            pass
    meter.flush()


def _response(status,reason,headers=None,body=b""):
    lines=[f"HTTP/1.1 {status} {reason}"]
    all_headers={"Connection":"close","Content-Length":str(len(body))}
    all_headers.update(headers or {})
    lines.extend(f"{k}: {v}" for k,v in all_headers.items())
    return ("\r\n".join(lines)+"\r\n\r\n").encode("latin1")+body


def _proxy_auth_required():
    return _response(
        407,"Proxy Authentication Required",
        {"Proxy-Authenticate":'Basic realm="Makia Browser VPN"'},
    )


def _extract_headers(raw):
    try:
        text=raw.decode("latin1")
    except UnicodeDecodeError as exc:
        raise ProxyError("invalid proxy request") from exc
    lines=text.split("\r\n")
    if not lines or len(lines[0])>8192:
        raise ProxyError("invalid request line")
    parts=lines[0].split(" ")
    if len(parts)!=3:
        raise ProxyError("invalid request line")
    method,target,version=parts
    if not version.startswith("HTTP/1."):
        raise ProxyError("unsupported proxy HTTP version")
    headers=[]
    mapping={}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            raise ProxyError("invalid proxy header")
        name,value=line.split(":",1)
        key=name.strip().lower()
        val=value.strip()
        mapping[key]=val
        headers.append((name.strip(),val))
    return method.upper(),target,version,headers,mapping


def _rewrite_http_request(method,target,version,headers):
    parsed=urllib.parse.urlsplit(target)
    if parsed.scheme.lower()!="http" or not parsed.hostname:
        raise ProxyError("only absolute HTTP URLs are accepted outside CONNECT")
    port=parsed.port or 80
    if port!=80:
        raise ProxyError("plain HTTP proxy target port is not allowed")
    path=urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    out=[f"{method} {path} {version}"]
    saw_host=False
    for name,value in headers:
        key=name.lower()
        if key in {"proxy-authorization","proxy-connection","connection"}:
            continue
        if key=="host":
            saw_host=True
        out.append(f"{name}: {value}")
    if not saw_host:
        out.append(f"Host: {parsed.netloc}")
    out.append("Connection: close")
    return parsed.hostname,port,("\r\n".join(out)+"\r\n\r\n").encode("latin1")


class Gateway:
    def __init__(self):
        self.sem=asyncio.Semaphore(MAX_CONNECTIONS)

    async def handle(self,reader,writer):
        async with self.sem:
            peer=writer.get_extra_info("peername")
            peer_ip=str(peer[0] if peer else "")[:96]
            remote_writer=None
            meter=None
            try:
                raw=await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"),timeout=15)
                if len(raw)>HEADER_LIMIT:
                    raise ProxyError("proxy headers too large")
                method,target,version,headers,mapping=_extract_headers(raw)
                username,password=_parse_basic(mapping.get("proxy-authorization",""))
                session=browser_gateway_store.validate(username,password,peer_ip)
                if not session:
                    writer.write(_proxy_auth_required())
                    await writer.drain()
                    return
                meter=UsageMeter(session["id"])

                if method=="CONNECT":
                    host,port=_split_authority(target,443)
                    if int(port)!=443:
                        raise ProxyError("CONNECT is limited to TCP/443")
                    remote_reader,remote_writer=await _open_public(host,port)
                    writer.write(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Makia/1.5\r\n\r\n")
                    await writer.drain()
                    await _tunnel(reader,writer,remote_reader,remote_writer,meter)
                    return

                if method not in {"GET","HEAD","POST","PUT","PATCH","DELETE","OPTIONS"}:
                    raise ProxyError("HTTP method is not allowed")
                host,port,forward_header=_rewrite_http_request(method,target,version,headers)
                remote_reader,remote_writer=await _open_public(host,port)
                remote_writer.write(forward_header)
                await remote_writer.drain()
                meter.add("up",len(forward_header))
                await _tunnel(reader,writer,remote_reader,remote_writer,meter)
            except asyncio.IncompleteReadError:
                pass
            except QuotaExceeded:
                LOG.info("browser VPN quota ended for %s",peer_ip)
            except (asyncio.LimitOverrunError,ProxyError,ValueError) as exc:
                LOG.info("proxy request rejected from %s: %s",peer_ip,str(exc))
                try:
                    writer.write(_response(403,"Forbidden",body=b"Makia Browser VPN request rejected"))
                    await writer.drain()
                except Exception:
                    pass
            except Exception:
                LOG.exception("browser gateway connection failure from %s",peer_ip)
            finally:
                if meter:
                    try:
                        meter.flush()
                    except Exception:
                        pass
                if remote_writer:
                    remote_writer.close()
                    try:
                        await remote_writer.wait_closed()
                    except Exception:
                        pass
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass


async def serve():
    browser_gateway_store.init_browser_gateway_db()
    cfg=validate_config()
    gateway=Gateway()
    server=await asyncio.start_server(
        gateway.handle,cfg["bind"],cfg["port"],
        ssl=tls_context(cfg),limit=HEADER_LIMIT,
        reuse_address=True,
    )
    sockets=", ".join(str(sock.getsockname()) for sock in (server.sockets or []))
    LOG.info("Makia Browser Gateway listening on %s for host %s",sockets,cfg["host"])
    async with server:
        await server.serve_forever()


def main():
    parser=argparse.ArgumentParser(prog="makia-browser-gateway")
    parser.add_argument("--check-config",action="store_true")
    args=parser.parse_args()
    logging.basicConfig(
        level=os.getenv("MAKIA_BROWSER_GATEWAY_LOG_LEVEL","INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.check_config:
        cfg=gateway_config()
        try:
            validate_config(cfg)
            result={"ok":True,**cfg}
        except Exception as exc:
            result={"ok":False,"error":str(exc),**cfg}
        print(json.dumps(result,separators=(",",":")))
        return 0 if result["ok"] else 2
    try:
        asyncio.run(serve())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        LOG.error("browser gateway startup failed: %s",exc)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
