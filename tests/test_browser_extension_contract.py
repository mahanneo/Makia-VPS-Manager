import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_browser_extension_manifest_contract():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"]==3
    assert manifest["version"]=="1.6.4.2"
    assert "nativeMessaging" not in manifest["permissions"]
    assert "webRequest" in manifest["permissions"]
    assert "webRequestAuthProvider" in manifest["permissions"]
    assert "privacy" in manifest["permissions"]
    assert "proxy" in manifest["permissions"]
    assert manifest["host_permissions"]==["<all_urls>"]
    assert manifest["optional_host_permissions"]==["https://*/*"]


def test_browser_extension_has_no_windows_native_host_dependency():
    manifest=(ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8")
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    install=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    assert "nativeMessaging" not in manifest
    assert "sendNativeMessage" not in background
    assert "NativeMessagingHosts" not in install
    assert "MakiaBrowserHost" not in install


def test_windows_package_is_full_device_only():
    install=(ROOT/"client/windows/install.ps1").read_text(encoding="utf-8")
    guide=(ROOT/"client/windows/INSTALL.txt").read_text(encoding="utf-8")
    assert "MakiaClientConnector.exe" in install
    assert "sing-box.exe" in install
    assert "Browser-only users" in guide
    assert "Makia Browser VPN" in guide


def test_proxy_auth_is_scoped_to_exact_gateway_challenger():
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert "details.challenger" in background
    assert "challengerHost !== expectedHost" in background
    assert "challengerPort !== expectedPort" in background


def test_browser_extension_enables_webrtc_and_dns_leak_protection():
    manifest=json.loads((ROOT/"client/browser-extension/manifest.json").read_text(encoding="utf-8"))
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert "privacy" in manifest["permissions"]
    assert "disable_non_proxied_udp" in background
    assert "networkPredictionEnabled.set" in background
    assert "networkPredictionEnabled.clear" in background
    assert "webRTCIPHandlingPolicy.clear" in background


def test_verified_proxy_requires_real_egress_probe_and_effective_chrome_settings():
    background=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    popup=(ROOT/"client/browser-extension/popup.js").read_text(encoding="utf-8")
    assert 'levelOfControl==="controlled_by_this_extension"' in background
    assert "verifyBrowserProxy()" in background
    assert 'exitIp===s.directIp' in background
    assert 'IP verification unavailable' in background
    assert 'connectionError' in background
    assert 'action:"verify"' in popup
    assert 'action:"status"' in popup


def test_proxy_errors_must_reverify_before_disconnecting():
    bg=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    assert "let proxyErrorRecheck=null" in bg
    assert "await verifyBrowserProxy();" in bg.split("chrome.proxy.onProxyError.addListener",1)[1]
    assert "Makia proxy changed during egress verification" in bg


def test_browser_auth_diagnostics_never_persist_credentials():
    source=(ROOT/"client/browser-extension/background.js").read_text(encoding="utf-8")
    popup=(ROOT/"client/browser-extension/popup.js").read_text(encoding="utf-8")
    assert 'authDiagnostic' in source
    assert 'authDiagnostic' in popup
    assert 'note("درخواست رمز Gateway دریافت شد' in source
    assert 'chrome.storage.local.set({proxyAuth:' not in source
