import os
import sqlite3

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from . import client_store, protocol_ops
from .db import list_protocol_clients, list_access_artifacts, get_setting, set_setting


class ClientAccountCreate(BaseModel):
    username:str=Field(min_length=3,max_length=64)
    password:str=Field(min_length=8,max_length=128)
    display_name:str=Field(default="",max_length=120)
    plan_name:str=Field(default="",max_length=120)
    expire_at:int=Field(default=0,ge=0)
    quota_gb:float=Field(default=0,ge=0,le=100000)
    device_limit:int=Field(default=1,ge=1,le=20)
    concurrent_device_limit:int=Field(default=1,ge=1,le=20)
    enabled:bool=True


class ClientAccountUpdate(BaseModel):
    display_name:str|None=Field(default=None,max_length=120)
    plan_name:str|None=Field(default=None,max_length=120)
    expire_at:int|None=Field(default=None,ge=0)
    quota_gb:float|None=Field(default=None,ge=0,le=100000)
    device_limit:int|None=Field(default=None,ge=1,le=20)
    concurrent_device_limit:int|None=Field(default=None,ge=1,le=20)
    enabled:bool|None=None


class ClientPasswordUpdate(BaseModel):
    password:str=Field(min_length=8,max_length=128)


class ClientProtocolBinding(BaseModel):
    protocol_client_id:int=Field(gt=0)
    label:str=Field(default="",max_length=120)
    priority:int=Field(default=100,ge=0,le=10000)
    enabled:bool=True


class ClientArtifactBinding(BaseModel):
    artifact_id:int=Field(gt=0)
    label:str=Field(default="",max_length=120)
    priority:int=Field(default=100,ge=0,le=10000)
    enabled:bool=True


def _feature_state():
    raw=str(os.getenv("MAKIA_CLIENT_PORTAL_ENABLED","auto")).strip().lower()
    if raw in {"1","true","yes","on"}:
        return True,"env_on"
    if raw in {"0","false","no","off"}:
        return False,"env_off"
    enabled=str(get_setting("client_portal_enabled","0")).strip().lower() in {"1","true","yes","on"}
    return enabled,"admin_setting"


class ClientPlatformSettings(BaseModel):
    enabled:bool


