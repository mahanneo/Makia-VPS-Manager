import pytest
from app.endpoint_preflight import ALL, evaluate

@pytest.mark.parametrize("protocol",["ssh","wireguard","openvpn","outline","xray-direct"])
def test_direct_protocols_support_public_ipv4(protocol):
    # Outline/Xray ports are runtime-defined rather than safe universal defaults.
    port=443 if protocol in {"outline","xray-direct"} else None
    r=evaluate(protocol,"212.100.171.183",port)
    assert r.ok and r.mode=="ip"

@pytest.mark.parametrize("protocol",["browser-gateway","wstunnel-wss","openvpn-wstunnel","stealth-tls","ikev2-cert"])
def test_tls_modes_reject_ip_without_a_real_name_certificate(protocol):
    r=evaluate(protocol,"212.100.171.183")
    assert not r.ok
    assert any("TLS certificate" in err for err in r.errors)

def test_good_direct_domain_and_dns_only_guidance():
    r=evaluate("wireguard","vpn.example.org",server_ipv4="212.100.171.183",
               resolved_ipv4=["212.100.171.183"])
    assert r.ok and r.mode=="domain"
    assert any("DNS-only" in s for s in r.next_steps)

def test_dns_mismatch_rejected_before_mutation():
    r=evaluate("openvpn","vpn.example.org",server_ipv4="212.100.171.183",
               resolved_ipv4=["8.8.8.8"])
    assert not r.ok and "A record" in r.errors[0]

def test_tls_hostname_requires_matching_certificate():
    r=evaluate("browser-gateway","p.example.org",
               resolved_ipv4=["212.100.171.183"],tls_names=["other.example.org"])
    assert not r.ok
    assert any("certificate" in s for s in r.errors)
    ok=evaluate("browser-gateway","p.example.org",
                resolved_ipv4=["212.100.171.183"],tls_names=["p.example.org"])
    assert ok.ok

@pytest.mark.parametrize("value",[
    "http://vpn.example.org","https://vpn.example.org:443","127.0.0.1",
    "192.168.1.5","localhost","vpn.example.org/path","vpn.example.org:443",
    "bad..example.org","foo@example.org","",
])
def test_rejects_invalid_address_input(value):
    with pytest.raises(ValueError):
        evaluate("wireguard",value)

def test_invalid_ports_are_not_accepted():
    assert not evaluate("ssh","212.100.171.183",0).ok
    assert not evaluate("ssh","212.100.171.183",65536).ok

def test_insecure_pptp_explicitly_rejected():
    with pytest.raises(ValueError,match="PPTP"):
        evaluate("pptp","212.100.171.183")


def test_runtime_defined_protocol_port_must_be_explicit():
    for protocol in ("outline","xray-direct"):
        result=evaluate(protocol,"212.100.171.183")
        assert not result.ok
        assert "Choose a port" in result.errors[0]

def test_private_dns_records_do_not_create_connectable_profiles():
    result=evaluate("wireguard","vpn.example.org",resolved_ipv4=["192.168.10.10"])
    assert not result.ok
    assert "non-public" in " ".join(result.errors)

def test_server_ipv4_input_is_validated():
    result=evaluate("ssh","212.100.171.183",server_ipv4="not-an-ip")
    assert not result.ok
    assert "public IPv4" in " ".join(result.errors)


def test_user_guidance_distinguishes_ip_from_tls_modes():
    direct=evaluate("wireguard","212.100.171.183",51820)
    assert direct.ok and direct.direct_ip_supported
    assert direct.recommended_for_first_setup
    assert not direct.needs_tls_certificate
    assert "اتصال واقعی" in direct.user_message_fa

    tls=evaluate("browser-gateway","212.100.171.183",9444)
    assert not tls.ok and tls.needs_tls_certificate
    assert not tls.direct_ip_supported
    assert "خطاها" in tls.user_message_fa

def test_port_not_an_integer_produces_clean_validation_error():
    with pytest.raises(ValueError,match="Port must be"):
        evaluate("ssh","212.100.171.183","twenty-two")
