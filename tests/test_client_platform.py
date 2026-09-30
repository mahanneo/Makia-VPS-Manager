import io
import sqlite3
import tarfile
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
    portal=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    assert 'cache:"no-store"' in js
    assert "function clearSensitiveDelivery()" in js
    assert 'form[action="/client/logout"]' in js
    assert 'window.addEventListener("pagehide",clearSensitiveDelivery)' in js
    assert 'window.addEventListener("pageshow",event=>{if(event.persisted)location.reload()})' in js
    assert 'u.pathname.startsWith("/client/")' in sw
    assert 'fetch(event.request,{cache:"no-store"})' in sw
    assert 'const SHELL=["/static/client.css","/static/client.js","/static/client-icon.svg"]' in sw
    assert '"/client/"' not in sw.split("const SHELL=",1)[1].split(";",1)[0]
    assert '@router.post("/client/logout")' in portal
    assert "client_store.revoke_session(token)" in portal
    assert "response.delete_cookie(CLIENT_SESSION_COOKIE,path=\"/client\")" in portal
    assert 'response.headers["Cache-Control"]="no-store"' in portal
    assert '"/client/sw.js"' in portal
    assert '"display":"standalone"' in portal


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
    accounting={item["engine"]:item.get("accounting_supported") for item in access}
    assert accounting["wireguard"] is True
    assert accounting["openvpn"] is False
    assert accounting["ssh"] is False

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


def test_client_quota_baseline_counts_only_usage_after_binding(client_db):
    account_id=client_store.create_account("baseline01","baseline-pass-001",quota_bytes=1000)
    protocol_id=db.create_protocol_client(
        "baseline-xray","xray","vless","baseline-in","cred","vless://baseline"
    )
    with db.connect() as con:
        con.execute("UPDATE protocol_clients SET used_up_bytes=80,used_down_bytes=20 WHERE id=?",(protocol_id,))
    client_store.bind_protocol_client(account_id,protocol_id)
    assert client_store.account_usage_bytes(account_id)==0
    with db.connect() as con:
        con.execute("UPDATE protocol_clients SET used_up_bytes=130,used_down_bytes=40 WHERE id=?",(protocol_id,))
    assert client_store.account_usage_bytes(account_id)==70
    client_store.reset_account_usage(account_id)
    assert client_store.account_usage_bytes(account_id)==0


def test_wireguard_artifact_counter_is_persistent_delta_not_prebind_history(client_db):
    from app import access_ops
    account_id=client_store.create_account("wgusage01","wgusage-pass-001",quota_bytes=5000)
    payload=access_ops.wireguard_payload("wgusage","[Interface]\nPrivateKey = x\n")
    artifact_id=db.upsert_access_artifact(
        "wireguard","wgusage","wgusage","wireguard",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)
    assert client_store.add_artifact_counter_sample(account_id,artifact_id,1000)==0
    assert client_store.add_artifact_counter_sample(account_id,artifact_id,1600)==600
    # wg counters can reset after interface/service restart; the new counter is
    # treated as additional usage, not as a negative delta.
    assert client_store.add_artifact_counter_sample(account_id,artifact_id,200)==800
    assert client_store.account_usage_bytes(account_id)==800


def test_client_xray_policy_suspends_and_restores_only_its_own_reason(client_db,monkeypatch):
    from app import client_policy, protocol_ops
    account_id=client_store.create_account("policyx01","policy-pass-001",quota_bytes=100)
    protocol_id=db.create_protocol_client(
        "policy-xray","xray","vless","policy-in","policy-cred","vless://policy"
    )
    client_store.bind_protocol_client(account_id,protocol_id)
    with db.connect() as con:
        con.execute("UPDATE protocol_clients SET used_up_bytes=100 WHERE id=?",(protocol_id,))
    calls=[]
    monkeypatch.setattr(protocol_ops,"disable_xray_client",lambda tag,name:(calls.append(("disable",tag,name)) or {"disabled":True}))
    monkeypatch.setattr(protocol_ops,"enable_xray_client",lambda tag,name,protocol,credential:(calls.append(("enable",tag,name)) or {"enabled":True}))
    result=client_policy.enforce_managed_protocols()
    assert result["suspended"]==1
    row=db.get_protocol_client(protocol_id)
    assert row["enabled"]==0
    assert row["disabled_reason"]=="client_account_quota"
    client_store.update_account(account_id,quota_bytes=1000)
    result=client_policy.enforce_managed_protocols()
    assert result["restored"]==1
    assert db.get_protocol_client(protocol_id)["enabled"]==1
    assert calls[0][0]=="disable" and calls[-1][0]=="enable"


