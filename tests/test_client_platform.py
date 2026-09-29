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
    assert "MAKIA_CLIENT_PORTAL_ENABLED=auto" in env
    assert 'MAKIA_CLIENT_PORTAL_ENABLED","auto"' in portal
    assert 'get_setting("client_portal_enabled","0")' in portal
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


def test_protocol_identity_cannot_be_shared_across_client_accounts(client_db):
    a1=client_store.create_account("owner01","owner-pass-001")
    a2=client_store.create_account("owner02","owner-pass-002")
    protocol_id=db.create_protocol_client(
        "exclusive-client","xray","vless","inbound-e","cred","vless://exclusive",
    )
    client_store.bind_protocol_client(a1,protocol_id)
    with pytest.raises(ValueError,match="already bound"):
        client_store.bind_protocol_client(a2,protocol_id)


def test_artifact_bindings_deliver_wireguard_openvpn_and_ssh_without_runtime_mutation(client_db):
    from app import access_ops
    account_id=client_store.create_account("client07","client-pass-777",device_limit=2)

    payloads=[
        ("wireguard","phone",access_ops.wireguard_payload("phone","[Interface]\nPrivateKey = secret\n[Peer]\nEndpoint = vpn.example:51820\n")),
        ("openvpn","laptop",access_ops.openvpn_payload("laptop","client\nremote vpn.example 1194 udp\n")),
        ("ssh","shell",access_ops.ssh_payload("vpn.example","shell","ssh-secret",22,{"enabled":False})),
    ]
    artifact_ids=[]
    for kind,key,payload in payloads:
        artifact_id=db.upsert_access_artifact(
            kind,key,key,kind,payload["native_filename"],
            access_ops.seal_payload(payload),"{}",
        )
        artifact_ids.append((kind,artifact_id))
        client_store.bind_access_artifact(account_id,artifact_id,label=kind.upper())

    access=client_store.client_access_list(account_id)
    kinds={item["engine"] for item in access}
    assert {"wireguard","openvpn","ssh"}.issubset(kinds)
    assert all(item.get("delivery_kind")=="artifact" for item in access)
    assert all(item.get("accounting_supported") is False for item in access)

    delivered={kind:client_store.artifact_delivery(account_id,artifact_id) for kind,artifact_id in artifact_ids}
    assert "PrivateKey = secret" in delivered["wireguard"]["share_link"]
    assert "remote vpn.example 1194 udp" in delivered["openvpn"]["share_link"]
    assert "Password: ssh-secret" in delivered["ssh"]["share_link"]


def test_artifact_identity_cannot_be_shared_across_client_accounts(client_db):
    from app import access_ops
    a1=client_store.create_account("artifact01","artifact-pass-001")
    a2=client_store.create_account("artifact02","artifact-pass-002")
    payload=access_ops.openvpn_payload("one","client\nremote vpn.example 1194\n")
    artifact_id=db.upsert_access_artifact(
        "openvpn","one","one","openvpn",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(a1,artifact_id)
    with pytest.raises(ValueError,match="already bound"):
        client_store.bind_access_artifact(a2,artifact_id)


def test_client_delete_is_metadata_only_and_runtime_untouched(client_db):
    from app import access_ops
    account_id=client_store.create_account("client08","client-pass-888")
    protocol_id=db.create_protocol_client(
        "keep-runtime","xray","vless","keep-inbound","keep-cred","vless://keep-runtime"
    )
    payload=access_ops.openvpn_payload("keep-ovpn","client\nremote keep.example 1194\n")
    artifact_id=db.upsert_access_artifact(
        "openvpn","keep-ovpn","keep-ovpn","openvpn",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_protocol_client(account_id,protocol_id)
    client_store.bind_access_artifact(account_id,artifact_id)
    client_store.delete_account(account_id)
    assert client_store.get_account(account_id) is None
    assert db.get_protocol_client(protocol_id)["name"]=="keep-runtime"
    assert db.get_access_artifact(artifact_id)["external_key"]=="keep-ovpn"


def test_artifact_delivery_includes_native_download_and_qr(client_db):
    from app import access_ops
    account_id=client_store.create_account("client09","client-pass-999")
    payload=access_ops.wireguard_payload(
        "phone","[Interface]\nPrivateKey = secret\n[Peer]\nEndpoint = wg.example:51820\n"
    )
    artifact_id=db.upsert_access_artifact(
        "wireguard","phone","phone","wireguard",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)
    delivery=client_store.artifact_delivery(account_id,artifact_id)
    assert delivery["native_filename"].endswith(".conf")
    assert delivery["native_base64"]
    assert delivery["qr"].startswith("data:image/svg+xml;base64,")


def test_client_admin_ui_contract_is_present():
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    admin=(ROOT/"app/client_admin.py").read_text(encoding="utf-8")
    assert 'data-view="clientplatform"' in dashboard
    assert "clientPlatformCenter" in js
    assert "client-account-new" in js
    assert "client-binding-add" in js
    assert "client-platform/settings" in admin
    assert "runtime_untouched=true" in admin


def test_client_pwa_delivery_supports_qr_file_and_install_prompt():
    html=(ROOT/"app/templates/client_app.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    assert 'id="deliveryQr"' in html
    assert 'id="downloadDelivery"' in html
    assert 'id="installClient"' in html
    assert "beforeinstallprompt" in js
    assert "native_base64" in js
    assert "canDeepOpen" in js
