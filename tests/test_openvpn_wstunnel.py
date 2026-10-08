from pathlib import Path
import socket

import pytest

from app import protocol_ops

ROOT=Path(__file__).resolve().parents[1]


def test_nginx_tls_server_block_selects_https_panel():
    text="""
server {
    listen 80;
    location / { proxy_pass http://127.0.0.1:8787; }
}
server {
    listen 443 ssl;
    server_name panel.example.com;
    location / { proxy_pass http://127.0.0.1:8787; }
}
"""
    start,end=protocol_ops._nginx_tls_server_block(text)
    block=text[start:end+1]
    assert "listen 443 ssl" in block
    assert "proxy_pass http://127.0.0.1:8787" in block


def test_openvpn_wstunnel_contract_is_separate_from_wireguard_wstunnel():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert '"id":"wstunnel-openvpn"' in source
    assert '"transport":"OpenVPN over WebSocket/TLS"' in source
    assert '"id":"wstunnel","label":"WStunnel WG"' in source
    assert "OVPN_WSTUNNEL_TARGET_PORT" in source
    assert "openvpn-server@makia-ws" in source


def test_openvpn_wstunnel_is_published_through_https_443():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert 'if public_port!=443:' in source
    assert 'wss://{domain}:{public_port}' in source
    assert 'proxy_set_header Upgrade $http_upgrade' in source
    assert 'proxy_set_header Connection "upgrade"' in source


def test_openvpn_wstunnel_server_is_destination_restricted():
    unit=(ROOT/"systemd/makia-openvpn-wstunnel.service").read_text(encoding="utf-8")
    assert "--restrict-to 127.0.0.1:" in unit
    assert "--restrict-http-upgrade-path-prefix" in unit
    assert "ws://127.0.0.1:" in unit


def test_windows_package_pins_wstunnel_runtime():
    workflow=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    assert "wstunnel_11.0.0_windows_amd64.tar.gz" in workflow
    assert "024323c9c2dd1ed1c6f38d417d9b2776e2f0083bba507e80d4a8124c8451b164" in workflow
    assert "package\\wstunnel.exe" in workflow


def test_client_delivery_contains_structured_transport_config():
    source=(ROOT/"app/client_store.py").read_text(encoding="utf-8")
    assert '"transport_config":transport_config' in source
    connector=(ROOT/"client/windows/makia_client_connector.py").read_text(encoding="utf-8")
    assert 'engine in {"openvpn_wstunnel","openvpn-wstunnel"}' in connector
    assert "--tls-verify-certificate" in connector
    assert 'remote_host!="127.0.0.1"' in connector


def test_wstunnel_identity_is_separate_and_deterministic():
    a=protocol_ops._openvpn_wstunnel_identity("alice")
    b=protocol_ops._openvpn_wstunnel_identity("alice")
    c=protocol_ops._openvpn_wstunnel_identity("alice2")
    assert a==b
    assert a!=c
    assert a.startswith("mwst-")
    assert len(a)<=48


