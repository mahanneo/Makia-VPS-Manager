from pathlib import Path
from types import SimpleNamespace

import pytest

from app import access_ops, protocol_ops


def test_xray_secure_runtime_file_uses_systemd_user(tmp_path,monkeypatch):
    target=tmp_path/"config.json"
    target.write_text("{}\n",encoding="utf-8")
    calls=[]
    monkeypatch.setattr(protocol_ops,"_xray_service_user",lambda:"nobody")
    monkeypatch.setattr(protocol_ops.os,"geteuid",lambda:0)
    monkeypatch.setattr(protocol_ops.pwd,"getpwnam",lambda user:SimpleNamespace(pw_uid=65534,pw_gid=65534))
    monkeypatch.setattr(protocol_ops.os,"chown",lambda path,uid,gid:calls.append((str(path),uid,gid)))
    user=protocol_ops._xray_secure_runtime_file(target)
    assert user=="nobody"
    assert target.stat().st_mode & 0o777 == 0o600
    assert calls==[(str(target),65534,65534)]


def test_xray_diagnostics_detects_root_service_user_mismatch(tmp_path,monkeypatch):
    config=tmp_path/"config.json"
    config.write_text('{"inbounds":[],"outbounds":[{"protocol":"freedom"}]}\n',encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"_binary",lambda:"/usr/local/bin/xray")
    monkeypatch.setattr(protocol_ops,"_config_path",lambda:str(config))
    monkeypatch.setattr(protocol_ops,"_xray_service_user",lambda:"nobody")
    monkeypatch.setattr(protocol_ops,"_active",lambda service:False)
    monkeypatch.setattr(protocol_ops,"_xray_test_config",lambda binary,path:"")
    def fail_service(binary,path):
        raise protocol_ops.ProtocolError("permission denied: config.json")
    monkeypatch.setattr(protocol_ops,"_xray_test_config_as_service",fail_service)
    monkeypatch.setattr(protocol_ops,"_xray_journal_tail",lambda lines=24:"failed to read config: permission denied")
    monkeypatch.setattr(
        protocol_ops.subprocess,"run",
        lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout="Xray 26.10.21 (Xray, Penetrates Everything.)\n",stderr=""),
    )
    result=protocol_ops.xray_diagnostics()
    assert result["root_validation"] is True
    assert result["service_validation"] is False
    assert result["service_user"]=="nobody"
    assert result["validated_version"] is True
    assert result["service_active"] is False
    assert any("Permission" in hint or "systemd" in hint for hint in result["hints"])


def test_rewrite_letsencrypt_certificates_uses_xray_runtime_path(monkeypatch):
    monkeypatch.setattr(
        protocol_ops,"_xray_materialize_tls",
        lambda domain:(Path(f"/usr/local/etc/xray/tls/{domain}/fullchain.pem"),Path(f"/usr/local/etc/xray/tls/{domain}/privkey.pem")),
    )
    data={
        "inbounds":[{
            "streamSettings":{
                "tlsSettings":{
                    "certificates":[{
                        "certificateFile":"/etc/letsencrypt/live/vpn.example.com/fullchain.pem",
                        "keyFile":"/etc/letsencrypt/live/vpn.example.com/privkey.pem",
                    }]
                }
            }
        }]
    }
    changed=protocol_ops._rewrite_letsencrypt_certificates(data)
    cert=data["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"][0]
    assert changed==1
    assert cert["certificateFile"]=="/usr/local/etc/xray/tls/vpn.example.com/fullchain.pem"
    assert cert["keyFile"]=="/usr/local/etc/xray/tls/vpn.example.com/privkey.pem"


@pytest.mark.parametrize(
    ("kind","payload"),
    [
        ("ssh",lambda:access_ops.ssh_payload("vpn.example.com","u1","123456",22,{"enabled":False})),
        ("wireguard",lambda:access_ops.wireguard_payload("u1","[Interface]\nPrivateKey = secret\n","10.66.66.2")),
        ("openvpn",lambda:access_ops.openvpn_payload("u1","client\nremote vpn.example.com 1194\n")),
        ("xray",lambda:access_ops.xray_payload("u1","vless","vless://uuid@vpn.example.com:443","","")),
    ],
)
def test_delivery_packages_include_persian_connection_guide(kind,payload):
    built=payload()
    assert "connection-guide-fa.txt" in built["files"]
    guide=built["files"]["connection-guide-fa.txt"].decode("utf-8")
    assert "راهنمای اتصال Makia" in guide


def test_doctor_version_gate_matches_validated_xray_core():
    script=Path(__file__).resolve().parents[1]/"scripts"/"doctor.sh"
    source=script.read_text(encoding="utf-8")
    assert 'if [[ "$XRAY_VERSION" == *"26.10.21"* ]]' in source
    assert "CI target: 26.10.21" in source
    assert "CI target: 26.3.27" not in source
