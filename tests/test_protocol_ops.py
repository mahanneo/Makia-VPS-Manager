import pytest
from app import protocol_ops
from app.protocol_ops import _validate_port, _validate_endpoint_host, _uri_host, _endpoint_is_private, create_xray_inbound, validate_endpoint_selection, ProtocolError

def test_valid_port():
    assert _validate_port(443) == 443

@pytest.mark.parametrize("value", [0, 65536, -1])
def test_invalid_port(value):
    with pytest.raises(ProtocolError):
        _validate_port(value)


@pytest.mark.parametrize("value,expected", [
    ("178.83.45.215","178.83.45.215"),
    (" example.com ","example.com"),
    ("VPN.Example.COM","vpn.example.com"),
    ("[2001:db8::1]","2001:db8::1"),
])
def test_valid_endpoint_host(value, expected):
    assert _validate_endpoint_host(value) == expected

@pytest.mark.parametrize("value", [
    "",
    "https://example.com",
    "example.com:443",
    "example.com/path",
    "bad host",
    "-bad.example.com",
    "bad_.example.com",
])
def test_invalid_endpoint_host(value):
    with pytest.raises(ProtocolError):
        _validate_endpoint_host(value)

def test_ipv6_uri_host_is_bracketed():
    assert _uri_host("2001:db8::1") == "[2001:db8::1]"

def test_ipv4_uri_host_is_not_bracketed():
    assert _uri_host("178.83.45.215") == "178.83.45.215"


def test_public_ipv4_is_not_private():
    assert _endpoint_is_private("178.83.45.215") is False

def test_private_ipv4_is_private():
    assert _endpoint_is_private("10.10.0.2") is True

def test_public_vless_none_is_rejected_before_core_mutation():
    with pytest.raises(ProtocolError, match="choose REALITY or TLS"):
        create_xray_inbound("vless",2087,"mahan","178.83.45.215","xhttp","none","/makia","","")

def test_explicit_endpoint_mode_rejects_wrong_type_and_private_ip():
    for endpoint,mode in [("vpn.example.com","ip"),("8.8.8.8","domain"),("10.0.0.1","ip"),("2001:db8::1","ip")]:
        with pytest.raises(ProtocolError):
            validate_endpoint_selection(endpoint,mode)
    assert validate_endpoint_selection("8.8.8.8","ip")=="8.8.8.8"

def test_direct_domain_selection_checks_a_record_and_vps_match(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["8.8.8.8"])
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,("8.8.8.8",0))])
    assert validate_endpoint_selection("VPN.Example.com","domain",direct=True)=="vpn.example.com"
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,("1.1.1.1",0))])
    with pytest.raises(ProtocolError,match="does not match"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True)
    assert validate_endpoint_selection("vpn.example.com","domain",direct=False)=="vpn.example.com"
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,(ip,0)) for ip in ("8.8.8.8","1.1.1.1")])
    with pytest.raises(ProtocolError,match="does not match"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True)

def test_domain_selection_requires_a_record(monkeypatch):
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[])
    with pytest.raises(ProtocolError,match="A/IPv4"):
        validate_endpoint_selection("vpn.example.com","domain")

def test_ssh_domain_rejects_aaaa_pointing_away_from_vps(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["8.8.8.8"])
    monkeypatch.setattr(protocol_ops,"_local_ipv6_candidates",lambda:[])
    def resolve(host,port,family):
        ip="8.8.8.8" if family==protocol_ops.socket.AF_INET else "2001:4860:4860::8888"
        return [(family,None,None,None,(ip,0))]
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",resolve)
    with pytest.raises(ProtocolError,match="AAAA"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True,check_aaaa=True)
