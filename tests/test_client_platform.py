import time
from pathlib import Path

import pytest

from app import client_store, db

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture()
def client_db(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","test-admin-password-12345")
    db.init_db()
    client_store.init_client_db()
    return tmp_path/"makia.db"


def test_client_schema_is_additive_and_account_password_isolated(client_db):
    account_id=client_store.create_account(
        "client01","client-pass-123","Client One","30 Day",
        expire_at=int(time.time())+86400,quota_bytes=5*1024**3,
        device_limit=2,concurrent_device_limit=1,
    )
    account=client_store.get_account(account_id)
    assert account["username"]=="client01"
    assert account["device_limit"]==2
    assert account["concurrent_device_limit"]==1
    assert client_store.verify_account_password("client01","client-pass-123")["id"]==account_id
    assert client_store.verify_account_password("client01","wrong-pass") is None
    with db.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM admins").fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM protocol_clients").fetchone()[0]==0


def test_device_limit_and_concurrent_device_limit_are_separate(client_db):
    account_id=client_store.create_account(
        "client02","client-pass-456",device_limit=2,concurrent_device_limit=1
    )
    d1,k1=client_store.register_or_get_device(account_id,label="Phone",user_agent="ua1")
    d2,k2=client_store.register_or_get_device(account_id,label="Laptop",user_agent="ua2")
    assert k1 and k2 and d1["id"]!=d2["id"]
    token,_=client_store.create_session(account_id,d1["id"],"10.0.0.1")
    assert client_store.session_by_token(token)["device_id"]==d1["id"]
    with pytest.raises(PermissionError,match="concurrent device limit"):
        client_store.create_session(account_id,d2["id"],"10.0.0.2")


def test_single_device_plan_rejects_new_browser_device(client_db):
    account_id=client_store.create_account(
        "client03","client-pass-789",device_limit=1,concurrent_device_limit=1
    )
    client_store.register_or_get_device(account_id,label="Phone")
    with pytest.raises(PermissionError,match="device limit"):
        client_store.register_or_get_device(account_id,label="Second phone")


def test_protocol_binding_hides_secret_until_authenticated_delivery(client_db):
    account_id=client_store.create_account("client04","client-pass-000")
    protocol_id=db.create_protocol_client(
        "xray-client","xray","vless","inbound-a","uuid-secret",
        "vless://uuid-secret@example.test:443?security=reality#Makia",
        quota_bytes=1024**3,expire_at=int(time.time())+86400,ip_limit=1,
    )
    client_store.bind_protocol_client(account_id,protocol_id,"Fast",10,True)
    visible=client_store.list_protocols(account_id,include_secrets=False)
    assert len(visible)==1
    assert visible[0]["available"] is True
    assert "share_link" not in visible[0]
    assert "subscription_id" not in visible[0]
    delivery=client_store.protocol_delivery(account_id,protocol_id)
    assert delivery["protocol"]=="vless"
    assert delivery["share_link"].startswith("vless://")


def test_account_quota_and_expiry_block_new_sessions(client_db):
    account_id=client_store.create_account(
        "client05","client-pass-111",quota_bytes=100,device_limit=1
    )
    protocol_id=db.create_protocol_client(
        "quota-client","xray","vless","inbound-q","cred","vless://example",
        quota_bytes=0,expire_at=0,ip_limit=1,
    )
    client_store.bind_protocol_client(account_id,protocol_id)
    with db.connect() as con:
        con.execute(
            "UPDATE protocol_clients SET used_up_bytes=60,used_down_bytes=40 WHERE id=?",
            (protocol_id,),
        )
    account=client_store.get_account(account_id)
    assert client_store.account_available(account)[1]=="quota"
    client_store.update_account(account_id,quota_bytes=0,expire_at=int(time.time())-1)
    assert client_store.account_available(client_store.get_account(account_id))[1]=="expired"


def test_password_rotation_revokes_existing_client_sessions(client_db):
    account_id=client_store.create_account("client06","client-pass-old")
    device,key=client_store.register_or_get_device(account_id,label="Phone")
    token,_=client_store.create_session(account_id,device["id"])
    assert client_store.session_by_token(token)
    client_store.set_account_password(account_id,"client-pass-new")
    assert client_store.session_by_token(token) is None
    assert client_store.verify_account_password("client06","client-pass-new")
    assert client_store.verify_account_password("client06","client-pass-old") is None


def test_client_platform_is_disabled_by_default_and_separate_from_admin_auth():
    env=(ROOT/".env.example").read_text(encoding="utf-8")
    portal=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    assert "MAKIA_CLIENT_PORTAL_ENABLED=0" in env
    assert 'MAKIA_CLIENT_PORTAL_ENABLED","0"' in portal
    assert 'CLIENT_SESSION_COOKIE="makia_client_session"' in portal
    assert 'CLIENT_DEVICE_COOKIE="makia_client_device"' in portal
    assert "makia_session" not in portal
    assert "app.include_router(client_portal.router)" in main


def test_client_admin_api_never_calls_protocol_runtime_mutators():
    source=(ROOT/"app/client_admin.py").read_text(encoding="utf-8")
    forbidden=(
        "create_xray","remove_xray","create_wireguard","remove_wireguard",
        "create_openvpn","delete_openvpn","systemctl","subprocess",
    )
    for token in forbidden:
        assert token not in source
    assert "bind_protocol_client" in source
    assert "list_protocol_clients" in source


def test_pwa_shell_uses_no_store_for_private_api_and_separate_service_worker():
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    sw=(ROOT/"app/static/client-sw.js").read_text(encoding="utf-8")
    manifest=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    assert 'cache:"no-store"' in js
    assert 'u.pathname.startsWith("/client/")' in sw
    assert 'cache:"no-store"' in sw
    assert 'const SHELL=["/static/client.css","/static/client.js","/static/client-icon.svg"]' in sw
    assert '"/client/sw.js"' in manifest
    assert '"display":"standalone"' in manifest
