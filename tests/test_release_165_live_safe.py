"""Release 1.6.5 must not restart active VPN clients for a backend hotfix."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_release_version_server_and_ci_agree():
    assert (ROOT/"VERSION").read_text().strip()=="1.6.5"
    config=(ROOT/"app/config.py").read_text()
    assert 'VERSION = "1.6.5"' in config
    ci=(ROOT/".github/workflows/ci.yml").read_text()
    assert "grep -Fxq '1.6.5' VERSION" in ci
    assert 'grep -q \'VERSION = "1.6.5"\' app/config.py' in ci


def test_live_safe_forward_rollout_preserves_gateway_and_network():
    source=(ROOT/"scripts/update.sh").read_text()
    assert 'MAKIA_LIVE_SAFE:-0' in source
    assert 'Live-safe: existing WStunnel 11.0.0 binary preserved.' in source
    assert 'Live-safe: preserving active Browser Gateway, policy and metrics runtimes.' in source
    assert 'Live-safe: keeping Nginx TLS sessions and Fail2ban service running.' in source
    assert 'systemctl restart makia-vps-manager' in source
    assert 'systemctl is-active --quiet "$service"' in source


def test_live_safe_rollback_does_not_restart_healthy_tunnels():
    source=(ROOT/"scripts/update.sh").read_text()
    rollback=source.split("on_exit(){",1)[1].split("trap on_exit EXIT",1)[0]
    for service in ["xray","wg-quick@wg0","openvpn-server@server","makia-wstunnel","openvpn-server@makia-ws","makia-openvpn-wstunnel"]:
        assert f'! systemctl is-active --quiet {service}; then' in rollback
        assert f'systemctl restart {service}' in rollback
    assert 'MAKIA_LIVE_SAFE:-0' in rollback


def test_browser_stable_release_assets_not_overwritten_automatically():
    workflow=(ROOT/".github/workflows/browser-extension.yml").read_text()
    assert 'github.event_name == \'push\'' not in workflow
    assert 'gh release upload' not in workflow
    assert 'gh release create' not in workflow
    assert 'actions/upload-artifact@v4' in workflow
