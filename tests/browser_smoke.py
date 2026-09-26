import os
import shutil
import subprocess
import sys
import time
import urllib.request
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import pyzipper
from playwright.sync_api import sync_playwright

DATA=Path(os.environ["MAKIA_DATA_DIR"])
BASE_URL="http://127.0.0.1:8787"
PASSWORD=os.environ["MAKIA_INITIAL_ADMIN_PASSWORD"]


def seed():
    shutil.rmtree(DATA,ignore_errors=True)
    DATA.mkdir(parents=True,exist_ok=True)
    from app.db import init_db, create_protocol_client, upsert_access_artifact, get_protocol_client, set_setting
    from app import access_ops, license_ops

    init_db()
    private=Ed25519PrivateKey.generate()
    pub_path=DATA/"test-license-public.pem"
    pub_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    os.environ["MAKIA_LICENSE_PUBLIC_KEY_PATH"]=str(pub_path)
    now=int(time.time())
    payload={
        "v":1,"license_id":"LIC-BROWSER","customer":"CI",
        "installation_id":license_ops.installation_id(),"tier":"full",
        "features":sorted(license_ops.FULL_FEATURES),"issued_at":now,"not_before":now-60,"expires_at":now+86400,
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    b64=lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
    set_setting("license_code","MKL1."+b64(raw)+"."+b64(private.sign(raw)))
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
            page.locator('input[name="username"]').fill("admin")
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url(BASE_URL+"/")
            assert page.locator('body[data-theme="glass"]').count()==1
            page.locator(".glass-status-hero").wait_for()
            assert page.locator(".glass-summary-grid article").count()==4
            assert page.locator(".glass-service-card").count()>=8
            assert "FULL ACCESS" in page.locator(".license-tier-chip").inner_text()
            scrollbar_width=page.locator("aside.sidebar nav").evaluate("(el)=>getComputedStyle(el,'::-webkit-scrollbar').width")
            assert scrollbar_width=="8px"
            page.locator('aside.sidebar button[data-view="protocols"]').click()
            page.locator('[data-action="connectivity-lab"]').wait_for()
            page.locator('[data-action="connectivity-lab"]').click()
            page.locator("#connectivityEndpoint").wait_for()
            page.locator("#connectivityEndpoint").fill("127.0.0.1")
            page.locator('[data-action="connectivity-run"]').click()
            page.locator(".connectivity-summary").wait_for()
            assert "SERVER-SIDE READINESS" in page.locator(".connectivity-summary").inner_text()
            page.locator('.close-btn[data-action="modal-close"]').click()
            page.locator('aside.sidebar button[data-view="license"]').click()
            page.locator(".license-hero.full").wait_for()
            assert "LIC-BROWSER" in page.locator("#content").inner_text()
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
            page.locator('aside.sidebar button[data-view="access"]').click()
            page.locator(".access-profile",has_text="browser-client").wait_for()

            row=page.locator(".access-profile",has_text="browser-client")
            row.locator('[data-action="access-share"]').click()
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

            row=page.locator(".access-profile",has_text="browser-client")
            row.locator('[data-action="protected-export"]').click()
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
            row=page.locator(".access-profile",has_text="browser-client")
            with page.expect_download() as native:
                row.locator('[data-action="native-export"]').click()
            native_path=Path("/tmp/makia-browser-native.txt")
            native.value.save_as(str(native_path))
            assert "vless://" in native_path.read_text(encoding="utf-8")

            page.locator('[data-shell-action="create-access"]').click()
            page.locator(".provision-wizard").wait_for()
            assert page.locator(".wizard-protocol").count()==4
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.locator('aside.sidebar button[data-view="dashboard"]').click()
            page.locator(".glass-status-hero").wait_for()
            page.locator('[data-action="self-test"]').click()
            page.locator(".diagnostics-modal").wait_for()
            assert page.locator(".diagnostic-score.pass").count()==1
            page.locator('.close-btn[data-action="modal-close"]').click()

            for view in ["sessions","protocols","guides","services","nodes","security","backups","audit","updates","settings","license"]:
                nav=page.locator(f'aside.sidebar nav button[data-view="{view}"]')
                nav.click()
                page.wait_for_timeout(450)
                assert page.locator("#content").inner_text().strip(), f"{view} rendered empty content"
                assert "active" in (nav.get_attribute("class") or ""), f"{view} sidebar item not active"

            page.evaluate("() => openXrayDiagnostics()")
            page.locator(".xray-diagnostics-modal").wait_for()
            assert "XRAY RUNTIME DIAGNOSTICS" in page.locator(".xray-diagnostics-modal").inner_text()
            page.locator('.close-btn[data-action="modal-close"]').click()

            page.locator('aside.sidebar button[data-view="guides"]').click()
            page.locator(".guide-admin-grid").wait_for()
            assert page.locator(".guide-admin-card").count()==4
            assert page.locator('[data-action="client-guide-copy"]').count()==4
            page.locator('aside.sidebar button[data-view="settings"]').click()
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

            for view in ["dashboard","access","sessions","protocols","guides","services","nodes","security","backups","audit","updates","settings","license"]:
                nav=page.locator(f'aside.sidebar nav button[data-view="{view}"]')
                nav.click()
                page.wait_for_timeout(450)
                assert page.locator("#content").inner_text().strip(), f"{view} rendered empty content"

            # Community regression: removing the signed license must immediately
            # leave SSH management available while premium engines become locked
            # in both the UI and backend.
            status=page.evaluate("""async () => {
              const r=await fetch('/api/license',{method:'DELETE',headers:{'X-Makia-Request':'1'}});
              return {status:r.status,body:await r.json()};
            }""")
            assert status["status"]==200
            assert status["body"]["tier"]=="community"
            page.reload(wait_until="networkidle")
            page.locator(".license-tier-chip.community").wait_for()
            page.locator('aside.sidebar button[data-view="access"]').click()
            page.locator(".protocol-launch-grid").wait_for()
            assert page.locator(".launch-card.license-locked").count()==3
            ssh_card=page.locator(".launch-card.ssh")
            assert ssh_card.locator('[data-action="wizard-open"]').count()==1
            assert "Full Access" in page.locator(".launch-card.xray").inner_text()
            page.locator('aside.sidebar button[data-view="protocols"]').click()
            page.locator(".license-lock-panel").wait_for()
            assert "FULL ACCESS REQUIRED" in page.locator(".license-lock-panel").inner_text()
            gate=page.evaluate("""async () => {
              const r=await fetch('/api/protocols/openvpn/diagnostics?endpoint=127.0.0.1',{
                headers:{'X-Makia-Request':'1'}
              });
              return {status:r.status,body:await r.json()};
            }""")
            assert gate["status"]==403
            assert gate["body"]["detail"]["code"]=="license_required"

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
