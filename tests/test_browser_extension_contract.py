import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_browser_extension_manifest_contract():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"]==3
    assert manifest["version"]=="1.4.1"
    assert "nativeMessaging" in manifest["permissions"]
    assert "proxy" in manifest["permissions"]
    assert manifest["optional_host_permissions"]==["https://*/*"]

def test_native_host_and_extension_id_contract():
    install=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    manifest=(ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8")
    extension_id="jgpmmenelldgfmjfnonhjaaaccfeniji"
    assert extension_id in install
    assert '"key"' in manifest
    assert "Google\\Chrome\\NativeMessagingHosts" in install
    assert "Microsoft\\Edge\\NativeMessagingHosts" in install

def test_browser_state_is_isolated_from_device_state():
    source=(ROOT/"client/windows/makia_client_connector.py").read_text(encoding="utf-8")
    assert 'BROWSER_STATE=ROOT/"browser-state.json"' in source
    assert 'BROWSER_PROFILE=ROOT/"browser-active.json"' in source
    assert 'connection_mode=="browser"' in source

def test_extension_api_never_returns_delivery_secret():
    source=(ROOT/"app/client_portal.py").read_text(encoding="utf-8")
    block=source.split('@router.post("/client/extension/connect/{delivery_kind}/{delivery_id}/ticket")',1)[1]
    assert '"ticket":ticket["ticket"]' in block
    assert '"share_link"' not in block.split("\n@router.",1)[0]
