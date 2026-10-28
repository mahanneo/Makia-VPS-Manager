from pathlib import Path
from types import SimpleNamespace
import json
import os
import urllib.parse

import pytest

from app import access_ops, tuic_ops


def _config(port=8445, users=None):
    return {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "tuic", "tag": tuic_ops.INBOUND_TAG,
            "listen": "0.0.0.0", "listen_port": port,
            "users": list(users or []),
            "congestion_control": "bbr", "zero_rtt_handshake": False,
            "tls": {"enabled": True, "alpn": ["h3"],
                    "certificate_path": "/etc/sing-box/tls/fullchain.pem",
                    "key_path": "/etc/sing-box/tls/privkey.pem"},
        }],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }


def test_tuic_share_link_encodes_password_and_keeps_tls_parameters():
    user = {"uuid": "4f3dfe2b-2f22-4f14-a3b7-7db6b824e6af", "password": "p@ss:/?&+word"}
    link = tuic_ops.share_link_for_user("test_user", user, "P.Mahinet.Shop", 8445)
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme == "tuic"
    assert parsed.hostname == "p.mahinet.shop"
    assert parsed.port == 8445
    assert urllib.parse.unquote(parsed.password) == user["password"]
    assert query["sni"] == ["P.Mahinet.Shop"]
    assert query["alpn"] == ["h3"]
    assert query["congestion_control"] == ["bbr"]
    assert query["udp_relay_mode"] == ["native"]
    assert "zero_rtt" not in query


def test_tuic_username_validation_rejects_path_and_control_characters():
    assert tuic_ops._validate_name("client_01") == "client_01"
    for name in ("", "a", "two words", "../admin", "x/y", "bad\nname"):
        with pytest.raises(tuic_ops.TUICError):
            tuic_ops._validate_name(name)


def test_tuic_payload_contains_share_link_qr_and_safe_guide():
    link = "tuic://4f3dfe2b-2f22-4f14-a3b7-7db6b824e6af:random@p.mahinet.shop:8445?alpn=h3&sni=p.mahinet.shop#test"
    payload = access_ops.tuic_payload("test_user", link, "p.mahinet.shop", 8445)
    assert payload["native_filename"] == "test_user-tuic.txt"
    assert payload["primary_text"] == link
    assert payload["share_type"] == "tuic"
    assert "test_user-tuic-qr.svg" in payload["files"]
    assert b"tuic://" in payload["files"]["test_user-tuic.txt"]
    assert "Zero-RTT" in payload["files"]["connection-guide-fa.txt"].decode()
    assert access_ops.describe_tuic_share(link)["port"] == 8445
    assert access_ops.describe_tuic_share(link)["sni"] == "p.mahinet.shop"


def test_tuic_status_is_read_only_and_safe_when_runtime_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(tuic_ops, "CONFIG_PATH", tmp_path / "missing-config.json")
    monkeypatch.setattr(tuic_ops, "STATE_PATH", tmp_path / "missing-state.json")
    monkeypatch.setattr(tuic_ops, "TLS_CERT", tmp_path / "missing-cert.pem")
    monkeypatch.setattr(tuic_ops, "TLS_KEY", tmp_path / "missing-key.pem")
    monkeypatch.setattr(tuic_ops, "_binary", lambda: None)
    monkeypatch.setattr(tuic_ops, "_active", lambda: False)
    monkeypatch.setattr(tuic_ops, "get_setting", lambda key, default="": default)
    state = tuic_ops.status()
    assert state["installed"] is False
    assert state["ready"] is False
    assert state["port"] == 8445
    assert state["users_count"] == 0
    assert state["warnings"]
    assert not (tmp_path / "missing-config.json").exists()


def test_tuic_config_update_validates_backups_and_atomically_applies(tmp_path, monkeypatch):
    config_path = tmp_path / "etc" / "sing-box" / "makia-tuic.json"
    config_path.parent.mkdir(parents=True)
    old = _config(users=[{"name": "before", "uuid": "old", "password": "old-password"}])
    config_path.write_text(json.dumps(old), encoding="utf-8")
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(tuic_ops, "CONFIG_PATH", config_path)
    monkeypatch.setattr(tuic_ops, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(tuic_ops, "_binary", lambda: "/usr/bin/sing-box")
    monkeypatch.setattr(tuic_ops, "_run", lambda args, timeout=30: "")
    monkeypatch.setattr(tuic_ops, "_active", lambda: True)
    monkeypatch.setattr(tuic_ops, "_port_listener", lambda port: port == 8445)
    monkeypatch.setattr(tuic_ops.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=os.getegid()))

    new = _config(users=[{"name": "after", "uuid": "new", "password": "new-password"}])
    result = tuic_ops._write_config(new)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["inbounds"][0]["users"][0]["name"] == "after"
    assert result["port"] == 8445
    assert result["backup"]
    assert json.loads(Path(result["backup"]).read_text(encoding="utf-8"))["inbounds"][0]["users"][0]["name"] == "before"
    assert config_path.stat().st_mode & 0o777 == 0o640


def test_tuic_config_update_rolls_back_if_udp_listener_does_not_return(tmp_path, monkeypatch):
    config_path = tmp_path / "etc" / "sing-box" / "makia-tuic.json"
    config_path.parent.mkdir(parents=True)
    old = _config(users=[{"name": "keep", "uuid": "keep-uuid", "password": "keep-password"}])
    original = json.dumps(old)
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(tuic_ops, "CONFIG_PATH", config_path)
    monkeypatch.setattr(tuic_ops, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(tuic_ops, "_binary", lambda: "/usr/bin/sing-box")
    monkeypatch.setattr(tuic_ops, "_run", lambda args, timeout=30: "")
    monkeypatch.setattr(tuic_ops, "_active", lambda: True)
    monkeypatch.setattr(tuic_ops, "_port_listener", lambda port: False)
    monkeypatch.setattr(tuic_ops.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=os.getegid()))
    ticks = iter([0, 1, 9])
    monkeypatch.setattr(tuic_ops.time, "time", lambda: next(ticks, 10))
    monkeypatch.setattr(tuic_ops.time, "sleep", lambda _seconds: None)

    with pytest.raises(tuic_ops.TUICError, match="rolled back"):
        tuic_ops._write_config(_config(users=[{"name": "new", "uuid": "new", "password": "new-password"}]))
    assert config_path.read_text(encoding="utf-8") == original
