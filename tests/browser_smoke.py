import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


import pyzipper
from playwright.sync_api import sync_playwright

DATA=Path(os.environ["MAKIA_DATA_DIR"])
BASE_URL="http://127.0.0.1:8787"
PASSWORD=os.environ["MAKIA_INITIAL_ADMIN_PASSWORD"]


def seed():
    shutil.rmtree(DATA,ignore_errors=True)
    DATA.mkdir(parents=True,exist_ok=True)
    from app.db import init_db, create_protocol_client, upsert_access_artifact, get_protocol_client
    from app import access_ops

    init_db()
    client_id=create_protocol_client(
        "browser-client","xray","vless","browser-inbound","browser-credential",
        "vless://browser-credential@example.test:443?type=tcp&security=none#browser-client",
        0,0,1,0,
    )
    payload=access_ops.xray_payload(
        "browser-client","vless",
        "vless://browser-credential@example.test:443?type=tcp&security=none#browser-client",
        f"{BASE_URL}/sub/browser?format=base64",
        f"{BASE_URL}/client/browser",
    )
    upsert_access_artifact(
        "xray",str(client_id),"browser-client","vless",payload["native_filename"],
        access_ops.seal_payload(payload),"{}",
    )
    return client_id,get_protocol_client(client_id)["subscription_id"]


def wait_server(timeout=20):
    deadline=time.time()+timeout
    while time.time()<deadline:
        try:
            with urllib.request.urlopen(BASE_URL+"/healthz",timeout=1) as r:
                if r.status==200:
                    return
        except Exception:
            time.sleep(.25)
    raise RuntimeError("test server did not become healthy")


