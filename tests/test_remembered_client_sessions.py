"""Remembered Client Portal/Browser VPN sessions are opt-in and revocable."""
import re
import time
from pathlib import Path

import pytest

from app import client_portal, client_store, db

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture()
def client_db(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","remember-tests-admin-secret-123")
    db.init_db()
    client_store.init_client_db()
    return tmp_path/"makia.db"


def test_explicit_remember_duration_is_bounded_and_default_stays_short():
    assert client_portal.CLIENT_SESSION_TTL==12*3600
    assert client_portal.CLIENT_REMEMBER_TTL==30*24*3600
    assert client_portal.CLIENT_REMEMBER_TTL<=30*86400


def test_session_persists_and_ends_at_fixed_maximum(client_db,monkeypatch):
    account=client_store.create_account("remember01","remember-pass-123",device_limit=2,concurrent_device_limit=2)
    device,_=client_store.register_or_get_device(account,label="Chrome",platform="browser-extension")
    now=int(time.time())
    token,expires=client_store.create_session(account,device["id"],ttl_seconds=client_portal.CLIENT_REMEMBER_TTL)
    assert 29*86400<expires-now<=30*86400
    assert client_store.session_by_token(token)["device_id"]==device["id"]
    # A 30-day cookie is not an infinite session or a stored account password.
    assert client_store.session_by_token("remember-pass-123") is None
    client_store.revoke_session(token)
    assert client_store.session_by_token(token) is None


def test_password_change_and_device_revoke_invalidate_remembered_session(client_db):
    account=client_store.create_account("remember02","remember-old-pass",device_limit=2,concurrent_device_limit=2)
    device,_=client_store.register_or_get_device(account,label="Browser",platform="browser-extension")
    token,_=client_store.create_session(account,device["id"],ttl_seconds=client_portal.CLIENT_REMEMBER_TTL)
    client_store.set_account_password(account,"remember-new-pass")
    assert client_store.session_by_token(token) is None
    second,_=client_store.create_session(account,device["id"],ttl_seconds=client_portal.CLIENT_REMEMBER_TTL)
    client_store.revoke_device(account,device["id"])
    assert client_store.session_by_token(second) is None


def test_short_proxy_credential_cannot_outlive_long_portal_login(client_db):
    account=client_store.create_account("remember03","remember-pass-123")
    device,_=client_store.register_or_get_device(account,label="Browser",platform="browser-extension")
    token,session_expiry=client_store.create_session(account,device["id"],ttl_seconds=client_portal.CLIENT_REMEMBER_TTL)
    session=client_store.session_by_token(token)
    creds=client_store.issue_browser_proxy_token(session,client_portal.CLIENT_SESSION_TTL)
    assert 0<creds["expires_at"]-int(time.time())<=12*3600
    assert session_expiry-creds["expires_at"]>28*86400
    assert creds["password"]!=token


def test_login_forms_make_remembering_opt_in_and_do_not_store_password():
    portal=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    web=(ROOT/"app/templates/client_login.html").read_text(encoding="utf-8")
    popup=(ROOT/"client/browser-extension/popup.js").read_text(encoding="utf-8")
    html=(ROOT/"client/browser-extension/popup.html").read_text(encoding="utf-8")
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert 'remember_device:str=Form("")' in portal
    assert 'remember_device=body.get("remember_device") is True' in portal
    assert 'name="remember_device" value="1"' in web
    assert 'name="remember_device" value="1" checked' not in web
    assert 'id="rememberDevice" type="checkbox"' in html
    assert 'id="rememberDevice" type="checkbox" checked' not in html
    assert 'rememberDevice:false,expiresAt:0' in popup
    assert '$("rememberDevice").checked=false;' in popup
    assert '$("rememberDevice").checked=state.rememberDevice!==false;' not in popup
    assert "remember_device:rememberDevice" in popup
    assert "clientSessionToken" in popup
    assert "chrome.storage.local.remove([\"token\",\"expiresAt\"])" in popup
    assert 'password:state.' not in popup
    assert "message.action===\"reconnect\"" in background
    assert "controlHost" in background
    assert "await verifyBrowserProxy();" in background


def test_ext_logout_and_account_disable_revoke_remembered_session(client_db):
    account=client_store.create_account("remember04","remember-pass-123")
    device,_=client_store.register_or_get_device(account,label="PWA")
    token,_=client_store.create_session(account,device["id"],ttl_seconds=client_portal.CLIENT_REMEMBER_TTL)
    client_store.update_account(account,enabled=False)
    assert client_store.session_by_token(token) is None


def test_web_login_remember_cookie_and_unchecked_short_session(client_db,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(client_portal,"enabled",lambda:True)
    account=client_store.create_account(
        "web-remembered","remember-pass-123",device_limit=2,concurrent_device_limit=2
    )
    app=FastAPI()
    app.include_router(client_portal.router)
    with TestClient(app,base_url="https://testserver") as browser:
        remembered=browser.post(
            "/client/login",data={
                "username":"web-remembered","password":"remember-pass-123",
                "remember_device":"1"
            },follow_redirects=False
        )
        assert remembered.status_code==302
        assert "/client/app" in remembered.headers["location"]
        remember_cookie=remembered.headers["set-cookie"]
        assert "makia_client_session=" in remember_cookie
        assert "HttpOnly" in remember_cookie and "Secure" in remember_cookie
        assert "samesite=strict" in remember_cookie.lower()
        remember_age=int(re.search(r"Max-Age=(\d+)",remember_cookie,re.I).group(1))
        assert 29*86400<remember_age<=30*86400
        assert browser.get("/client/app").status_code==200
        browser.post("/client/logout",follow_redirects=False)
        short=browser.post(
            "/client/login",data={
                "username":"web-remembered","password":"remember-pass-123"
            },follow_redirects=False
        )
        assert short.status_code==302
        short_age=int(re.search(r"Max-Age=(\d+)",short.headers["set-cookie"],re.I).group(1))
        assert 0<short_age<=12*3600
        assert browser.get("/client/app").status_code==200


def test_extension_remember_api_has_30_day_opt_in_and_revocable_token(client_db,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(client_portal,"enabled",lambda:True)
    account_id=client_store.create_account(
        "ext-remembered","remember-pass-123",device_limit=2,concurrent_device_limit=2
    )
    app=FastAPI()
    app.include_router(client_portal.router)
    with TestClient(app) as browser:
        headers={"x-makia-extension":"1","user-agent":"Chrome test"}
        first=browser.post("/client/extension/login",headers=headers,json={
            "username":"ext-remembered","password":"remember-pass-123",
            "remember_device":True
        })
        assert first.status_code==200,first.text
        payload=first.json()
        assert payload["remember_device"] is True
        assert 29*86400<payload["expires_at"]-int(time.time())<=30*86400
        assert client_store.session_by_token(payload["token"])["account_id"]==account_id
        second=browser.post("/client/extension/login",headers=headers,json={
            "username":"ext-remembered","password":"remember-pass-123",
            "device_key":payload["device_key"],"remember_device":False
        })
        assert second.status_code==200,second.text
        short=second.json()
        assert short["remember_device"] is False
        assert 0<short["expires_at"]-int(time.time())<=12*3600
        logout=browser.post("/client/extension/logout",headers={
            **headers,"authorization":"Bearer "+payload["token"]
        })
        assert logout.status_code==200
        assert client_store.session_by_token(payload["token"]) is None
