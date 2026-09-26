import time
from pathlib import Path

from app import protocol_ops


def _write_wg(root:Path, extra=""):
    root.mkdir(parents=True,exist_ok=True)
    conf=root/"wg0.conf"
    conf.write_text(
        "[Interface]\n"
        "Address = 10.66.66.1/24\n"
        "ListenPort = 443\n"
        "PrivateKey = server-private\n"
        + extra,
        encoding="utf-8",
    )
    return conf


def test_wireguard_rules_are_idempotent_and_subnet_scoped():
    up,down=protocol_ops._wireguard_rule_lines("wg0","10.66.66.0/24","eth0")
    assert "iptables -w 5 -C FORWARD -i wg0 -j ACCEPT" in up
    assert "iptables -w 5 -I FORWARD 1 -i wg0 -j ACCEPT" in up
    assert "iptables -w 5 -C FORWARD -o wg0 -j ACCEPT" in up
    assert "-t nat -C POSTROUTING -s 10.66.66.0/24 -o eth0 -j MASQUERADE" in up
    assert "-t nat -A POSTROUTING -s 10.66.66.0/24 -o eth0 -j MASQUERADE" in up
    assert "-D FORWARD -i wg0" in down
    assert "-D FORWARD -o wg0" in down


def test_wireguard_diagnostics_domain_runtime_pass(tmp_path,monkeypatch):
    _write_wg(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"_installed",lambda binary: True)
    monkeypatch.setattr(protocol_ops,"_active",lambda service: service=="wg-quick@wg0")
    monkeypatch.setattr(protocol_ops,"_listener_present",lambda port,proto: port==443 and proto=="udp")
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_iptables_rule_exists",lambda *args,**kwargs:True)
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])

    now=int(time.time())
    def fake_run(args,*a,**kw):
        if args[:3]==["wg","show","interfaces"]:
            return "wg0"
        if args[:4]==["wg","show","wg0","dump"]:
            return "server\npeer\n"
        if args[:4]==["wg","show","wg0","latest-handshakes"]:
            return f"peerkey\t{now}"
        if args[:3]==["sysctl","-n","net.ipv4.ip_forward"]:
            return "1"
        return ""
    monkeypatch.setattr(protocol_ops,"_run",fake_run)

    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(family,protocol_ops.socket.SOCK_DGRAM,17,"",("203.0.113.10",0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)

    d=protocol_ops.wireguard_diagnostics("wg0","vpn.example.test")
    assert d["runtime_ok"] is True
    assert d["ok"] is True
    assert d["listener"] is True
    assert d["nat_rule"] is True
    assert d["forward_in_rule"] is True and d["forward_out_rule"] is True
    assert d["endpoint"]["dns_matches_server"] is True
    assert d["recent_handshakes"]==1


def test_wireguard_diagnostics_flags_wrong_domain(tmp_path,monkeypatch):
    _write_wg(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"_installed",lambda binary: True)
    monkeypatch.setattr(protocol_ops,"_active",lambda service: True)
    monkeypatch.setattr(protocol_ops,"_listener_present",lambda port,proto: True)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_iptables_rule_exists",lambda *args,**kwargs:True)
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    monkeypatch.setattr(protocol_ops,"_run",lambda args,*a,**kw: "wg0" if args[:3]==["wg","show","interfaces"] else ("1" if args[:3]==["sysctl","-n","net.ipv4.ip_forward"] else ""))

    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(family,protocol_ops.socket.SOCK_DGRAM,17,"",("198.51.100.20",0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)
    d=protocol_ops.wireguard_diagnostics("wg0","vpn.example.test")
    assert d["runtime_ok"] is True
    assert d["ok"] is False
    assert d["endpoint"]["dns_matches_server"] is False
    assert any("DNS-only" in x for x in d["warnings"])


def test_wireguard_repair_preserves_keys_and_peers(tmp_path,monkeypatch):
    conf=_write_wg(
        tmp_path,
        "PostUp = iptables -A FORWARD -i wg0 -j ACCEPT\n"
        "PostDown = iptables -D FORWARD -i wg0 -j ACCEPT\n\n"
        "# Makia peer: client01\n"
        "[Peer]\n"
        "PublicKey = client-public\n"
        "AllowedIPs = 10.66.66.2/32\n",
    )
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"BACKUP_DIR",tmp_path/"backups")
    monkeypatch.setattr(protocol_ops,"WG_SYSCTL_PATH",tmp_path/"99-makia-wireguard.conf")
    monkeypatch.setattr(protocol_ops,"_installed",lambda binary: True)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_ops,"_ufw_allow_if_active",lambda *args,**kwargs:{"active":False,"changed":False})
    monkeypatch.setattr(protocol_ops,"wireguard_diagnostics",lambda iface="wg0",endpoint="":{
        "runtime_ok":True,"warnings":[],"port":443,"network":"10.66.66.0/24"
    })

    result=protocol_ops.repair_wireguard_runtime("wg0")
    text=conf.read_text(encoding="utf-8")
    assert "PrivateKey = server-private" in text
    assert "PublicKey = client-public" in text
    assert "AllowedIPs = 10.66.66.2/32" in text
    assert "-C FORWARD -i wg0 -j ACCEPT" in text
    assert "-I FORWARD 1 -i wg0 -j ACCEPT" in text
    assert "-s 10.66.66.0/24 -o eth0 -j MASQUERADE" in text
    assert Path(result["backup"]).exists()


def test_wireguard_domain_peer_includes_direct_ip_fallback(tmp_path,monkeypatch):
    _write_wg(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"wireguard_diagnostics",lambda iface="wg0",endpoint="":{
        "runtime_ok":True,
        "endpoint":{
            "endpoint_is_ip":False,
            "resolved_ipv4":["203.0.113.10"],
            "local_ipv4":["203.0.113.10"],
            "dns_matches_server":True,
        },
    })
    def fake_run(args,input_text=None,**kwargs):
        if args==["wg","genkey"]: return "client-private"
        if args==["wg","pubkey"]: return "client-public"
        if args==["wg","show","wg0","public-key"]: return "server-public"
        if args[:3]==["wg","set","wg0"]: return ""
        return ""
    monkeypatch.setattr(protocol_ops,"_run",fake_run)

    result=protocol_ops.create_wireguard_peer("client01","vpn.example.test")
    assert "Endpoint = vpn.example.test:443" in result["config"]
    assert result["fallback_ipv4"]=="203.0.113.10"
    assert "Endpoint = 203.0.113.10:443" in result["ip_config"]
    assert "PrivateKey = client-private" in result["ip_config"]


def test_wireguard_ip_peer_has_no_duplicate_fallback(tmp_path,monkeypatch):
    _write_wg(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    monkeypatch.setattr(protocol_ops,"wireguard_diagnostics",lambda iface="wg0",endpoint="":{
        "runtime_ok":True,
        "endpoint":{
            "endpoint_is_ip":True,
            "resolved_ipv4":["203.0.113.10"],
            "local_ipv4":["203.0.113.10"],
            "dns_matches_server":True,
        },
    })
    def fake_run(args,input_text=None,**kwargs):
        if args==["wg","genkey"]: return "client-private"
        if args==["wg","pubkey"]: return "client-public"
        if args==["wg","show","wg0","public-key"]: return "server-public"
        return ""
    monkeypatch.setattr(protocol_ops,"_run",fake_run)
    result=protocol_ops.create_wireguard_peer("client02","203.0.113.10")
    assert "Endpoint = 203.0.113.10:443" in result["config"]
    assert result["ip_config"]==""
    assert result["fallback_ipv4"]==""
