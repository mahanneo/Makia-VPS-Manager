#!/usr/bin/env python3
import asyncio
import base64
import ipaddress
import os
import signal
import socket
import ssl
import sys
import time
import urllib.parse
from pathlib import Path

from app import client_store
from app.db import get_setting

APP=Path("/opt/makia-vps-manager")
DEFAULT_PORT=int(os.getenv("MAKIA_BROWSER_GATEWAY_PORT","9443"))
ALLOWED_PORTS={
    int(p.strip()) for p in os.getenv("MAKIA_BROWSER_GATEWAY_ALLOWED_PORTS","80,443").split(",")
    if p.strip().isdigit()
}
MAX_HEADER=64*1024
CONNECT_TIMEOUT=12
IDLE_TIMEOUT=120
MAX_CONNECTIONS_PER_ACCOUNT=max(4,int(os.getenv("MAKIA_BROWSER_GATEWAY_MAX_CONNECTIONS","32")))
_active={}
_stopping=False


def _peer_ip(writer):
    peer=writer.get_extra_info("peername")
    return str(peer[0]) if isinstance(peer,tuple) and peer else ""


def _parse_basic(value):
    value=str(value or "").strip()
    if not value.lower().startswith("basic "):
        return None,None
    try:
        raw=base64.b64decode(value.split(" ",1)[1],validate=True).decode("utf-8")
    except Exception:
        return None,None
    if ":" not in raw:
        return None,None
    return raw.split(":",1)


def _public_ip(value):
    try:
        ip=ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(ip.is_global)


async def _resolve_public(host,port):
    loop=asyncio.get_running_loop()
    try:
        infos=await asyncio.wait_for(
            loop.getaddrinfo(host,port,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP),
            timeout=CONNECT_TIMEOUT,
        )
    except Exception:
        return []
    out=[]
    seen=set()
    for family,stype,proto,canonname,sockaddr in infos:
        ip=str(sockaddr[0])
        if ip in seen or not _public_ip(ip):
            continue
        seen.add(ip)
        out.append((family,ip,port))
    return out


async def _connect_public(host,port):
    if int(port) not in ALLOWED_PORTS:
        raise PermissionError("destination port is not allowed")
    targets=await _resolve_public(host,port)
    if not targets:
        raise PermissionError("destination does not resolve to a public address")
    last=None
    for family,ip,p in targets:
        try:
            return await asyncio.wait_for(asyncio.open_connection(ip,p,family=family),timeout=CONNECT_TIMEOUT)
        except Exception as exc:
            last=exc
    raise ConnectionError(str(last or "destination unavailable"))


def _proxy_error(writer,status,message,auth=False):
    headers=[
        f"HTTP/1.1 {status}\r\n",
        "Connection: close\r\n",
        "Content-Type: text/plain; charset=utf-8\r\n",
        f"Content-Length: {len(message.encode('utf-8'))}\r\n",
    ]
    if auth:
        headers.append('Proxy-Authenticate: Basic realm="Makia Browser Gateway"\r\n')
    headers.append("\r\n")
    writer.write("".join(headers).encode("ascii")+message.encode("utf-8"))


async def _read_headers(reader):
    data=await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"),timeout=IDLE_TIMEOUT)
    if len(data)>MAX_HEADER:
        raise ValueError("request headers too large")
    return data


def _parse_request(data):
    head=data.decode("iso-8859-1")
    lines=head.split("\r\n")
    parts=lines[0].split(" ",2)
    if len(parts)!=3:
        raise ValueError("invalid proxy request")
    method,target,version=parts
    headers=[]
    auth=""
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            raise ValueError("invalid request header")
        name,value=line.split(":",1)
        lname=name.strip().lower()
        if lname=="proxy-authorization":
            auth=value.strip()
            continue
        if lname in {"proxy-connection","connection"}:
            continue
        headers.append((name.strip(),value.lstrip()))
    return method.upper(),target,version,headers,auth


async def _relay(reader,writer,limit,usage):
    chunk_total=0
    try:
        while True:
            data=await asyncio.wait_for(reader.read(65536),timeout=IDLE_TIMEOUT)
            if not data:
                break
            if limit and usage[0]+len(data)>limit:
                allowed=max(0,limit-usage[0])
                if allowed:
                    writer.write(data[:allowed])
                    await writer.drain()
                    usage[0]+=allowed
                    chunk_total+=allowed
                break
            writer.write(data)
            await writer.drain()
            usage[0]+=len(data)
            chunk_total+=len(data)
    except (asyncio.TimeoutError,ConnectionError,BrokenPipeError,asyncio.IncompleteReadError):
        pass
    finally:
        return chunk_total


async def _serve_tunnel(client_reader,client_writer,target_reader,target_writer,account_id,limit):
    usage=[0]
    try:
        await asyncio.gather(
            _relay(client_reader,target_writer,limit,usage),
            _relay(target_reader,client_writer,limit,usage),
        )
    finally:
        if usage[0]:
            try:
                client_store.add_browser_usage(account_id,usage[0])
            except Exception:
                pass
        for w in (target_writer,client_writer):
            try:
                w.close()
                await w.wait_closed()
            except Exception:
                pass


