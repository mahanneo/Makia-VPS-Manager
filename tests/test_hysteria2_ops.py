from pathlib import Path
from types import SimpleNamespace
import json
import os
import urllib.parse

import pytest

from app import access_ops, hysteria2_ops


def _config(port=8446, users=None):
    return {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "hysteria2", "tag": hysteria2_ops.INBOUND_TAG,
            "listen": "0.0.0.0", "listen_port": port,
            "users": list(users or []),
            "tls": {"enabled": True, "alpn": ["h3"],
                    "certificate_path": "/etc/sing-box/tls/fullchain.pem",
                    "key_path": "/etc/sing-box/tls/privkey.pem"},
        }],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }


def test_hysteria2_share_link_escapes_password_and_keeps_tls_sni():
    user = {"name": "test_user", "password": "p@ss:/?&+word"}
    link = hysteria2_ops.share_link_for_user("test_user", user, "P.Mahinet.Shop", 8446)
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme == "hysteria2"
    assert parsed.hostname == "p.mahinet.shop"
    assert parsed.port == 8446
    assert urllib.parse.unquote(parsed.username or "") == user["password"]
    assert parsed.password is None
    assert query["sni"] == ["P.Mahinet.Shop"]
    assert query["alpn"] == ["h3"]


def test_hysteria2_listener_parser_uses_ss_headerless_local_address(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(hysteria2_ops.shutil, "which", lambda name: "/usr/bin/ss" if name == "ss" else None)
    monkeypatch.setattr(hysteria2_ops.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='UNCONN 0 0 0.0.0.0:8446 0.0.0.0:* users:(("sing-box",pid=123,fd=7))\\n'
    ))
    assert hysteria2_ops._port_listener(8446)
    assert not hysteria2_ops._port_listener(8445)


def test_hysteria2_username_validation_rejects_path_and_control_characters():
    assert hysteria2_ops._validate_name("client_01") == "client_01"
    for name in ("", "a", "two words", "../admin", "x/y", "bad\nname"):
        with pytest.raises(hysteria2_ops.Hysteria2Error):
            hysteria2_ops._validate_name(name)


def test_hysteria2_payload_contains_share_link_qr_and_safe_guide():
    link = "hysteria2://random%2Fpassword@p.mahinet.shop:8446/?alpn=h3&sni=p.mahinet.shop#test"
    payload = access_ops.hysteria2_payload("test_user", link, "p.mahinet.shop", 8446)
    assert payload["native_filename"] == "test_user-hysteria2.txt"
    assert payload["primary_text"] == link
    assert payload["share_type"] == "hysteria2"
    assert "test_user-hysteria2-qr.svg" in payload["files"]
    assert b"hysteria2://" in payload["files"]["test_user-hysteria2.txt"]
    assert "Hysteria2" in payload["files"]["connection-guide-fa.txt"].decode()
    desc = access_ops.describe_hysteria2_share(link)
    assert desc["port"] == 8446
    assert desc["sni"] == "p.mahinet.shop"
    assert desc["transport"] == "udp/quic"


def test_hysteria2_status_is_read_only_and_safe_when_runtime_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(hysteria2_ops, "CONFIG_PATH", tmp_path / "missing-config.json")
    monkeypatch.setattr(hysteria2_ops, "STATE_PATH", tmp_path / "missing-state.json")
    monkeypatch.setattr(hysteria2_ops, "TLS_CERT", tmp_path / "missing-cert.pem")
    monkeypatch.setattr(hysteria2_ops, "TLS_KEY", tmp_path / "missing-key.pem")
    monkeypatch.setattr(hysteria2_ops, "_binary", lambda: None)
    monkeypatch.setattr(hysteria2_ops, "_active", lambda: False)
    monkeypatch.setattr(hysteria2_ops, "get_setting", lambda key, default="": default)
    state = hysteria2_ops.status()
    assert state["installed"] is False
    assert state["ready"] is False
    assert state["port"] == 8446
    assert state["users_count"] == 0
    assert state["warnings"]
    assert not (tmp_path / "missing-config.json").exists()


