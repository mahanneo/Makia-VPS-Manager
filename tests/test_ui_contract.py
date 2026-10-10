import re
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
SHELL=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")


def test_access_exports_use_delegated_actions():
    assert 'data-action="protected-export"' in JS
    assert 'data-action="native-export"' in JS
    assert 'onclick="downloadProtectedAccess(' not in JS
    assert 'onclick="downloadAccessNative(' not in JS
    assert "async function performProtectedDownload" in JS
    assert "async function downloadAccessNative" in JS


def test_shell_has_no_inline_click_handlers():
    assert "onclick=" not in SHELL
    assert 'data-shell-action="create-access"' in SHELL
    assert 'data-shell-action="command"' in SHELL


def test_provisioning_wizard_contract():
    for marker in [
        "NEW ACCESS",
        "wizard-protocol",
        "wizard-create",
        "provision-drawer",
        "protocol-bootstrap",
        "runSelfTest",
    ]:
        assert marker in JS


def test_dashboard_uses_live_operational_sources():
    assert "Promise.all([" in JS
    assert "api('/api/overview')" in JS
    assert "api('/api/access')" in JS
    assert "api('/api/protocols')" in JS
    assert "System history" in JS
    assert "sx-vitals" in JS


def test_every_literal_data_action_has_dispatch_handler():
    actions=set(re.findall(r'data-action=["\']([a-z0-9-]+)["\']',JS))
    handled=set(re.findall(r"action==='([a-z0-9-]+)'",JS))
    missing=sorted(actions-handled)
    assert not missing, f"UI data-action without dispatcher handler: {missing}"


def test_every_shell_action_has_dispatch_handler():
    actions=set(re.findall(r'data-shell-action=["\']([a-z0-9-]+)["\']',SHELL))
    expected={"create-access","command","refresh","sidebar-open","sidebar-close","sidebar-group","telegram-shop-studio"}
    assert actions==expected
    for action in actions:
        assert f"a==='{action}'" in JS


def test_inline_handler_functions_exist():
    definitions=set(re.findall(r'(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(',JS))
    calls=set()
    for double,single in re.findall(r'onclick=(?:"([^"]*)"|\'([^\']*)\')',JS):
        body=double or single
        calls.update(re.findall(r'([A-Za-z_$][\w$]*)\s*\(',body))
    browser_or_language={"if","confirm","prompt","alert","Number","String","JSON","encodeURIComponent","setTimeout","getElementById"}
    missing=sorted(calls-definitions-browser_or_language)
    assert not missing, f"inline handlers call missing functions: {missing}"


def test_single_access_owner_in_primary_navigation():
    assert 'data-view="access"' in SHELL
    assert 'data-view="accounts"' not in SHELL
    assert "['SSH Accounts','accounts']" not in JS


def test_primary_navigation_has_dedicated_protocol_workspaces():
    for view in ["ssh","xray","wireguard","openvpn","protocols"]:
        assert f'data-view="{view}"' in SHELL
    assert "xrayWorkspace" in JS
    assert "openvpnWorkspace" in JS
    assert "ssh:accounts" in JS


def test_xray_workspace_exposes_real_policy_controls():
    for marker in ["Clientهای مدیریت‌شده","QUOTA · EXPIRY · IP LIMIT","protocolClientRow","resetProtocolTraffic"]:
        assert marker in JS


def test_openvpn_workspace_does_not_fake_per_client_quota():
    assert "Quota/Reset per-client برای OpenVPN" in JS


def test_professional_information_architecture_contract():
    assert 'class="pro-sidebar"' in SHELL
    assert 'data-view="dashboard"' in SHELL
    assert 'data-view="access"' in SHELL
    assert 'data-view="inbounds"' in SHELL
    assert 'data-group="protocols"' in SHELL
    assert 'data-group="infra"' in SHELL
    assert 'data-group="system"' in SHELL
    assert 'data-view="connectivity"' in SHELL
    assert "inboundsWorkspace" in JS
    assert "connectivityLab" in JS
    assert "access-detail" in JS
    assert "provision-drawer" in JS


def test_user_directory_uses_progressive_disclosure():
    assert "pro-user-table-head" in JS
    assert "pro-user-row" in JS
    assert "openAccessDetail" in JS
    assert "detail-actions" in JS
    assert "Protected ZIP" in JS


def test_connectivity_lab_does_not_fake_iran_validation():
    assert "نیاز به تست از داخل ایران" in JS
    assert "Server Ready به معنی" in JS
    assert "IRAN FIELD GATE" in JS


