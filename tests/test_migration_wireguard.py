import json
import sqlite3
from pathlib import Path

from app import protocol_ops, system_ops, access_ops


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
            "makia_etc":str(tmp_path/"missing-makia-etc"),
            "stunnel":str(tmp_path/"missing-stunnel"),
            "ipsec_d":str(tmp_path/"missing-ipsec-d"),
            "ipsec_conf":str(tmp_path/"missing-ipsec-conf"),
            "ipsec_secrets":str(tmp_path/"missing-ipsec-secrets"),
            "stunnel_defaults":str(tmp_path/"missing-stunnel-defaults"),
        },
    )
    assert "manifest.json" in files
    assert "payload/data.tar.gz" in files
    assert "payload/wireguard.tar.gz" in files
    assert "payload/ssh-users.json" in files
    assert "payload/nginx_site" in files
    manifest=json.loads(files["manifest.json"])
    assert manifest["format"]=="makia-portable-migration"
    assert manifest["panel_domain"]=="vpn.example.com"
    assert manifest["managed_ssh_users"]==1
    assert manifest["format_version"]==2
    assert manifest["components"]["wireguard"] is True
    assert manifest["restore_contract"]["preserve_credentials"] is True
    assert manifest["restore_contract"]["rebind_destination_network"] is True
    assert manifest["payload_sha256"]["payload/data.tar.gz"]
    assert manifest["payload_sha256"]["payload/wireguard.tar.gz"]


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


def test_portable_migration_v2_includes_protocol_identity_trees(tmp_path,monkeypatch):
    data=tmp_path/"data"; data.mkdir()
    (data/".secret").write_text("secret",encoding="utf-8")
    makia_etc=tmp_path/"makia_etc"; makia_etc.mkdir()
    (makia_etc/"wstunnel.env").write_text("WSTUNNEL_LISTEN_PORT=8444\n",encoding="utf-8")
    stunnel=tmp_path/"stunnel"; stunnel.mkdir()
    (stunnel/"makia-openvpn.conf").write_text("[makia-openvpn]\n",encoding="utf-8")
    ipsec_d=tmp_path/"ipsec_d"; ipsec_d.mkdir()
    (ipsec_d/"marker").write_text("ike",encoding="utf-8")
    ipsec_conf=tmp_path/"ipsec.conf"; ipsec_conf.write_text("# BEGIN MAKIA IKEV2\n",encoding="utf-8")
    ipsec_secrets=tmp_path/"ipsec.secrets"; ipsec_secrets.write_text(': RSA makia-ikev2.key\n',encoding="utf-8")
    defaults=tmp_path/"stunnel4"; defaults.write_text("ENABLED=1\n",encoding="utf-8")
    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[])
    missing=tmp_path/"missing"
    files=system_ops.portable_migration_files(
        str(data),[],panel_domain="vpn.example.com",version="0.26.0-rc1",
        system_paths={
            "wireguard":str(missing),"openvpn":str(missing),"letsencrypt":str(missing),
            "xray":str(missing),"xray_alt":str(missing),"nginx_site":str(missing),
            "makia_etc":str(makia_etc),"stunnel":str(stunnel),"ipsec_d":str(ipsec_d),
            "ipsec_conf":str(ipsec_conf),"ipsec_secrets":str(ipsec_secrets),
            "stunnel_defaults":str(defaults),
        }
    )
    for name in [
        "payload/makia_etc.tar.gz","payload/stunnel.tar.gz","payload/ipsec_d.tar.gz",
        "payload/ipsec_conf","payload/ipsec_secrets","payload/stunnel_defaults",
    ]:
        assert name in files
    manifest=json.loads(files["manifest.json"])
    assert manifest["components"]["makia_etc"] is True
    assert manifest["components"]["stunnel"] is True
    assert manifest["components"]["ipsec_conf"] is True


def test_full_migration_bundle_is_encrypted_verified_and_listed(tmp_path,monkeypatch):
    data=tmp_path/"data"; data.mkdir()
    (data/".secret").write_text("server-secret",encoding="utf-8")
    db=sqlite3.connect(data/"makia.db"); db.execute("create table t(x integer)"); db.commit(); db.close()
    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[])
    monkeypatch.setenv("MAKIA_BACKUP_DIR",str(tmp_path/"backups"))
    missing=tmp_path/"missing"
    files=system_ops.portable_migration_files(
        str(data),[],panel_domain="p.example.com",version="0.26.0-rc2",
        system_paths={
            "wireguard":str(missing),"openvpn":str(missing),"letsencrypt":str(missing),
            "xray":str(missing),"xray_alt":str(missing),"nginx_site":str(missing),
            "makia_etc":str(missing),"stunnel":str(missing),"ipsec_d":str(missing),
            "ipsec_conf":str(missing),"ipsec_secrets":str(missing),"stunnel_defaults":str(missing),
        },
    )
    password="MigrationPass!2026"
    blob=access_ops.protected_zip(files,password)
    preview=system_ops.inspect_portable_migration_blob(blob,password,"0.26.0-rc2")
    assert preview["compatible"] is True
    assert preview["manifest"]["panel_domain"]=="p.example.com"
    assert preview["sha256"]
    saved=system_ops.save_full_migration_backup(blob,"0.26.0-rc2",preview["manifest"])
    assert Path(saved["path"]).stat().st_mode & 0o077 == 0
    rows=system_ops.backup_list()
    assert rows[0]["type"]=="full_migration"
    assert rows[0]["encrypted"] is True
    assert rows[0]["restore_ready"] is True
    assert rows[0]["version"]=="0.26.0-rc2"
    assert rows[0]["sha256"]==preview["sha256"]
    staged=system_ops.stage_migration_restore(blob,password,"0.26.0-rc2")
    job_dir=Path(system_ops._backup_root())/"restore-jobs"/staged["job_id"]
    assert not (job_dir/"password").exists(), "verify/preview must not persist the password"
    armed=system_ops.arm_migration_restore(staged["job_id"],password,"0.26.0-rc2")
    assert armed["state"]=="armed"
    assert (job_dir/"password").stat().st_mode & 0o077 == 0
    system_ops.discard_migration_restore_password(staged["job_id"])
    assert not (job_dir/"password").exists()


