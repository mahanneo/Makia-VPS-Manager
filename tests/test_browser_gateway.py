import base64
import json
from pathlib import Path

from app import browser_gateway

ROOT=Path(__file__).resolve().parents[1]


def test_gateway_rejects_non_public_addresses():
    for value in ["127.0.0.1","10.0.0.1","172.16.0.1","192.168.1.1","169.254.169.254","::1","fc00::1","fe80::1"]:
        assert browser_gateway._public_ip(value) is False
    assert browser_gateway._public_ip("8.8.8.8") is True
    assert browser_gateway._public_ip("1.1.1.1") is True


def test_gateway_basic_auth_parser():
    raw=base64.b64encode(b"alice:secret").decode()
    assert browser_gateway._parse_basic("Basic "+raw)==["alice","secret"]
    assert browser_gateway._parse_basic("Bearer nope")== (None,None)


def test_gateway_request_parser_strips_proxy_credentials():
    auth=base64.b64encode(b"alice:secret").decode()
    raw=(
        "CONNECT example.com:443 HTTP/1.1\r\n"
        "Host: example.com:443\r\n"
        f"Proxy-Authorization: Basic {auth}\r\n"
        "Proxy-Connection: keep-alive\r\n\r\n"
    ).encode("ascii")
    method,target,version,headers,auth_header=browser_gateway._parse_request(raw)
    assert method=="CONNECT"
    assert target=="example.com:443"
    assert auth_header=="Basic "+auth
    assert all(name.lower()!="proxy-authorization" for name,_ in headers)
    assert all(name.lower()!="proxy-connection" for name,_ in headers)


def test_gateway_default_destination_ports_are_web_only():
    assert browser_gateway.ALLOWED_PORTS=={80,443}


def test_extension_is_pure_browser_no_native_messaging():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert manifest["version"]=="1.6.0"
    assert "nativeMessaging" not in manifest["permissions"]
    assert "webRequestAuthProvider" in manifest["permissions"]
    assert "sendNativeMessage" not in background
    assert 'scheme:"https"' in background
    assert 'host:"127.0.0.1"' not in background


def test_gateway_service_hardening_contract():
    service=(ROOT/"systemd/makia-browser-gateway.service").read_text(encoding="utf-8")
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
    assert "ReadOnlyPaths=/etc/letsencrypt" in service
    assert "ReadWritePaths=/opt/makia-vps-manager/data" in service


def test_client_store_has_browser_token_and_usage_tables():
    source=(ROOT/"app/client_store.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS client_browser_tokens" in source
    assert "CREATE TABLE IF NOT EXISTS client_browser_usage" in source
    assert "def issue_browser_proxy_token" in source
    assert "def browser_proxy_auth" in source
    assert "def add_browser_usage" in source
    assert "client_browser_usage" in source.split("def account_usage_bytes",1)[1].split("def ",1)[0]


def test_extension_api_supports_store_id_allowlist():
    source=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    assert "MAKIA_BROWSER_EXTENSION_IDS" in source
    assert "def _browser_extension_ids" in source
    assert "def _browser_extension_origin" in source
    assert 're.fullmatch(r"[a-p]{32}"' in source


def test_gateway_connection_counter_only_decrements_after_successful_increment():
    source=(ROOT/"app/browser_gateway.py").read_text(encoding="utf-8")
    assert "counted_active=False" in source
    assert "counted_active=True" in source
    assert "if account_id and counted_active:" in source


def test_gateway_tls_host_honors_explicit_override():
    source=(ROOT/"app/browser_gateway.py").read_text(encoding="utf-8")
    assert 'os.getenv("MAKIA_BROWSER_GATEWAY_HOST","") or get_setting("panel_domain","")' in source