def test_hysteria2_config_update_validates_backups_and_atomically_applies(tmp_path, monkeypatch):
    config_path = tmp_path / "etc" / "sing-box" / "makia-hysteria2.json"
    config_path.parent.mkdir(parents=True)
    old = _config(users=[{"name": "before", "password": "old-password"}])
    config_path.write_text(json.dumps(old), encoding="utf-8")
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(hysteria2_ops, "CONFIG_PATH", config_path)
    monkeypatch.setattr(hysteria2_ops, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(hysteria2_ops, "_binary", lambda: "/usr/bin/sing-box")
    monkeypatch.setattr(hysteria2_ops, "_run", lambda args, timeout=30: "")
    monkeypatch.setattr(hysteria2_ops, "_active", lambda: True)
    monkeypatch.setattr(hysteria2_ops, "_port_listener", lambda port: port == 8446)
    monkeypatch.setattr(hysteria2_ops.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=os.getegid()))

    new = _config(users=[{"name": "after", "password": "new-password"}])
    result = hysteria2_ops._write_config(new)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["inbounds"][0]["users"][0]["name"] == "after"
    assert result["port"] == 8446
    assert result["backup"]
    assert json.loads(Path(result["backup"]).read_text(encoding="utf-8"))["inbounds"][0]["users"][0]["name"] == "before"
    assert config_path.stat().st_mode & 0o777 == 0o640


def test_hysteria2_config_update_rolls_back_if_udp_listener_does_not_return(tmp_path, monkeypatch):
    config_path = tmp_path / "etc" / "sing-box" / "makia-hysteria2.json"
    config_path.parent.mkdir(parents=True)
    old = _config(users=[{"name": "keep", "password": "keep-password"}])
    original = json.dumps(old)
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(hysteria2_ops, "CONFIG_PATH", config_path)
    monkeypatch.setattr(hysteria2_ops, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(hysteria2_ops, "_binary", lambda: "/usr/bin/sing-box")
    monkeypatch.setattr(hysteria2_ops, "_run", lambda args, timeout=30: "")
    monkeypatch.setattr(hysteria2_ops, "_active", lambda: True)
    monkeypatch.setattr(hysteria2_ops, "_port_listener", lambda port: False)
    monkeypatch.setattr(hysteria2_ops.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=os.getegid()))
    ticks = iter([0, 1, 9])
    monkeypatch.setattr(hysteria2_ops.time, "time", lambda: next(ticks, 10))
    monkeypatch.setattr(hysteria2_ops.time, "sleep", lambda _seconds: None)

    with pytest.raises(hysteria2_ops.Hysteria2Error, match="rolled back"):
        hysteria2_ops._write_config(_config(users=[{"name": "new", "password": "new-password"}]))
    assert config_path.read_text(encoding="utf-8") == original


def test_hysteria2_service_isolated_and_pinned_setup_contract():
    root = Path(__file__).resolve().parents[1]
    unit = (root / "systemd/makia-hysteria2.service").read_text(encoding="utf-8")
    setup = (root / "scripts/setup-hysteria2-backend.sh").read_text(encoding="utf-8")
    assert "User=sing-box" in unit
    assert "Group=sing-box" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    assert "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK" in unit
    assert 'PINNED_VERSION="1.14.4"' in setup
    assert 'UDP/$PORT is already bound. No changes made.' in setup
    assert "refusing to overwrite users or runtime state" in setup
    assert "UDP/8446" in setup
    assert "no Hysteria2 listener is active yet" in setup
    assert "systemctl enable --now makia-hysteria2.service" not in setup
    assert "trap rollback_setup ERR" in setup
    assert "previous files restored" in setup
    assert "/etc/makia-vps-manager/hysteria2-state.json" in setup
