import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_browser_extension_manifest_contract():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"]==3
    assert manifest["version"]=="1.5.0"
    assert "nativeMessaging" not in manifest["permissions"]
    assert "webRequest" in manifest["permissions"]
    assert "webRequestAuthProvider" in manifest["permissions"]
    assert manifest["host_permissions"]==["<all_urls>"]
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


def test_windows_installer_has_machine_and_user_native_host_registration():
    source=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    assert "HKCU:\\Software\\Google\\Chrome\\NativeMessagingHosts" in source
    assert "HKLM:\\Software\\Google\\Chrome\\NativeMessagingHosts" in source
    assert "HKLM:\\Software\\Microsoft\\Edge\\NativeMessagingHosts" in source
    assert "WOW6432Node" in source
    assert "--self-test" in source
    assert "jgpmmenelldgfmjfnonhjaaaccfeniji" in source


def test_browser_repair_tools_are_packaged_sources():
    assert (ROOT/"client/windows/Repair-Makia-Browser.cmd").is_file()
    assert (ROOT/"client/windows/Check-Makia-Browser.ps1").is_file()


def test_proxy_auth_is_scoped_to_exact_gateway_challenger():
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert "details.challenger" in background
    assert "challengerHost !== expectedHost" in background
    assert "challengerPort !== expectedPort" in background
