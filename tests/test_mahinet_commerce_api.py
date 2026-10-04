from types import SimpleNamespace

import pytest

from app import db, main as main_app


class DummyRequest:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client=SimpleNamespace(host=host)
        self.headers=headers or {}
        self.state=SimpleNamespace()


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","A-Strong-Temporary-Password-123!")
    db.init_db()


def _payload(name="buyer-1"):
    return main_app.CommerceProvisionRequest(
        external_id="order-10001",
        name=name,
        profile="xray:test-inbound",
        quota_gb=10,
        expire_days=30,
        ip_limit=1,
        attributes={"endpoint":"vpn.example.test"},
    )


def test_commerce_scopes_and_safe_default_are_explicit():
    source=open(main_app.__file__,encoding="utf-8").read()
    assert '"commerce:provision"' in source
    assert '"commerce:service"' in source
    assert "MAKIA_COMMERCE_ALLOWED_CIDRS" in source
    assert '"127.0.0.1/32,::1/128"' in source
    assert "valid Idempotency-Key header required" in source


def test_commerce_allowlist_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("MAKIA_COMMERCE_ALLOWED_CIDRS",raising=False)
    monkeypatch.setattr(
        main_app,"require_api_scope",
        lambda request,scope:{"id":7,"name":"mahinet","scopes":[scope]},
    )
    identity=main_app._commerce_require(DummyRequest("127.0.0.1"),"commerce:provision")
    assert identity["id"]==7


def test_commerce_allowlist_rejects_remote_source(monkeypatch):
    monkeypatch.delenv("MAKIA_COMMERCE_ALLOWED_CIDRS",raising=False)
    monkeypatch.setattr(
        main_app,"require_api_scope",
        lambda request,scope:{"id":7,"name":"mahinet","scopes":[scope]},
    )
    monkeypatch.setattr(main_app,"audit",lambda *args,**kwargs:None)
    with pytest.raises(Exception) as exc:
        main_app._commerce_require(DummyRequest("203.0.113.7"),"commerce:provision")
    assert getattr(exc.value,"status_code",None)==403


def test_forwarded_source_is_only_trusted_from_loopback_proxy():
    proxied=DummyRequest(
        "127.0.0.1",
        {"x-forwarded-for":"198.51.100.8, 127.0.0.1"},
    )
    assert main_app._commerce_source_ip(proxied)=="198.51.100.8"

    direct=DummyRequest(
        "198.51.100.7",
        {"x-forwarded-for":"10.0.0.1"},
    )
    assert main_app._commerce_source_ip(direct)=="198.51.100.7"


def test_commerce_idempotency_is_atomic_encrypted_and_replayable(tmp_path,monkeypatch):
    _init_temp_db(tmp_path,monkeypatch)
    monkeypatch.setattr(main_app.access_ops,"ensure_secret",lambda:b"commerce-test-secret")
    identity={"id":9,"name":"mahinet","scopes":["commerce:provision"]}
    payload=_payload()

    first=DummyRequest(headers={"idempotency-key":"order-10001"})
    key,req_hash,cached=main_app._commerce_idempotency(
        first,identity,"provision",payload
    )
    assert key=="order-10001"
    assert req_hash
    assert cached is None

    second=DummyRequest(headers={"idempotency-key":"order-10001"})
    with pytest.raises(Exception) as exc:
        main_app._commerce_idempotency(second,identity,"provision",payload)
    assert getattr(exc.value,"status_code",None)==409

    response={"ok":True,"credential":"super-secret-config"}
    main_app._commerce_idempotency_store(first,response)

    with db.connect() as con:
        row=con.execute(
            "SELECT status,response_enc FROM commerce_idempotency "
            "WHERE token_id=? AND route=? AND idempotency_key=?",
            (9,"provision","order-10001"),
        ).fetchone()
    assert row["status"]=="complete"
    assert row["response_enc"]
    assert "super-secret-config" not in row["response_enc"]

    replay=DummyRequest(headers={"idempotency-key":"order-10001"})
    _,_,cached=main_app._commerce_idempotency(replay,identity,"provision",payload)
    assert cached==response


def test_commerce_idempotency_rejects_key_reuse_with_changed_payload(tmp_path,monkeypatch):
    _init_temp_db(tmp_path,monkeypatch)
    monkeypatch.setattr(main_app.access_ops,"ensure_secret",lambda:b"commerce-test-secret")
    identity={"id":11,"name":"mahinet","scopes":["commerce:provision"]}

    request=DummyRequest(headers={"idempotency-key":"order-20002"})
    main_app._commerce_idempotency(request,identity,"provision",_payload("buyer-1"))
    main_app._commerce_idempotency_store(request,{"ok":True})

    reused=DummyRequest(headers={"idempotency-key":"order-20002"})
    with pytest.raises(Exception) as exc:
        main_app._commerce_idempotency(
            reused,identity,"provision",_payload("buyer-2")
        )
    assert getattr(exc.value,"status_code",None)==409


def test_failed_claim_is_not_replayed_as_success(tmp_path,monkeypatch):
    _init_temp_db(tmp_path,monkeypatch)
    identity={"id":13,"name":"mahinet","scopes":["commerce:service"]}
    request=DummyRequest(headers={"idempotency-key":"action-30003"})
    payload=main_app.CommerceServiceActionRequest(
        external_id="order-30003",
        provision_ref="xray:1",
        action="renew",
        days=30,
    )

    main_app._commerce_idempotency(request,identity,"service-action",payload)
    main_app._commerce_idempotency_fail(request)

    retry=DummyRequest(headers={"idempotency-key":"action-30003"})
    with pytest.raises(Exception) as exc:
        main_app._commerce_idempotency(retry,identity,"service-action",payload)
    assert getattr(exc.value,"status_code",None)==409
