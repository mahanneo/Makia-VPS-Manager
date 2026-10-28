import os
from pathlib import Path

from app import network_services


def test_mtproxy_config_records_detected_public_ipv4_for_faketls(tmp_path, monkeypatch):
    config = tmp_path / "mtproxy.toml"
    monkeypatch.setattr(network_services, "MTPROXY_CONFIG", config)
    monkeypatch.setattr(network_services, "_default_public_ipv4", lambda: "198.51.100.23")
    monkeypatch.setattr(network_services, "_ensure_mtproxy_config_access", lambda: os.getgid())
    monkeypatch.setattr(network_services.os, "chown", lambda *args, **kwargs: None)
    secret = "ee0123456789abcdef0123456789abcdef"
    network_services._write_mtproxy_config(secret, 10443)
    text = config.read_text(encoding="utf-8")
    assert f'secret = "{secret}"' in text
    assert 'bind-to = "0.0.0.0:10443"' in text
    assert 'public-ipv4 = "198.51.100.23"' in text
    assert '[network]' in text
    assert 'dns = "https://1.1.1.1"' in text
