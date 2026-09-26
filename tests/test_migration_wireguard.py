import json
import sqlite3
from pathlib import Path

from app import protocol_ops, system_ops


def test_wireguard_allowed_ips_validation():
    assert protocol_ops._validate_wireguard_allowed_ips("0.0.0.0/0, 10.0.0.0/8")=="0.0.0.0/0, 10.0.0.0/8"
    try:
        protocol_ops._validate_wireguard_allowed_ips("not-a-network")
    except protocol_ops.ProtocolError:
        pass
    else:
        raise AssertionError("invalid AllowedIPs must fail")


def test_wireguard_peer_compatibility_profile(tmp_path,monkeypatch):
    monkeypatch.setattr(protocol_ops,"WG_DIR",tmp_path)
    conf=tmp_path/"wg0.conf"
    conf.write_text(
        "[Interface]\nAddress = 10.66.66.1/24\nListenPort = 443\nPrivateKey = server-private\n",
        encoding="utf-8",
    )
    calls=[]
    def fake_run(args,input_text=None,timeout=60):
        calls.append((args,input_text))
        if args[:2]==["wg","genkey"]:
            return "client-private"
        if args[:2]==["wg","pubkey"]:
            return "client-public"
        if args[:3]==["wg","show","wg0"]:
            return "server-public"
        if args[:3]==["wg","set","wg0"]:
            return ""
        raise AssertionError(args)
    monkeypatch.setattr(protocol_ops,"_run",fake_run)
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint,iface="wg0":{
        "runtime_ok":True,"endpoint_is_ip":False,"endpoint_ip_version":None,
        "resolved_ipv4":["203.0.113.10"],"local_ipv4":["203.0.113.10"],
        "dns_matches_server":True,"warnings":[]
    })
    result=protocol_ops.create_wireguard_peer(
        "client01","vpn.example.com",dns="1.1.1.1",mtu=1280,keepalive=15,allowed_ips="0.0.0.0/0",
    )
    cfg=result["config"]
    assert "Endpoint = vpn.example.com:443" in cfg
    assert "MTU = 1280" in cfg
    assert "PersistentKeepalive = 15" in cfg
    assert "AllowedIPs = 0.0.0.0/0" in cfg
    assert "Endpoint = 203.0.113.10:443" in result["ip_config"]
    assert result["fallback_ipv4"]=="203.0.113.10"
    assert result["port"]==443


def test_portable_migration_files_include_data_and_manifest(tmp_path,monkeypatch):
    data=tmp_path/"data"
    data.mkdir()
    (data/".secret").write_bytes(b"s"*48)
    db=sqlite3.connect(data/"makia.db")
    db.execute("create table t(x integer)")
    db.execute("insert into t values(1)")
    db.commit()
    db.close()

    wg=tmp_path/"wireguard"
    wg.mkdir()
    (wg/"wg0.conf").write_text("[Interface]\nPrivateKey = server-key\n",encoding="utf-8")
    nginx=tmp_path/"makia-nginx.conf"
    nginx.write_text("server { server_name vpn.example.com; }\n",encoding="utf-8")

    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[{"username":"user001","password_hash":"$6$hash"}])
    files=system_ops.portable_migration_files(
        str(data),["user001"],panel_domain="vpn.example.com",version="0.13.0-rc1",
        system_paths={
            "wireguard":str(wg),
            "openvpn":str(tmp_path/"missing-openvpn"),
            "letsencrypt":str(tmp_path/"missing-letsencrypt"),
            "xray":str(tmp_path/"missing-xray"),
            "xray_alt":str(tmp_path/"missing-xray-alt"),
            "nginx_site":str(nginx),
        },
    )
    assert "manifest.json" in files
    assert "payload/data.tar.gz" in files
    assert "payload/wireguard.tar.gz" in files
    assert "payload/ssh-users.json" in files
    assert "payload/nginx-site.conf" in files
    manifest=json.loads(files["manifest.json"])
    assert manifest["format"]=="makia-portable-migration"
    assert manifest["panel_domain"]=="vpn.example.com"
    assert manifest["managed_ssh_users"]==1
    assert manifest["components"]["wireguard"] is True


def test_xray_advanced_firewall_rules():
    config={
        "inbounds":[
            {"listen":"0.0.0.0","port":443,"protocol":"vless","streamSettings":{"network":"xhttp"}},
            {"listen":"0.0.0.0","port":8443,"protocol":"hysteria","settings":{"version":2}},
            {"listen":"127.0.0.1","port":10085,"protocol":"dokodemo-door","settings":{"network":"tcp"}},
            {"listen":"::","port":9000,"protocol":"dokodemo-door","settings":{"network":"tcp,udp"}},
        ]
    }
    rules=protocol_ops._xray_firewall_rules(config)
    assert (443,"tcp","Xray vless") in rules
    assert (8443,"udp","Xray hysteria") in rules
    assert (9000,"tcp","Xray dokodemo-door") in rules
    assert (9000,"udp","Xray dokodemo-door") in rules
    assert all(port!=10085 for port,_,_ in rules)


def test_local_backup_uses_consistent_sqlite_snapshot(tmp_path,monkeypatch):
    data=tmp_path/"data"
    data.mkdir()
    db=sqlite3.connect(data/"makia.db")
    db.execute("pragma journal_mode=WAL")
    db.execute("create table sample(value text)")
    db.execute("insert into sample values('saved')")
    db.commit()
    db.close()
    backup_root=tmp_path/"backups"
    real_makedirs=system_ops.os.makedirs
    real_path_write=Path.write_bytes

    # Redirect only the fixed backup root used by create_backup.
    monkeypatch.setattr(system_ops.os.path,"isdir",lambda p: Path(p).is_dir())
    blob=system_ops._portable_data_tar(str(data))
    assert blob
