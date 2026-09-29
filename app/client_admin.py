import os
import sqlite3

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from . import client_store
from .db import list_protocol_clients, list_access_artifacts


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


def _feature_enabled():
    return str(os.getenv("MAKIA_CLIENT_PORTAL_ENABLED","0")).strip().lower() in {"1","true","yes","on"}


def register_client_admin(app,require_user,require_mutation,audit_func,ip_func):
    """Register admin-only control-plane endpoints.

    This is intentionally invoked from app.main after the existing admin
    authentication/CSRF helpers are defined. It never mutates protocol runtime;
    it only manages client-plane accounts/devices and bindings to existing
    protocol_client rows.
    """

    @app.get("/api/client-platform/status")
    def client_platform_status(request:Request):
        require_user(request)
        return {
            "enabled":_feature_enabled(),
            "mode":"pwa-control-plane",
            "native_agent":False,
            "account_count":len(client_store.list_accounts()),
        }

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
        items=[]
        for row in list_protocol_clients():
            items.append({
                "id":row["id"],
                "name":row["name"],
                "engine":row["engine"],
                "protocol":row["protocol"],
                "enabled":bool(row.get("enabled")),
                "expire_at":int(row.get("expire_at") or 0),
                "quota_bytes":int(row.get("quota_bytes") or 0),
            })
        return {"items":items}

    @app.get("/api/client-platform/artifacts")
    def client_platform_artifacts(request:Request):
        require_user(request)
        allowed={"ssh","wireguard","openvpn","xray","outline"}
        return {"items":[item for item in list_access_artifacts() if str(item.get("kind") or "").lower() in allowed]}

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
        client_store.unbind_access_artifact(account_id,artifact_id)
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
        client_store.unbind_protocol_client(account_id,protocol_client_id)
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