def test_migration_bundle_wrong_password_is_rejected(tmp_path,monkeypatch):
    data=tmp_path/"data"; data.mkdir(); (data/".secret").write_text("secret",encoding="utf-8")
    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[])
    missing=tmp_path/"missing"
    files=system_ops.portable_migration_files(
        str(data),[],version="0.26.0-rc2",
        system_paths={
            "wireguard":str(missing),"openvpn":str(missing),"letsencrypt":str(missing),
            "xray":str(missing),"xray_alt":str(missing),"nginx_site":str(missing),
            "makia_etc":str(missing),"stunnel":str(missing),"ipsec_d":str(missing),
            "ipsec_conf":str(missing),"ipsec_secrets":str(missing),"stunnel_defaults":str(missing),
        },
    )
    blob=access_ops.protected_zip(files,"CorrectPass!2026")
    try:
        system_ops.inspect_portable_migration_blob(blob,"WrongPass!2026","0.26.0-rc2")
    except system_ops.OperationError:
        pass
    else:
        raise AssertionError("wrong migration password must fail verification")


def test_stage_restore_rejects_version_mismatch_before_commit(tmp_path,monkeypatch):
    data=tmp_path/"data"; data.mkdir(); (data/".secret").write_text("secret",encoding="utf-8")
    monkeypatch.setattr(system_ops,"_managed_ssh_export",lambda users:[])
    monkeypatch.setenv("MAKIA_BACKUP_DIR",str(tmp_path/"backups"))
    missing=tmp_path/"missing"
    files=system_ops.portable_migration_files(
        str(data),[],version="0.25.0",
        system_paths={
            "wireguard":str(missing),"openvpn":str(missing),"letsencrypt":str(missing),
            "xray":str(missing),"xray_alt":str(missing),"nginx_site":str(missing),
            "makia_etc":str(missing),"stunnel":str(missing),"ipsec_d":str(missing),
            "ipsec_conf":str(missing),"ipsec_secrets":str(missing),"stunnel_defaults":str(missing),
        },
    )
    blob=access_ops.protected_zip(files,"MigrationPass!2026")
    try:
        system_ops.stage_migration_restore(blob,"MigrationPass!2026","0.26.0-rc2")
    except system_ops.OperationError as exc:
        assert "version mismatch" in str(exc)
    else:
        raise AssertionError("version mismatch must be rejected before staging")


def test_protected_zip_preserves_systemd_template_at_sign():
    files={
        "manifest.json":b"{}",
        "payload/systemd/makia-migration-restore@.service":b"[Service]\\nType=oneshot\\n",
    }
    blob=access_ops.protected_zip(files,"MigrationPass!2026")
    import io, pyzipper
    with pyzipper.AESZipFile(io.BytesIO(blob),"r") as zf:
        zf.setpassword(b"MigrationPass!2026")
        assert "payload/systemd/makia-migration-restore@.service" in zf.namelist()


def test_migration_inspector_accepts_legacy_sanitized_systemd_template(tmp_path,monkeypatch):
    import hashlib, io, json, pyzipper
    monkeypatch.setenv("MAKIA_BACKUP_DIR",str(tmp_path/"backups"))
    expected_name="payload/systemd/makia-migration-restore@.service"
    legacy_name="payload/systemd/makia-migration-restore-.service"
    unit=b"[Service]\\nType=oneshot\\n"
    data=b"legacy-data"
    users=b"[]"
    manifest={
        "format":"makia-portable-migration","format_version":2,"app_version":"0.26.0-rc2",
        "panel_domain":"","components":{"systemd":True},
        "payload_sha256":{
            "payload/data.tar.gz":hashlib.sha256(data).hexdigest(),
            "payload/ssh-users.json":hashlib.sha256(users).hexdigest(),
            expected_name:hashlib.sha256(unit).hexdigest(),
        },
    }
    files={
        "manifest.json":json.dumps(manifest).encode(),
        "payload/data.tar.gz":data,
        "payload/ssh-users.json":users,
        legacy_name:unit,
    }
    blob=access_ops.protected_zip(files,"MigrationPass!2026")
    preview=system_ops.inspect_portable_migration_blob(blob,"MigrationPass!2026","0.26.0-rc5")
    assert preview["compatible"] is True
    staged=system_ops.stage_migration_restore(blob,"MigrationPass!2026","0.26.0-rc5")
    assert staged["bundle_version"]=="0.26.0-rc2"
    assert staged["restore_ready"] is True


def test_migration_version_compatibility_is_narrow_and_directional():
    assert system_ops._migration_versions_compatible("0.26.0-rc10","0.26.0-rc10") is True
    for source in ("0.26.0-rc2","0.26.0-rc3","0.26.0-rc4","0.26.0-rc5","0.26.0-rc6","0.26.0-rc7","0.26.0-rc8","0.26.0-rc9"):
        assert system_ops._migration_versions_compatible(source,"0.26.0-rc10") is True
    assert system_ops._migration_versions_compatible("0.26.0-rc10","0.26.0-rc9") is False
    assert system_ops._migration_versions_compatible("0.25.0","0.26.0-rc10") is False

