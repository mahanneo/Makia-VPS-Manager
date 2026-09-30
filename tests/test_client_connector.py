import base64
import importlib.util
import json
import time
from pathlib import Path

import pytest

from app import client_connector, client_portal, client_store, db, access_ops

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture()
def client_db(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","test-admin-password-12345")
    db.init_db()
    client_store.init_client_db()
    return tmp_path/"makia.db"


def test_connector_ticket_is_one_time_and_device_bound(client_db):
    account_id=client_store.create_account("native01","native-pass-001",device_limit=1)
    device,_=client_store.register_or_get_device(account_id,label="Windows",platform="windows")
    pid=db.create_protocol_client(
        "native-xray","xray","vless","native-in","cred",
        "vless://00000000-0000-0000-0000-000000000001@example.test:443?security=tls&sni=example.test",
    )
    client_store.bind_protocol_client(account_id,pid)
    issued=client_connector.issue_ticket(account_id,device["id"],"protocol",pid,ttl=60)
    payload=client_connector.redeem_ticket(issued["ticket"])
    assert payload["account_id"]==account_id
    assert payload["device_id"]==device["id"]
    assert payload["delivery"]["share_link"].startswith("vless://")
    with pytest.raises(PermissionError):
        client_connector.redeem_ticket(issued["ticket"])


def test_connector_ticket_rejects_revoked_device(client_db):
    account_id=client_store.create_account("native02","native-pass-002",device_limit=1)
    device,_=client_store.register_or_get_device(account_id,label="Windows",platform="windows")
    payload=access_ops.wireguard_payload("wg","[Interface]\nPrivateKey = x\n")
    artifact_id=db.upsert_access_artifact(
        "wireguard","wg","wg","wireguard",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    client_store.bind_access_artifact(account_id,artifact_id)
    issued=client_connector.issue_ticket(account_id,device["id"],"artifact",artifact_id,ttl=60)
    client_store.revoke_device(account_id,device["id"])
    with pytest.raises(PermissionError):
        client_connector.redeem_ticket(issued["ticket"])


def _connector_module():
    path=ROOT/"client/windows/makia_client_connector.py"
    spec=importlib.util.spec_from_file_location("makia_windows_connector",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_windows_connector_builds_tun_vless_reality_config():
    c=_connector_module()
    uri=("vless://00000000-0000-0000-0000-000000000001@example.test:443"
         "?security=reality&sni=www.example.com&pbk=abc123&sid=01&type=ws&path=%2Fws&host=cdn.example.com&fp=chrome")
    out=c.outbound_from_share(uri)
    assert out["type"]=="vless"
    assert out["server"]=="example.test"
    assert out["tls"]["reality"]["public_key"]=="abc123"
    assert out["transport"]["type"]=="ws"
    cfg=c.singbox_config(out)
    assert cfg["inbounds"][0]["type"]=="tun"
    assert cfg["inbounds"][0]["auto_route"] is True
    assert cfg["route"]["final"]=="proxy"


def test_windows_connector_parses_vmess_shadowsocks_and_npvt_ssh():
    c=_connector_module()
    vmess=base64.urlsafe_b64encode(json.dumps({
        "v":"2","ps":"Makia","add":"vm.example","port":"443","id":"00000000-0000-0000-0000-000000000002",
        "aid":"0","scy":"auto","net":"ws","type":"none","host":"cdn.example","path":"/v","tls":"tls","sni":"vm.example"
    }).encode()).decode().rstrip("=")
    assert c.outbound_from_share("vmess://"+vmess)["type"]=="vmess"
    ss_auth=base64.urlsafe_b64encode(b"aes-256-gcm:secret").decode().rstrip("=")
    assert c.outbound_from_share("ss://"+ss_auth+"@ss.example:8388#Makia")["method"]=="aes-256-gcm"
    ssh_obj={
        "sshHost":"ssh.example","sshPort":22,"sshUsername":"user","sshPassword":"pass"
    }
    ssh=base64.b64encode(json.dumps(ssh_obj,separators=(",",":")).encode()).decode()
    out=c.outbound_from_share("npvt-ssh://"+ssh)
    assert out["type"]=="ssh" and out["user"]=="user" and out["password"]=="pass"


def test_pwa_native_connector_contract_is_present():
    portal=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    html=(ROOT/"app/templates/client_app.html").read_text(encoding="utf-8")
    workflow=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    assert '"/client/api/connect/{delivery_kind}/{delivery_id}/ticket"' in portal
    assert '"/client/connector/redeem"' in portal
    assert "client_connector.issue_ticket" in portal
    assert 'data-direct-kind' in js
    assert 'makia://disconnect' in js
    assert 'id="disconnectDirect"' in html
    assert "pyinstaller" in workflow.lower()
    assert "sing-box-1.14.2-windows-amd64.zip" in workflow
    assert "c2d8bfff918755808781dfdeeb8581b6c91eb3a243d9a7b55483cfc0c0684d32" in workflow
    assert "Install-Makia.cmd" in workflow
    assert "Smoke package and real installer" in workflow
    install=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    assert "\\nparam" not in install
    assert 'Set-Item -Path $base -Value "URL:Makia Client Connector"' in install
    connector=(ROOT/"client/windows/makia_client_connector.py").read_text(encoding="utf-8")
    assert "MessageBoxW" in connector

def test_android_connector_overlay_and_reproducible_build_contract():
    activity=(ROOT/"client/android/MakiaEntryActivity.kt").read_text(encoding="utf-8")
    patch=(ROOT/"client/android/patch_sfa.py").read_text(encoding="utf-8")
    workflow=(ROOT/".github/workflows/android-connector.yml").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    assert 'uri.scheme != "makia"' in activity
    assert 'VpnService.prepare(this)' in activity
    assert 'Libbox.checkConfig(config)' in activity
    assert 'Settings.rebuildServiceMode()' in activity
    assert 'BoxService.start()' in activity
    assert 'BoxService.stop()' in activity
    assert '"wireguard"' in activity
    assert '"vless"' in activity
    assert '"vmess"' in activity
    assert '"hysteria2"' in activity
    assert '"npvt-ssh"' in activity
    assert 'applicationId = "com.makia.client"' in patch
    assert 'a3668ae6e4bbcb3ceff8461d0cac55d79edf504f' in workflow
    assert 'v1.14.1' in workflow
    assert 'build_libbox -target android' in workflow
    assert ':app:assembleOtherDebug' in workflow
    assert 'Makia-Android-Connector-RC' in workflow
    assert 'function directSupported(x)' in js
    assert 'p!=="android"' in js


def test_connector_public_origin_uses_forwarded_https(monkeypatch):
    class RequestStub:
        headers={"x-forwarded-proto":"https","host":"panel.example.test"}
        base_url="http://127.0.0.1:8000/"
    monkeypatch.delenv("MAKIA_PUBLIC_BASE_URL",raising=False)
    assert client_portal._public_origin(RequestStub())=="https://panel.example.test"


def test_connector_public_origin_prefers_explicit_https(monkeypatch):
    class RequestStub:
        headers={"host":"internal.local:8000"}
        base_url="http://internal.local:8000/"
    monkeypatch.setenv("MAKIA_PUBLIC_BASE_URL","https://vpn.example.test/")
    assert client_portal._public_origin(RequestStub())=="https://vpn.example.test"


def test_connector_public_origin_ignores_forwarded_host(monkeypatch):
    class RequestStub:
        headers={
            "x-forwarded-proto":"https",
            "x-forwarded-host":"attacker.example",
            "host":"panel.example.test",
        }
        base_url="http://127.0.0.1:8000/"
    monkeypatch.delenv("MAKIA_PUBLIC_BASE_URL",raising=False)
    assert client_portal._public_origin(RequestStub())=="https://panel.example.test"
