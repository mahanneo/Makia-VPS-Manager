import json
from types import SimpleNamespace

import pytest

from app import protocol_modes


def test_connection_modes_exposes_six_real_modes(monkeypatch):
    monkeypatch.setattr(protocol_modes.protocol_ops,"wireguard_status",lambda:{"installed":True,"service_active":True,"config":"/etc/wireguard/wg0.conf","port":443})
    monkeypatch.setattr(protocol_modes.protocol_ops,"openvpn_status",lambda:{"installed":True,"service_active":True,"config":"/etc/openvpn/server/server.conf","port":1194,"proto":"udp4"})
    monkeypatch.setattr(protocol_modes,"ikev2_status",lambda:{"installed":True,"ready":False})
    monkeypatch.setattr(protocol_modes,"stealth_status",lambda:{"installed":True,"ready":False})
    monkeypatch.setattr(protocol_modes,"wstunnel_status",lambda:{"installed":True,"ready":False})
    result=protocol_modes.connection_modes()
    assert [m["id"] for m in result["modes"]]==["ikev2","wireguard","udp","tcp","stealth","wstunnel"]
    assert next(m for m in result["modes"] if m["id"]=="wireguard")["ready"] is True
    assert next(m for m in result["modes"] if m["id"]=="udp")["ready"] is True
    assert next(m for m in result["modes"] if m["id"]=="tcp")["ready"] is False


def test_create_ikev2_user_persists_and_renders_swanctl_secret(monkeypatch,tmp_path):
    users=tmp_path/"users.json"
    secrets_file=tmp_path/"makia-secrets.conf"
    conf=tmp_path/"makia.conf"
    conf.write_text("local {\n  id = vpn.example.com\n}\n",encoding="utf-8")
    monkeypatch.setattr(protocol_modes,"IKEV2_USERS",users)
    monkeypatch.setattr(protocol_modes,"IKEV2_DIR",tmp_path)
    monkeypatch.setattr(protocol_modes,"SWANCTL_SECRETS",secrets_file)
    monkeypatch.setattr(protocol_modes,"SWANCTL_CONF",conf)
    monkeypatch.setattr(protocol_modes,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_modes,"ikev2_status",lambda:{"domain":"vpn.example.com"})
    result=protocol_modes.create_ikev2_user("phone01","StrongPass-2026")
    assert result["server"]=="vpn.example.com"
    assert result["password"]=="StrongPass-2026"
    saved=json.loads(users.read_text(encoding="utf-8"))
    assert saved["phone01"]["password"]=="StrongPass-2026"
    rendered=secrets_file.read_text(encoding="utf-8")
    assert 'id = "phone01"' in rendered
    assert 'secret = "StrongPass-2026"' in rendered
    with pytest.raises(protocol_modes.ProtocolModeError,match="already exists"):
        protocol_modes.create_ikev2_user("phone01","AnotherPass-2026")


def test_stealth_requires_openvpn_tcp(monkeypatch,tmp_path):
    monkeypatch.setattr(protocol_modes,"STEALTH_CONF",tmp_path/"stunnel.conf")
    monkeypatch.setattr(protocol_modes,"_letsencrypt",lambda domain:(domain,tmp_path/"cert",tmp_path/"chain",tmp_path/"fullchain",tmp_path/"key"))
    monkeypatch.setattr(protocol_modes.protocol_ops,"_openvpn_server_runtime",lambda:{"service_active":True,"listener":True,"proto":"udp4","port":1194})
    with pytest.raises(protocol_modes.ProtocolModeError,match="OpenVPN/TCP"):
        protocol_modes.configure_stealth("vpn.example.com",8443)


def test_wstunnel_rejects_short_path_secret(monkeypatch,tmp_path):
    service=tmp_path/"makia-wstunnel.service"
    service.write_text("[Service]\n",encoding="utf-8")
    original_exists=protocol_modes.Path.exists
    monkeypatch.setattr(protocol_modes.Path,"exists",lambda self: True if str(self)=="/etc/systemd/system/makia-wstunnel.service" else original_exists(self))
    monkeypatch.setattr(protocol_modes.shutil,"which",lambda name:"/usr/local/bin/wstunnel" if name=="wstunnel" else f"/usr/bin/{name}")
    monkeypatch.setattr(protocol_modes,"_letsencrypt",lambda domain:(domain,tmp_path/"cert",tmp_path/"chain",tmp_path/"fullchain",tmp_path/"key"))
    monkeypatch.setattr(protocol_modes,"_openvpn_tcp_runtime",lambda:{"port":1194,"proto":"tcp4-server","service_active":True,"listener":True})
    monkeypatch.setattr(protocol_modes,"wstunnel_status",lambda:{"service_active":False,"port":None,"ready":False})
    monkeypatch.setattr(protocol_modes.protocol_ops,"_port_transport_in_use",lambda port,proto:False)
    with pytest.raises(protocol_modes.ProtocolModeError,match="12-96"):
        protocol_modes.configure_wstunnel("vpn.example.com",9443,"short")


def test_ikev2_payload_contains_native_credentials():
    from app import access_ops
    payload=access_ops.ikev2_payload("phone01","vpn.example.com","StrongPass-2026")
    assert payload["native_filename"]=="phone01-ikev2.txt"
    text=payload["files"]["phone01-ikev2.txt"].decode("utf-8")
    assert "Server: vpn.example.com" in text
    assert "Remote ID: vpn.example.com" in text
    assert "Username: phone01" in text
    assert "Password: StrongPass-2026" in text
