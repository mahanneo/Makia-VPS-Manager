import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_browser_extension_manifest_contract():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"]==3
    assert manifest["version"]=="1.5.0"
    permissions=set(manifest["permissions"])
    assert "nativeMessaging" not in permissions
    assert {"storage","proxy","webRequest","webRequestAuthProvider","alarms"} <= permissions
    assert manifest["host_permissions"]==["<all_urls>"]
    assert '"key"' in (ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8")


def test_extension_is_pure_browser_and_uses_secure_proxy_gateway():
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    popup=(ROOT/"client/browser-extension/popup.js").read_text(encoding="utf-8")
    assert "sendNativeMessage" not in background
    assert "com.makia.browser_host" not in background
    assert 'scheme:"https"' in background
    assert "/client/extension/browser-session" in background
    assert "chrome.webRequest.onAuthRequired" in background
    assert "chrome.storage.session" in background
    assert "proxyUsername" in background and "proxyPassword" in background
    assert "/client/extension/browser-status" in popup
    assert "/client/extension/connect/" not in popup


def test_extension_api_never_returns_protocol_delivery_secrets():
    source=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    block=source.split('@router.post("/client/extension/browser-session")',1)[1]
    block=block.split("\n@router.",1)[0]
    assert "share_link" not in block
    assert "native_base64" not in block
    assert '"username":proxy["username"]' in block
    assert '"password":proxy["password"]' in block
    assert '"ttl":proxy["ttl"]' in block


def test_gateway_runtime_is_managed_by_install_update_and_tls_hook():
    install=(ROOT/"scripts/install.sh").read_text(encoding="utf-8")
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    tls=(ROOT/"scripts/makia-vpn-tls-sync.sh").read_text(encoding="utf-8")
    unit=(ROOT/"systemd/makia-browser-gateway.service").read_text(encoding="utf-8")
    assert "makia-browser-gateway.service" in install
    assert "makia-browser-gateway-sync" in install
    assert "makia-browser-gateway.service" in update
    assert "makia-browser-gateway-sync" in update
    assert "systemctl restart makia-browser-gateway" in tls
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit


def test_gateway_blocks_lan_pivot_by_contract():
    source=(ROOT/"app/browser_gateway.py").read_text(encoding="utf-8")
    assert "addr.is_global" in source
    assert "private/reserved proxy targets are blocked" in source
    assert "ALLOWED_CONNECT_PORTS={80,443}" in source
    assert 'if int(port)!=443' in source
