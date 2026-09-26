import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import main as panel


def _request(path):
    return Request({"type":"http","method":"POST","path":path,"headers":[],"query_string":b"","scheme":"http","server":("testserver",80),"client":("127.0.0.1",12345)})


@pytest.mark.parametrize("kind,endpoint,mode",[
    ("ssh","vpn.example.com","ip"),
    ("xray","8.8.8.8","domain"),
    ("wireguard","10.0.0.1","ip"),
    ("openvpn","8.8.8.8","domain"),
])
def test_each_protocol_rejects_wrong_endpoint_type_before_provisioning(monkeypatch,kind,endpoint,mode):
    monkeypatch.setattr(panel,"require_feature",lambda *args:"admin")
    monkeypatch.setattr(panel,"require_mutation",lambda *args:"admin")
    monkeypatch.setattr(panel,"list_protocol_clients",lambda:[])
    def must_not_provision(*args,**kwargs):
        raise AssertionError("provisioning must not start with an invalid endpoint")
    monkeypatch.setattr(panel.system_ops,"create_ssh_user",must_not_provision)
    monkeypatch.setattr(panel.protocol_ops,"create_xray_inbound",must_not_provision)
    monkeypatch.setattr(panel.protocol_ops,"create_wireguard_peer",must_not_provision)
    monkeypatch.setattr(panel.protocol_ops,"create_openvpn_client",must_not_provision)
    if kind=="ssh":
        invoke=lambda:panel.create_account(panel.AccountCreate(username="user001",password="123456",endpoint=endpoint,endpoint_mode=mode),_request("/api/accounts"))
    elif kind=="xray":
        invoke=lambda:panel.xray_quick_inbound(panel.XrayQuickInbound(protocol="vless",port=443,name="client01",endpoint=endpoint,endpoint_mode=mode),_request("/api/protocols/xray/quick-inbound"))
    elif kind=="wireguard":
        invoke=lambda:panel.wireguard_peer_create(panel.WireGuardPeer(name="client01",endpoint=endpoint,endpoint_mode=mode),_request("/api/protocols/wireguard/peers"))
    else:
        invoke=lambda:panel.openvpn_client_create(panel.OpenVPNClient(name="client01",endpoint=endpoint,endpoint_mode=mode),_request("/api/protocols/openvpn/clients"))
    with pytest.raises(HTTPException) as error:
        invoke()
    assert error.value.status_code==400
