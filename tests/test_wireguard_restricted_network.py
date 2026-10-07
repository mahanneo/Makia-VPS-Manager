from pathlib import Path

from app import protocol_ops

ROOT=Path(__file__).resolve().parents[1]


def test_wireguard_firewall_directives_include_bidirectional_mss_clamp():
    up,down=protocol_ops._wireguard_firewall_directives("wg0","10.66.66.0/24","ens18")
    assert "TCPMSS --clamp-mss-to-pmtu" in up
    assert "-i wg0" in up
    assert "-o wg0" in up
    assert "-t nat" in up and "MASQUERADE" in up
    assert "TCPMSS --clamp-mss-to-pmtu" in down


def test_wireguard_restricted_profile_contract_is_wired_to_api_and_ui():
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert '/api/protocols/wireguard/restricted-network-profile' in main
    assert "apply_wireguard_restricted_network_profile" in main
    assert "default_wireguard_mtu" in main
    assert "default_wireguard_keepalive" in main
    assert "1.1.1.1, 8.8.8.8" in main
    assert "wg-restricted-runtime" in js
    assert "Apply Restricted-Network Tuning" in js
    assert "TCP MSS clamp" in js


def test_wireguard_restricted_profile_preserves_active_listen_port():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    start=source.index("def apply_wireguard_restricted_network_profile")
    section=source[start:start+5000]
    assert '_wireguard_set_interface_directive(original,"MTU","MTU = 1280")' in section
    assert '_wireguard_set_interface_directive(original,"ListenPort"' not in section
    assert "Existing WireGuard listen port was preserved" in section


def test_wireguard_diagnostics_exposes_restricted_network_readiness():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert '"mss_clamp_in":mss_clamp_in' in source
    assert '"mss_clamp_out":mss_clamp_out' in source
    assert '"restricted_network_ready":restricted_network_ready' in source


def test_wireguard_performance_profile_is_reversible_and_bbr_is_conditional(monkeypatch):
    values={
        "net.ipv4.tcp_available_congestion_control":"reno cubic bbr",
    }
    monkeypatch.setattr(protocol_ops,"_proc_sysctl_value",lambda key:values.get(key,""))
    text=protocol_ops._wireguard_performance_sysctl_text()
    assert "net.core.rmem_max=16777216" in text
    assert "net.core.wmem_max=16777216" in text
    assert "net.ipv4.udp_rmem_min=16384" in text
    assert "net.ipv4.udp_wmem_min=16384" in text
    assert "net.core.netdev_max_backlog=16384" in text
    assert "net.ipv4.tcp_mtu_probing=1" in text
    assert "net.core.default_qdisc=fq" in text
    assert "net.ipv4.tcp_congestion_control=bbr" in text

    monkeypatch.setattr(protocol_ops,"_proc_sysctl_value",lambda key:"reno cubic" if key=="net.ipv4.tcp_available_congestion_control" else "")
    no_bbr=protocol_ops._wireguard_performance_sysctl_text()
    assert "net.ipv4.tcp_congestion_control=bbr" not in no_bbr
    assert "net.core.default_qdisc=fq" not in no_bbr


def test_wireguard_performance_status_is_exposed_to_panel_and_doctor():
    source=(ROOT/"app/protocol_ops.py").read_text(encoding="utf-8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    doctor=(ROOT/"scripts/doctor.sh").read_text(encoding="utf-8")
    assert '"performance":wireguard_performance_status(iface)' in source
    assert "Network performance" in js
    assert "WireGuard network tuning" in doctor
    assert "Repair Runtime applies safe tuning" in doctor
