import io
import json
import pytest
import pyzipper
from starlette.requests import Request

from app import access_ops
from app import main as main_app


def test_qr_svg_generation():
    svg=access_ops.make_qr_svg("vless://uuid@example.com:443")
    assert svg.startswith(b"<?xml") or b"<svg" in svg[:300]
    assert b"<svg" in svg


def test_encrypted_payload_roundtrip(monkeypatch):
    monkeypatch.setattr(access_ops, "ensure_secret", lambda: b"x"*48)
    original={
        "native_filename":"client.conf",
        "files":{"client.conf":b"[Interface]\nPrivateKey = secret\n"},
        "summary":{"protocol":"wireguard"},
    }
    token=access_ops.seal_payload(original)
    assert "PrivateKey" not in token
    restored=access_ops.open_payload(token)
    assert restored["files"]["client.conf"] == original["files"]["client.conf"]
    assert restored["summary"]["protocol"] == "wireguard"

def test_wireguard_endpoint_change_preserves_keys_port_and_lines():
    original="[Interface]\nPrivateKey = secret\nAddress = 10.66.66.2/32\n\n[Peer]\nPublicKey = server\nEndpoint = 8.8.8.8:443\nAllowedIPs = 0.0.0.0/0\n"
    updated=access_ops.wireguard_replace_endpoint(original,"vpn.example.com")
    assert updated==original.replace("Endpoint = 8.8.8.8:443","Endpoint = vpn.example.com:443")
    assert access_ops.wireguard_replace_endpoint(updated,"8.8.8.8")==original
    with pytest.raises(access_ops.AccessPackageError):
        access_ops.wireguard_replace_endpoint("[Interface]\nPrivateKey = secret\n","vpn.example.com")

def test_wireguard_endpoint_update_keeps_peer_and_rebuilds_delivery(monkeypatch):
    config="[Interface]\nPrivateKey = secret\n\n[Peer]\nPublicKey = server\nEndpoint = 8.8.8.8:443\nAllowedIPs = 0.0.0.0/0\n"
    saved=[]
    monkeypatch.setattr(main_app,"require_feature",lambda *a:"admin")
    monkeypatch.setattr(main_app,"require_local_admin",lambda *a:"admin")
    monkeypatch.setattr(main_app,"get_access_artifact_by_key",lambda kind,key:{"payload_enc":"sealed","display_name":key,"metadata_json":json.dumps({"public_key":"peerkey","address":"10.66.66.2","port":443})})
    monkeypatch.setattr(access_ops,"open_payload",lambda token:{"primary_text":config})
    monkeypatch.setattr(main_app.protocol_ops,"list_wireguard_peers",lambda:[{"name":"client","public_key":"peerkey"}])
    monkeypatch.setattr(main_app.protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint:{"endpoint_ok":True,"endpoint_is_ip":False,"resolved_ipv4":["8.8.8.8"]})
    monkeypatch.setattr(main_app,"artifact_save",lambda *args:saved.append(args))
    monkeypatch.setattr(main_app,"audit",lambda *args,**kw:None)
    scope={"type":"http","method":"POST","path":"/api/access/wireguard/client/endpoint","headers":[],"query_string":b"","scheme":"http","server":("testserver",80),"client":("127.0.0.1",12345)}
    response=main_app.wireguard_endpoint_update("client",main_app.WireGuardEndpointUpdate(endpoint="vpn.example.com"),Request(scope))
    assert response["ok"] is True
    assert saved[0][4]["primary_text"]==config.replace("8.8.8.8:443","vpn.example.com:443")
    assert b"vpn.example.com:443" in saved[0][4]["files"]["client.conf"]
    assert saved[0][5]["endpoint"]=="vpn.example.com"


def test_protected_zip_requires_password():
    data=access_ops.protected_zip({"credentials.txt":b"top-secret"},"583921")
    assert b"top-secret" not in data
    verified=access_ops.verify_protected_zip(data,"583921","credentials.txt")
    assert verified["ok"] is True
    assert verified["sample_size"] == len(b"top-secret")
    with pyzipper.AESZipFile(io.BytesIO(data),"r") as zf:
        zf.setpassword(b"583921")
        assert zf.read("credentials.txt") == b"top-secret"


def test_protected_zip_rejects_wrong_password():
    data=access_ops.protected_zip({"credentials.txt":b"top-secret"},"583921")
    with pytest.raises(access_ops.AccessPackageError):
        access_ops.verify_protected_zip(data,"000000","credentials.txt")


def test_access_package_endpoint_returns_downloadable_aes_zip(monkeypatch):
    payload={
        "native_filename":"credentials.txt",
        "files":{"credentials.txt":b"server=example\npassword=secret\n"},
        "primary_text":"server=example",
        "summary":{},
    }
    monkeypatch.setattr(main_app,"require_mutation",lambda request:"admin")
    monkeypatch.setattr(main_app,"require_local_admin",lambda request:"admin")
    monkeypatch.setattr(main_app,"assert_license_feature",lambda feature:None)
    monkeypatch.setattr(main_app,"_resolve_access_payload",lambda kind,key,request:(payload,{"id":1}))
    monkeypatch.setattr(main_app,"audit",lambda *args,**kwargs:None)
    scope={
        "type":"http","method":"POST","path":"/api/access/ssh/u/package",
        "headers":[],"query_string":b"","scheme":"http",
        "server":("testserver",80),"client":("127.0.0.1",12345),
    }
    request=Request(scope)
    response=main_app.access_package("ssh","u",main_app.AccessPackageRequest(password="739251"),request)
    assert response.status_code == 200
    assert response.media_type == "application/zip"
    assert response.headers["cache-control"] == "no-store, private"
    assert "attachment;" in response.headers["content-disposition"]
    verified=access_ops.verify_protected_zip(response.body,"739251","credentials.txt")
    assert verified["ok"] is True


