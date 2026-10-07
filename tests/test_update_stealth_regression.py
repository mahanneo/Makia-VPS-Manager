from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_update_tracks_stealth_pre_state_and_protects_active_runtime():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert "STUNNEL_WAS_CONFIGURED=0" in source
    assert "STUNNEL_WAS_ACTIVE=0" in source
    assert 'STUNNEL_RUNTIME_SERVICE=""' in source
    assert 'STUNNEL_RUNTIME_SERVICE="makia-stealth"' in source
    assert 'STUNNEL_RUNTIME_SERVICE="stunnel4"' in source
    assert 'systemctl is-active --quiet makia-stealth 2>/dev/null && STUNNEL_WAS_ACTIVE=1' in source
    assert 'systemctl is-active --quiet stunnel4 2>/dev/null && STUNNEL_WAS_ACTIVE=1' in source
    assert '! systemctl is-active --quiet "$STUNNEL_RUNTIME_SERVICE"' in source
    assert "Stealth/Stunnel was active before update but is no longer active" in source


def test_update_softfails_only_preexisting_inactive_stealth():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert 'if [[ "$STUNNEL_WAS_CONFIGURED" -eq 1 && "$STUNNEL_WAS_ACTIVE" -eq 0 ]]' in source
    assert "MAKIA_UAT_STEALTH_SOFTFAIL=1" in source


def test_host_smoke_supports_dedicated_and_legacy_stealth_states():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "/etc/makia-vps-manager/stunnel-openvpn.conf" in source
    assert "systemctl is-active --quiet makia-stealth" in source
    assert "Legacy Stealth config is inactive; Configure / Repair will migrate it" in source
    assert 'bad "Stealth Makia config exists but makia-stealth is inactive"' in source


def test_host_smoke_prints_failure_summary():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "FAILURES=()" in source
    assert 'FAILURES+=("$1")' in source
    assert "Failure summary (%d):" in source


def test_doctor_reports_dedicated_stealth_and_legacy_migration():
    source=(ROOT/"scripts/doctor.sh").read_text(encoding="utf-8")
    assert "/etc/makia-vps-manager/stunnel-openvpn.conf" in source
    assert "Makia config exists but makia-stealth is inactive; use Configure / Repair Stealth" in source
    assert "legacy Makia config retained but inactive; Configure / Repair will migrate it" in source


def test_rollback_snapshot_covers_cli_and_protocol_state():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    for required in [
        "usr/local/sbin/makia-upgrade",
        "usr/local/sbin/makia-doctor",
        "usr/local/sbin/makia-uat-smoke",
        "etc/wireguard/wg0.conf",
        "etc/openvpn/server",
        "etc/stunnel/makia-openvpn.conf",
        "etc/makia-vps-manager/stunnel-openvpn.conf",
        "etc/systemd/system/makia-stealth.service",
    ]:
        assert required in source


def test_rollback_restarts_previously_active_core_protocols():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert 'systemctl restart xray' in source
    assert 'systemctl restart wg-quick@wg0' in source
    assert 'systemctl restart openvpn-server@server' in source
    assert 'systemctl restart "$STUNNEL_RUNTIME_SERVICE"' in source
