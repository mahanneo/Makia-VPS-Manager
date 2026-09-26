from pathlib import Path
from app import protocol_ops

def _wg_fixture(tmp_path):
    wg=tmp_path/"wireguard"
    wg.mkdir()
    conf=wg/"wg0.conf"
    conf.write_text(
        "[Interface]\n"
        "Address = 10.66.66.1/24\n"
        "ListenPort = 443\n"
        "PrivateKey = SERVER_PRIVATE\n"
        "PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
        "PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE\n",
        encoding="utf-8",
    )
    return wg,conf

def test_wireguard_peer_profile_accepts_ipv4_endpoint(tmp_path,monkeypatch):
    wg,conf=_wg_fixture(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    outputs=iter(["CLIENT_PRIVATE","CLIENT_PUBLIC","SERVER_PUBLIC",""])
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:next(outputs))
    result=protocol_ops.create_wireguard_peer("client01","203.0.113.10")
    assert "Endpoint = 203.0.113.10:443" in result["config"]
    assert "PersistentKeepalive = 15" in result["config"]
    assert result["port"]==443

def test_wireguard_peer_profile_accepts_domain_endpoint(tmp_path,monkeypatch):
    wg,conf=_wg_fixture(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    outputs=iter(["CLIENT_PRIVATE","CLIENT_PUBLIC","SERVER_PUBLIC",""])
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:next(outputs))
    result=protocol_ops.create_wireguard_peer("client02","vpn.example.com")
    assert "Endpoint = vpn.example.com:443" in result["config"]
    assert result["endpoint"]=="vpn.example.com"

def test_wireguard_domain_diagnostics_matches_server_ipv4(tmp_path,monkeypatch):
    wg,conf=_wg_fixture(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_active",lambda svc:True)
    monkeypatch.setattr(protocol_ops,"_installed",lambda name:True)
    monkeypatch.setattr(protocol_ops,"_wireguard_udp_listener",lambda port:True)
    monkeypatch.setattr(protocol_ops,"_iptables_check",lambda args:True)
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    monkeypatch.setattr(protocol_ops.Path,"read_text",protocol_ops.Path.read_text)
    original_run=protocol_ops._run
    def fake_run(args,*a,**kw):
        if args[:3]==["wg","show","interfaces"]: return "wg0"
        if len(args)>=4 and args[:3]==["wg","show","wg0"]:
            return ""
        return ""
    monkeypatch.setattr(protocol_ops,"_run",fake_run)
    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(protocol_ops.socket.AF_INET,protocol_ops.socket.SOCK_DGRAM,17,"",("203.0.113.10",0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)
    real_read=Path.read_text
    def fake_read(self,*a,**kw):
        if str(self)=="/proc/sys/net/ipv4/ip_forward": return "1\n"
        return real_read(self,*a,**kw)
    monkeypatch.setattr(protocol_ops.Path,"read_text",fake_read)
    result=protocol_ops.wireguard_endpoint_diagnostics("vpn.example.com")
    assert result["runtime_ok"] is True
    assert result["endpoint_ok"] is True
    assert result["dns_matches_server"] is True
    assert result["ok"] is True

def test_wireguard_domain_diagnostics_rejects_proxy_or_wrong_a(tmp_path,monkeypatch):
    wg,conf=_wg_fixture(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"eth0")
    monkeypatch.setattr(protocol_ops,"_active",lambda svc:True)
    monkeypatch.setattr(protocol_ops,"_installed",lambda name:True)
    monkeypatch.setattr(protocol_ops,"_wireguard_udp_listener",lambda port:True)
    monkeypatch.setattr(protocol_ops,"_iptables_check",lambda args:True)
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    def fake_run(args,*a,**kw):
        if args[:3]==["wg","show","interfaces"]: return "wg0"
        return ""
    monkeypatch.setattr(protocol_ops,"_run",fake_run)
    def fake_getaddrinfo(host,port,family):
        if family==protocol_ops.socket.AF_INET:
            return [(protocol_ops.socket.AF_INET,protocol_ops.socket.SOCK_DGRAM,17,"",("198.51.100.25",0))]
        return []
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",fake_getaddrinfo)
    real_read=Path.read_text
    def fake_read(self,*a,**kw):
        if str(self)=="/proc/sys/net/ipv4/ip_forward": return "1\n"
        return real_read(self,*a,**kw)
    monkeypatch.setattr(protocol_ops.Path,"read_text",fake_read)
    result=protocol_ops.wireguard_endpoint_diagnostics("vpn.example.com")
    assert result["runtime_ok"] is True
    assert result["endpoint_ok"] is False
    assert result["ok"] is False
    assert any("DNS-only" in x for x in result["warnings"])

def test_wireguard_repair_rewrites_idempotent_forward_and_scoped_nat(tmp_path,monkeypatch):
    wg,conf=_wg_fixture(tmp_path)
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    monkeypatch.setattr(protocol_ops,"_default_iface",lambda:"ens3")
    monkeypatch.setenv("MAKIA_BACKUP_DIR",str(tmp_path/"backups"))
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_ops,"_ufw_allow_if_active",lambda *args,**kwargs:{"active":False,"changed":False})
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint="",iface="wg0":{"runtime_ok":True,"warnings":[]})
    result=protocol_ops.repair_wireguard_runtime()
    text=conf.read_text(encoding="utf-8")
    assert "iptables -I FORWARD 1 -i wg0 -j ACCEPT" in text
    assert "iptables -I FORWARD 1 -o wg0 -j ACCEPT" in text
    assert "-t nat -C POSTROUTING -s 10.66.66.0/24 -o ens3 -j MASQUERADE" in text
    assert Path(result["backup"]).exists()
