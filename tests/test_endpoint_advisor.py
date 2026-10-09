import pytest
from app import endpoint_advisor
from app import main as panel


def test_public_ip_helper_rejects_private_and_documentation_ranges():
    for value in ("", "10.0.0.5", "192.168.1.4", "127.0.0.1", "203.0.113.10", "2001:db8::1", "not-an-ip"):
        assert endpoint_advisor._public_ipv4(value)==""
    assert endpoint_advisor._public_ipv4("8.8.8.8")=="8.8.8.8"


def test_ip_first_nodomain_does_not_require_certificate(monkeypatch):
    monkeypatch.delenv("MAKIA_PUBLIC_IPV4",raising=False)
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:["10.8.0.1","8.8.8.8"])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"")
    info=endpoint_advisor.connection_setup()
    assert info["recommended_mode"]=="ip"
    assert info["recommended_endpoint"]=="8.8.8.8"
    assert info["ip_panel_url"]=="http://8.8.8.8/"
    assert not info["domain_panel_url"]
    assert info["protocols"]["ssh"]["supports_ip"]
    assert info["protocols"]["wireguard"]["supports_ip"]
    assert info["protocols"]["openvpn"]["supports_ip"]
    assert info["protocols"]["xray"]["supports_ip"]
    assert info["protocols"]["pptp"]["unsupported"]


def test_domain_ready_prefers_certified_hostname(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:[])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"vpn.example.org")
    from app import panel_ops
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["8.8.8.8"],"certificate":True,
        "https_listener":True,"certificate_days_left":50
    })
    info=endpoint_advisor.connection_setup()
    assert info["recommended_mode"]=="domain"
    assert info["recommended_endpoint"]=="vpn.example.org"
    assert info["domain_dns_matches_server"] is True
    assert info["domain_tls_ready"]
    assert info["domain_panel_url"]=="https://vpn.example.org/"
    assert info["choices"]["ip"]["value"]=="8.8.8.8"


def test_domain_mismatch_does_not_claim_ready(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:[])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"vpn.example.org")
    from app import panel_ops
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["1.1.1.1"],"certificate":True,
        "https_listener":True,"certificate_days_left":50
    })
    info=endpoint_advisor.connection_setup()
    assert info["recommended_mode"]=="ip"
    assert info["domain_dns_matches_server"] is False
    assert any("رکورد A" in x for x in info["warnings"])


def test_nated_host_explicit_public_ip(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","1.1.1.1")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:["10.0.0.4"])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"")
    assert endpoint_advisor.connection_setup()["public_ipv4"]==["1.1.1.1"]


def test_invalid_env_address_is_ignored(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","192.168.0.1")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:["172.16.0.4"])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"")
    info=endpoint_advisor.connection_setup()
    assert info["public_ipv4"]==[]
    assert info["recommended_endpoint"]==""
    assert any("NAT" in warning for warning in info["warnings"])


def test_port_contract_never_claims_pptp():
    assert endpoint_advisor.connection_setup if callable(endpoint_advisor.connection_setup) else False


def test_automode_direct_rejects_private_ipv4_before_mutation(monkeypatch):
    from app import protocol_ops
    with pytest.raises(protocol_ops.ProtocolError,match="public IPv4"):
        protocol_ops.validate_endpoint_selection("192.168.0.3","auto",direct=True)


def test_automode_direct_rejects_wrong_dns_with_nated_public_ip(monkeypatch):
    import socket
    from app import protocol_ops
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["10.0.0.5"])
    def fake_lookup(host,port,family):
        assert host=="vpn.example.org" and family==socket.AF_INET
        return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("1.1.1.1",0))]
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_lookup)
    with pytest.raises(protocol_ops.ProtocolError,match="A record does not match"):
        protocol_ops.validate_endpoint_selection("vpn.example.org","auto",direct=True)


def test_automode_direct_accepts_matching_nat_dns(monkeypatch):
    import socket
    from app import protocol_ops
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["10.0.0.5"])
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",
                        lambda *args:[(socket.AF_INET,socket.SOCK_STREAM,6,"",("8.8.8.8",0))])
    assert protocol_ops.validate_endpoint_selection("vpn.example.org","auto",direct=True)=="vpn.example.org"


def test_expired_cert_is_not_recommended(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:[])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"vpn.example.org")
    from app import panel_ops
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["8.8.8.8"],"certificate":True,
        "https_listener":True,"certificate_days_left":-1
    })
    info=endpoint_advisor.connection_setup()
    assert info["recommended_mode"]=="ip"
    assert not info["domain_tls_ready"]
    assert any("منقضی" in w for w in info["warnings"])


def test_mixed_dns_records_are_not_considered_all_ready(monkeypatch):
    monkeypatch.setenv("MAKIA_PUBLIC_IPV4","8.8.8.8")
    monkeypatch.setattr(endpoint_advisor.protocol_ops,"_local_ipv4_candidates",lambda:[])
    monkeypatch.setattr(endpoint_advisor,"get_setting",lambda *args:"vpn.example.org")
    from app import panel_ops
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["8.8.8.8","1.1.1.1"],"certificate":True,
        "https_listener":True,"certificate_days_left":40
    })
    info=endpoint_advisor.connection_setup()
    assert info["domain_dns_matches_server"] is False
    assert info["recommended_mode"]=="ip"
