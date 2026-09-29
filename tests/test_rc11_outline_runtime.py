from pathlib import Path

import pytest

from app import access_ops, integration_ops, main as main_app


ROOT=Path(__file__).resolve().parents[1]


class DummyRequest:
    client=None


def test_outline_create_ui_never_relies_on_dom_id_globals():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "const nameEl=document.getElementById('olName')" in js
    assert "const quotaEl=document.getElementById('olQuota')" in js
    assert "const daysEl=document.getElementById('olDays')" in js
    assert "name:olName.value" not in js
    assert "olName.value.trim()" not in js


def test_xray_workspaces_request_only_xray_engine_clients():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert js.count("api('/api/protocol-clients?engine=xray')") >= 2
    assert "managed=clients.filter(x=>String(x.engine||'xray').toLowerCase()==='xray')" in js


def test_protocol_client_api_engine_filter_excludes_outline(monkeypatch):
    monkeypatch.setattr(main_app,"require_capability",lambda *a,**k:{"username":"admin"})
    monkeypatch.setattr(main_app,"list_protocol_clients",lambda:[
        {
            "id":1,"engine":"xray","name":"xray01","protocol":"vless","enabled":0,
            "quota_bytes":0,"expire_at":0,"ip_limit":1,"used_up_bytes":0,"used_down_bytes":0,
        },
        {
            "id":2,"engine":"outline","name":"outline01","protocol":"outline","enabled":1,
            "quota_bytes":0,"expire_at":0,"ip_limit":1,"used_up_bytes":0,"used_down_bytes":0,
        },
    ])
    rows=main_app.protocol_clients_get(DummyRequest(),engine="xray")
    assert [row["engine"] for row in rows]==["xray"]
    with pytest.raises(Exception):
        main_app.protocol_clients_get(DummyRequest(),engine="wireguard")


def test_outline_create_uses_stable_manager_api_flow(monkeypatch):
    calls=[]
    def fake(path,method="GET",body=None):
        calls.append((path,method,body))
        if path=="/access-keys" and method=="POST":
            return {"id":"17","accessUrl":"ss://YWVzLTI1Ni1nY206c2VjcmV0@example.com:443/?outline=1"}
        if path=="/access-keys/17/name" and method=="PUT":
            return {}
        if path=="/access-keys/17/data-limit" and method=="PUT":
            return {}
        raise AssertionError((path,method,body))
    monkeypatch.setattr(integration_ops,"_outline_request",fake)
    result=integration_ops.outline_create_key("phone01",5*1024**3)
    assert result["id"]=="17"
    assert result["accessUrl"].startswith("ss://")
    assert calls==[
        ("/access-keys","POST",None),
        ("/access-keys/17/name","PUT",{"name":"phone01"}),
        ("/access-keys/17/data-limit","PUT",{"limit":{"bytes":5*1024**3}}),
    ]


def test_outline_create_rolls_back_partial_key(monkeypatch):
    calls=[]
    def fake(path,method="GET",body=None):
        calls.append((path,method,body))
        if path=="/access-keys" and method=="POST":
            return {"id":"18","accessUrl":"ss://YWVzLTI1Ni1nY206c2VjcmV0@example.com:443/?outline=1"}
        if path=="/access-keys/18/name" and method=="PUT":
            raise integration_ops.IntegrationError("rename failed")
        if path=="/access-keys/18" and method=="DELETE":
            return {}
        raise AssertionError((path,method,body))
    monkeypatch.setattr(integration_ops,"_outline_request",fake)
    with pytest.raises(integration_ops.IntegrationError,match="rename failed"):
        integration_ops.outline_create_key("phone02",0)
    assert ("/access-keys/18","DELETE",None) in calls


def test_outline_delivery_contract_is_importable_and_qr_ready():
    key="ss://YWVzLTI1Ni1nY206c2VjcmV0@example.com:443/?outline=1"
    payload=access_ops.outline_payload("phone01",key,"17",10*1024**3)
    assert payload["share_text"]==key
    assert payload["primary_text"]==key
    assert payload["native_filename"].endswith("-outline.txt")
    assert any(name.endswith("-outline-qr.svg") for name in payload["files"])
    assert main_app._portal_one_tap("outline",key,"/download")==key


def test_outline_access_rows_remain_outline_not_xray_static_contract():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    assert "rows=accessRows.filter(x=>x.kind==='xray')" in js
    assert 'if engine_filter and str(item.get("engine") or "").lower()!=engine_filter:' in main
    assert '"kind":kind' in main