def test_client_policy_does_not_restore_preexisting_manual_xray_disable(client_db,monkeypatch):
    from app import client_policy, protocol_ops
    account_id=client_store.create_account("policyx02","policy-pass-002")
    protocol_id=db.create_protocol_client(
        "manual-xray","xray","vless","manual-in","manual-cred","vless://manual"
    )
    client_store.bind_protocol_client(account_id,protocol_id)
    db.set_protocol_client_enabled(protocol_id,False,"manual")
    monkeypatch.setattr(protocol_ops,"enable_xray_client",lambda *args: (_ for _ in ()).throw(AssertionError("must not enable")))
    result=client_policy.enforce_managed_protocols()
    assert result["restored"]==0
    assert db.get_protocol_client(protocol_id)["disabled_reason"]=="manual"


def test_wireguard_expiry_policy_round_trip_is_non_destructive(client_db,monkeypatch):
    from app import access_ops, client_policy, protocol_ops
    account_id=client_store.create_account(
        "policywg01","policywg-pass-001",expire_at=int(time.time())-1
    )
    payload=access_ops.wireguard_payload("policy-wg","[Interface]\nPrivateKey = x\n")
    artifact_id=db.upsert_access_artifact(
        "wireguard","policy-wg","policy-wg","wireguard",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)
    state={"enabled":True}
    monkeypatch.setattr(protocol_ops,"_wireguard_peer_runtime",lambda:[{"name":"policy-wg","rx":10,"tx":20}])
    monkeypatch.setattr(protocol_ops,"list_wireguard_peers",lambda:[{"name":"policy-wg","enabled":state["enabled"],"public_key":"k","allowed_ips":"10.0.0.2/32"}])
    def set_state(name,enabled):
        state["enabled"]=bool(enabled)
        return {"name":name,"enabled":bool(enabled)}
    monkeypatch.setattr(protocol_ops,"set_wireguard_peer_enabled",set_state)
    monkeypatch.setattr(client_policy.system_ops,"online_sessions",lambda:[])
    result=client_policy.enforce_host_artifacts()
    assert result["suspended"]==1 and state["enabled"] is False
    assert client_store.get_artifact_policy_state(account_id,artifact_id)["suspended_reason"]=="client_account_expiry"
    client_store.update_account(account_id,expire_at=int(time.time())+3600)
    result=client_policy.enforce_host_artifacts()
    assert result["restored"]==1 and state["enabled"] is True
    assert client_store.get_artifact_policy_state(account_id,artifact_id)["suspended_reason"]==""


def test_policy_suspended_binding_cannot_be_deleted_until_restored(client_db):
    from app import access_ops
    account_id=client_store.create_account("holds01","holds-pass-001")
    protocol_id=db.create_protocol_client("held","xray","vless","held-in","cred","vless://held")
    client_store.bind_protocol_client(account_id,protocol_id)
    db.set_protocol_client_enabled(protocol_id,False,"client_account_expiry")
    with pytest.raises(PermissionError,match="restore"):
        client_store.unbind_protocol_client(account_id,protocol_id)
    with pytest.raises(PermissionError,match="restore"):
        client_store.delete_account(account_id)
    db.set_protocol_client_enabled(protocol_id,True)
    client_store.unbind_protocol_client(account_id,protocol_id)
    client_store.delete_account(account_id)
    assert client_store.get_account(account_id) is None


