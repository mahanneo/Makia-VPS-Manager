from pathlib import Path

import pytest

from app import system_ops

ROOT=Path(__file__).resolve().parents[1]


def test_unconfigured_optional_service_start_is_blocked(monkeypatch):
    monkeypatch.setattr(
        system_ops,
        "_service_setup_meta",
        lambda name:{
            "configured":False,
            "setup_action":"openvpn-wstunnel-setup",
            "setup_label":"Configure / Repair WStunnel 443",
            "managed_by":"",
        },
    )
    called=[]
    monkeypatch.setattr(system_ops,"_run",lambda *args,**kwargs:called.append(args))
    with pytest.raises(system_ops.OperationError,match="not configured yet"):
        system_ops.service_action("makia-openvpn-wstunnel","start")
    assert called==[]


def test_managed_wstunnel_backend_cannot_be_started_directly(monkeypatch):
    monkeypatch.setattr(
        system_ops,
        "_service_setup_meta",
        lambda name:{
            "configured":True,
            "setup_action":"openvpn-wstunnel-setup",
            "setup_label":"Manage from WStunnel 443",
            "managed_by":"makia-openvpn-wstunnel",
        },
    )
    called=[]
    monkeypatch.setattr(system_ops,"_run",lambda *args,**kwargs:called.append(args))
    with pytest.raises(system_ops.OperationError,match="managed by makia-openvpn-wstunnel"):
        system_ops.service_action("openvpn-server@makia-ws","restart")
    assert called==[]


def test_optional_service_status_exposes_setup_contract(monkeypatch):
    monkeypatch.setattr(
        system_ops,
        "_service_setup_meta",
        lambda name:{
            "configured":False,
            "setup_action":"stealth-setup",
            "setup_label":"Configure / Repair Stealth",
            "managed_by":"",
        },
    )
    class Result:
        returncode=3
        stdout="inactive\n"
        stderr=""
    monkeypatch.setattr(system_ops.shutil,"which",lambda name:"/bin/systemctl")
    monkeypatch.setattr(system_ops.subprocess,"run",lambda *args,**kwargs:Result())
    state=system_ops.service_status("makia-stealth")
    assert state["state"]=="not-configured"
    assert state["configured"] is False
    assert state["setup_action"]=="stealth-setup"


def test_service_ui_does_not_offer_raw_start_for_optional_runtime():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "const optionalSetup=String(s.setup_action||'')" in js
    assert "const managedBy=String(s.managed_by||'')" in js
    assert "نیاز به راه‌اندازی" in js
    assert "else if(optionalSetup)" in js


def test_wstunnel_service_has_configuration_conditions():
    unit=(ROOT/"systemd/makia-openvpn-wstunnel.service").read_text(encoding="utf-8")
    assert "ConditionPathExists=/etc/makia-vps-manager/openvpn-wstunnel.env" in unit
    assert "ConditionPathExists=/etc/openvpn/server/makia-ws.conf" in unit


def test_update_softfails_only_preexisting_openvpn_listener_gap():
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    smoke=(ROOT/"scripts/uat-smoke.sh").read_text(encoding="utf-8")
    assert "OVPN_WAS_LISTENING=0" in update
    assert "openvpn_primary_listener_present" in update
    assert 'OVPN_WAS_ACTIVE" -eq 1 && "$OVPN_WAS_LISTENING" -eq 1' in update
    assert "MAKIA_UAT_OPENVPN_LISTENER_SOFTFAIL=1" in update
    assert "MAKIA_UAT_OPENVPN_LISTENER_SOFTFAIL" in smoke
    assert "WStunnel 443 uses its separate makia-ws backend" in smoke


def test_dashboard_busts_cached_service_controls_after_hotfix():
    html=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    assert "/static/app.js?v={{version}}-wstunnel-hotfix2" in html


def test_services_use_makia_owned_stealth_runtime():
    config=(ROOT/"app/config.py").read_text(encoding="utf-8")
    ops=(ROOT/"app/system_ops.py").read_text(encoding="utf-8")
    assert '"makia-stealth": "Stealth TLS / Stunnel"' in config
    assert '"stunnel4": "Stunnel"' not in config
    assert '"makia-stealth":{' in ops
    assert 'Path("/etc/makia-vps-manager/stunnel-openvpn.conf")' in ops