def test_v026_login_controls_are_functional_and_single_surface():
    login=(ROOT/"app/templates/login.html").read_text(encoding="utf-8")
    assert 'id="loginLangToggle"' in login
    assert 'id="loginThemeToggle"' in login
    assert "let lang='{{language}}'==='en'?'en':'fa'" in login
    assert "makia-login-theme" in login
    assert 'class="pro-login-field"' in login
    assert "pro-login-field input:focus" in (ROOT/"app/static/app.css").read_text(encoding="utf-8")


def test_xray_guided_ui_has_compatibility_matrix():
    for marker in ["XRAY_PROFILE_MATRIX","XRAY_MANUAL_MATRIX","normalizeXrayProfile","xrayPrerequisiteMessage","hysteria2","shadowsocks"]:
        assert marker in JS
    assert "Manual / Expert Builder" in JS
    assert "این ترکیب توسط Builder قابل Export نیست" in JS
    assert "Advanced JSON" in JS


def test_openvpn_exposes_real_tcp_udp_advanced_server_controls():
    assert "openvpn-configure-save" in JS
    assert "/api/protocols/openvpn/configure" in JS
    assert 'name="ovpnTransport"' in JS
    assert "redirect_gateway" in JS
    assert "client_to_client" in JS


def test_support_and_security_are_progressively_disclosed():
    assert "HELP & DIAGNOSTICS" in JS
    assert "Connectivity Lab" in JS
    assert "support-advanced" in JS
    assert "security-posture-grid" in JS
    assert "Admin Security" in JS


def test_visual_guide_has_protocol_step_illustrations():
    guide=(ROOT/"app/templates/client_guide.html").read_text(encoding="utf-8")
    assert guide.count('class="visual-steps"')==5
    assert 'id="outline"' in guide
    assert guide.count("<svg")>=12


def test_mkcp_ui_does_not_expose_removed_seed_control():
    assert "Path / Service / Seed" not in JS
    assert "mKCP جدید Seed قدیمی ندارد." in JS
    assert "kcpSettings" not in JS


def test_protocol_hub_exposes_seven_real_connection_modes():
    for marker in [
        "Connection Modes",
        "ikev2-setup",
        "ikev2-user",
        "ikev2-users",
        "ikev2-user-delete",
        "openvpn-mode",
        "stealth-setup",
        "wstunnel-setup",
        "openvpn-wstunnel-setup",
        "openvpn-wstunnel-client",
        "/api/protocols/modes",
        "/api/protocols/ikev2/bootstrap",
        "/api/protocols/ikev2/users",
        "/api/protocols/stealth/bootstrap",
        "/api/protocols/openvpn/wstunnel/bootstrap",
        "/api/protocols/openvpn/wstunnel/clients",
        "/api/protocols/wstunnel/bootstrap",
    ]:
        assert marker in JS
    assert "WStunnel 443 جدید OpenVPN را داخل WebSocket/TLS" in JS
    assert "Listener خام TCP/443 فقط یک Owner دارد" in JS


def test_protocol_workspace_access_actions_refresh_their_cache():
    assert "async function openAccessDetail(id)" in JS
    assert "accessCache=await api('/api/access')" in JS
    assert "window.__protocolData=stack;window.__operatorSettings=operator;accessCache=rows;" in JS
    assert "window.__protocolData=stack;window.__protocolClients=clients;window.__operatorSettings=operator;accessCache=accessRows;" in JS
    assert "if(action==='access-detail'){await openAccessDetail" in JS


def test_xray_inbound_center_has_3x_style_sections():
    for marker in [
        "XRAY INBOUND CENTER","Inbound → Client → Transport → Security → Sniffing → Sockopt",
        "xray-inbound-builder","xray-builder-create","xbProtocol","xbTransport","xbSecurity",
        "xbSniffEnabled","xbTcpFastOpen","xbExtraStream",
        "/api/protocols/xray/inbound-capabilities","/api/protocols/xray/inbounds"
    ]:
        assert marker in JS


def test_self_service_portal_and_localization_contract():
    main_text=(ROOT/"app/main.py").read_text(encoding="utf-8")
    portal=(ROOT/"app/templates/access_portal.html").read_text(encoding="utf-8")
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    for marker in [
        "/api/access/{kind}/{key}/portal","/access/{token}","/access/{token}/download",
        "/access/{token}/qr.svg","access_portal.html","public_token"
    ]:
        assert marker in main_text
    for marker in [
        "دانلود فایل اتصال","Download connection file","راهنمای سریع","QUICK GUIDE",
        "Treat this link like a password","این لینک مانند رمز عبور محرمانه است"
    ]:
        assert marker in portal
    assert "localizeVisibleUi" in JS
    assert "MutationObserver(scheduleUiLocalization)" in JS
    assert "window.MAKIA_LANG" in JS
    assert "language == 'en'" in dashboard or 'language == "en"' in dashboard