def test_openvpn_policy_ready_profile_tracks_usage_and_round_trips_expiry(client_db,monkeypatch):
    from app import access_ops, client_policy, protocol_ops
    account_id=client_store.create_account(
        "ovpnpolicy01","ovpnpolicy-pass-001",expire_at=int(time.time())+3600,quota_bytes=5000
    )
    payload=access_ops.openvpn_payload("ovpn-one","client\nremote vpn.example 1194 udp\n")
    artifact_id=db.upsert_access_artifact(
        "openvpn","ovpn-one","ovpn-one","openvpn",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)

    runtime={"total":1000}
    state={"enabled":True}
    monkeypatch.setattr(client_policy.system_ops,"online_sessions",lambda:[])
    monkeypatch.setattr(protocol_ops,"_wireguard_peer_runtime",lambda:[])
    monkeypatch.setattr(protocol_ops,"list_wireguard_peers",lambda:[])
    monkeypatch.setattr(protocol_ops,"openvpn_management_status",lambda:{
        "available":True,"clients":{"ovpn-one":{"name":"ovpn-one","total":runtime["total"],"real_addresses":["1.2.3.4"],"client_ids":["1"]}},"error":""
    })
    monkeypatch.setattr(protocol_ops,"openvpn_policy_status",lambda:{
        "installed":True,"configured":True,"ready":True,"conflict":""
    })
    def set_enabled(name,enabled):
        state["enabled"]=bool(enabled)
        return {"name":name,"enabled":bool(enabled),"disconnected":not enabled}
    monkeypatch.setattr(protocol_ops,"set_openvpn_client_policy_enabled",set_enabled)

    # First sample establishes the post-bind baseline.
    client_policy.enforce_host_artifacts()
    assert client_store.account_usage_bytes(account_id)==0
    runtime["total"]=1600
    client_policy.enforce_host_artifacts()
    assert client_store.account_usage_bytes(account_id)==600

    client_store.update_account(account_id,expire_at=int(time.time())-1)
    result=client_policy.enforce_host_artifacts()
    assert result["suspended"]==1 and state["enabled"] is False
    assert client_store.get_artifact_policy_state(account_id,artifact_id)["suspended_reason"]=="client_account_expiry"

    client_store.update_account(account_id,expire_at=int(time.time())+3600)
    result=client_policy.enforce_host_artifacts()
    assert result["restored"]==1 and state["enabled"] is True
    assert client_store.get_artifact_policy_state(account_id,artifact_id)["suspended_reason"]==""


def test_openvpn_existing_server_is_never_bootstrapped_from_policy_poll(client_db,monkeypatch):
    from app import access_ops, client_policy, protocol_ops
    account_id=client_store.create_account(
        "ovpnpolicy02","ovpnpolicy-pass-002",expire_at=int(time.time())-1
    )
    payload=access_ops.openvpn_payload("ovpn-two","client\nremote vpn.example 1194 udp\n")
    artifact_id=db.upsert_access_artifact(
        "openvpn","ovpn-two","ovpn-two","openvpn",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)
    monkeypatch.setattr(client_policy.system_ops,"online_sessions",lambda:[])
    monkeypatch.setattr(protocol_ops,"_wireguard_peer_runtime",lambda:[])
    monkeypatch.setattr(protocol_ops,"list_wireguard_peers",lambda:[])
    monkeypatch.setattr(protocol_ops,"openvpn_management_status",lambda:{"available":False,"clients":{},"error":"not configured"})
    monkeypatch.setattr(protocol_ops,"openvpn_policy_status",lambda:{
        "installed":True,"configured":False,"ready":False,"conflict":""
    })
    monkeypatch.setattr(protocol_ops,"set_openvpn_client_policy_enabled",lambda *args:(_ for _ in ()).throw(AssertionError("must not mutate unconfigured OpenVPN")))
    result=client_policy.enforce_host_artifacts()
    assert result["suspended"]==0
    assert client_store.get_artifact_policy_state(account_id,artifact_id)["suspended_reason"]==""


def test_openvpn_policy_setup_requires_local_admin_contract():
    admin=(ROOT/"app/client_admin.py").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert '"/api/client-platform/openvpn-policy/enable"' in admin
    assert "require_local_admin(request)" in admin
    assert "enable_openvpn_policy_runtime()" in admin
    assert "register_client_admin(app,require_user,require_mutation,require_local_admin" in main
    assert "client-openvpn-policy-enable" in js
    assert "Restart" in js