def test_regular_openvpn_listing_hides_wstunnel_internal_identities(tmp_path,monkeypatch):
    easy=tmp_path/"easy-rsa"
    issued=easy/"pki"/"issued"
    issued.mkdir(parents=True)
    for name in ("server","normal-user","mwst-alice-12345678"):
        (issued/f"{name}.crt").write_text("cert",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    rows=protocol_ops.list_openvpn_clients()
    assert [x["name"] for x in rows]==["normal-user"]


def test_wstunnel_status_requires_exact_managed_path(tmp_path,monkeypatch):
    env=tmp_path/"openvpn-wstunnel.env"
    nginx=tmp_path/"makia-nginx"
    env.write_text(
        "OVPN_WSTUNNEL_DOMAIN=vpn.example.com\n"
        "OVPN_WSTUNNEL_PUBLIC_PORT=443\n"
        "OVPN_WSTUNNEL_BRIDGE_PORT=10445\n"
        "OVPN_WSTUNNEL_TARGET_PORT=11940\n"
        "OVPN_WSTUNNEL_PATH_PREFIX=secretprefix123456\n",
        encoding="utf-8",
    )
    nginx.write_text(
        protocol_ops.OVPN_WSTUNNEL_NGINX_BEGIN+"\nlocation /wrongprefix {}\n"+
        protocol_ops.OVPN_WSTUNNEL_NGINX_END+"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"OVPN_WSTUNNEL_ENV",env)
    monkeypatch.setattr(protocol_ops,"OVPN_WSTUNNEL_NGINX",nginx)
    monkeypatch.setattr(protocol_ops.shutil,"which",lambda x:"/usr/bin/wstunnel" if x=="wstunnel" else None)
    monkeypatch.setattr(protocol_ops,"_active",lambda svc:True)
    monkeypatch.setattr(protocol_ops,"_tcp_listener",lambda port,loopback_only=False:True)
    monkeypatch.setattr(protocol_ops,"_openvpn_named_runtime",lambda stem:{"service_active":True,"listener":True})
    assert protocol_ops.openvpn_wstunnel_status()["ready"] is False
    nginx.write_text(
        protocol_ops.OVPN_WSTUNNEL_NGINX_BEGIN+"\nlocation /secretprefix123456 {}\n"+
        protocol_ops.OVPN_WSTUNNEL_NGINX_END+"\n",
        encoding="utf-8",
    )
    assert protocol_ops.openvpn_wstunnel_status()["ready"] is True


def test_nginx_wstunnel_block_is_idempotent(tmp_path,monkeypatch):
    site=tmp_path/"makia-vps-manager"
    backup=tmp_path/"backups"
    backup.mkdir()
    site.write_text(
        "server {\n"
        "  listen 443 ssl;\n"
        "  server_name vpn.example.com;\n"
        "  location / { proxy_pass http://127.0.0.1:8787; }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"OVPN_WSTUNNEL_NGINX",site)
    monkeypatch.setattr(protocol_ops,"_backup_dir",lambda:backup)
    monkeypatch.setattr(protocol_ops,"_run",lambda *a,**k:"")
    protocol_ops._configure_openvpn_wstunnel_nginx("secretprefix123456",10445)
    first=site.read_text(encoding="utf-8")
    assert first.count(protocol_ops.OVPN_WSTUNNEL_NGINX_BEGIN)==1
    assert "proxy_pass http://127.0.0.1:10445;" in first
    assert "location ^~ /secretprefix123456" in first
    protocol_ops._configure_openvpn_wstunnel_nginx("secretprefix123456",10445)
    second=site.read_text(encoding="utf-8")
    assert second.count(protocol_ops.OVPN_WSTUNNEL_NGINX_BEGIN)==1


def test_wstunnel_backend_has_dedicated_root_only_management_socket_and_duplicate_cn():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert 'OVPN_WSTUNNEL_MANAGEMENT_SOCKET=Path("/run/makia-openvpn-wstunnel-management.sock")' in source
    assert 'management {OVPN_WSTUNNEL_MANAGEMENT_SOCKET} unix' in source
    assert '"management-client-user root\\nmanagement-client-group root\\n"' in source
    assert '"duplicate-cn\\n"' in source


def test_wstunnel_policy_uses_dedicated_management_runtime():
    source=(ROOT/"app/client_policy.py").read_text(encoding="utf-8")
    assert "openvpn_wstunnel_management_status()" in source
    assert 'kind not in {"wireguard","ssh","openvpn","openvpn_wstunnel"}' in source
    assert "set_openvpn_wstunnel_client_policy_enabled" in source
    assert "client_policy_wstunnel_concurrent_limit" in source
    store=(ROOT/"app/client_store.py").read_text(encoding="utf-8")
    assert '"accounting_supported":kind in {"wireguard","openvpn_wstunnel"}' in store
    assert '"expiry + quota + concurrent" if kind=="openvpn_wstunnel"' in store


def test_management_client_kill_uses_cid_and_selected_socket(tmp_path,monkeypatch):
    socket_path=tmp_path/"mgmt.sock"
    socket_path.touch()
    seen={}
    def fake(command,until_end=False,socket_path=None):
        seen["command"]=command
        seen["socket"]=socket_path
        return "SUCCESS: client-kill command succeeded"
    monkeypatch.setattr(protocol_ops,"_openvpn_management_command",fake)
    out=protocol_ops.openvpn_management_client_kill(17,socket_path)
    assert out["disconnected"] is True
    assert seen["command"]=="client-kill 17"
    assert seen["socket"]==socket_path


def test_nginx_wstunnel_route_has_abuse_guards():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert "limit_req_zone $binary_remote_addr zone=makia_wstunnel_req:10m rate=30r/s;" in source
    assert "limit_conn_zone $binary_remote_addr zone=makia_wstunnel_conn:10m;" in source
    assert "limit_req zone=makia_wstunnel_req burst=60 nodelay;" in source
    assert "limit_conn makia_wstunnel_conn 128;" in source
    assert "proxy_connect_timeout 5s;" in source


def test_access_wizard_offers_wstunnel_443_without_parallel_browser_gateway():
    source=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "['openvpn_wstunnel','WStunnel 443'" in source
    assert "wizardProtocolReady(kind)" in source
    assert "s.openvpn_wstunnel?.ready" in source
    assert "/api/protocols/openvpn/wstunnel/clients" in source
    assert "Concurrent Connection Limit" in source
    assert "/artifact-bindings" in source


def test_openvpn_management_status_preserves_per_session_counters():
    text=(
        "HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Virtual IPv6 Address,"
        "Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher\n"
        "CLIENT_LIST,mwst-user-a,198.51.100.2:51000,10.10.0.2,,100,200,now,1700000000,UNDEF,12,0,AES-256-GCM\n"
        "CLIENT_LIST,mwst-user-a,198.51.100.3:52000,10.10.0.3,,300,400,now,1700000001,UNDEF,13,1,AES-256-GCM\n"
    )
    clients=protocol_ops._parse_openvpn_management_status(text)
    row=clients["mwst-user-a"]
    assert row["total"]==1000
    assert len(row["instances"])==2
    assert row["instances"][0]["session_key"]=="12:1700000000"
    assert row["instances"][1]["total"]==700

def test_android_wstunnel_443_native_contract():
    unit=(ROOT/"systemd/makia-openvpn-wstunnel.service").read_text(encoding="utf-8")
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    kotlin=(ROOT/"client/android/MakiaEntryActivity.kt").read_text(encoding="utf-8")
    workflow=(ROOT/".github/workflows/android-connector.yml").read_text(encoding="utf-8")
    assert "--restrict-to 127.0.0.1:${OVPN_WSTUNNEL_TARGET_PORT}" in unit
    assert "--restrict-to 127.0.0.1:${OVPN_WSTUNNEL_WG_PORT}" in unit
    assert "def render_android_wstunnel_wireguard_client" in source
    assert '"type":"wireguard-wstunnel"' in source
    assert 'engine == "wstunnel_wireguard"' in kotlin
    assert '"exclude_package"' in kotlin
    assert '"libwstunnel.so"' in kotlin
    assert 'if (port != 443)' in kotlin
    assert 'if (remoteHost != "127.0.0.1")' in kotlin
    assert "9618838a4c3da6b53a4f6d67d24504b2a9aad14716387ca4c3d4cc53d861dcb4" in workflow



def test_wstunnel_internal_ports_are_auto_reallocated():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert "(11950,12940,13940,14940,15940,16940)" in source
    assert "(10445,11445,12445,13445,14445,15445)" in source
    assert "No free internal TCP port is available for the WStunnel OpenVPN backend" in source
    assert "No free internal TCP port is available for the WStunnel loopback bridge" in source
    # Historical 11940 remains a preference, not a hard blocker.
    assert "backend_port=11940" in source
    assert "backend_port=selected" in source


def test_wstunnel_backend_waits_for_real_listener_before_failing(monkeypatch):
    states=[
        {"service_active":True,"listener":False,"port":11950},
        {"service_active":True,"listener":False,"port":11950},
        {"service_active":True,"listener":True,"port":11950},
    ]
    monkeypatch.setattr(protocol_ops,"_openvpn_named_runtime",lambda stem: states.pop(0) if states else {"service_active":True,"listener":True,"port":11950})
    monkeypatch.setattr(protocol_ops.time,"sleep",lambda _x: None)
    out=protocol_ops._wait_openvpn_named_runtime("makia-ws",timeout=1.0,interval=0.01)
    assert out["service_active"] is True
    assert out["listener"] is True


def test_wstunnel_bootstrap_rejects_stale_internal_port_ownership_contract():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert "backend_is_ours=bool(" in source
    assert "bridge_is_ours=bool(" in source
    assert 'and existing_backend_state.get("service_active")' in source
    assert 'and existing_backend_state.get("listener")' in source
    assert 'if _port_transport_in_use(backend_port,"tcp") and not backend_is_ours:' in source
    assert 'if _port_transport_in_use(bridge_port,"tcp") and not bridge_is_ours:' in source


def test_wstunnel_user_button_uses_managed_access_wizard_and_binding():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert 'data-action="wizard-open" data-kind="openvpn_wstunnel"' in js
    assert "2) ساخت کاربر WStunnel" in js
    assert "/api/client-platform/accounts" in js
    assert "/artifact-bindings" in js
    assert "concurrent_device_limit" in js
    assert "Device Limit" in js
    assert "Concurrent Connection Limit" in js


def test_wstunnel_refuses_certificate_creation_until_server_ready(monkeypatch):
    monkeypatch.setattr(protocol_ops,"openvpn_wstunnel_status",lambda:{"ready":False})
    def forbidden(_identity):
        raise AssertionError("certificate identity must not be created")
    monkeypatch.setattr(protocol_ops,"_ensure_openvpn_client_identity",forbidden)
    with pytest.raises(protocol_ops.ProtocolError,match="not configured"):
        protocol_ops.render_openvpn_wstunnel_client("not-ready")


def test_healthy_wstunnel_backend_repair_is_noop(tmp_path,monkeypatch):
    root=tmp_path/"openvpn"
    server=root/"server"
    server.mkdir(parents=True)
    for part in ("ca.crt","server.crt","server.key","dh.pem","crl.pem","ta.key"):
        (server/part).write_text("mock",encoding="utf-8")
    (server/"makia-ws.conf").write_text("port 11950\nproto tcp4-server\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",root)
    monkeypatch.setattr(protocol_ops,"OVPN_WSTUNNEL_BACKEND_CONF",server/"makia-ws.conf")
    policy_sock=tmp_path/"management.sock"
    monkeypatch.setattr(protocol_ops,"OVPN_WSTUNNEL_MANAGEMENT_SOCKET",policy_sock)
    monkeypatch.setattr(protocol_ops,"_openvpn_named_runtime",lambda stem:{
        "config":str(server/"makia-ws.conf"),"port":11950,
        "proto":"tcp4-server","service_active":True,"listener":True,
    })
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:True)
    monkeypatch.setattr(protocol_ops,"_run",lambda *a,**k:pytest.fail("healthy backend must not restart"))
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.bind(str(policy_sock))
        state=protocol_ops.ensure_openvpn_wstunnel_backend(11950)
    assert state["service_active"] and state["listener"]


def test_wstunnel_provision_binding_failure_cleans_new_assets(monkeypatch):
    from app import main
    changes=[]
    monkeypatch.setattr(main,"require_capability",lambda request,feature,mutation=False:"admin")
    monkeypatch.setattr(main,"require_mutation",lambda request:"admin")
    monkeypatch.setattr(main,"ip",lambda request:"127.0.0.1")
    monkeypatch.setattr(main,"audit",lambda *a,**k:None)
    monkeypatch.setattr(main.client_store,"account_by_username",lambda name:None)
    monkeypatch.setattr(main,"_wstunnel_new_user_preflight",lambda name:("identity","mobile-peer"))
    monkeypatch.setattr(main.client_store,"create_account",lambda *a:99)
    monkeypatch.setattr(main,"_wstunnel_new_user_artifact",lambda *a:({"ok":True},88))
    def failed_bind(*args,**kwargs):
        raise ValueError("test binding failure")
    monkeypatch.setattr(main.client_store,"bind_access_artifact",failed_bind)
    monkeypatch.setattr(main,"_wstunnel_new_user_cleanup",
        lambda name,identity,mobile,artifact_created=False:changes.append(("assets",artifact_created)) or [])
    monkeypatch.setattr(main.client_store,"delete_account",lambda account_id:changes.append(("account",account_id)))
    payload=main.OpenVPNWStunnelProvision(name="alice",password="valid-pass-123")
    with pytest.raises(main.HTTPException) as exc:
        main.openvpn_wstunnel_provision(payload,object())
    assert exc.value.status_code==400
    assert changes==[("assets",True),("account",99)]


def test_wstunnel_provision_rejects_existing_account_without_mutations(monkeypatch):
    from app import main
    monkeypatch.setattr(main,"require_capability",lambda *a,**k:"admin")
    monkeypatch.setattr(main,"require_mutation",lambda *a,**k:"admin")
    monkeypatch.setattr(main.client_store,"account_by_username",lambda name:{"id":17})
    monkeypatch.setattr(main,"_wstunnel_new_user_artifact",lambda *a:pytest.fail("never touch existing assets"))
    payload=main.OpenVPNWStunnelProvision(name="alice",password="valid-pass-123")
    with pytest.raises(main.HTTPException) as exc:
        main.openvpn_wstunnel_provision(payload,object())
    assert exc.value.status_code==409


def test_wstunnel_wizard_provisions_atomically_in_backend():
    javascript=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    start=javascript.index("async function createProvisionedAccess()")
    end=javascript.index("function showProvisionSuccess(",start)
    create_flow=javascript[start:end]
    assert "'/api/protocols/openvpn/wstunnel/provision'" in create_flow
    assert "'/api/client-platform/accounts'" not in create_flow
    assert "'/artifact-bindings'" not in create_flow
