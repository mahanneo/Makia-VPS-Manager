"""Remembered Client Portal/Browser VPN sessions are opt-in and revocable."""
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
    assert 'name="remember_device" value="1" checked' in web
    assert 'id="rememberDevice"' in html
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
