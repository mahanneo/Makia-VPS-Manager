import asyncio
import os

import pytest

from app import browser_gateway, browser_gateway_store, client_store, db


def _fresh_client_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "makia-test.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD", "BrowserGatewayTest-Admin-Only-123!")
    db.init_db()
    client_store.init_client_db()


def test_gateway_proxy_session_lifecycle_and_usage(tmp_path, monkeypatch):
    _fresh_client_db(tmp_path, monkeypatch)
    account_id=client_store.create_account(
        "browser-user",
        "BrowserUserPassword-123!",
        quota_bytes=1024*1024,
        device_limit=2,
        concurrent_device_limit=2,
    )
    device,device_key=client_store.register_or_get_device(
        account_id,
        None,
        label="Chrome / Makia",
        platform="browser-extension",
        user_agent="pytest",
        ip="203.0.113.20",
    )
    token,_=client_store.create_session(account_id,device["id"],"203.0.113.20",3600)
    session=client_store.session_by_token(token,"203.0.113.20")
    assert session

    issued=browser_gateway_store.issue(session,900)
    assert issued["username"].startswith("mbg_")
    assert issued["password"]
    assert 0 < issued["ttl"] <= 900

    validated=browser_gateway_store.validate(
        issued["username"],issued["password"],"203.0.113.20"
    )
    assert validated
    assert int(validated["account_id"])==account_id
    assert browser_gateway_store.validate(issued["username"],"wrong","203.0.113.20") is None

    assert browser_gateway_store.add_usage(validated["id"],123,456)
    assert client_store.account_usage_bytes(account_id)==579

    client_store.revoke_session(token)
    assert browser_gateway_store.validate(
        issued["username"],issued["password"],"203.0.113.20"
    ) is None


def test_gateway_private_targets_are_blocked():
    with pytest.raises(browser_gateway.ProxyError,match="private/reserved"):
        asyncio.run(browser_gateway._resolve_public("127.0.0.1",443))
    with pytest.raises(browser_gateway.ProxyError,match="private/reserved"):
        asyncio.run(browser_gateway._resolve_public("10.0.0.1",443))


def test_gateway_connect_ports_are_restricted():
    with pytest.raises(browser_gateway.ProxyError,match="not allowed"):
        asyncio.run(browser_gateway._open_public("1.1.1.1",22))


def test_http_proxy_rewrite_removes_proxy_credentials():
    headers=[
        ("Host","example.com"),
        ("Proxy-Authorization","Basic secret"),
        ("Proxy-Connection","keep-alive"),
        ("User-Agent","MakiaTest"),
    ]
    host,port,payload=browser_gateway._rewrite_http_request(
        "GET","http://example.com/path?q=1","HTTP/1.1",headers
    )
    text=payload.decode("latin1")
    assert host=="example.com"
    assert port==80
    assert text.startswith("GET /path?q=1 HTTP/1.1\r\n")
    assert "Proxy-Authorization" not in text
    assert "Proxy-Connection" not in text
    assert "Connection: close" in text


def test_basic_proxy_auth_parser():
    import base64
    value="Basic "+base64.b64encode(b"user:pass").decode("ascii")
    assert browser_gateway._parse_basic(value)==("user","pass")
    assert browser_gateway._parse_basic("Basic not-base64")== (None,None)


def test_gateway_config_requires_https_certificate_files(tmp_path,monkeypatch):
    monkeypatch.setenv("MAKIA_BROWSER_GATEWAY_ENABLED","1")
    monkeypatch.setenv("MAKIA_BROWSER_GATEWAY_HOST","vpn.example.com")
    monkeypatch.setenv("MAKIA_BROWSER_GATEWAY_CERT",str(tmp_path/"missing.crt"))
    monkeypatch.setenv("MAKIA_BROWSER_GATEWAY_KEY",str(tmp_path/"missing.key"))
    cfg=browser_gateway.gateway_config()
    with pytest.raises(browser_gateway.ProxyError,match="certificate missing"):
        browser_gateway.validate_config(cfg,require_files=True)
