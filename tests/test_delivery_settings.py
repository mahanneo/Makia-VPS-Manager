import base64
import json
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import main as main_app
from app import security


def _request(path="/api/test"):
    return Request({
        "type":"http","method":"GET","path":path,"headers":[],
        "query_string":b"","scheme":"http",
        "server":("127.0.0.1",8787),"client":("127.0.0.1",1234),
    })


def test_short_configurable_session_ttl(monkeypatch):
    monkeypatch.setattr(security,"ensure_secret",lambda:b"s"*48)
    token=security.make_session("admin",300)
    raw=token.split(".",1)[0]
    payload=json.loads(base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)).decode())
    remaining=payload["exp"]-int(time.time())
    assert 295 <= remaining <= 300


def test_public_origin_preserves_non_default_port(monkeypatch):
    monkeypatch.setattr(main_app,"get_setting",lambda key,default=None: default)
    assert main_app.public_origin(_request())=="http://127.0.0.1:8787"


def test_share_response_is_no_store(monkeypatch):
    payload={
        "share_type":"xray",
        "share_text":"vless://abc@example.test:443",
        "primary_text":"vless://abc@example.test:443",
        "summary":{"subscription_url":"http://127.0.0.1:8787/sub/abc?format=base64"},
        "files":{},
    }
    monkeypatch.setattr(main_app,"require_user",lambda request:"admin")
    monkeypatch.setattr(main_app,"require_access_kind",lambda request,kind,mutation=False:"admin")
    monkeypatch.setattr(main_app,"_resolve_access_payload",lambda kind,key,request:(payload,{"id":1}))
    monkeypatch.setattr(main_app,"get_protocol_client",lambda client_id:{"subscription_id":"abc","protocol":"vless"})
    monkeypatch.setattr(main_app,"get_setting",lambda key,default=None: default)
    response=main_app.access_share("xray","1",_request("/api/access/xray/1/share"))
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store, private"
    body=json.loads(response.body)
    assert body["share_text"].startswith("vless://")
    assert body["qr"].startswith("data:image/svg+xml;base64,")
    assert body["subscription_qr"].startswith("data:image/svg+xml;base64,")
    assert body["connection"]["protocol"]=="vless"
    assert body["connection"]["host"]=="example.test"
    assert body["connection"]["port"]==443


def test_ssh_share_respects_disabled_npv(monkeypatch):
    monkeypatch.setattr(main_app,"require_user",lambda request:"admin")
    monkeypatch.setattr(main_app,"operator_settings_snapshot",lambda:{
        "delivery":{"npv_enabled":False}
    })
    with pytest.raises(HTTPException) as exc:
        main_app.access_share("ssh","user001",_request("/api/access/ssh/user001/share"))
    assert exc.value.status_code==409


def test_operator_settings_persist_and_validate(monkeypatch):
    store={}
    monkeypatch.setattr(main_app,"require_mutation",lambda request:"admin")
    monkeypatch.setattr(main_app,"set_setting",lambda key,value:store.__setitem__(str(key),str(value)))
    monkeypatch.setattr(main_app,"get_setting",lambda key,default=None:store.get(str(key),default))
    monkeypatch.setattr(main_app,"audit",lambda *args,**kwargs:None)
    payload=main_app.OperatorSettings(
        session_max_age_minutes=180,
        profile_prefix="Makia Test",
        npv_enabled=True,
        npv_dns_mode="UDP",
        npv_udpgw_port=7300,
        npv_transparent_dns=False,
        show_qr=True,
        ssh_password_mode="pin6",
        ssh_expire_days=30,
        ssh_sessions=2,
        ssh_devices=1,
        xray_protocol="vless",
        xray_port=2087,
        xray_transport="xhttp",
        xray_security="reality",
        xray_path="/makia",
        xray_sni="www.microsoft.com",
        xray_reality_target="www.microsoft.com:443",
        xray_quota_gb=50,
        xray_expire_days=30,
        xray_ip_limit=1,
        xray_reset_days=30,
        wireguard_dns="1.1.1.1",
        wireguard_port=443,
        wireguard_mtu=1280,
        wireguard_keepalive=15,
        wireguard_allowed_ips="0.0.0.0/0",
        wireguard_cidr="10.66.66.1/24",
        openvpn_port=1194,
        openvpn_proto="udp",
        subscription_enabled=True,
        subscription_client_page_enabled=True,
        subscription_default_format="raw",
    )
    result=main_app.operator_settings_put(payload,_request("/api/settings/operator"))
    assert result["session_max_age_minutes"]==180
    assert result["delivery"]["profile_prefix"]=="Makia Test"
    assert result["defaults"]["ssh_sessions"]==2
    assert result["defaults"]["xray_transport"]=="xhttp"
    assert result["defaults"]["wireguard_port"]==443
    assert result["defaults"]["wireguard_mtu"]==1280
    assert result["defaults"]["wireguard_keepalive"]==15
    assert result["defaults"]["wireguard_allowed_ips"]=="0.0.0.0/0"
    assert result["subscription"]["enabled"] is True
    assert result["subscription"]["client_page_enabled"] is True
    assert result["subscription"]["default_format"]=="raw"


