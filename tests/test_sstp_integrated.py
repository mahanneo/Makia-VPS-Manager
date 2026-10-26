"""SSTP safety gates: require an independently verified listener, never claim nginx 443."""
from pathlib import Path
import stat

import pytest
from app import sstp_ops, protocol_ops, access_ops, main


def test_missing_daemon_remains_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(sstp_ops, "CONFIG_LOCATIONS", (tmp_path / "missing.conf",))
    monkeypatch.setattr(sstp_ops, "SSTP_CHAP", tmp_path / "missing.secrets")
    monkeypatch.setattr(sstp_ops.shutil, "which", lambda name: None)
    result = sstp_ops.sstp_status()
    assert not result["ready"]
    assert not result["installed"]
    with pytest.raises(protocol_ops.ProtocolError, match="unavailable"):
        sstp_ops.create_sstp_user("client001")


def test_existing_nginx_listener_cannot_be_treated_as_sstp(monkeypatch, tmp_path):
    conf = tmp_path / "accel.conf"
    store = tmp_path / "sstp-chap-secrets"
    conf.write_text(
        "[modules]\nsstp\nchap-secrets\n[sstp]\nbind=203.0.113.2\nport=443\n"
        "host-name=vpn.example.test\nssl-pemfile=/tmp/cert.pem\n"
        "ssl-keyfile=/tmp/key.pem\n"
        "[chap-secrets]\nchap-secrets=" + str(store) + "\n"
    )
    store.write_text("")
    store.chmod(0o600)
    monkeypatch.setattr(sstp_ops, "CONFIG_LOCATIONS", (conf,))
    monkeypatch.setattr(sstp_ops, "SSTP_CHAP", store)
    monkeypatch.setattr(sstp_ops.shutil, "which", lambda name: "/usr/bin/accel-pppd")
    monkeypatch.setattr(sstp_ops, "_listener", lambda bind, port: (True, False))
    status = sstp_ops.sstp_status()
    assert status["tcp_443_occupied"]
    assert status["listener"] is False
    assert status["ready"] is False


def test_sstp_account_file_only_written_if_ready(monkeypatch, tmp_path):
    store=tmp_path/"sstp-chap-secrets"
    store.write_text("")
    store.chmod(0o600)
    monkeypatch.setattr(sstp_ops, "SSTP_CHAP", store)
    monkeypatch.setattr(sstp_ops, "sstp_status", lambda: {"ready":True,"domain":"vpn.example.test"})
    result=sstp_ops.create_sstp_user("client001", "ValidPassword123")
    assert result["name"]=="client001"
    assert "ValidPassword123" in store.read_text()
    assert stat.S_IMODE(store.stat().st_mode)==0o600
    assert sstp_ops.get_sstp_user_credentials("client001")["password"]=="ValidPassword123"
    assert sstp_ops.list_sstp_users()==[{"name":"client001"}]
    with pytest.raises(protocol_ops.ProtocolError, match="exists"):
        sstp_ops.create_sstp_user("client001")
    result=sstp_ops.remove_sstp_user("client001")
    assert result["ok"] and result["warning"]
    assert sstp_ops.list_sstp_users()==[]


def test_sstp_rejects_injection(monkeypatch, tmp_path):
    store=tmp_path/"sstp-chap-secrets"
    store.write_text("")
    store.chmod(0o600)
    monkeypatch.setattr(sstp_ops, "SSTP_CHAP", store)
    monkeypatch.setattr(sstp_ops, "sstp_status", lambda: {"ready":True,"domain":"vpn.example.test"})
    for bad_name in ["root\nadmin", "../root", "a", "username test"]:
        with pytest.raises(protocol_ops.ProtocolError):
            sstp_ops.create_sstp_user(bad_name)
    with pytest.raises(protocol_ops.ProtocolError):
        sstp_ops.create_sstp_user("client001", "bad pass space")
    assert store.read_text()==""


def test_sstp_native_connection_profile_uses_no_fake_apple_or_psk():
    profile = access_ops.native_vpn_payload(
        "sstp","client001","vpn.example.test","client001","ValidPassword123"
    )
    assert profile["native_filename"].endswith("-sstp.txt")
    assert all(not name.endswith(".mobileconfig") for name in profile["files"])
    assert "SSTP" in profile["primary_text"]
    assert "MS-CHAPv2" in profile["primary_text"]
    assert "Disable certificate" not in profile["primary_text"]


def test_sstp_authenticated_routes_wired_and_dashboard_visible():
    paths = {
        (route.path, ",".join(sorted(route.methods or [])))
        for route in main.app.routes if hasattr(route, "methods")
    }
    assert ("/api/protocols/sstp/users","POST") in paths
    assert ("/api/protocols/sstp/users","GET") in paths
    assert ("/api/protocols/sstp/users/{name}","DELETE") in paths
    assert ("/api/protocols/sstp/diagnostics","GET") in paths
    ui=Path(__file__).resolve().parents[1]/"app/static/app.js"
    html=Path(__file__).resolve().parents[1]/"app/templates/dashboard.html"
    assert "sstpWorkspace" in ui.read_text()
    assert 'data-view="sstp"' in html.read_text()
