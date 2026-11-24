import ipaddress
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from .db import connect, audit, protocol_client_by_subscription
from . import network_services

router=APIRouter()

def _source_ip(request):
    raw=(request.client.host if request.client else "").strip()
    try:
        peer=ipaddress.ip_address(raw)
    except ValueError:
        raise HTTPException(400,"unable to identify public client IP")
    if peer.is_loopback:
        raw=(request.headers.get("x-real-ip") or "").split(",",1)[0].strip()
        if not raw:
            raw=(request.headers.get("x-forwarded-for") or "").split(",",1)[0].strip()
    try:
        addr=ipaddress.ip_address(raw)
    except ValueError:
        raise HTTPException(400,"invalid public client IP")
    if addr.version!=4 or not addr.is_global:
        raise HTTPException(400,"gaming DNS currently requires a public IPv4 connection")
    return addr.compressed

def _active_ips():
    now=int(time.time())
    with connect() as con:
        rows=con.execute(
            "SELECT DISTINCT d.ip FROM dns_client_ips d JOIN protocol_clients p ON p.id=d.client_id "
            "WHERE p.enabled=1 AND (p.expire_at=0 OR p.expire_at>?) "
            "AND (p.quota_bytes=0 OR p.used_up_bytes+p.used_down_bytes<p.quota_bytes)",(now,)
        ).fetchall()
    return list(dict.fromkeys(r["ip"] for r in rows if r["ip"]))

def _apply():
    state=network_services._dns_state()
    # Subscription registrations are the source of truth; inactive or changed-IP clients are removed.
    allowed=_active_ips()
    if not allowed:
        return network_services.configure_dns(mode="private",upstream=state.get("upstream") or "cloudflare")
    return network_services.configure_dns(
        mode="public",upstream=state.get("upstream") or "cloudflare",
        allowed_cidrs=allowed,
        public_address=state.get("public_address") or network_services._default_public_ipv4()
    )

def _active_subscription(subscription_id):
    row=protocol_client_by_subscription(subscription_id)
    if not row:
        raise HTTPException(404,"subscription not found")
    from .main import _subscription_snapshot
    snap=_subscription_snapshot(row)
    if not snap.get("enabled") or snap.get("expired") or snap.get("quota_exhausted"):
        raise HTTPException(403,"subscription is inactive")
    return row

@router.post("/client/{subscription_id}/dns/register")
def register(subscription_id:str,request:Request):
    if request.headers.get("x-makia-dns-register")!="1":
        raise HTTPException(403,"invalid DNS registration request")
    row=_active_subscription(subscription_id)
    ip=_source_ip(request); now=int(time.time())
    with connect() as con:
        old=con.execute("SELECT ip,updated_at FROM dns_client_ips WHERE client_id=?",(row["id"],)).fetchone()
        if old and old["ip"]!=ip and now-int(old["updated_at"] or 0)<30:
            raise HTTPException(429,"wait 30 seconds before changing the registered IP")
        con.execute("INSERT INTO dns_client_ips(client_id,ip,updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(client_id) DO UPDATE SET ip=excluded.ip,updated_at=excluded.updated_at",
                    (row["id"],ip,now))
    try:
        result=_apply()
    except Exception as exc:
        with connect() as con:
            if old:
                con.execute("UPDATE dns_client_ips SET ip=?,updated_at=? WHERE client_id=?",(old["ip"],old["updated_at"],row["id"]))
            else:
                con.execute("DELETE FROM dns_client_ips WHERE client_id=?",(row["id"],))
        raise HTTPException(503,"DNS activation failed: "+str(exc)[:240])
    audit("subscription","dns_ip_registered",str(row["name"]),"gaming DNS public IPv4 registered",ip=ip)
    return JSONResponse({"ok":True,"ip":ip,"dns_primary":result.get("public_address"),"dns_secondary":"1.1.1.1"},
                        headers={"Cache-Control":"no-store, private"})

@router.post("/client/{subscription_id}/dns/unregister")
def unregister(subscription_id:str,request:Request):
    if request.headers.get("x-makia-dns-register")!="1":
        raise HTTPException(403,"invalid DNS registration request")
    row=_active_subscription(subscription_id); ip=_source_ip(request)
    with connect() as con:
        old=con.execute("SELECT ip FROM dns_client_ips WHERE client_id=?",(row["id"],)).fetchone()
        if not old:
            return JSONResponse({"ok":True},headers={"Cache-Control":"no-store, private"})
        if old["ip"]!=ip:
            raise HTTPException(403,"remove registration from the registered public IP")
        con.execute("DELETE FROM dns_client_ips WHERE client_id=?",(row["id"],))
    try:
        result=_apply()
    except Exception as exc:
        raise HTTPException(503,"DNS update failed: "+str(exc)[:240])
    audit("subscription","dns_ip_unregistered",str(row["name"]),"gaming DNS IP removed",ip=ip)
    return JSONResponse({"ok":True,"mode":result.get("mode")},headers={"Cache-Control":"no-store, private"})
