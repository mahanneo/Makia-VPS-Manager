import json
from types import SimpleNamespace

import pytest

from app import access_ops, db, main as main_app


class DummyRequest:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client=SimpleNamespace(host=host)
        self.headers=headers or {}


def test_write_api_scopes_are_explicit_static_contract():
    source=open(main_app.__file__,encoding="utf-8").read()
    for scope in (
        "xray:provision","outline:provision","wireguard:provision",
        "openvpn:provision","protocols:write","credentials:read",
    ):
        assert f'"{scope}"' in source
    assert "MAKIA_WRITE_API_ALLOWED_CIDRS" in source
    assert "Idempotency-Key" in source


def test_write_api_allowlist_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("MAKIA_WRITE_API_ALLOWED_CIDRS",raising=False)
    monkeypatch.setattr(main_app,"require_api_scope",lambda request,scope:{"id":7,"name":"mahinet","scopes":[scope]})
    request=DummyRequest("127.0.0.1")
    identity=main_app.require_write_api_scope(request,"xray:provision")
    assert identity["id"]==7


def test_write_api_allowlist_rejects_non_allowlisted_peer(monkeypatch):
    monkeypatch.setenv("MAKIA_WRITE_API_ALLOWED_CIDRS","10.10.0.0/16")
    monkeypatch.setattr(main_app,"require_api_scope",lambda request,scope:{"id":7,"name":"mahinet","scopes":[scope]})
    monkeypatch.setattr(main_app,"audit",lambda *a,**k:None)
    with pytest.raises(Exception) as exc:
        main_app.require_write_api_scope(DummyRequest("203.0.113.9"),"xray:provision")
    assert getattr(exc.value,"status_code",None)==403


def test_forwarded_for_only_trusted_from_loopback_proxy():
    proxied=DummyRequest("127.0.0.1",{"x-forwarded-for":"198.51.100.8, 127.0.0.1"})
    assert str(main_app._write_api_client_ip(proxied))=="198.51.100.8"
    direct=DummyRequest("198.51.100.7",{"x-forwarded-for":"10.0.0.1"})
    assert str(main_app._write_api_client_ip(direct))=="198.51.100.7"


def test_idempotency_ledger_round_trip(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","A-Strong-Temporary-Password-123!")
    db.init_db()
    created=db.create_api_token("mahinet",["xray:provision"])
    assert db.idempotency_claim(created["id"],"xray:provision","order-10001","abc123")
    assert not db.idempotency_claim(created["id"],"xray:provision","order-10001","abc123")
    row=db.idempotency_get(created["id"],"xray:provision","order-10001")
    assert row["status"]=="pending"
    encrypted=access_ops.seal_payload({"response":{"ok":True,"client_id":44}})
    db.idempotency_complete(created["id"],"xray:provision","order-10001",encrypted)
    row=db.idempotency_get(created["id"],"xray:provision","order-10001")
    assert row["status"]=="complete"
    assert access_ops.open_payload(row["response_enc"])["response"]["client_id"]==44


def test_idempotent_write_replays_without_second_callback(monkeypatch):
    store={}
    monkeypatch.setattr(main_app,"idempotency_get",lambda token_id,operation,key:store.get((token_id,operation,key)))
    def claim(token_id,operation,key,request_hash):
        store[(token_id,operation,key)]={"token_id":token_id,"operation":operation,"idempotency_key":key,"request_hash":request_hash,"status":"pending","response_enc":""}
        return True
    monkeypatch.setattr(main_app,"idempotency_claim",claim)
    def complete(token_id,operation,key,response_enc):
        store[(token_id,operation,key)].update({"status":"complete","response_enc":response_enc})
    monkeypatch.setattr(main_app,"idempotency_complete",complete)
    monkeypatch.setattr(main_app,"idempotency_fail",lambda *a,**k:None)
    req=DummyRequest("127.0.0.1",{"idempotency-key":"order-12345678"})
    identity={"id":9,"name":"mahinet"}
    calls={"n":0}
    def callback():
        calls["n"]+=1
        return {"ok":True,"credential":"secret-value"}
    first=main_app._idempotent_write(req,identity,"xray:provision",{"name":"u1"},callback)
    second=main_app._idempotent_write(req,identity,"xray:provision",{"name":"u1"},callback)
    assert first==second
    assert calls["n"]==1


def test_idempotent_write_rejects_key_reuse_with_different_payload(monkeypatch):
    body=json.dumps({"name":"u1"},sort_keys=True,separators=(",",":"),ensure_ascii=False)
    request_hash=main_app.hashlib.sha256(body.encode("utf-8")).hexdigest()
    monkeypatch.setattr(main_app,"idempotency_get",lambda *a,**k:{
        "request_hash":request_hash,"status":"complete",
        "response_enc":access_ops.seal_payload({"response":{"ok":True}}),
    })
    req=DummyRequest("127.0.0.1",{"idempotency-key":"order-12345678"})
    with pytest.raises(Exception) as exc:
        main_app._idempotent_write(req,{"id":9},"xray:provision",{"name":"u2"},lambda:{"ok":True})
    assert getattr(exc.value,"status_code",None)==409
