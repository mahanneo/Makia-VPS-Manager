from pathlib import Path

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