async def _handle(reader,writer):
    account_id=0
    try:
        raw=await _read_headers(reader)
        method,target,version,headers,auth_header=_parse_request(raw)
        username,password=_parse_basic(auth_header)
        auth=client_store.browser_proxy_auth(username,password,_peer_ip(writer))
        if not auth:
            _proxy_error(writer,"407 Proxy Authentication Required","Proxy authentication required.",True)
            await writer.drain()
            return

        account_id=int(auth["account_id"])
        current=_active.get(account_id,0)
        if current>=MAX_CONNECTIONS_PER_ACCOUNT:
            _proxy_error(writer,"429 Too Many Requests","Too many browser connections.")
            await writer.drain()
            return
        _active[account_id]=current+1

        account=client_store.get_account(account_id)
        used=client_store.account_usage_bytes(account_id)
        quota=int((account or {}).get("quota_bytes") or 0)
        remaining=max(0,quota-used) if quota else 0
        if quota and remaining<=0:
            _proxy_error(writer,"403 Forbidden","Traffic quota exhausted.")
            await writer.drain()
            return

        if method=="CONNECT":
            if ":" not in target:
                raise ValueError("CONNECT target must include port")
            host,port_s=target.rsplit(":",1)
            host=host.strip("[]")
            port=int(port_s)
            target_reader,target_writer=await _connect_public(host,port)
            writer.write(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Makia/1.5\r\n\r\n")
            await writer.drain()
            await _serve_tunnel(reader,writer,target_reader,target_writer,account_id,remaining)
            return

        url=urllib.parse.urlsplit(target)
        if url.scheme.lower()!="http" or not url.hostname:
            _proxy_error(writer,"400 Bad Request","Only HTTP requests and HTTPS CONNECT are supported.")
            await writer.drain()
            return
        port=url.port or 80
        target_reader,target_writer=await _connect_public(url.hostname,port)
        path=urllib.parse.urlunsplit(("", "", url.path or "/", url.query, ""))
        target_writer.write(f"{method} {path} {version}\r\n".encode("ascii"))
        saw_host=False
        for name,value in headers:
            lname=name.lower()
            if lname=="host":
                saw_host=True
            target_writer.write(f"{name}: {value}\r\n".encode("iso-8859-1"))
        if not saw_host:
            host_header=url.hostname if port==80 else f"{url.hostname}:{port}"
            target_writer.write(f"Host: {host_header}\r\n".encode("ascii"))
        target_writer.write(b"Connection: close\r\n\r\n")
        await target_writer.drain()
        await _serve_tunnel(reader,writer,target_reader,target_writer,account_id,remaining)
    except asyncio.LimitOverrunError:
        _proxy_error(writer,"431 Request Header Fields Too Large","Headers too large.")
        await writer.drain()
    except PermissionError:
        _proxy_error(writer,"403 Forbidden","Destination is not allowed.")
        await writer.drain()
    except (ValueError,urllib.parse.PortNotFoundError):
        _proxy_error(writer,"400 Bad Request","Invalid proxy request.")
        await writer.drain()
    except Exception:
        try:
            _proxy_error(writer,"502 Bad Gateway","Proxy destination unavailable.")
            await writer.drain()
        except Exception:
            pass
    finally:
        if account_id:
            _active[account_id]=max(0,_active.get(account_id,1)-1)
            if not _active[account_id]:
                _active.pop(account_id,None)
        if not writer.is_closing():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


def _tls_material():
    domain=str(get_setting("panel_domain","") or "").strip().lower()
    if not domain:
        return None
    cert=Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    key=Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
    if not cert.is_file() or not key.is_file():
        return None
    return domain,cert,key,cert.resolve(),key.resolve()


async def run():
    global _stopping
    server=None
    current=None
    while not _stopping:
        material=_tls_material()
        signature=tuple(str(x) for x in material) if material else None
        if signature!=current:
            if server:
                server.close()
                await server.wait_closed()
                server=None
            current=signature
            if material:
                domain,cert,key,cert_real,key_real=material
                ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.minimum_version=ssl.TLSVersion.TLSv1_2
                ctx.load_cert_chain(str(cert),str(key))
                server=await asyncio.start_server(
                    _handle,"0.0.0.0",DEFAULT_PORT,ssl=ctx,
                    limit=MAX_HEADER,
                    reuse_address=True,
                )
                print(f"Makia Browser Gateway listening on {domain}:{DEFAULT_PORT}",flush=True)
            else:
                print("Makia Browser Gateway waiting for panel domain + Let's Encrypt certificate",flush=True)
        await asyncio.sleep(15)
    if server:
        server.close()
        await server.wait_closed()


def main():
    loop=asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    def stop():
        global _stopping
        _stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT):
        try:
            loop.add_signal_handler(sig,stop)
        except NotImplementedError:
            pass
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


if __name__=="__main__":
    main()
