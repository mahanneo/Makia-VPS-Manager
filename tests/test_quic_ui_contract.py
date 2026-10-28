from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
SHELL = (ROOT / "app/templates/dashboard.html").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_cyberpunk_theme_is_selectable_and_scoped():
    assert 'value="cyberpunk"' in JS
    assert 'body[data-theme="cyberpunk"]' in CSS
    assert "prefers-reduced-motion:reduce" in CSS
    assert "data-theme=\"{{theme}}\"" in SHELL


def test_tuic_workspace_has_real_managed_api_and_navigation():
    assert 'data-view="tuic"' in SHELL
    guide = (ROOT / "app/templates/client_guide.html").read_text(encoding="utf-8")
    assert '<a href="#tuic"><span class="guide-mini-icon outline">Q</span>TUIC / QUIC</a>' in guide
    assert 'id="tuic"' in guide
    assert "tuic:tuicWorkspace" in JS
    assert "api('/api/protocols/tuic/diagnostics')" in JS
    assert "api('/api/protocols/tuic/users')" in JS
    assert "tuic-user-create" in JS
    assert "tuic-user-delete" in JS
    assert "canCreate=Boolean(s.installed&&s.configured&&s.certificate_valid&&(ready||users.length===0))" in JS
    assert 'kind in {"xray","outline","tuic","hysteria2"} and not state.get("active")' in MAIN
    assert 'kind in {"xray","wireguard","ssh","outline","tuic","hysteria2"}' in MAIN
    for route in (
        '/api/protocols/tuic/diagnostics',
        '/api/protocols/tuic/users',
        '/api/protocols/tuic/users/{name}',
    ):
        assert route in MAIN


def test_tuic_exports_use_existing_private_access_delivery():
    assert '"tuic":"sing-box"' in MAIN
    assert 'access_ops.tuic_payload' in MAIN
    assert 'require_access_kind(request,kind)' in MAIN
    assert 'data-action="native-export" data-kind="tuic"' in JS
    assert 'data-action="protected-export"' in JS


def test_tuic_service_isolated_and_pinned_setup_contract():
    unit = (ROOT / "systemd/makia-tuic.service").read_text(encoding="utf-8")
    setup = (ROOT / "scripts/setup-tuic-backend.sh").read_text(encoding="utf-8")
    assert "User=sing-box" in unit
    assert "Group=sing-box" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ExecStartPre=/usr/bin/sing-box check -c /etc/sing-box/makia-tuic.json" in unit
    assert 'PINNED_VERSION="1.14.4"' in setup
    assert 'UDP/$PORT is already bound. No changes made.' in setup
    assert "refusing to overwrite users or runtime state" in setup
    assert "UDP/8445" in setup
    assert "no TUIC listener is active yet" in setup
    assert "systemctl enable --now makia-tuic.service" not in setup
    assert "trap rollback_setup ERR" in setup
    assert "previous files restored" in setup
    assert "/etc/makia-vps-manager/tuic-state.json" in setup


def test_hysteria2_workspace_and_access_routes_are_managed():
    guide = (ROOT / "app/templates/client_guide.html").read_text(encoding="utf-8")
    setup = (ROOT / "scripts/setup-hysteria2-backend.sh").read_text(encoding="utf-8")
    unit = (ROOT / "systemd/makia-hysteria2.service").read_text(encoding="utf-8")
    assert 'data-view="hysteria2"' in SHELL
    assert '<a href="#hysteria2"><span class="guide-mini-icon outline">H</span>Hysteria2</a>' in guide
    assert 'id="hysteria2"' in guide
    assert "hysteria2:hysteria2Workspace" in JS
    assert "api('/api/protocols/hysteria2/diagnostics')" in JS
    assert "api('/api/protocols/hysteria2/users')" in JS
    assert "hysteria2-user-create" in JS
    assert "hysteria2-user-delete" in JS
    assert '\"hysteria2\":\"sing-box\"' in MAIN
    assert 'access_ops.hysteria2_payload' in MAIN
    assert 'ExecStartPre=/usr/bin/sing-box check -c /etc/sing-box/makia-hysteria2.json' in unit
    assert 'PINNED_VERSION="1.14.4"' in setup
    assert 'UDP/$PORT is already bound. No changes made.' in setup
    assert "no Hysteria2 listener is active yet" in setup
    assert "systemctl enable --now makia-hysteria2.service" not in setup
