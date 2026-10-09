"""Transactional SSH provisioning guards (no real host accounts created)."""
import pytest
from fastapi import HTTPException

from app import main as main_app
from app import system_ops


class Request:
    client = None


@pytest.fixture
def provision(monkeypatch):
    events = []
    payload = main_app.AccountCreate(
        username="newtester", password="not-a-real-password", endpoint="212.100.171.183", endpoint_mode="ip"
    )
    monkeypatch.setattr(main_app, "require_mutation", lambda request: "admin")
    monkeypatch.setattr(main_app.protocol_ops, "validate_endpoint_selection", lambda host, mode, **opts: host)
    monkeypatch.setattr(main_app, "get_profile", lambda username: None)
    monkeypatch.setattr(main_app, "get_access_artifact_by_key", lambda kind, key: None)
    monkeypatch.setattr(main_app, "ssh_npv_options", lambda username: {})
    monkeypatch.setattr(main_app.system_ops, "create_ssh_user", lambda *args: events.append("create"))
    monkeypatch.setattr(main_app, "upsert_profile", lambda *args: events.append("profile"))
    monkeypatch.setattr(main_app.access_ops, "ssh_payload", lambda *args: {"config": "dummy"})
    monkeypatch.setattr(main_app, "artifact_save", lambda *args: events.append("artifact") or 71)
    monkeypatch.setattr(main_app, "audit", lambda *args: events.append("audit:" + args[1]))
    monkeypatch.setattr(main_app, "delete_access_artifact_by_key", lambda *args: events.append("revoke-artifact"))
    monkeypatch.setattr(main_app, "delete_profile", lambda username: events.append("delete-profile"))
    monkeypatch.setattr(main_app.system_ops, "delete_user", lambda username: events.append("delete-os-user"))
    return payload, events


def test_successful_ssh_provision(provision):
    payload, events = provision
    result = main_app.create_account(payload, Request())
    assert result["ok"] and result["artifact_id"] == 71
    assert events == ["create", "profile", "artifact", "audit:account_create"]


@pytest.mark.parametrize("failing_stage", ["profile", "delivery", "artifact", "audit"])
def test_failure_after_host_user_creation_rolls_back_all_new_state(monkeypatch, provision, failing_stage):
    payload, events = provision
    def fail(*args):
        events.append(failing_stage + ":failure")
        raise RuntimeError("intentional test failure")
    if failing_stage == "profile":
        monkeypatch.setattr(main_app, "upsert_profile", fail)
    elif failing_stage == "delivery":
        monkeypatch.setattr(main_app.access_ops, "ssh_payload", fail)
    elif failing_stage == "artifact":
        monkeypatch.setattr(main_app, "artifact_save", fail)
    else:
        old = main_app.audit
        def fail_audit(*args):
            if args[1] == "account_create":
                fail()
            else:
                old(*args)
        monkeypatch.setattr(main_app, "audit", fail_audit)
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 500
    assert events[-4:] == ["revoke-artifact", "delete-profile", "delete-os-user", "audit:account_create_failed"]
    assert events.index("revoke-artifact") < events.index("delete-os-user")


def test_existing_profile_causes_conflict_without_host_mutation(monkeypatch, provision):
    payload, events = provision
    monkeypatch.setattr(main_app, "get_profile", lambda username: {"username": username})
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 409
    assert events == []


def test_existing_artifact_causes_conflict_without_host_mutation(monkeypatch, provision):
    payload, events = provision
    monkeypatch.setattr(main_app, "get_access_artifact_by_key", lambda kind, key: {"id": 12})
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 409
    assert events == []


def test_useradd_failure_does_not_destroy_existing_linux_account(monkeypatch, provision):
    payload, events = provision
    def failed_useradd(*args):
        raise system_ops.OperationError("user already exists")
    monkeypatch.setattr(main_app.system_ops, "create_ssh_user", failed_useradd)
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 400
    assert events == []


def test_cleanup_failure_is_reported_not_masked_as_success(monkeypatch, provision):
    payload, events = provision
    def failed_artifact(*args):
        raise RuntimeError("test artifact failure")
    def failed_delete(*args):
        events.append("delete-os-user-error")
        raise system_ops.OperationError("permission denied")
    monkeypatch.setattr(main_app, "artifact_save", failed_artifact)
    monkeypatch.setattr(main_app.system_ops, "delete_user", failed_delete)
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 500
    assert "incomplete" in exc.value.detail
    assert "delete-os-user-error" in events
    assert "audit:account_create_failed" in events

def test_unrecoverable_chpasswd_cleanup_reports_manual_reconciliation(monkeypatch, provision):
    payload, events = provision
    def initial_failure(*args):
        raise system_ops.ProvisionRollbackError("new Linux account remains")
    monkeypatch.setattr(main_app.system_ops, "create_ssh_user", initial_failure)
    with pytest.raises(HTTPException) as exc:
        main_app.create_account(payload, Request())
    assert exc.value.status_code == 500
    assert "new Linux account remains" in exc.value.detail
    assert events == ["audit:account_create_failed"]


@pytest.mark.parametrize("userdel_fails", [False, True])
def test_chpasswd_failure_removes_new_os_account_or_reports_orphan(monkeypatch, userdel_fails):
    calls = []
    def fake_run(argv, input_text=None, timeout=15):
        calls.append(argv[0])
        if argv[0] == "chpasswd":
            raise system_ops.OperationError("password update failed")
        if argv[0] == "userdel" and userdel_fails:
            raise system_ops.OperationError("cleanup refused")
        return ""
    monkeypatch.setattr(system_ops, "_run", fake_run)
    expected = system_ops.ProvisionRollbackError if userdel_fails else system_ops.OperationError
    with pytest.raises(expected):
        system_ops.create_ssh_user("freshuser", "secure1234")
    assert calls == ["useradd", "chpasswd", "userdel"]