def test_client_platform_backup_snapshot_preserves_accounts_devices_bindings_and_policy_state(client_db,tmp_path):
    from app import system_ops

    account_id=client_store.create_account(
        "backup-client","backup-client-pass","Backup Client","UAT",
        expire_at=int(time.time())+86400,quota_bytes=1024**3,
        device_limit=1,concurrent_device_limit=1,
    )
    device,_device_key=client_store.register_or_get_device(account_id,label="UAT browser",platform="web")
    client_store.create_session(account_id,device["id"],"127.0.0.1")
    protocol_id=db.create_protocol_client(
        "backup-xray","xray","vless","backup-inbound","backup-credential",
        "vless://backup-credential@example.test:443",0,0,1,0,
    )
    client_store.bind_protocol_client(account_id,protocol_id,"Backup Xray",10,True)
    artifact_id=db.upsert_access_artifact(
        "wireguard","backup-wg","backup-wg","wireguard","backup-wg.conf","sealed-test-payload","{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id,"Backup WireGuard",20,True)
    client_store.set_artifact_policy_state(account_id,artifact_id,"client_account_expiry")

    blob=system_ops._portable_data_tar(str(client_db.parent))
    restored_root=tmp_path/"restored"
    restored_root.mkdir()
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tf:
        tf.extract("data/makia.db",path=restored_root)

    restored_db=restored_root/"data"/"makia.db"
    con=sqlite3.connect(restored_db)
    try:
        assert con.execute("SELECT COUNT(*) FROM client_accounts WHERE username='backup-client'").fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM client_devices WHERE account_id=? AND active=1",(account_id,)).fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM client_sessions WHERE account_id=? AND revoked_at=0",(account_id,)).fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM client_protocol_bindings WHERE account_id=? AND protocol_client_id=?",(account_id,protocol_id)).fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM client_artifact_bindings WHERE account_id=? AND artifact_id=?",(account_id,artifact_id)).fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM client_usage_baselines WHERE account_id=? AND protocol_client_id=?",(account_id,protocol_id)).fetchone()[0]==1
        assert con.execute("SELECT suspended_reason FROM client_artifact_policy_state WHERE account_id=? AND artifact_id=?",(account_id,artifact_id)).fetchone()[0]=="client_account_expiry"
    finally:
        con.close()


def test_update_contract_preserves_client_data_tree_and_takes_consistent_sqlite_backup():
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert "--exclude='data/makia.db'" in update
    assert 'source.backup(target)' in update
    assert 'tar -C "$BACKUP_TMP" -czf "$BACKUP" data' in update
    assert 'rm -rf "$APP/data"' not in update



def test_host_uat_smoke_checks_client_schema_without_mutating_runtime():
    smoke=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    for table in (
        "client_accounts","client_devices","client_sessions",
        "client_protocol_bindings","client_artifact_bindings",
        "client_usage_baselines","client_artifact_usage","client_artifact_policy_state",
    ):
        assert table in smoke
    assert 'get_setting("client_portal_enabled","0")' in smoke
    assert "Client Portal rollout switch remains disabled" in smoke
    client_block=smoke.split("Client Platform schema + persistent policy state",1)[0].rsplit("if ( cd",1)[-1]
    for forbidden in ("systemctl restart","systemctl stop","systemctl start","UPDATE client_","DELETE FROM client_","INSERT INTO client_"):
        assert forbidden not in client_block

def test_client_pwa_rc_has_cross_platform_install_and_browser_security_contract():
    html=(ROOT/"app/templates/client_app.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    css=(ROOT/"app/static/client.css").read_text(encoding="utf-8")
    sw=(ROOT/"app/static/client-sw.js").read_text(encoding="utf-8")
    portal=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    assert 'id="installDialog"' in html
    assert 'id="platformName"' in html
    assert 'id="sessionText"' in html
    assert 'id="networkState"' in html
    assert 'apple-mobile-web-app-capable' in html
    assert 'function platform()' in js
    assert 'function installCopy' in js
    assert 'function startSessionClock' in js
    assert 'window.addEventListener("online"' in js
    assert 'document.addEventListener("visibilitychange"' in js
    assert ".mc-grid-4" in css
    assert 'const CACHE="makia-client-v131"' in sw
    assert 'response.headers["X-Frame-Options"]="DENY"' in portal
    assert 'response.headers["Referrer-Policy"]="no-referrer"' in portal
    assert 'response.headers["Content-Security-Policy"]' in portal
    assert '"lang":"fa"' in portal
    assert '"dir":"rtl"' in portal
    assert '"id":"/client/"' in portal
