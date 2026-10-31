from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_axon_dashboard_has_live_runtime_hub_and_accessible_motion_preferences():
    html = (ROOT / "app/templates/dashboard.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/axon-dashboard.css").read_text(encoding="utf-8")
    system_css = (ROOT / "app/static/axon-system.css").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "axon-global-environment" in html
    assert "three-r150.min.js" in html
    assert "axon-dashboard.js" in html
    assert "axon-dashboard.css" in html
    assert "axon-system.css" in html
    assert ".axon-hub-metrics" in css
    assert ".axon-module-grid" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert "@media(prefers-reduced-motion:reduce)" in system_css
    assert "const inboundCount=(x.inbounds||[]).length" in js
    assert "api('/api/network/mtproxy').catch" in js
    assert "data-current-host=" in js
    assert "savedHost!==requestedHost" in js
    assert "r.public_ipv4" in js
    assert "r.link_changed" in js
    assert "moduleTiles" in js
    assert "filterAxonModules" in js
    assert "window.MakiaAxon?.mount" in js


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
