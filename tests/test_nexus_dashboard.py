from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nexus_shell_has_live_command_hud_and_accessible_motion_preferences():
    html = (ROOT / "app/templates/dashboard.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "NEXUS OPERATIONS GRID" in html
    assert "pro-topbar-center" in html
    assert "sx-future-hero" in css
    assert "sx-runtime-grid" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert 'html[dir="rtl"] .pro-main{margin-right:0}' in css
    assert "const inboundCount=(x.inbounds||[]).length" in js
    assert "api('/api/network/mtproxy').catch" in js
    assert "runtimeCard('TG','Telegram MTProto'" in js
    assert "runtimeCard('X','Xray / V2Ray'" in js


def test_inbounds_view_is_driven_by_xray_runtime_not_fake_demo_data():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "const engine=stack.xray||{},rows=engine.inbounds||[]" in js
    assert "api('/api/protocols')" in js
    assert "Inbounds" in js or "Inbound list" in js


def test_mtproxy_configure_does_not_require_setuid_inside_hardened_panel_unit():
    source = (ROOT / "app/network_services.py").read_text(encoding="utf-8")
    assert "def _assert_mtproxy_config_access" in source
    assert "_assert_mtproxy_config_access()" in source
    assert '\"runuser\",\"-u\",\"makia-mtproxy\",\"--\",\"test\",\"-r\"' not in source


def test_public_guide_has_one_visual_step_group_per_protocol_and_hysteria2_anchor():
    guide = (ROOT / "app/templates/client_guide.html").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert guide.count('class="visual-steps"') == 7
    assert 'id="hysteria2"' in guide
    assert "'hysteria2' if kind=='hysteria2'" in main
