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


def test_port_collision_check_is_transport_aware(monkeypatch):
    class FakeSocket:
        def __init__(self, kind):
            self.kind=kind
        def bind(self, address):
            if self.kind==protocol_ops.socket.SOCK_DGRAM:
                raise OSError("udp occupied")
        def close(self):
            pass
    monkeypatch.setattr(protocol_ops.socket,"socket",lambda family,kind:FakeSocket(kind))
    assert protocol_ops._port_transport_in_use(443,"udp") is True
    assert protocol_ops._port_transport_in_use(443,"tcp") is False


def test_invalid_port_transport_is_rejected():
    with pytest.raises(ProtocolError, match="transport"):
        protocol_ops._port_transport_in_use(443,"sctp")


def test_select_available_port_uses_fallback(monkeypatch):
    occupied={(443,"udp"),(51820,"udp")}
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:(int(port),str(proto)) in occupied)
    assert protocol_ops._select_available_port(443,"udp",(51820,51821,8443)) == 51821


def test_select_available_port_raises_when_all_candidates_busy(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:True)
    with pytest.raises(ProtocolError, match="no free UDP port"):
        protocol_ops._select_available_port(443,"udp",(51820,51821))


def test_full_stack_provisions_missing_engines(monkeypatch):
    state={
        "xray":False,
        "wg_installed":False,"wg_config":False,"wg_active":False,"wg_port":0,
        "ovpn_installed":False,"ovpn_config":False,"ovpn_active":False,"ovpn_port":0,
        "stunnel":False,
    }
    def xray_status():
        return {"installed":state["xray"],"service_active":state["xray"],"config_path":"/usr/local/etc/xray/config.json" if state["xray"] else None}
    def wg_status():
        return {"installed":state["wg_installed"],"service_active":state["wg_active"],"config":"/etc/wireguard/wg0.conf" if state["wg_config"] else None,"port":state["wg_port"]}
    def ovpn_status():
        return {"installed":state["ovpn_installed"],"service_active":state["ovpn_active"],"config":"/etc/openvpn/server/server.conf" if state["ovpn_config"] else None,"port":state["ovpn_port"],"proto":"udp"}
    def st_status():
        return {"installed":state["stunnel"],"service_active":False}
    def install_component(name):
        if name=="xray":
            state["xray"]=True
            return xray_status()
        if name=="wireguard":
            state["wg_installed"]=True
            return wg_status()
        if name=="openvpn":
            state["ovpn_installed"]=True
            return ovpn_status()
        if name=="stunnel":
            state["stunnel"]=True
            return st_status()
        raise AssertionError(name)
    def bootstrap_wg(port,cidr,iface,mtu):
        state.update(wg_config=True,wg_active=True,wg_port=int(port))
        return {"port":int(port)}
    def bootstrap_ovpn(port,proto):
        state.update(ovpn_config=True,ovpn_active=True,ovpn_port=int(port))
        return {"port":int(port),"proto":proto}

    monkeypatch.setattr(protocol_ops,"xray_status",xray_status)
    monkeypatch.setattr(protocol_ops,"wireguard_status",wg_status)
    monkeypatch.setattr(protocol_ops,"openvpn_status",ovpn_status)
    monkeypatch.setattr(protocol_ops,"stunnel_status",st_status)
    monkeypatch.setattr(protocol_ops,"install_component",install_component)
    monkeypatch.setattr(protocol_ops,"bootstrap_wireguard",bootstrap_wg)
    monkeypatch.setattr(protocol_ops,"bootstrap_openvpn",bootstrap_ovpn)
    monkeypatch.setattr(protocol_ops,"_select_available_port",lambda preferred,proto,fallbacks=():preferred)
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint="",iface="wg0":{"runtime_ok":True,"port":state["wg_port"],"warnings":[]})
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{"service_active":state["ovpn_active"],"listener":state["ovpn_active"],"port":state["ovpn_port"]})

    result=protocol_ops.ensure_full_protocol_stack()
    assert result["xray"]["service_active"] is True
    assert result["wireguard"]["service_active"] is True
    assert result["openvpn"]["service_active"] is True
    assert result["stunnel"]["installed"] is True
    assert result["ports"]=={"wireguard":443,"openvpn":1194}
