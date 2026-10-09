import importlib
from fastapi import HTTPException
import pytest


def test_read_only_endpoint_preview_checks_auth_before_validation(monkeypatch):
    module=importlib.import_module("app.main")
    calls=[]
    monkeypatch.setattr(module,"require_user",lambda request:calls.append("authorized"))
    result=module.endpoint_preflight_get(None,"wireguard","212.100.171.183",51820,"")
    assert calls==["authorized"]
    assert result["ok"] is True and result["mode"]=="ip"
    assert result["read_only"] is True
    assert result["live_runtime_validated"] is False


def test_read_only_endpoint_preview_rejects_tls_over_plain_ip(monkeypatch):
    module=importlib.import_module("app.main")
    monkeypatch.setattr(module,"require_user",lambda request:"admin")
    result=module.endpoint_preflight_get(None,"browser-gateway","212.100.171.183",9444,"")
    assert not result["ok"]
    assert any("TLS" in error for error in result["errors"])


def test_endpoint_preview_invalid_input_is_400(monkeypatch):
    module=importlib.import_module("app.main")
    monkeypatch.setattr(module,"require_user",lambda request:"admin")
    with pytest.raises(HTTPException) as exc:
        module.endpoint_preflight_get(None,"ssh","https://wrong.example.com:443",22,"")
    assert exc.value.status_code==400
