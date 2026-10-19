import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import client_connector,client_desktop,client_portal,client_store,db

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture()
def app_client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"test.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","desktop-test-admin-password-123")
    monkeypatch.setattr(client_portal,"enabled",lambda:True)
    db.init_db()
    client_store.init_client_db()
    app=FastAPI()
    app.include_router(client_desktop.router)
    app.include_router(client_portal.router)
    with TestClient(app,base_url="https://testserver") as client:
        yield client


def auth(token):
    return {"X-Makia-Desktop":"1","Authorization":"Bearer "+token}


def create_user():
    return client_store.create_account(
        "desktop01","DesktopPassword123",display_name="Windows One",
        expire_at=int(time.time())+86400,quota_bytes=5*1024**3,
        device_limit=2,concurrent_device_limit=2
    )


def login(client,remember=True,key=""):
    return client.post("/client/desktop/login",headers={"X-Makia-Desktop":"1"},
        json={"username":"desktop01","password":"DesktopPassword123",
              "remember_device":remember,"device_key":key})


def test_native_login_30d_and_12h_limits_and_no_password_response(app_client):
    create_user()
    r=login(app_client,True)
    assert r.status_code==200,r.text
    data=r.json()
    assert data["remember_device"] is True
    assert 29*86400<data["expires_at"]-int(time.time())<=30*86400
    assert data["device_key"]
    assert "password" not in r.text.lower()
    session=client_store.session_by_token(data["token"])
    assert session["platform"]=="windows"
    second=login(app_client,False,data["device_key"])
    assert second.status_code==200,second.text
    assert 0<second.json()["expires_at"]-int(time.time())<=43200
    assert app_client.get("/client/desktop/me",headers=auth(data["token"])).status_code==200
    assert app_client.post("/client/desktop/logout",headers=auth(data["token"]),json={}).status_code==200
    assert app_client.get("/client/desktop/me",headers=auth(data["token"])).status_code==401


def test_native_login_rejects_web_origin_wrong_header_bad_password_and_expiry(app_client):
    user=create_user()
    no_header=app_client.post("/client/desktop/login",json={"username":"desktop01","password":"DesktopPassword123"})
    assert no_header.status_code==403
    origin=app_client.post("/client/desktop/login",headers={"X-Makia-Desktop":"1","Origin":"https://evil.example"},
        json={"username":"desktop01","password":"DesktopPassword123"})
    assert origin.status_code==403
    bad=app_client.post("/client/desktop/login",headers={"X-Makia-Desktop":"1"},
        json={"username":"desktop01","password":"wrong"})
    assert bad.status_code==401
    too_large=app_client.post("/client/desktop/login",headers={"X-Makia-Desktop":"1"},
        json={"username":"desktop01","password":"x"*9000})
    assert too_large.status_code==413
    client_store.update_account(user,enabled=False)
    disabled=login(app_client)
    assert disabled.status_code==401  # generic bad-credential response avoids disclosing account state


def test_desktop_access_excludes_secrets_and_ticket_is_one_time(app_client):
    account_id=create_user()
    protocol_id=db.create_protocol_client(
        "desktop-sample","xray","vless","inbound-windows","uuid-must-never-be-listed",
        "vless://uuid-must-never-be-listed@vpn.example.test:443?security=tls#Makia",
        quota_bytes=1024**3,expire_at=int(time.time())+3600,ip_limit=1
    )
    client_store.bind_protocol_client(account_id,protocol_id,label="My Makia",priority=1)
    logged=login(app_client).json()
    h=auth(logged["token"])
    info=app_client.get("/client/desktop/access",headers=h)
    assert info.status_code==200
    assert len(info.json()["items"])==1
    assert "uuid-must-never-be-listed" not in info.text
    assert "share_link" not in info.text
    denied=app_client.post("/client/desktop/ticket/protocol/999999",headers=h,json={})
    assert denied.status_code==404
    ticket=app_client.post(f"/client/desktop/ticket/protocol/{protocol_id}",headers=h,json={})
    assert ticket.status_code==200,ticket.text
    url=ticket.json()["launch_url"]
    assert url.startswith("makia://connect?")
    assert "uuid-must-never-be-listed" not in url
    assert "DesktopPassword123" not in url
    from urllib.parse import parse_qs,urlsplit
    parsed=parse_qs(urlsplit(url).query)
    redeemed=client_connector.redeem_ticket(parsed["ticket"][0])
    assert redeemed["device_id"]==logged["account"]["current_device_id"]
    assert redeemed["delivery"]["share_link"].startswith("vless://")
    with pytest.raises(PermissionError):
        client_connector.redeem_ticket(parsed["ticket"][0])
    assert ticket.headers["cache-control"]=="no-store"


def test_device_revoke_invalidates_native_session(app_client):
    account_id=create_user()
    data=login(app_client).json()
    device_id=data["account"]["current_device_id"]
    client_store.revoke_device(account_id,device_id)
    assert app_client.get("/client/desktop/me",headers=auth(data["token"])).status_code==401


def test_gui_source_is_native_and_does_not_persist_password():
    source=(ROOT/"client/windows/makia_desktop.py").read_text("utf-8")
    assert "import tkinter" in source
    assert "CryptProtectData" in source and "CryptUnprotectData" in source
    assert "save_record(self.controller,self.device_key,self.token,self.expires,remember)" in source
    assert "os.startfile(launch_url)" in source
    assert "self.password.set(\"\")" in source
    assert "IP_ENDPOINTS" in source
    assert 'ProxyHandler({})' in source
    assert "password_sealed" not in source
