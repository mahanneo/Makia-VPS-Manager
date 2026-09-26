from app import access_ops, protocol_ops


def _direct_dns(monkeypatch,host="vpn.example.test",ip="203.0.113.10"):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:[ip])
    def fake_getaddrinfo(name,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(family,protocol_ops.socket.SOCK_STREAM,6,"",(ip,0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)


def test_ssh_delivery_accepts_domain_and_ipv4():
    domain=access_ops.ssh_payload("vpn.example.test","user001","123456")
    direct=access_ops.ssh_payload("203.0.113.10","user001","123456")
    assert b"HostName vpn.example.test" in domain["files"]["user001-ssh-config.txt"]
    assert b"HostName 203.0.113.10" in direct["files"]["user001-ssh-config.txt"]
    assert domain["summary"]["host"]=="vpn.example.test"
    assert direct["summary"]["host"]=="203.0.113.10"


def test_xray_share_parser_preserves_domain_and_ipv4():
    domain=access_ops.describe_xray_share(
        "vless://11111111-1111-1111-1111-111111111111@vpn.example.test:2087?type=tcp&security=reality#domain",
        "vless",
    )
    direct=access_ops.describe_xray_share(
        "vless://11111111-1111-1111-1111-111111111111@203.0.113.10:2087?type=tcp&security=reality#ip",
        "vless",
    )
    assert domain["host"]=="vpn.example.test"
    assert direct["host"]=="203.0.113.10"
    assert domain["port"]==2087 and direct["port"]==2087


def test_xray_runtime_endpoint_diagnostics_passes_domain_and_ipv4(monkeypatch):
    _direct_dns(monkeypatch)
    monkeypatch.setattr(protocol_ops,"xray_status",lambda:{
        "installed":True,
        "service_active":True,
        "inbounds":[{
            "tag":"makia-vless-2087",
            "protocol":"vless",
            "transport":"raw",
            "security":"reality",
            "listen":"0.0.0.0",
            "port":2087,
            "clients":1,
        }],
    })
    monkeypatch.setattr(protocol_ops,"_listener_present",lambda port,proto: port==2087 and proto=="tcp")

    domain=protocol_ops.xray_endpoint_diagnostics("vpn.example.test")
    direct=protocol_ops.xray_endpoint_diagnostics("203.0.113.10")
    assert domain["ok"] is True
    assert domain["dns_matches_server"] is True
    assert domain["inbounds"][0]["listener"] is True
    assert direct["ok"] is True
    assert direct["endpoint_is_ip"] is True


def test_ssh_runtime_endpoint_diagnostics_passes_domain_and_ipv4(monkeypatch):
    _direct_dns(monkeypatch)
    monkeypatch.setattr(protocol_ops,"_active",lambda service: service in {"ssh","sshd"})
    monkeypatch.setattr(protocol_ops,"_listener_present",lambda port,proto: port==22 and proto=="tcp")
    domain=protocol_ops.ssh_endpoint_diagnostics("vpn.example.test")
    direct=protocol_ops.ssh_endpoint_diagnostics("203.0.113.10")
    assert domain["ok"] is True
    assert domain["dns_matches_server"] is True
    assert direct["ok"] is True
