from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_update_tracks_stealth_pre_state_and_protects_active_runtime():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert "STUNNEL_WAS_CONFIGURED=0" in source
    assert "STUNNEL_WAS_ACTIVE=0" in source
    assert 'systemctl is-active --quiet stunnel4 2>/dev/null && STUNNEL_WAS_ACTIVE=1' in source
    assert 'if [[ "$STUNNEL_WAS_ACTIVE" -eq 1 ]] && ! systemctl is-active --quiet stunnel4' in source
    assert "Stealth/Stunnel was active before update but is no longer active" in source

def test_update_softfails_only_preexisting_inactive_stealth():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert 'if [[ "$STUNNEL_WAS_CONFIGURED" -eq 1 && "$STUNNEL_WAS_ACTIVE" -eq 0 ]]' in source
    assert "MAKIA_UAT_STEALTH_SOFTFAIL=1" in source

def test_host_smoke_honors_explicit_stealth_softfail():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert 'MAKIA_UAT_STEALTH_SOFTFAIL:-0' in source
    assert "Stealth config retained; stunnel4 was already inactive before update" in source
    assert 'bad "Stealth configured but stunnel4 inactive"' in source


def test_host_smoke_prints_failure_summary():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "FAILURES=()" in source
    assert 'FAILURES+=("$1")' in source
    assert "Failure summary (%d):" in source

def test_doctor_distinguishes_disabled_from_broken_stealth():
    source=(ROOT/"scripts/doctor.sh").read_text(encoding="utf-8")
    assert "configured + ENABLED=1 but service inactive" in source
    assert "config retained but service is disabled/inactive" in source


def test_rollback_snapshot_covers_cli_and_protocol_state():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    for required in [
        "usr/local/sbin/makia-upgrade",
        "usr/local/sbin/makia-doctor",
        "usr/local/sbin/makia-uat-smoke",
        "etc/wireguard/wg0.conf",
        "etc/openvpn/server",
        "etc/stunnel/makia-openvpn.conf",
        "etc/default/stunnel4",
    ]:
        assert required in source

def test_rollback_restarts_previously_active_core_protocols():
    source=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert 'systemctl restart xray' in source
    assert 'systemctl restart wg-quick@wg0' in source
    assert 'systemctl restart openvpn-server@server' in source
    assert 'systemctl restart stunnel4' in source
