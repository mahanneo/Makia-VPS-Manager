import base64
import hashlib
import ipaddress
import io
import json
import os
import secrets
import time
from typing import Any

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import access_ops, client_store, integration_ops, protocol_ops
from .db import (
    audit, connect, create_protocol_client, delete_access_artifact_by_key,
    delete_protocol_client, get_protocol_client, list_protocol_clients,
    replace_protocol_client_identity, update_protocol_client_state,
    upsert_access_artifact, verify_api_token,
)

router=APIRouter()
WRITE_SCOPES={
    "provision:xray","provision:wireguard","provision:openvpn",
    "provision:outline","provision:lifecycle",
}

def ensure_write_api_schema():
    client_store.init_client_db()
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS api_token_policies(
          token_id INTEGER PRIMARY KEY,
          allowed_cidrs TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(token_id) REFERENCES api_tokens(id)
        );
        CREATE TABLE IF NOT EXISTS api_idempotency(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token_id INTEGER NOT NULL,
          idempotency_key TEXT NOT NULL,
          route TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'processing',
          status_code INTEGER NOT NULL DEFAULT 0,
          response_enc TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          UNIQUE(token_id,idempotency_key),
          FOREIGN KEY(token_id) REFERENCES api_tokens(id)
        );
        CREATE INDEX IF NOT EXISTS idx_api_idempotency_updated ON api_idempotency(updated_at);
        """)

def normalize_cidrs(values):
    out=[]
    for raw in values or []:
        item=str(raw or "").strip()
        if not item: continue
        try: item=str(ipaddress.ip_network(item,strict=False))
        except ValueError as exc: raise ValueError(f"invalid CIDR: {item}") from exc
        if item not in out: out.append(item)
    return out

def set_token_policy(token_id,allowed_cidrs):
    ensure_write_api_schema()
    cidrs=normalize_cidrs(allowed_cidrs)
    now=str(int(time.time()))
    with connect() as con:
        con.execute(
            """INSERT INTO api_token_policies(token_id,allowed_cidrs,created_at,updated_at)
               VALUES(?,?,?,?)
               ON CONFLICT(token_id) DO UPDATE SET allowed_cidrs=excluded.allowed_cidrs,updated_at=excluded.updated_at""",
            (int(token_id),",".join(cidrs),now,now)
        )
    return {"token_id":int(token_id),"allowed_cidrs":cidrs}

def token_policy(token_id):
    ensure_write_api_schema()
    with connect() as con:
        row=con.execute("SELECT allowed_cidrs FROM api_token_policies WHERE token_id=?",(int(token_id),)).fetchone()
    return {"token_id":int(token_id),"allowed_cidrs":[x for x in str(row["allowed_cidrs"] if row else "").split(",") if x]}

def enrich_token_rows(rows):
    return [{**row,"allowed_cidrs":token_policy(int(row["id"]))["allowed_cidrs"]} for row in rows]

def _trusted_proxy_networks():
    raw=os.getenv("MAKIA_TRUSTED_PROXY_CIDRS","127.0.0.1/32,::1/128")
    out=[]
    for item in raw.split(","):
        try: out.append(ipaddress.ip_network(item.strip(),strict=False))
        except ValueError: pass
    return out

def _client_ip(request):
    direct=str(request.client.host if request.client else "").strip()
    try: addr=ipaddress.ip_address(direct)
    except ValueError: return direct
    if any(addr in n for n in _trusted_proxy_networks()):
        forwarded=(request.headers.get("x-forwarded-for") or "").split(",",1)[0].strip()
        if forwarded:
            try: return str(ipaddress.ip_address(forwarded))
            except ValueError: pass
    return str(addr)

def _bearer(request):
    auth=request.headers.get("authorization","")
    return auth.split(" ",1)[1].strip() if auth.lower().startswith("bearer ") else ""

def _require_scope(request,scope):
    token=_bearer(request)
    if not token: raise HTTPException(401,"bearer token required")
    identity=verify_api_token(token,scope)
    if not identity: raise HTTPException(403,"invalid token or scope")
    cidrs=token_policy(int(identity["id"]))["allowed_cidrs"]
    if not cidrs: raise HTTPException(403,"write token has no IP allowlist")
    client_ip=_client_ip(request)
    try:
        addr=ipaddress.ip_address(client_ip)
        allowed=any(addr in ipaddress.ip_network(x,strict=False) for x in cidrs)
    except ValueError: allowed=False
    if not allowed: raise HTTPException(403,"request IP is not allowed for this token")
    return {**identity,"client_ip":client_ip}

def _idem_key(request):
    key=str(request.headers.get("x-idempotency-key") or "").strip()
    if not key or len(key)>128 or not all(c.isalnum() or c in "-_.:" for c in key):
        raise HTTPException(400,"valid X-Idempotency-Key is required")
    return key

def _payload_hash(payload):
    raw=json.dumps(payload.model_dump(mode="json"),sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def _idem_begin(token_id,key,route,request_hash):
    ensure_write_api_schema(); now=int(time.time())
    with connect() as con:
        row=con.execute("SELECT * FROM api_idempotency WHERE token_id=? AND idempotency_key=?",(token_id,key)).fetchone()
        if row:
            item=dict(row)
            if item["route"]!=route or item["request_hash"]!=request_hash:
                raise HTTPException(409,"idempotency key already used for a different request")
            if item["state"]=="done" and item["response_enc"]:
                return access_ops.open_payload(item["response_enc"])
            if now-int(item["updated_at"] or 0)<300:
                raise HTTPException(409,"idempotent request is already processing")
            con.execute("UPDATE api_idempotency SET state='processing',status_code=0,response_enc='',updated_at=? WHERE id=?",(now,item["id"]))
            return None
        con.execute(
            """INSERT INTO api_idempotency(token_id,idempotency_key,route,request_hash,state,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?)""",
            (token_id,key,route,request_hash,"processing",now,now)
        )
    return None

def _idem_finish(token_id,key,body):
    with connect() as con:
        con.execute(
            "UPDATE api_idempotency SET state='done',status_code=200,response_enc=?,updated_at=? WHERE token_id=? AND idempotency_key=?",
            (access_ops.seal_payload(body),int(time.time()),token_id,key)
        )

def _idem_fail(token_id,key):
    with connect() as con:
        con.execute("DELETE FROM api_idempotency WHERE token_id=? AND idempotency_key=? AND state='processing'",(token_id,key))

def _run_idempotent(request,identity,payload,route,fn):
    key=_idem_key(request)
    replay=_idem_begin(int(identity["id"]),key,route,_payload_hash(payload))
    if replay is not None: return {**replay,"idempotent_replay":True}
    try:
        body=fn(); _idem_finish(int(identity["id"]),key,body); return body
    except HTTPException:
        _idem_fail(int(identity["id"]),key); raise
    except Exception as exc:
        _idem_fail(int(identity["id"]),key)
        raise HTTPException(409,str(exc)[:500]) from exc

def _qr(text):
    image=qrcode.make(text,image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO(); image.save(buf)
    return "data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode("ascii")

def _artifact(kind,key,name,protocol,payload,meta=None):
    metadata={**(meta or {}),"external_write_api":True}
    return upsert_access_artifact(
        kind,key,name,protocol,payload.get("native_filename",""),
        access_ops.seal_payload(payload),
        json.dumps(metadata,ensure_ascii=False,separators=(",",":"))
    )

def _policy_name(kind,service_key):
    return f"mn-{kind[:3]}-{hashlib.sha256((kind+':'+service_key).encode()).hexdigest()[:18]}"

def _policy_account(kind,service_key,name,expire_at,quota_bytes):
    username=_policy_name(kind,service_key)
    existing=client_store.account_by_username(username)
    if existing:
        client_store.update_account(existing["id"],name,"MahiNet",expire_at,quota_bytes,None,None,True)
        return int(existing["id"])
    return client_store.create_account(
        username,secrets.token_urlsafe(24),name,"MahiNet",
        expire_at,quota_bytes,1,1,True
    )

class XrayProvision(BaseModel):
    service_key:str=Field(min_length=3,max_length=96)
    inbound_tag:str=Field(min_length=1,max_length=120)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    credential:str=Field(default="",max_length=128)
    flow:str=Field(default="",max_length=80)
    quota_bytes:int=Field(default=0,ge=0)
    expire_at:int=Field(default=0,ge=0)
    ip_limit:int=Field(default=1,ge=1,le=50)
    reset_days:int=Field(default=0,ge=0,le=3650)

class WireGuardProvision(BaseModel):
    service_key:str=Field(min_length=3,max_length=96)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    dns:str=Field(default="1.1.1.1",max_length=64)
    mtu:int=Field(default=1280,ge=576,le=1500)
    keepalive:int=Field(default=15,ge=0,le=3600)
    allowed_ips:str=Field(default="0.0.0.0/0",max_length=255)
    quota_bytes:int=Field(default=0,ge=0)
    expire_at:int=Field(default=0,ge=0)

class OpenVPNProvision(BaseModel):
    service_key:str=Field(min_length=3,max_length=96)
    name:str=Field(min_length=1,max_length=48)
    endpoint:str=Field(min_length=1,max_length=255)
    endpoint_mode:str="auto"
    port:int=Field(default=1194,ge=1,le=65535)
    proto:str="udp"
    quota_bytes:int=Field(default=0,ge=0)
    expire_at:int=Field(default=0,ge=0)

class OutlineProvision(BaseModel):
    service_key:str=Field(min_length=3,max_length=96)
    name:str=Field(min_length=1,max_length=80)
    quota_bytes:int=Field(default=0,ge=0)
    expire_at:int=Field(default=0,ge=0)

class LifecycleChange(BaseModel):
    kind:str=Field(pattern="^(xray|outline|wireguard|openvpn)$")
    resource_id:str=Field(min_length=1,max_length=128)
    client_account_id:int=Field(gt=0)
    enabled:bool|None=None
    expire_at:int|None=Field(default=None,ge=0)
    quota_bytes:int|None=Field(default=None,ge=0)
    reissue:bool=False

@router.post("/api/v1/provision/xray")
def provision_xray(payload:XrayProvision,request:Request):
    identity=_require_scope(request,"provision:xray")
    def op():
        if any(x.get("engine")=="xray" and x.get("name")==payload.name for x in list_protocol_clients()):
            raise HTTPException(409,"Xray client name already exists")
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode)
        result=protocol_ops.add_xray_client_to_inbound(payload.inbound_tag,payload.name,endpoint,payload.credential,payload.flow)
        client_id=None
        try:
            client_id=create_protocol_client(
                payload.name,"xray",result["protocol"],result["tag"],result["credential"],result["share_link"],
                payload.quota_bytes,payload.expire_at,payload.ip_limit,payload.reset_days
            )
            row=get_protocol_client(client_id) or {}
            delivery=access_ops.xray_payload(payload.name,result["protocol"],result["share_link"],"","")
            artifact_id=_artifact("xray",str(client_id),payload.name,result["protocol"],delivery,{"client_id":client_id,"inbound_tag":result["tag"],"service_key":payload.service_key})
            account_id=_policy_account("xray",payload.service_key,payload.name,payload.expire_at,payload.quota_bytes)
            client_store.bind_protocol_client(account_id,client_id,label=payload.name)
        except Exception:
            try: protocol_ops.remove_xray_client_from_inbound(result["tag"],payload.name)
            except Exception: pass
            if client_id is not None:
                try:
                    delete_access_artifact_by_key("xray",str(client_id)); delete_protocol_client(client_id)
                except Exception: pass
            raise
        audit("api:"+identity["name"],"external_provision_xray",str(client_id),payload.service_key,identity["client_ip"])
        return {
            "ok":True,"kind":"xray","resource_id":str(client_id),"client_account_id":account_id,
            "artifact_id":artifact_id,"protocol":result["protocol"],"share_link":result["share_link"],
            "subscription_id":row.get("subscription_id") or "","qr":_qr(result["share_link"]),
            "expire_at":payload.expire_at,"quota_bytes":payload.quota_bytes
        }
    return _run_idempotent(request,identity,payload,"/api/v1/provision/xray",op)

@router.post("/api/v1/provision/wireguard")
def provision_wireguard(payload:WireGuardProvision,request:Request):
    identity=_require_scope(request,"provision:wireguard")
    def op():
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode,direct=True)
        result=protocol_ops.create_wireguard_peer(payload.name,endpoint,dns=payload.dns,mtu=payload.mtu,keepalive=payload.keepalive,allowed_ips=payload.allowed_ips)
        try:
            delivery=access_ops.wireguard_payload(payload.name,result["config"],result.get("address"))
            artifact_id=_artifact("wireguard",payload.name,payload.name,"wireguard",delivery,{"public_key":result.get("public_key",""),"service_key":payload.service_key})
            account_id=_policy_account("wireguard",payload.service_key,payload.name,payload.expire_at,payload.quota_bytes)
            client_store.bind_access_artifact(account_id,artifact_id,label=payload.name)
        except Exception:
            try: protocol_ops.remove_wireguard_peer(result["public_key"])
            except Exception: pass
            raise
        audit("api:"+identity["name"],"external_provision_wireguard",payload.name,payload.service_key,identity["client_ip"])
        return {
            "ok":True,"kind":"wireguard","resource_id":payload.name,"client_account_id":account_id,
            "artifact_id":artifact_id,"config":result["config"],"qr":_qr(result["config"]),
            "address":result.get("address"),"expire_at":payload.expire_at,"quota_bytes":payload.quota_bytes
        }
    return _run_idempotent(request,identity,payload,"/api/v1/provision/wireguard",op)

@router.post("/api/v1/provision/openvpn")
def provision_openvpn(payload:OpenVPNProvision,request:Request):
    identity=_require_scope(request,"provision:openvpn")
    def op():
        policy=protocol_ops.openvpn_policy_status()
        if (payload.expire_at or payload.quota_bytes) and not policy.get("ready"):
            raise HTTPException(409,"OpenVPN hard policy runtime is required for quota/expiry managed services")
        endpoint=protocol_ops.validate_endpoint_selection(payload.endpoint,payload.endpoint_mode,direct=True)
        result=protocol_ops.create_openvpn_client(payload.name,endpoint,payload.port,payload.proto)
        try:
            delivery=access_ops.openvpn_payload(payload.name,result["config"])
            artifact_id=_artifact("openvpn",payload.name,payload.name,"openvpn",delivery,{"service_key":payload.service_key,"endpoint":endpoint,"port":payload.port,"proto":payload.proto})
            account_id=_policy_account("openvpn",payload.service_key,payload.name,payload.expire_at,payload.quota_bytes)
            client_store.bind_access_artifact(account_id,artifact_id,label=payload.name)
        except Exception:
            try: protocol_ops.revoke_openvpn_client(payload.name)
            except Exception: pass
            raise
        audit("api:"+identity["name"],"external_provision_openvpn",payload.name,payload.service_key,identity["client_ip"])
        return {
            "ok":True,"kind":"openvpn","resource_id":payload.name,"client_account_id":account_id,
            "artifact_id":artifact_id,"config":result["config"],"qr":_qr(result["config"]),
            "expire_at":payload.expire_at,"quota_bytes":payload.quota_bytes,"policy_ready":True
        }
    return _run_idempotent(request,identity,payload,"/api/v1/provision/openvpn",op)

@router.post("/api/v1/provision/outline")
def provision_outline(payload:OutlineProvision,request:Request):
    identity=_require_scope(request,"provision:outline")
    def op():
        created=integration_ops.outline_create_key(payload.name,payload.quota_bytes)
        client_id=None
        try:
            key_id=str(created.get("id") or ""); access_url=str(created.get("accessUrl") or "")
            if not key_id or not access_url: raise RuntimeError("Outline did not return a usable access key")
            client_id=create_protocol_client(payload.name,"outline","outline",key_id,key_id,access_url,payload.quota_bytes,payload.expire_at,1,0)
            delivery=access_ops.outline_payload(payload.name,access_url,key_id,payload.quota_bytes)
            artifact_id=_artifact("outline",str(client_id),payload.name,"outline",delivery,{"client_id":client_id,"outline_key_id":key_id,"service_key":payload.service_key})
            account_id=_policy_account("outline",payload.service_key,payload.name,payload.expire_at,payload.quota_bytes)
            client_store.bind_protocol_client(account_id,client_id,label=payload.name)
        except Exception:
            if created and created.get("id"):
                try: integration_ops.outline_delete_key(created["id"])
                except Exception: pass
            if client_id:
                try: delete_protocol_client(client_id)
                except Exception: pass
            raise
        audit("api:"+identity["name"],"external_provision_outline",str(client_id),payload.service_key,identity["client_ip"])
        return {
            "ok":True,"kind":"outline","resource_id":str(client_id),"client_account_id":account_id,
            "artifact_id":artifact_id,"share_link":access_url,"qr":_qr(access_url),
            "expire_at":payload.expire_at,"quota_bytes":payload.quota_bytes
        }
    return _run_idempotent(request,identity,payload,"/api/v1/provision/outline",op)

def _update_policy_account(account_id,expire_at,quota_bytes,enabled):
    if not client_store.get_account(account_id): raise HTTPException(404,"policy account not found")
    return client_store.update_account(account_id,None,None,expire_at,quota_bytes,None,None,enabled)

def _outline_reissue(row,quota):
    old_id=str(row.get("inbound_tag") or "")
    created=integration_ops.outline_create_key(row["name"],quota)
    new_id=str(created.get("id") or ""); access_url=str(created.get("accessUrl") or "")
    if not new_id or not access_url: raise RuntimeError("Outline did not return a replacement key")
    replace_protocol_client_identity(row["id"],new_id,new_id,access_url)
    update_protocol_client_state(row["id"],True,quota,int(row.get("expire_at") or 0),None,None)
    delivery=access_ops.outline_payload(row["name"],access_url,new_id,quota)
    _artifact("outline",str(row["id"]),row["name"],"outline",delivery,{"client_id":row["id"],"outline_key_id":new_id})
    if old_id and old_id!=new_id and bool(row.get("enabled")):
        try: integration_ops.outline_delete_key(old_id)
        except Exception: pass
    return {"outline_key_id":new_id,"share_link":access_url,"qr":_qr(access_url)}

@router.post("/api/v1/provision/lifecycle")
def provision_lifecycle(payload:LifecycleChange,request:Request):
    identity=_require_scope(request,"provision:lifecycle")
    def op():
        account=_update_policy_account(payload.client_account_id,payload.expire_at,payload.quota_bytes,payload.enabled)
        result={"ok":True,"kind":payload.kind,"resource_id":payload.resource_id,"client_account_id":payload.client_account_id}
        if payload.kind in {"xray","outline"}:
            try: row=get_protocol_client(int(payload.resource_id))
            except Exception: row=None
            if not row or row.get("engine")!=payload.kind: raise HTTPException(404,"managed protocol client not found")
            quota=int(payload.quota_bytes if payload.quota_bytes is not None else row.get("quota_bytes") or 0)
            expire=int(payload.expire_at if payload.expire_at is not None else row.get("expire_at") or 0)
            if payload.kind=="xray":
                if payload.enabled is not None and bool(payload.enabled)!=bool(row.get("enabled")):
                    if payload.enabled: protocol_ops.enable_xray_client(row["inbound_tag"],row["name"],row["protocol"],row["credential"])
                    else: protocol_ops.disable_xray_client(row["inbound_tag"],row["name"])
                update_protocol_client_state(row["id"],payload.enabled,quota,expire,None,None)
            else:
                if payload.reissue or (payload.enabled is True and not bool(row.get("enabled"))):
                    result.update(_outline_reissue(row,quota))
                    update_protocol_client_state(row["id"],True,quota,expire,None,None)
                elif payload.enabled is False and bool(row.get("enabled")):
                    integration_ops.outline_delete_key(row["inbound_tag"])
                    update_protocol_client_state(row["id"],False,quota,expire,None,None)
                else:
                    if bool(row.get("enabled")) and payload.quota_bytes is not None:
                        integration_ops.outline_set_limit(str(row.get("inbound_tag") or ""),quota)
                    update_protocol_client_state(row["id"],payload.enabled,quota,expire,None,None)
        elif payload.kind=="wireguard" and payload.enabled is not None:
            protocol_ops.set_wireguard_peer_enabled(payload.resource_id,bool(payload.enabled))
        elif payload.kind=="openvpn" and payload.enabled is not None:
            if not protocol_ops.openvpn_policy_status().get("ready"):
                raise HTTPException(409,"OpenVPN hard policy runtime is not ready")
            protocol_ops.set_openvpn_client_policy_enabled(payload.resource_id,bool(payload.enabled))
        result["policy_account"]=account
        audit("api:"+identity["name"],"external_provision_lifecycle",payload.resource_id,json.dumps(payload.model_dump(mode="json"),separators=(",",":")),identity["client_ip"])
        return result
    return _run_idempotent(request,identity,payload,"/api/v1/provision/lifecycle",op)

@router.get("/api/v1/provision/service/{client_account_id}")
def provision_service_status(client_account_id:int,request:Request):
    identity=_require_scope(request,"provision:lifecycle")
    account=client_store.account_admin_snapshot(client_account_id)
    if not account: raise HTTPException(404,"service policy account not found")
    audit("api:"+identity["name"],"external_provision_status",str(client_account_id),"",identity["client_ip"])
    return {"ok":True,"account":account}
