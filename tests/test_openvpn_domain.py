from pathlib import Path
from types import SimpleNamespace
import pytest

from app import protocol_ops


def _write_openvpn_fixture(root:Path,proto="udp"):
    ovpn=root/"openvpn"
    pki=root/"easy-rsa"/"pki"
    (ovpn/"server").mkdir(parents=True)
    (pki/"issued").mkdir(parents=True)
    (pki/"private").mkdir(parents=True)
    (ovpn/"server"/"server.conf").write_text(
        f"port 1194\nproto {proto}\ndev tun\n",
        encoding="utf-8",
    )
    (ovpn/"server"/"ta.key").write_text("TA-KEY\n",encoding="utf-8")
    (pki/"ca.crt").write_text("CA\n",encoding="utf-8")
    (pki/"issued"/"client01.crt").write_text("CLIENT-CERT\n",encoding="utf-8")
    (pki/"private"/"client01.key").write_text("CLIENT-KEY\n",encoding="utf-8")
    return ovpn,root/"easy-rsa"


def test_render_openvpn_domain_profile_is_ipv4_safe(tmp_path,monkeypatch):
    ovpn,easy=_write_openvpn_fixture(tmp_path,"udp")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    monkeypatch.setattr(protocol_ops,"_openvpn_remote_block",lambda endpoint,port:(
        "remote vpn.example.com 1194\nremote 203.0.113.10 1194\n","203.0.113.10",True
    ))
    result=protocol_ops.render_openvpn_client("client01","vpn.example.com")
    config=result["config"]
    assert "proto udp4\n" in config
    assert "remote vpn.example.com 1194\n" in config
    assert "remote 203.0.113.10 1194\n" in config
    assert "resolv-retry 5" in config
    assert "server-poll-timeout 8" in config
    assert "auth-nocache" in config
    assert "remote-cert-tls server" in config
    assert "verify-x509-name server name" in config
    assert result["endpoint"]=="vpn.example.com"
    assert result["fallback_ipv4"]=="203.0.113.10"
    assert result["hybrid_endpoint"] is True
    assert result["proto"]=="udp"


def test_render_openvpn_tcp_domain_profile_uses_tcp4_client(tmp_path,monkeypatch):
    ovpn,easy=_write_openvpn_fixture(tmp_path,"tcp-server")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    monkeypatch.setattr(protocol_ops,"_openvpn_remote_block",lambda endpoint,port:(
        "remote vpn.example.com 1194\nremote 203.0.113.10 1194\n","203.0.113.10",True
    ))
    result=protocol_ops.render_openvpn_client("client01","vpn.example.com")
    assert "proto tcp4-client\n" in result["config"]
    assert result["proto"]=="tcp"


def test_openvpn_domain_diagnostics_matches_vps_ipv4(monkeypatch,tmp_path):
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{
        "config":"/etc/openvpn/server/server.conf",
        "port":1194,"proto":"udp4","service_active":True,"listener":True,
    })
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(protocol_ops.socket.AF_INET,protocol_ops.socket.SOCK_STREAM,6,"",("203.0.113.10",0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)
    result=protocol_ops.openvpn_endpoint_diagnostics("vpn.example.com")
    assert result["ok"] is True
    assert result["resolved_ipv4"]==["203.0.113.10"]
    assert result["dns_matches_server"] is True
    assert result["hybrid_available"] is True
    assert result["hybrid_fallback_ipv4"]=="203.0.113.10"
    assert result["warnings"]==[]


def test_openvpn_domain_diagnostics_flags_proxy_or_wrong_a(monkeypatch,tmp_path):
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{
        "config":"/etc/openvpn/server/server.conf",
        "port":1194,"proto":"udp4","service_active":True,"listener":True,
    })
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(protocol_ops.socket.AF_INET,protocol_ops.socket.SOCK_STREAM,6,"",("198.51.100.25",0))]
        if family==protocol_ops.socket.AF_INET6:
            return [(protocol_ops.socket.AF_INET6,protocol_ops.socket.SOCK_STREAM,6,"",("2001:db8::25",0,0,0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)
    result=protocol_ops.openvpn_endpoint_diagnostics("vpn.example.com")
    assert result["ok"] is False
    assert result["dns_matches_server"] is False
    joined=" ".join(result["warnings"])
    assert "DNS-only" in joined
    assert "IPv6" in joined


def test_openvpn_diagnostics_warns_tcp_443_https_collision(monkeypatch,tmp_path):
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{
        "config":"/etc/openvpn/server/server.conf",
        "port":443,"proto":"tcp4-server","service_active":True,"listener":True,
    })
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    result=protocol_ops.openvpn_endpoint_diagnostics("203.0.113.10")
    assert result["ok"] is True
    assert any("HTTPS/Nginx" in x for x in result["warnings"])


def test_openvpn_runtime_repair_normalizes_ipv4(tmp_path,monkeypatch):
    ovpn=tmp_path/"openvpn"
    (ovpn/"server").mkdir(parents=True)
    conf=ovpn/"server"/"server.conf"
    conf.write_text("port 1194\nproto udp\ndev tun\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_ops,"_active",lambda name:True)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{
        "config":str(conf),"port":1194,"proto":"udp4","service_active":True,"listener":True,
    })
    result=protocol_ops.repair_openvpn_ipv4_runtime()
    text=conf.read_text(encoding="utf-8")
    assert "proto udp4" in text
    assert "local 0.0.0.0" in text
    assert Path(result["backup"]).exists()
    assert result["runtime"]["listener"] is True


def test_openvpn_remote_block_domain_first_then_matching_vps_ip(monkeypatch):
    monkeypatch.setattr(protocol_ops,"openvpn_endpoint_diagnostics",lambda endpoint:{
        "resolved_ipv4":["203.0.113.10"],
        "local_ipv4":["10.8.0.1","203.0.113.10"],
    })
    block,fallback,hybrid=protocol_ops._openvpn_remote_block("vpn.example.com",1194)
    assert block.splitlines()==[
        "remote vpn.example.com 1194",
        "remote 203.0.113.10 1194",
    ]
    assert fallback=="203.0.113.10"
    assert hybrid is True


def test_openvpn_remote_block_ip_stays_single_endpoint():
    block,fallback,hybrid=protocol_ops._openvpn_remote_block("203.0.113.10",1194)
    assert block=="remote 203.0.113.10 1194\n"
    assert fallback==""
    assert hybrid is False


def test_openvpn_client_rejects_wrong_port_before_issuing_certificate(tmp_path,monkeypatch):
    ovpn,easy=_write_openvpn_fixture(tmp_path,"udp4")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{"port":1194,"proto":"udp4"})
    monkeypatch.setattr(protocol_ops.subprocess,"run",lambda *args,**kw:(_ for _ in ()).throw(AssertionError("must not issue certificate")))
    with pytest.raises(protocol_ops.ProtocolError,match="match the OpenVPN server"):
        protocol_ops.create_openvpn_client("client02","8.8.8.8",443,"udp")
