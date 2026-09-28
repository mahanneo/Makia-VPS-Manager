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
    monkeypatch.setattr(protocol_ops,"_openvpn_transport_runtimes",lambda:{
        "udp":{"port":1194,"proto":"udp4","service_active":True,"listener":True,"name":"server"},
        "tcp":None,
    })
    monkeypatch.setattr(protocol_ops.subprocess,"run",lambda *args,**kw:(_ for _ in ()).throw(AssertionError("must not issue certificate")))
    with pytest.raises(protocol_ops.ProtocolError,match="must match the active OpenVPN UDP server"):
        protocol_ops.create_openvpn_client("client02","8.8.8.8",443,"udp")


def test_openvpn_gateway_scripts_add_forward_and_nat_rules(tmp_path,monkeypatch):
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",tmp_path)
    up,down=protocol_ops._openvpn_forward_scripts("eth0")
    assert 'iptables -I FORWARD 1 -i "$dev" -j ACCEPT' in up.read_text()
    assert 'iptables -I FORWARD 1 -o "$dev" -j ACCEPT' in up.read_text()
    assert "-s 10.8.0.0/24 -o eth0 -j MASQUERADE" in up.read_text()
    assert 'iptables -D FORWARD -i "$dev" -j ACCEPT' in down.read_text()
    assert 'iptables -D FORWARD -o "$dev" -j ACCEPT' in down.read_text()
    import subprocess
    for script in (up,down):
        assert subprocess.run(["sh","-n",str(script)],check=False).returncode==0


def test_openvpn_repair_updates_managed_gateway_and_preserves_config(tmp_path,monkeypatch):
    ovpn=tmp_path/"openvpn"
    (ovpn/"server").mkdir(parents=True)
    up=ovpn/"makia-up.sh"
    down=ovpn/"makia-down.sh"
    for script in (up,down): script.write_text("#!/bin/sh\n",encoding="utf-8")
    conf=ovpn/"server/server.conf"
    conf.write_text(f"port 1194\nproto udp4\ndev tun\nup {up}\ndown {down}\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_ops,"_active",lambda name:True)
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{"service_active":True,"listener":True})
    result=protocol_ops.repair_openvpn_ipv4_runtime()
    assert "iptables -I FORWARD" in up.read_text()
    assert "iptables -I FORWARD" in down.read_text() or "iptables -D FORWARD" in down.read_text()
    assert "proto udp4" in conf.read_text()
    assert Path(result["backup"]).exists()


def test_openvpn_diagnostics_report_missing_forward_rules(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{"port":1194,"proto":"udp4","service_active":True,"listener":True})
    monkeypatch.setattr(protocol_ops,"_openvpn_forwarding_runtime",lambda:{"interface":"tun0","forward_in":False,"forward_out":False,"nat":False})
    result=protocol_ops.openvpn_endpoint_diagnostics("8.8.8.8")
    assert any("FORWARD" in warning for warning in result["warnings"])
    assert any("NAT" in warning for warning in result["warnings"])


def test_openvpn_repair_restores_gateway_scripts_if_restart_fails(tmp_path,monkeypatch):
    ovpn=tmp_path/"openvpn"
    (ovpn/"server").mkdir(parents=True)
    up=ovpn/"makia-up.sh"
    down=ovpn/"makia-down.sh"
    up.write_text("#!/bin/sh\nold-up\n")
    down.write_text("#!/bin/sh\nold-down\n")
    conf=ovpn/"server/server.conf"
    original=f"port 1194\nproto udp\ndev tun\nup {up}\ndown {down}\n"
    conf.write_text(original)
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    calls=[]
    def restart(*args,**kwargs):
        calls.append(args)
        if len(calls)==1: raise protocol_ops.ProtocolError("restart failed")
        return ""
    monkeypatch.setattr(protocol_ops,"_run",restart)
    with pytest.raises(protocol_ops.ProtocolError,match="restart failed"):
        protocol_ops.repair_openvpn_ipv4_runtime()
    assert conf.read_text()==original
    assert up.read_text()=="#!/bin/sh\nold-up\n"
    assert down.read_text()=="#!/bin/sh\nold-down\n"
    assert len(calls)==2


def test_render_openvpn_client_can_select_auxiliary_tcp_runtime(tmp_path,monkeypatch):
    ovpn,easy=_write_openvpn_fixture(tmp_path,"udp4")
    tcp_conf=ovpn/"server"/"transport-tcp.conf"
    tcp_conf.write_text("port 8443\nproto tcp4-server\ndev tun-makia-tcp\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    monkeypatch.setattr(protocol_ops,"_openvpn_transport_runtimes",lambda:{
        "udp":{"name":"server","config":str(ovpn/"server"/"server.conf"),"port":1194,"proto":"udp4","service_active":True,"listener":True},
        "tcp":{"name":"transport-tcp","config":str(tcp_conf),"port":8443,"proto":"tcp4-server","service_active":True,"listener":True},
    })
    monkeypatch.setattr(protocol_ops,"_openvpn_remote_block",lambda endpoint,port:(
        f"remote vpn.example.com {port}\n","",False
    ))
    result=protocol_ops.render_openvpn_client("client01","vpn.example.com","tcp")
    assert "proto tcp4-client\n" in result["config"]
    assert "remote vpn.example.com 8443\n" in result["config"]
    assert result["server"]=="transport-tcp"
    assert result["port"]==8443
    assert result["proto"]=="tcp"


def test_render_openvpn_client_rejects_unknown_transport(tmp_path,monkeypatch):
    ovpn,easy=_write_openvpn_fixture(tmp_path,"udp4")
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"OVPN_EASYRSA",easy)
    with pytest.raises(protocol_ops.ProtocolError,match="must be UDP or TCP"):
        protocol_ops.render_openvpn_client("client01","vpn.example.com","quic")