def test_ssh_package_does_not_embed_password_in_openssh_config():
    payload=access_ops.ssh_payload("vpn.example.com","user001","123456",22)
    config=payload["files"]["user001-ssh-config.txt"].decode()
    credentials=payload["files"]["credentials.txt"].decode()
    assert "123456" not in config
    assert "Password: 123456" in credentials


def test_xray_package_contains_qr_profile_and_subscription_artifacts():
    payload=access_ops.xray_payload("u1","vless","vless://abc@example.com:443","https://example.com/sub/a","https://example.com/client/a")
    assert "u1-vless.txt" in payload["files"]
    assert "u1-profile.json" in payload["files"]
    assert "u1-qr.svg" in payload["files"]
    assert "u1-subscription.txt" in payload["files"]
    assert "u1-subscription-qr.svg" in payload["files"]
    assert payload["files"]["u1-subscription.txt"].decode().strip()=="https://example.com/sub/a"


@pytest.mark.parametrize(
    ("protocol","link","expected"),
    [
        ("vless","vless://uuid@example.com:443?type=xhttp&security=reality&sni=www.microsoft.com&fp=chrome&pbk=pubkey&sid=abcd&path=%2Fmakia#User",{"protocol":"vless","host":"example.com","port":443,"transport":"xhttp","security":"reality"}),
        ("trojan","trojan://secret@example.com:8443?type=grpc&security=tls&sni=example.com&serviceName=makia#User",{"protocol":"trojan","host":"example.com","port":8443,"transport":"grpc","security":"tls"}),
        ("hysteria2","hysteria2://secret@example.com:443/?sni=example.com&insecure=0#User",{"protocol":"hysteria2","host":"example.com","port":443,"transport":"hysteria2","security":"tls"}),
        ("shadowsocks","ss://YWVzLTEyOC1nY206c2VjcmV0@example.com:8388#User",{"protocol":"shadowsocks","host":"example.com","port":8388,"cipher":"aes-128-gcm"}),
    ],
)
def test_xray_share_description(protocol,link,expected):
    info=access_ops.describe_xray_share(link,protocol)
    for key,value in expected.items():
        assert info[key]==value


def test_vmess_share_description():
    import base64, json
    profile={"v":"2","ps":"VMess User","add":"vm.example.com","port":"443","id":"uuid","aid":"0","scy":"auto","net":"ws","type":"none","host":"","path":"/ws","tls":"tls"}
    link="vmess://"+base64.b64encode(json.dumps(profile,separators=(",",":")).encode()).decode()
    info=access_ops.describe_xray_share(link,"vmess")
    assert info["protocol"]=="vmess"
    assert info["host"]=="vm.example.com"
    assert info["port"]==443
    assert info["transport"]=="ws"
    assert info["security"]=="tls"


def test_npvt_ssh_link_roundtrip():
    import base64, json
    link=access_ops.npvt_ssh_link(
        "178.83.45.215","mahan","123456",22,
        remarks="Makia mahan",dns_mode="UDP",udpgw_port=7300,transparent_dns=False,
    )
    assert link.startswith("npvt-ssh://")
    raw=base64.b64decode(link.split("://",1)[1])
    profile=json.loads(raw.decode("utf-8"))
    assert profile["sshConfigType"]=="SSH-Direct"
    assert profile["sshHost"]=="178.83.45.215"
    assert profile["sshPort"]==22
    assert profile["sshUsername"]=="mahan"
    assert profile["sshPassword"]=="123456"
    assert profile["dnsTTMode"]=="UDP"
    assert profile["udpgwPort"]==7300


def test_ssh_payload_includes_npv_share_and_qr_when_enabled():
    payload=access_ops.ssh_payload(
        "vpn.example.com","user001","123456",22,
        {"enabled":True,"remarks":"Makia user001","dns_mode":"UDP","udpgw_port":7300,"transparent_dns":False}
    )
    assert payload["share_type"]=="npvt-ssh"
    assert payload["share_text"].startswith("npvt-ssh://")
    assert "user001-npvt-ssh.txt" in payload["files"]
    assert "user001-npvt-qr.svg" in payload["files"]


def test_ssh_payload_respects_npv_disabled_setting():
    payload=access_ops.ssh_payload("vpn.example.com","user001","123456",22,{"enabled":False})
    assert "share_text" not in payload
    assert all("npvt" not in name for name in payload["files"])
    assert "NPV Tunnel" not in payload["files"]["credentials.txt"].decode("utf-8")


def test_xray_share_payload_has_qr_source():
    payload=access_ops.xray_payload("u1","vless","vless://abc@example.com:443","https://example.com/sub/a","https://example.com/client/a")
    assert payload["share_type"]=="xray"
    assert payload["share_text"]=="vless://abc@example.com:443"


def test_protected_zip_preserves_safe_relative_paths():
    data=access_ops.protected_zip({"payload/data.tar.gz":b"data","../escape.txt":b"nope"},"583921")
    with pyzipper.AESZipFile(io.BytesIO(data),"r") as zf:
        zf.setpassword(b"583921")
        names=zf.namelist()
        assert "payload/data.tar.gz" in names
        assert "escape.txt" in names
        assert all(".." not in name for name in names)
