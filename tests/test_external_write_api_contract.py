from pathlib import Path
import ast

import pytest

from app import external_write_api


def test_write_scopes_are_explicit_and_no_wildcard():
    assert "*" not in external_write_api.WRITE_SCOPES
    assert external_write_api.WRITE_SCOPES == {
        "provision:xray",
        "provision:wireguard",
        "provision:openvpn",
        "provision:outline",
        "provision:lifecycle",
    }


def test_cidr_normalization_rejects_invalid_values():
    assert external_write_api.normalize_cidrs(["127.0.0.1/32", "10.20.30.40"]) == [
        "127.0.0.1/32",
        "10.20.30.40/32",
    ]
    with pytest.raises(ValueError):
        external_write_api.normalize_cidrs(["not-an-ip"])


def test_write_api_has_no_shell_execution_primitives():
    source = Path("app/external_write_api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert "subprocess" not in imported
    assert "pty" not in imported
    assert "shlex" not in imported
    assert "os.system(" not in source
    assert "Popen(" not in source


def test_mutating_routes_require_idempotency_wrapper():
    source = Path("app/external_write_api.py").read_text(encoding="utf-8")
    for route in (
        "/api/v1/provision/xray",
        "/api/v1/provision/wireguard",
        "/api/v1/provision/openvpn",
        "/api/v1/provision/outline",
        "/api/v1/provision/lifecycle",
    ):
        assert route in source
    assert source.count("_run_idempotent(request,identity,payload") >= 5
    assert "X-Idempotency-Key" in source or "x-idempotency-key" in source