def register_client_admin(app,require_user,require_mutation,require_local_admin,audit_func,ip_func):
    """Register admin-only Client Platform control-plane endpoints.

    Normal account, device, session and binding operations do not mutate or
    rotate protocol runtime credentials. The explicit local-admin OpenVPN
    policy setup endpoint is the sole runtime-bootstrap exception: it performs
    a transactional OpenVPN restart with backup/rollback so an existing server
    can opt into hard Client expiry/quota enforcement.
    """

    @app.get("/api/client-platform/status")
    def client_platform_status(request:Request):
        require_user(request)
        enabled,source=_feature_state()
        accounts=client_store.list_accounts()
        try:
            ovpn_policy=protocol_ops.openvpn_policy_status()
        except Exception as exc:
            ovpn_policy={"installed":False,"configured":False,"ready":False,"conflict":str(exc)[:300]}
        return {
            "enabled":enabled,
            "enable_source":source,
            "mode":"pwa-control-plane",
            "native_agent":False,
            "account_count":len(accounts),
            "active_accounts":sum(1 for a in accounts if a.get("enabled")),
            "registered_devices":sum(int(a.get("active_devices") or 0) for a in accounts),
            "bindings":sum(int(a.get("bindings") or 0) for a in accounts),
            "portal_path":"/client/",
            "admin_toggle_available":source=="admin_setting",
            "enforcement":{
                "xray":{"expiry":True,"quota":True,"device":False,"mode":"hard"},
                "outline":{"expiry":True,"quota":True,"device":False,"mode":"hard"},
                "wireguard":{"expiry":True,"quota":True,"device":False,"mode":"hard"},
                "ssh":{"expiry":True,"quota":False,"device":True,"mode":"hard"},
                "openvpn":{
                    "expiry":bool(ovpn_policy.get("ready")),
                    "quota":bool(ovpn_policy.get("ready")),
                    "device":False,
                    "mode":"hard" if ovpn_policy.get("ready") else ("setup_required" if ovpn_policy.get("installed") else "unavailable"),
                    "policy_ready":bool(ovpn_policy.get("ready")),
                    "policy_configured":bool(ovpn_policy.get("configured")),
                    "policy_conflict":str(ovpn_policy.get("conflict") or ""),
                },
            },
            "openvpn_policy":ovpn_policy,
        }

    @app.post("/api/client-platform/settings")
    def client_platform_settings(payload:ClientPlatformSettings,request:Request):
        actor=require_mutation(request)
        _enabled,source=_feature_state()
        if source in {"env_on","env_off"}:
            raise HTTPException(409,"MAKIA_CLIENT_PORTAL_ENABLED environment override is active")
        set_setting("client_portal_enabled","1" if payload.enabled else "0")
        audit_func(actor,"client_platform_toggle","portal",f"enabled={payload.enabled}",ip_func(request))
        enabled,source=_feature_state()
        return {"ok":True,"enabled":enabled,"enable_source":source}

    @app.post("/api/client-platform/openvpn-policy/enable")
    def client_platform_openvpn_policy_enable(request:Request):
        actor=require_mutation(request)
        require_local_admin(request)
        try:
            result=protocol_ops.enable_openvpn_policy_runtime()
        except protocol_ops.ProtocolError as exc:
            raise HTTPException(409,str(exc))
        audit_func(
            actor,"client_openvpn_policy_enable","openvpn",
            f"configured={result.get('configured')}; ready={result.get('ready')}; changed={result.get('changed')}",
            ip_func(request),
        )
        return result

    @app.get("/api/client-platform/accounts")
    def client_platform_accounts(request:Request):
        require_user(request)
        return client_store.list_accounts()

    @app.post("/api/client-platform/accounts")
    def client_platform_account_create(payload:ClientAccountCreate,request:Request):
        actor=require_mutation(request)
        if payload.concurrent_device_limit>payload.device_limit:
            raise HTTPException(400,"concurrent_device_limit cannot exceed device_limit")
        try:
            account_id=client_store.create_account(
                payload.username,payload.password,payload.display_name,payload.plan_name,
                payload.expire_at,int(payload.quota_gb*1024*1024*1024),
                payload.device_limit,payload.concurrent_device_limit,payload.enabled,
            )
        except (ValueError,sqlite3.IntegrityError) as exc:
            raise HTTPException(400,str(exc))
        audit_func(
            actor,"client_account_create",str(account_id),
            f"username={payload.username}; devices={payload.device_limit}; concurrent={payload.concurrent_device_limit}",
            ip_func(request),
        )
        return client_store.account_admin_snapshot(account_id)

    @app.get("/api/client-platform/accounts/{account_id}")
    def client_platform_account_get(account_id:int,request:Request):
        require_user(request)
        item=client_store.account_admin_snapshot(account_id)
        if not item:
            raise HTTPException(404,"client account not found")
        return item

    @app.put("/api/client-platform/accounts/{account_id}")
    def client_platform_account_update(account_id:int,payload:ClientAccountUpdate,request:Request):
        actor=require_mutation(request)
        current=client_store.get_account(account_id)
        if not current:
            raise HTTPException(404,"client account not found")
        new_device_limit=payload.device_limit if payload.device_limit is not None else current["device_limit"]
        new_concurrent=(
            payload.concurrent_device_limit
            if payload.concurrent_device_limit is not None
            else current["concurrent_device_limit"]
        )
        if int(new_concurrent)>int(new_device_limit):
            raise HTTPException(400,"concurrent_device_limit cannot exceed device_limit")
        try:
            item=client_store.update_account(
                account_id,
                payload.display_name,payload.plan_name,payload.expire_at,
                None if payload.quota_gb is None else int(payload.quota_gb*1024*1024*1024),
                payload.device_limit,payload.concurrent_device_limit,payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(400,str(exc))
        audit_func(actor,"client_account_update",str(account_id),f"enabled={item['enabled']}",ip_func(request))
        return client_store.account_admin_snapshot(account_id)

    @app.post("/api/client-platform/accounts/{account_id}/password")
    def client_platform_password(account_id:int,payload:ClientPasswordUpdate,request:Request):
        actor=require_mutation(request)
        try:
            client_store.set_account_password(account_id,payload.password)
        except ValueError as exc:
            raise HTTPException(400,str(exc))
        audit_func(actor,"client_account_password_rotate",str(account_id),"sessions_revoked=true",ip_func(request))
        return {"ok":True,"sessions_revoked":True}

    @app.get("/api/client-platform/protocols")
    def client_platform_protocols(request:Request):
        require_user(request)
        owners=client_store.protocol_binding_owners()
        items=[]
        for row in list_protocol_clients():
            owner=owners.get(int(row["id"]))
            items.append({
                "id":row["id"],
                "name":row["name"],
                "engine":row["engine"],
                "protocol":row["protocol"],
                "enabled":bool(row.get("enabled")),
                "expire_at":int(row.get("expire_at") or 0),
                "quota_bytes":int(row.get("quota_bytes") or 0),
                "bound":bool(owner),
                "bound_account_id":owner.get("account_id") if owner else None,
                "bound_username":owner.get("username") if owner else "",
            })
        return {"items":items}

    @app.get("/api/client-platform/artifacts")
    def client_platform_artifacts(request:Request):
        require_user(request)
        allowed={"ssh","wireguard","openvpn","xray","outline"}
        owners=client_store.artifact_binding_owners()
        items=[]
        for item in list_access_artifacts():
            if str(item.get("kind") or "").lower() not in allowed:
                continue
            owner=owners.get(int(item["id"]))
            row=dict(item)
            row.update({
                "bound":bool(owner),
                "bound_account_id":owner.get("account_id") if owner else None,
                "bound_username":owner.get("username") if owner else "",
            })
            items.append(row)
        return {"items":items}

    @app.post("/api/client-platform/accounts/{account_id}/artifact-bindings")
    def client_platform_artifact_binding_create(account_id:int,payload:ClientArtifactBinding,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        try:
            client_store.bind_access_artifact(
                account_id,payload.artifact_id,payload.label,payload.priority,payload.enabled
            )
        except ValueError as exc:
            raise HTTPException(400,str(exc))
        audit_func(
            actor,"client_artifact_bind",str(account_id),
            f"artifact_id={payload.artifact_id}",ip_func(request),
        )
        return {"ok":True,"bindings":client_store.list_artifact_bindings(account_id)}

    @app.delete("/api/client-platform/accounts/{account_id}/artifact-bindings/{artifact_id}")
    def client_platform_artifact_binding_delete(account_id:int,artifact_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        try:
            client_store.unbind_access_artifact(account_id,artifact_id)
        except PermissionError as exc:
            raise HTTPException(409,str(exc))
        audit_func(
            actor,"client_artifact_unbind",str(account_id),
            f"artifact_id={artifact_id}",ip_func(request),
        )
        return {"ok":True}

    @app.post("/api/client-platform/accounts/{account_id}/bindings")
    def client_platform_binding_create(account_id:int,payload:ClientProtocolBinding,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        try:
            client_store.bind_protocol_client(
                account_id,payload.protocol_client_id,payload.label,payload.priority,payload.enabled
            )
        except ValueError as exc:
            raise HTTPException(400,str(exc))
        audit_func(
            actor,"client_protocol_bind",str(account_id),
            f"protocol_client_id={payload.protocol_client_id}",ip_func(request),
        )
        return {"ok":True,"bindings":client_store.list_bindings(account_id)}

    @app.delete("/api/client-platform/accounts/{account_id}/bindings/{protocol_client_id}")
    def client_platform_binding_delete(account_id:int,protocol_client_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        try:
            client_store.unbind_protocol_client(account_id,protocol_client_id)
        except PermissionError as exc:
            raise HTTPException(409,str(exc))
        audit_func(
            actor,"client_protocol_unbind",str(account_id),
            f"protocol_client_id={protocol_client_id}",ip_func(request),
        )
        return {"ok":True}

    @app.post("/api/client-platform/accounts/{account_id}/devices/{device_id}/revoke")
    def client_platform_device_revoke(account_id:int,device_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        client_store.revoke_device(account_id,device_id)
        audit_func(actor,"client_device_admin_revoke",str(account_id),f"device_id={device_id}",ip_func(request))
        return {"ok":True}

    @app.post("/api/client-platform/accounts/{account_id}/devices/revoke-all")
    def client_platform_devices_revoke_all(account_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        client_store.revoke_all_devices(account_id)
        audit_func(actor,"client_devices_revoke_all",str(account_id),"sessions_revoked=true",ip_func(request))
        return {"ok":True}

    @app.post("/api/client-platform/accounts/{account_id}/sessions/revoke-all")
    def client_platform_sessions_revoke_all(account_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        client_store.revoke_all_sessions(account_id)
        audit_func(actor,"client_sessions_revoke_all",str(account_id),"",ip_func(request))
        return {"ok":True}

    @app.post("/api/client-platform/accounts/{account_id}/usage/reset")
    def client_platform_usage_reset(account_id:int,request:Request):
        actor=require_mutation(request)
        if not client_store.get_account(account_id):
            raise HTTPException(404,"client account not found")
        result=client_store.reset_account_usage(account_id)
        audit_func(actor,"client_usage_reset",str(account_id),"policy_recheck<=30s",ip_func(request))
        return {**result,"policy_recheck_seconds":30}

    @app.delete("/api/client-platform/accounts/{account_id}")
    def client_platform_account_delete(account_id:int,request:Request):
        actor=require_mutation(request)
        account=client_store.get_account(account_id)
        if not account:
            raise HTTPException(404,"client account not found")
        username=account.get("username") or str(account_id)
        try:
            client_store.delete_account(account_id)
        except PermissionError as exc:
            raise HTTPException(409,str(exc))
        audit_func(actor,"client_account_delete",str(account_id),f"username={username}; runtime_untouched=true",ip_func(request))
        return {"ok":True,"runtime_untouched":True}
