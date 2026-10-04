import json
from pathlib import Path

import pytest

from app import client_browser, client_store, db

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture()
def client_db(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","test-admin-password-12345")
    db.init_db()
    client_store.init_client_db()
    return tmp_path/"makia.db"


def test_browser_pair_code_is_hashed_one_time_and_reuses_client_session_controls(client_db):
    account_id=client_store.create_account("browser01","browser-pass-001",device_limit=1)
    device,_=client_store.register_or_get_device(account_id,label="Windows Chrome",platform="windows")
    pair=client_browser.issue_pair_code(account_id,device["id"],ttl=120)
    with db.connect() as con:
        row=con.execute("SELECT token_hash FROM client_browser_pair_tickets").fetchone()
        assert row and pair["code"] not in row["token_hash"]
    redeemed=client_browser.redeem_pair_code(pair["code"],"127.0.0.1")
    session=client_store.session_by_token(redeemed["token"],"127.0.0.1")
    assert session and session["account_id"]==account_id and session["device_id"]==device["id"]
    with pytest.raises(PermissionError):
        client_browser.redeem_pair_code(pair["code"],"127.0.0.1")
    client_store.set_account_password(account_id,"browser-pass-002")
    assert client_store.session_by_token(redeemed["token"],"127.0.0.1") is None


def test_browser_pair_code_rejects_revoked_device(client_db):
    account_id=client_store.create_account("browser02","browser-pass-003",device_limit=1)
    device,_=client_store.register_or_get_device(account_id,label="Windows Chrome",platform="windows")
    pair=client_browser.issue_pair_code(account_id,device["id"])
    client_store.revoke_device(account_id,device["id"])
    with pytest.raises(PermissionError):
        client_browser.redeem_pair_code(pair["code"],"127.0.0.1")


def test_browser_extension_manifest_is_narrow_and_manifest_v3():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"]==3
    assert set(manifest["permissions"])=={"nativeMessaging","proxy","privacy"}
    assert "host_permissions" not in manifest
    assert "content_scripts" not in manifest
    assert manifest["background"]["service_worker"]=="background.js"
    assert manifest["key"]
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert "disable_non_proxied_udp" in background
    assert "clearWebRtcLeakProtection" in background
    assert (ROOT/"client/browser-extension/icons/makia.png").is_file()


def test_browser_host_and_connector_contract_is_narrow():
    host=(ROOT/"client/windows/makia_browser_host.py").read_text(encoding="utf-8")
    connector=(ROOT/"client/windows/makia_client_connector.py").read_text(encoding="utf-8")
    installer=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    workflow=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    for action in ('action=="pair"','action=="me"','action=="protocols"','action=="status"','action=="connect"','action=="disconnect"','action=="logout"'):
        assert action in host
    assert "subprocess.list2cmdline" in host
    assert "ShellExecuteW" in host
    assert "def singbox_browser_config" in connector
    assert "browser_only=False" in connector
    assert "MakiaBrowserHost.exe" in workflow
    assert "Makia-Browser-Extension-Chromium-1.4.0" in workflow
    assert "NativeMessagingHosts" in installer
    assert "kifidlpkeejegkcolpjfipmjllldakik" in installer