def test_legacy_ssh_share_upgrade_generates_npvt_link(monkeypatch):
    payload={
        "primary_text":"legacy",
        "summary":{"host":"vpn.example.test","port":22,"username":"user001"},
        "files":{"credentials.txt":b"Makia SSH Access\nPassword: 123456\n"},
    }
    monkeypatch.setattr(main_app,"require_user",lambda request:"admin")
    monkeypatch.setattr(main_app,"operator_settings_snapshot",lambda:{
        "delivery":{"npv_enabled":True,"profile_prefix":"Makia","npv_dns_mode":"UDP","npv_udpgw_port":7300,"npv_transparent_dns":False,"show_qr":True},
        "subscription":{"enabled":True,"client_page_enabled":True,"default_format":"base64"},
        "defaults":{},
    })
    monkeypatch.setattr(main_app,"_resolve_access_payload",lambda kind,key,request:(payload,{"id":1}))
    monkeypatch.setattr(main_app,"artifact_save",lambda *args,**kwargs:1)
    monkeypatch.setattr(main_app,"public_origin",lambda request:"http://testserver")
    response=main_app.access_share("ssh","user001",_request("/api/access/ssh/user001/share"))
    body=json.loads(response.body)
    assert body["share_text"].startswith("npvt-ssh://")
    assert body["share_type"]=="npvt-ssh"


def test_subscription_can_be_disabled(monkeypatch):
    monkeypatch.setattr(main_app,"operator_settings_snapshot",lambda:{
        "subscription":{"enabled":False,"client_page_enabled":True,"default_format":"base64"}
    })
    with pytest.raises(HTTPException) as exc:
        main_app.subscription_get("unused")
    assert exc.value.status_code==404


def test_protected_ssh_package_uses_current_npv_setting(monkeypatch):
    from app import access_ops
    original=access_ops.ssh_payload(
        "vpn.example.test","user001","123456",22,
        {"enabled":True,"remarks":"Old","dns_mode":"UDP","udpgw_port":7300,"transparent_dns":False},
    )
    monkeypatch.setattr(main_app,"require_mutation",lambda request:"admin")
    monkeypatch.setattr(main_app,"require_local_admin",lambda request:"admin")
    monkeypatch.setattr(main_app,"require_access_kind",lambda request,kind,mutation=False:"admin")
    monkeypatch.setattr(main_app,"assert_license_feature",lambda feature:None)
    monkeypatch.setattr(main_app,"_resolve_access_payload",lambda kind,key,request:(original,{"id":1}))
    monkeypatch.setattr(main_app,"operator_settings_snapshot",lambda:{
        "delivery":{"npv_enabled":False,"profile_prefix":"Makia","npv_dns_mode":"UDP","npv_udpgw_port":7300,"npv_transparent_dns":False,"show_qr":True},
        "subscription":{"enabled":True,"client_page_enabled":True,"default_format":"base64"},
        "defaults":{},
    })
    monkeypatch.setattr(main_app,"audit",lambda *args,**kwargs:None)
    response=main_app.access_package("ssh","user001",main_app.AccessPackageRequest(password="739251"),_request("/api/access/ssh/user001/package"))
    import io, pyzipper
    with pyzipper.AESZipFile(io.BytesIO(response.body),"r") as zf:
        zf.setpassword(b"739251")
        names=zf.namelist()
        assert "credentials.txt" in names
        assert all("npvt" not in name for name in names)


def test_openvpn_delivery_preserves_selected_client_endpoint(monkeypatch):
    original={
        "primary_text":"client\nproto udp\nremote 192.0.2.10 1194\n",
        "native_filename":"client01.ovpn",
        "files":{"client01.ovpn":b"client\nproto udp\nremote 192.0.2.10 1194\n"},
        "summary":{"name":"client01","protocol":"openvpn"},
    }
    monkeypatch.setattr(main_app,"public_host",lambda request:"vpn.example.test")
    monkeypatch.setattr(main_app.protocol_ops,"render_openvpn_client",lambda *args:(_ for _ in ()).throw(AssertionError("chosen endpoint must not be overwritten")))
    refreshed=main_app._current_delivery_payload("openvpn","client01",original,_request("/api/access/openvpn/client01/native"))
    assert refreshed["primary_text"]==original["primary_text"]
    assert refreshed["files"]["client01.ovpn"]==original["files"]["client01.ovpn"]
