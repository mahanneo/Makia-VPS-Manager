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

def test_host_smoke_treats_inactive_stealth_as_optional_warning():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "Stealth optional config is enabled but stunnel4 is inactive" in source
    assert 'bad "Stealth enabled but stunnel4 inactive"' not in source


def test_host_smoke_prints_failure_summary():
    source=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "FAILURES=()" in source
    assert 'FAILURES+=("$1")' in source
    assert "Failure summary (%d):" in source

def test_doctor_keeps_optional_inactive_stealth_out_of_fail_count():
    source=(ROOT/"scripts/doctor.sh").read_text(encoding="utf-8")
    assert "optional config is ENABLED=1 but service is inactive; core VPNs are unaffected" in source
    assert "optional config retained but service is disabled/inactive" in source
    assert 'fail "Stealth TLS/Stunnel"' not in source


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
