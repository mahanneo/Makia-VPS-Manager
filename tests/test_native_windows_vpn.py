"""No native Windows VPN profile may be advertised as live without runtime evidence."""
import pytest

from app import native_windows


def _ike(*,up=True):
    return {
        "installed":True,"configured":True,"service_active":up,
        "listeners":{"500_udp":up,"4500_udp":up},
        "domain":"vpn.example.com","cidr":"10.77.0.0/24","users":1,
    }


def test_ikev2_status_requires_running_service_and_both_udp_listeners(monkeypatch):
    monkeypatch.setattr(native_windows.protocol_ops,"ikev2_status",lambda:_ike())
    status=native_windows.readiness()["protocols"]
    assert status[0]["id"]=="ikev2" and status[0]["ready"] is True
    assert all(m["ready"] is False for m in status[1:])
    monkeypatch.setattr(native_windows.protocol_ops,"ikev2_status",lambda:_ike(up=False))
    assert native_windows.readiness()["protocols"][0]["ready"] is False
    broken=_ike()
    broken["listeners"]["4500_udp"]=False
    monkeypatch.setattr(native_windows.protocol_ops,"ikev2_status",lambda:broken)
    assert native_windows.readiness()["protocols"][0]["ready"] is False


def test_windows_profile_is_builtin_repeatable_and_contains_no_credentials():
    text=native_windows.profile_script("ikev2","vpn.example.com")
    assert "Add-VpnConnection" in text
    assert "-TunnelType Ikev2" in text
    assert "-AuthenticationMethod Eap" in text
    assert "-RememberCredential" in text
    assert "Get-VpnConnection" in text and "no automatic overwrite" in text
    assert "$server = 'vpn.example.com'" in text
    assert "password supplied by the administrator" in text
    assert "Read-Host" not in text
    assert "-L2tpPsk" not in text
    assert "ExecutionPolicy Bypass" not in text


@pytest.mark.parametrize("kind",["sstp","l2tp-ipsec","pptp","xray",""])
def test_no_fabricated_native_vpn_exports(kind):
    with pytest.raises(native_windows.NativeWindowsError):
        native_windows.profile_script(kind,"vpn.example.com")


@pytest.mark.parametrize("host",[
    "example.com'; Stop-Service nginx; #","https://vpn.example.com",
    "bad host.example.com","localhost","127.0.0.1",
])
def test_no_powershell_host_injection(host):
    with pytest.raises((native_windows.NativeWindowsError,native_windows.protocol_ops.ProtocolError)):
        native_windows.profile_script("ikev2",host)


def test_runtime_readiness_never_claims_sstp_l2tp_are_built(monkeypatch):
    monkeypatch.setattr(native_windows.protocol_ops,"ikev2_status",lambda:_ike())
    result=native_windows.readiness()
    assert result["protocols"][1]["id"]=="sstp"
    assert "TCP/443" in result["protocols"][1]["ports"]
    assert result["protocols"][2]["id"]=="l2tp-ipsec"
    assert "UDP/1701 inside IPsec" in result["protocols"][2]["ports"]
    assert result["protocols"][1]["ready"] is False
    assert result["protocols"][2]["ready"] is False


def test_controller_export_requires_live_runtime_and_admin_auth():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/"app/main.py").read_text(encoding="utf-8")
    assert '"/api/protocols/native-windows/ikev2/profile.ps1"' in source
    assert 'raise HTTPException(409,"IKEv2 has not passed live service and UDP port checks")' in source
    assert '"Content-Disposition":\'attachment; filename="Makia-IKEv2-Windows.ps1"\'' in source
    assert '"\\ufeff"+text' in source
