import os, time
from app import db

def test_remote_support_code_is_one_time_and_revocable(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","StrongInitialPass!123")
    db.init_db()
    grant=db.create_support_grant("admin",minutes=30,scope="operator")
    assert grant["code"].startswith("SUP-")
    first=db.consume_support_grant(grant["code"].lower())
    assert first and first["scope"]=="operator"
    assert db.consume_support_grant(grant["code"]) is None
    state=db.support_grant_by_id(grant["id"])
    assert state["active"] is True
    db.revoke_support_grant(grant["id"])
    assert db.support_grant_by_id(grant["id"])["active"] is False

def test_new_support_grant_revokes_previous_active_grant(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"makia.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","StrongInitialPass!123")
    db.init_db()
    one=db.create_support_grant("admin",30,"readonly")
    two=db.create_support_grant("admin",30,"operator")
    rows=db.list_support_grants()
    first=next(x for x in rows if x["id"]==one["id"])
    second=next(x for x in rows if x["id"]==two["id"])
    assert first["active"] is False
    assert second["active"] is True


def _request(path,method="POST"):
    from starlette.requests import Request
    scope={
        "type":"http","method":method,"path":path,
        "headers":[(b"x-makia-request",b"1")],
        "query_string":b"","scheme":"https",
        "server":("panel.example.test",443),"client":("203.0.113.9",12345),
    }
    return Request(scope)

def test_remote_operator_mutation_allowlist(monkeypatch):
    from fastapi import HTTPException
    from app import main as main_app
    monkeypatch.setattr(main_app,"require_user",lambda request:"support:7:operator")
    assert main_app.require_mutation(_request("/api/protocols/xray/repair"))=="support:7:operator"
    assert main_app.require_mutation(_request("/api/protocols/wireguard/repair"))=="support:7:operator"
    assert main_app.require_mutation(_request("/api/protocols/openvpn/repair"))=="support:7:operator"
    assert main_app.require_mutation(_request("/api/services/xray/restart"))=="support:7:operator"
    assert main_app.require_mutation(_request("/api/support/requests"))=="support:7:operator"
    for blocked in [
        "/api/accounts",
        "/api/settings/general",
        "/api/license/activate",
        "/api/backups",
        "/api/access/ssh/user001/package",
    ]:
        try:
            main_app.require_mutation(_request(blocked))
        except HTTPException as exc:
            assert exc.status_code==403
        else:
            raise AssertionError(f"remote operator unexpectedly allowed: {blocked}")

def test_remote_readonly_blocks_all_mutations(monkeypatch):
    from fastapi import HTTPException
    from app import main as main_app
    monkeypatch.setattr(main_app,"require_user",lambda request:"support:9:readonly")
    try:
        main_app.require_mutation(_request("/api/protocols/xray/repair"))
    except HTTPException as exc:
        assert exc.status_code==403
        assert "read-only" in str(exc.detail)
    else:
        raise AssertionError("read-only support mutation must fail")