def leave_sidebar(page):
    vp=page.viewport_size or {"width":1280,"height":800}
    page.mouse.move(max(12,min(vp["width"]-20,vp["width"]//2)),max(12,min(vp["height"]-20,vp["height"]//2)))
    page.wait_for_timeout(250)


def main():
    client_id,subscription_id=seed()
    env=os.environ.copy()
    proc=subprocess.Popen(
        [sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8787"],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,
    )
    try:
        wait_server()
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            portal=browser.new_page()
            portal.goto(BASE_URL+"/client/"+subscription_id,wait_until="networkidle")
            assert portal.locator(".client-qr-card").count()==2
            assert portal.locator('img[alt="Profile QR"]').count()==1
            assert portal.locator('img[alt="Subscription QR"]').count()==1
            assert portal.locator('a',has_text="راهنمای نصب و اتصال").count()==1
            portal.goto(BASE_URL+"/help/connect",wait_until="networkidle")
            assert portal.locator("#xray").count()==1
            assert portal.locator("#wireguard").count()==1
            assert portal.locator("#openvpn").count()==1
            assert portal.locator("#ssh").count()==1
            assert "چطور کانفیگ Makia را اضافه کنم؟" in portal.locator("body").inner_text()
            portal.close()

            page=browser.new_page(accept_downloads=True)
            page_errors=[]
            page.on("pageerror",lambda exc: page_errors.append(str(exc)))
            page.goto(BASE_URL+"/login",wait_until="networkidle")
            page.screenshot(path='/tmp/makia-login.png',full_page=True)
            page.locator('input[name="username"]').fill("admin")
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url(BASE_URL+"/")
            assert page.locator('body[data-theme="glass"]').count()==1
            page.locator(".sx-vitals").wait_for()
            assert page.locator(".sx-vital").count()==4
            assert page.locator(".sx-system-cell").count()==4
            assert page.locator(".sx-protocol-row").count()==4
            assert page.locator(".pro-nav").count()==1
            assert "Inboundها" in page.locator(".pro-sidebar").inner_text()
            assert page.locator('.pro-sidebar button[data-view="inbounds"]').count()>=1
            page.screenshot(path='/tmp/makia-dashboard.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="inbounds"]').click()
            leave_sidebar(page)
            page.locator(".sx-inbound-list").wait_for()
            page.screenshot(path='/tmp/makia-inbounds.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="ssh"]').click()
            leave_sidebar(page)
            page.locator(".protocol-page-header").wait_for()
            page.screenshot(path='/tmp/makia-ssh.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="xray"]').click()
            leave_sidebar(page)
            page.locator(".protocol-client-list").wait_for()
            page.screenshot(path='/tmp/makia-xray.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="openvpn"]').click()
            leave_sidebar(page)
            page.locator(".protocol-page-header").wait_for()
            page.screenshot(path='/tmp/makia-openvpn.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="support"]').click()
            leave_sidebar(page)
            page.locator(".support-hero").wait_for()
            assert "پشتیبانی Makia" in page.locator("#content").inner_text()
            page.locator("#supportGrantScope").select_option("readonly")
            page.locator('[data-action="support-grant-create"]').click()
            page.locator(".support-code-box").wait_for()
            support_code=page.locator("#supportGrantCode").inner_text().strip()
            assert support_code.startswith("SUP-")
            page.locator('[data-action="modal-close-refresh"]').click()
            support_context=browser.new_context()
            support_page=support_context.new_page()
            support_page.goto(BASE_URL+"/support/login",wait_until="networkidle")
            support_page.locator('input[name="code"]').fill(support_code)
            support_page.locator('button[type="submit"]').click()
            support_page.wait_for_url(BASE_URL+"/")
            support_page.locator("#remoteSupportBanner").wait_for()
            assert "REMOTE SUPPORT SESSION" in support_page.locator("#remoteSupportBanner").inner_text()
            support_context.close()
            page.locator('.pro-sidebar button[data-view="access"]').click()
            leave_sidebar(page)
            page.locator(".pro-user-row",has_text="browser-client").wait_for()
            page.screenshot(path='/tmp/makia-users.png',full_page=True)

            row=page.locator(".pro-user-row",has_text="browser-client")
            row.locator('[data-action="access-detail"]').click()
            page.locator(".access-detail-drawer").wait_for()
            page.screenshot(path='/tmp/makia-user-detail.png',full_page=True)
            page.locator('[data-action="access-share"]').click()
            page.locator(".share-modal").wait_for()
            assert page.locator(".share-qr").count() >= 1
            assert page.locator("#shareText").input_value().startswith("vless://")
            assert page.locator("#shareSubscription").input_value().startswith(BASE_URL+"/sub/")
            details=page.locator(".xray-share-details").inner_text()
            assert "VLESS" in details.upper()
            assert "example.test" in details
            assert "443" in details
            with page.expect_download() as qr_download:
                page.locator('[data-action="qr-download"]').click()
            qr_path=Path("/tmp/makia-browser-xray-qr.svg")
            qr_download.value.save_as(str(qr_path))
            assert "<svg" in qr_path.read_text(encoding="utf-8")
            with page.expect_download() as sub_qr_download:
                page.locator('[data-action="subscription-qr-download"]').click()
            sub_qr_path=Path("/tmp/makia-browser-xray-subscription-qr.svg")
            sub_qr_download.value.save_as(str(sub_qr_path))
            assert "<svg" in sub_qr_path.read_text(encoding="utf-8")
            page.locator('.close-btn[data-action="modal-close"]').click()

            row=page.locator(".pro-user-row",has_text="browser-client")
            row.locator('[data-action="access-detail"]').click()
            page.locator(".access-detail-drawer").wait_for()
            page.locator('[data-action="protected-export"]').click()
            page.locator("#protectedPassword").wait_for()
            page.locator("#protectedPassword").fill("739251")
            with page.expect_download() as dl:
                page.locator('[data-action="protected-download-confirm"]').click()
            zip_path=Path("/tmp/makia-browser-protected.zip")
            dl.value.save_as(str(zip_path))
            assert zip_path.stat().st_size>100
            with pyzipper.AESZipFile(zip_path,"r") as zf:
                zf.setpassword(b"739251")
                names=zf.namelist()
                assert any(name.endswith("-profile.json") for name in names)
                assert any(name.endswith("-qr.svg") for name in names)
                assert any(name.endswith("-subscription.txt") for name in names)
                assert any(name.endswith("-subscription-qr.svg") for name in names)
                assert "connection-guide-fa.txt" in names
                assert "راهنمای اتصال Makia" in zf.read("connection-guide-fa.txt").decode("utf-8")

            page.locator('.close-btn[data-action="modal-close"]').click()
            row=page.locator(".pro-user-row",has_text="browser-client")
            row.locator('[data-action="access-detail"]').click()
            page.locator(".access-detail-drawer").wait_for()
            with page.expect_download() as native:
                page.locator('[data-action="native-export"]').click()
            native_path=Path("/tmp/makia-browser-native.txt")
            native.value.save_as(str(native_path))
            assert "vless://" in native_path.read_text(encoding="utf-8")
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.locator('.pro-sidebar .pro-create-access').click()
            page.locator(".provision-drawer").wait_for()
            page.screenshot(path='/tmp/makia-new-access.png',full_page=True)
            assert page.locator(".wizard-protocol").count()==4
            page.locator('[data-action="wizard-protocol"][data-kind="ssh"]').click()
            page.locator("#wizEndpointMode").select_option("ip")
            page.locator("#wizEndpoint").fill("8.8.8.8")
            page.locator("#wizEndpointMode").select_option("domain")
            page.locator("#wizEndpoint").fill("vpn.example.com")
            page.locator("#wizEndpointMode").select_option("ip")
            assert page.locator("#wizEndpoint").input_value()=="8.8.8.8"
            page.locator('[data-action="wizard-next"]').click()
            assert page.locator("#wizSessions").count()==1
            page.locator('[data-action="wizard-next"]').click()
            assert "Endpoint" in page.locator(".review-grid").text_content()
            assert "8.8.8.8" in page.locator(".review-grid").text_content()
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.evaluate("window.__protocolData.xray.installed=true")
            page.locator('.pro-sidebar .pro-create-access').click()
            page.locator('[data-action="wizard-protocol"][data-kind="xray"]').click()
            page.locator("#wizXrayProtocol").select_option("vmess")
            page.locator("#wizEndpoint").fill("8.8.8.8")
            page.locator('[data-action="wizard-next"]').click()
            assert "VMESS" in page.locator(".recommended-profile").text_content()
            assert "TCP" in page.locator(".recommended-profile").text_content()
            assert "NONE" in page.locator(".recommended-profile").text_content()
            assert page.locator("#wizSecurity").count()==0
            page.locator('[data-action="wizard-xray-advanced"]').click()
            assert page.locator("#wizSecurity").count()==1
            page.locator('[data-action="wizard-xray-simple"]').click()
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.locator('.pro-sidebar button[data-view="dashboard"]').click()
            leave_sidebar(page)
            page.locator(".sx-vitals").wait_for()
            page.locator('[data-action="self-test"]').click()
            page.locator(".diagnostics-modal").wait_for()
            assert page.locator(".diagnostic-score.pass").count()==1
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.locator('.pro-sidebar button[data-view="wireguard"]').click()
            leave_sidebar(page)
            page.locator('.wg-workspace-hero').wait_for()
            assert page.locator('.wg-workspace-metrics>div').count()==4
            assert 'ساخت همتا' in page.locator('.wg-workspace-hero').inner_text() or 'راه‌اندازی WireGuard' in page.locator('.wg-workspace-hero').inner_text()
            page.screenshot(path='/tmp/makia-wg-desktop.png',full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            page.locator('.mobile-menu-toggle').click()
            assert page.locator('.mobile-menu-toggle').get_attribute('aria-expanded')=='true'
            page.locator('.pro-sidebar button[data-view="dashboard"]').click()
            assert page.locator('.mobile-menu-toggle').get_attribute('aria-expanded')=='false'
            page.locator('.mobile-menu-toggle').click()
            page.locator('.pro-sidebar button[data-view="wireguard"]').click()
            leave_sidebar(page)
            page.locator('.wg-workspace-hero').wait_for()
            assert page.locator('body.menu-open').count()==0
            page.wait_for_timeout(350)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile WireGuard page overflows horizontally'
            page.screenshot(path='/tmp/makia-wg-mobile.png',full_page=True)
            page.set_viewport_size({"width":1280,"height":800})

            page.evaluate("switchView('connectivity')")
            page.locator(".connectivity-grid").wait_for()
            page.screenshot(path='/tmp/makia-connectivity.png',full_page=True)

            for view in ["inbounds","access","sessions","protocols","guides","services","nodes","backups","audit","updates","support"]:
                page.evaluate(f"switchView('{view}')")
                leave_sidebar(page)
                page.wait_for_timeout(450)
                assert page.locator("#content").inner_text().strip(), f"{view} rendered empty content"
                nav=page.locator(f'.pro-sidebar nav button[data-view="{view}"]')
                if nav.count():
                    assert "active" in (nav.get_attribute("class") or ""), f"{view} sidebar item not active"

            page.evaluate("() => openXrayDiagnostics()")
            page.locator(".xray-diagnostics-modal").wait_for()
            assert "XRAY RUNTIME DIAGNOSTICS" in page.locator(".xray-diagnostics-modal").inner_text()
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.evaluate("switchView('guides')")
            page.locator(".guide-admin-grid").wait_for()
            assert page.locator(".guide-admin-card").count()==4
            assert page.locator('[data-action="client-guide-copy"]').count()==4
            page.locator('.pro-sidebar button[data-view="settings"]').click()
            leave_sidebar(page)
            page.locator(".settings-content-v2").wait_for()

            page.locator('[data-action="settings-tab"][data-tab="delivery"]').click()
            page.locator("#opProfilePrefix").wait_for()
            page.locator("#opProfilePrefix").fill("BrowserMakia")
            page.locator('[data-action="settings-operator-save"]').click()
            page.locator("#opProfilePrefix").wait_for()
            assert page.locator("#opProfilePrefix").input_value()=="BrowserMakia"

            page.locator('[data-action="settings-tab"][data-tab="subscription"]').click()
            page.locator("#opSubscriptionFormat").wait_for()
            page.locator("#opSubscriptionFormat").select_option("raw")
            page.locator('[data-action="settings-operator-save"]').click()
            page.locator("#opSubscriptionFormat").wait_for()
            assert page.locator("#opSubscriptionFormat").input_value()=="raw"

            page.locator('[data-action="settings-tab"][data-tab="vpn"]').click()
            page.locator("#opWgPort").wait_for()
            page.locator('[data-action="wg-compat-preset"]').click()
            assert page.locator("#opWgPort").input_value()=="443"
            assert page.locator("#opWgMtu").input_value()=="1280"
            assert page.locator("#opWgKeepalive").input_value()=="15"
            assert page.locator("#opWgAllowedIps").input_value()=="0.0.0.0/0"
            page.locator('[data-action="openvpn-diagnostics"]').click()
            page.locator(".openvpn-diagnostics-modal").wait_for()
            assert "OPENVPN DOMAIN DIAGNOSTICS" in page.locator(".openvpn-diagnostics-modal").inner_text()
            page.locator('.close-btn[data-action="modal-close"]').click()
            page.locator('[data-action="settings-operator-save"]').click()
            page.locator("#opWgPort").wait_for()
            assert page.locator("#opWgPort").input_value()=="443"

            for tab in ["general","domain","ssh","xray","vpn","delivery","subscription","security","api","recovery"]:
                page.locator(f'[data-action="settings-tab"][data-tab="{tab}"]').click()
                page.wait_for_timeout(180)
                assert page.locator(".settings-content-v2").inner_text().strip(), f"settings tab {tab} empty"

            page.locator('[data-action="settings-tab"][data-tab="recovery"]').click()
            page.locator('[data-action="portable-backup"]').click()
            page.locator("#migrationPassword").fill("MigrationPass!2026")
            with page.expect_download() as portable:
                page.locator('[data-action="portable-backup-download"]').click()
            portable_path=Path("/tmp/makia-browser-portable.zip")
            portable.value.save_as(str(portable_path))
            with pyzipper.AESZipFile(portable_path,"r") as zf:
                zf.setpassword(b"MigrationPass!2026")
                names=zf.namelist()
                assert "manifest.json" in names
                assert "payload/data.tar.gz" in names
                manifest=zf.read("manifest.json").decode("utf-8")
                assert "makia-portable-migration" in manifest
            page.locator('.close-btn[data-action="modal-close"]').click()

            for view in ["dashboard","inbounds","access","sessions","protocols","guides","services","nodes","connectivity","backups","audit","updates","support"]:
                page.evaluate(f"switchView('{view}')")
                leave_sidebar(page)
                page.wait_for_timeout(450)
                assert page.locator("#content").inner_text().strip(), f"{view} rendered empty content"

            page.locator('.pro-sidebar button[data-view="access"]').click()
            leave_sidebar(page)
            page.locator(".pro-directory").wait_for()
            assert page.locator("#accessSegments button").count()==5
            assert page.locator(".license-lock-panel").count()==0
            page.locator('.pro-sidebar button[data-view="services"]').click()
            leave_sidebar(page)
            page.locator(".service-control-list").wait_for()
            page.screenshot(path='/tmp/makia-services.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="protocols"]').click()
            leave_sidebar(page)
            page.locator(".port-management-panel").wait_for()
            assert page.locator(".port-table-row").count()>=1
            page.screenshot(path='/tmp/makia-ports.png',full_page=True)
            page.locator('.pro-sidebar button[data-view="settings"]').click()
            page.locator(".settings-content-v2").wait_for()
            page.screenshot(path='/tmp/makia-settings.png',full_page=True)
            assert page.locator(".license-lock-panel").count()==0

            assert not page_errors, "JavaScript page errors: "+repr(page_errors)
            browser.close()
        print(f"browser smoke PASS; client_id={client_id}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if proc.returncode not in (0,-15,None):
            print(proc.stdout.read() if proc.stdout else "")


if __name__=="__main__":
    main()
