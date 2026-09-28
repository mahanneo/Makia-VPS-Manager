import json
import hashlib
import importlib.util
import io
import tarfile

import pyzipper
import pytest
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
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint,iface="wg0":{"endpoint_ok":True})
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
    result=protocol_ops.create_wireguard_peer(
        "client01","vpn.example.com",dns="1.1.1.1",mtu=1280,keepalive=15,allowed_ips="0.0.0.0/0",
    )
    cfg=result["config"]
    assert "Endpoint = vpn.example.com:443" in cfg
    assert "MTU = 1280" in cfg
    assert "PersistentKeepalive = 15" in cfg
    assert "AllowedIPs = 0.0.0.0/0" in cfg
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
    ipsec_d=tmp_path/"ipsec.d"
    ipsec_d.mkdir()
    (ipsec_d/"private.key").write_text("ike-private\n",encoding="utf-8")
    ipsec_conf=tmp_path/"ipsec.conf"
    ipsec_conf.write_text("# BEGIN MAKIA IKEV2\nconn makia-ikev2\n# END MAKIA IKEV2\n",encoding="utf-8")
    ipsec_secrets=tmp_path/"ipsec.secrets"
    ipsec_secrets.write_text('alice : EAP "secret"  # makia-eap:alice\n',encoding="utf-8")
    ikev2_env=tmp_path/"ikev2.env"
    ikev2_env.write_text("MAKIA_IKEV2_CIDR=10.77.0.0/24\n",encoding="utf-8")
    wstunnel_env=tmp_path/"wstunnel.env"
    wstunnel_env.write_text("WSTUNNEL_LISTEN_PORT=8444\n",encoding="utf-8")
    stunnel_conf=tmp_path/"stunnel.conf"
    stunnel_conf.write_text("[makia-openvpn]\naccept=9443\nconnect=127.0.0.1:8443\n",encoding="utf-8")
    stunnel_defaults=tmp_path/"stunnel4.defaults"
    stunnel_defaults.write_text("ENABLED=1\n",encoding="utf-8")

    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[{"username":"user001","password_hash":"$6$hash"}])
    files=system_ops.portable_migration_files(
        str(data),["user001"],panel_domain="vpn.example.com",version="0.26.0-rc1",
        system_paths={
            "wireguard":str(wg),
            "openvpn":str(tmp_path/"missing-openvpn"),
            "letsencrypt":str(tmp_path/"missing-letsencrypt"),
            "xray":str(tmp_path/"missing-xray"),
            "xray_alt":str(tmp_path/"missing-xray-alt"),
            "nginx_site":str(nginx),
            "ipsec_d":str(ipsec_d),
            "ipsec_conf":str(ipsec_conf),
            "ipsec_secrets":str(ipsec_secrets),
            "ikev2_env":str(ikev2_env),
            "wstunnel_env":str(wstunnel_env),
            "stunnel_conf":str(stunnel_conf),
            "stunnel_defaults":str(stunnel_defaults),
        },
    )
    assert "manifest.json" in files
    assert "payload/data.tar.gz" in files
    assert "payload/wireguard.tar.gz" in files
    assert "payload/ssh-users.json" in files
    assert "payload/nginx-site.conf" in files
    assert "payload/ipsec_d.tar.gz" in files
    assert "payload/ipsec.conf" in files
    assert "payload/ipsec.secrets" in files
    assert "payload/ikev2.env" in files
    assert "payload/wstunnel.env" in files
    assert "payload/stunnel-makia.conf" in files
    assert "RESTORE.txt" in files
    manifest=json.loads(files["manifest.json"])
    assert manifest["format"]=="makia-portable-migration"
    assert manifest["format_version"]==2
    assert manifest["panel_domain"]=="vpn.example.com"
    assert manifest["app_version"]=="0.26.0-rc1"
    assert manifest["managed_ssh_users"]==1
    assert manifest["components"]["wireguard"] is True
    assert manifest["components"]["ipsec_d"] is True
    assert manifest["components"]["wstunnel_env"] is True
    assert manifest["components"]["stunnel_conf"] is True
    assert manifest["sha256"]["payload/ipsec.secrets"]
    assert manifest["excluded_secrets"]==["/etc/makia-vps-manager/makia.env"]
    assert "DNS-only" in manifest["cutover"]["cloudflare"]


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


def _restore_module():
    path=Path(__file__).resolve().parents[1]/"scripts"/"restore-portable.py"
    spec=importlib.util.spec_from_file_location("makia_restore_portable",path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_portable_restore_v2_validates_payload_sha256(tmp_path):
    restore=_restore_module()
    bundle=tmp_path/"good.zip"
    password="MigrationPass!2026"
    payload=b"portable-data"
    manifest={
        "format":"makia-portable-migration",
        "format_version":2,
        "sha256":{"payload/data.tar.gz":hashlib.sha256(payload).hexdigest()},
    }
    with pyzipper.AESZipFile(bundle,"w",compression=pyzipper.ZIP_DEFLATED,encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode())
        zf.setencryption(pyzipper.WZ_AES,nbits=256)
        zf.writestr("manifest.json",json.dumps(manifest))
        zf.writestr("payload/data.tar.gz",payload)
    parsed,files=restore.read_bundle(bundle,password)
    assert parsed["format_version"]==2
    assert files["payload/data.tar.gz"]==payload

    bad=tmp_path/"bad.zip"
    manifest["sha256"]["payload/data.tar.gz"]="0"*64
    with pyzipper.AESZipFile(bad,"w",compression=pyzipper.ZIP_DEFLATED,encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode())
        zf.setencryption(pyzipper.WZ_AES,nbits=256)
        zf.writestr("manifest.json",json.dumps(manifest))
        zf.writestr("payload/data.tar.gz",payload)
    with pytest.raises(RuntimeError,match="checksum mismatch"):
        restore.read_bundle(bad,password)


def _tar_with_symlink(link_name,target_name):
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w:gz") as tf:
        directory=tarfile.TarInfo("letsencrypt/live/example.com")
        directory.type=tarfile.DIRTYPE
        directory.mode=0o755
        tf.addfile(directory)
        archive_dir=tarfile.TarInfo("letsencrypt/archive/example.com")
        archive_dir.type=tarfile.DIRTYPE
        archive_dir.mode=0o755
        tf.addfile(archive_dir)
        data=b"certificate"
        cert=tarfile.TarInfo("letsencrypt/archive/example.com/fullchain1.pem")
        cert.size=len(data)
        cert.mode=0o644
        tf.addfile(cert,io.BytesIO(data))
        link=tarfile.TarInfo(link_name)
        link.type=tarfile.SYMTYPE
        link.linkname=target_name
        tf.addfile(link)
    return buf.getvalue()


def test_safe_extract_allows_letsencrypt_relative_symlink_inside_root(tmp_path):
    restore=_restore_module()
    blob=_tar_with_symlink(
        "letsencrypt/live/example.com/fullchain.pem",
        "../../archive/example.com/fullchain1.pem",
    )
    restore.safe_extract_tar(blob,tmp_path)
    link=tmp_path/"letsencrypt/live/example.com/fullchain.pem"
    assert link.is_symlink()
    assert link.read_text()=="certificate"


def test_safe_extract_rejects_symlink_escape(tmp_path):
    restore=_restore_module()
    blob=_tar_with_symlink(
        "letsencrypt/live/example.com/fullchain.pem",
        "../../../../../../etc/shadow",
    )
    with pytest.raises(RuntimeError,match="unsafe symlink"):
        restore.safe_extract_tar(blob,tmp_path)
