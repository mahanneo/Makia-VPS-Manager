import base64
import time
import urllib.parse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import access_ops, client_portal, db, security
from app.security import hash_password


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("MAKIA_CLIENT_APP_ENABLED", "1")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD", "AgentPhaseBAdminPass!123")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "agent-phase-b.db")
    monkeypatch.setattr(security, "SECRET_PATH", tmp_path / ".secret")
    db.init_db()
    ts = db.now()
    db.upsert_profile(
        "alice",
        plan="Agent Test",
        expire_date="2099-12-31",
        connection_limit=1,
        device_limit=1,
        quota_mb=20480,
        enabled=1,
    )
    with db.connect() as con:
        account_id = con.execute(
            """INSERT INTO client_accounts
               (username,password_hash,display_name,profile_username,active,created_at,updated_at)
               VALUES(?,?,?,?,1,?,?)""",
            ("alice", hash_password("AgentClientPass!123"), "Alice", "alice", ts, ts),
        ).lastrowid
        device_id = con.execute(
            """INSERT INTO client_devices
               (account_id,device_hash,label,platform,first_seen_at,last_seen_at,last_ip,active)
               VALUES(?,?,?,?,?,?,?,1)""",
            (account_id, "browser-device-hash", "Windows", "Windows", ts, ts, "192.0.2.10"),
        ).lastrowid
        session_token = "mkc_agent_phase_b_session"
        con.execute(
            """INSERT INTO client_sessions
               (account_id,device_id,token_hash,created_at,last_seen_at,expires_at,revoked_at,ip,user_agent)
               VALUES(?,?,?,?,?,?,0,?,?)""",
            (
                account_id,
                device_id,
                client_portal._token_hash(session_token),
                ts,
                ts,
                int(time.time()) + 3600,
                "192.0.2.10",
                "PhaseBTest",
            ),
        )
        payload = access_ops.wireguard_payload(
            "alice-wg",
            "[Interface]\nPrivateKey = test-private\nAddress = 10.66.66.9/32\n\n[Peer]\nPublicKey = test-public\nEndpoint = vpn.example.test:51820\n",
            "10.66.66.9/32",
        )
        con.execute(
            """INSERT INTO access_artifacts
               (kind,external_key,display_name,protocol,native_filename,payload_enc,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                "wireguard",
                "wg-alice",
                "Alice WireGuard",
                "wireguard",
                payload["native_filename"],
                access_ops.seal_payload(payload),
                "{}",
                ts,
                ts,
            ),
        )
        binding_id = con.execute(
            """INSERT INTO client_access_bindings(account_id,kind,external_key,active,created_at)
               VALUES(?,?,?,1,?)""",
            (account_id, "wireguard", "wg-alice", ts),
        ).lastrowid
    app = FastAPI()
    app.include_router(client_portal.router)
    client = TestClient(app)
    client.cookies.set(client_portal.CLIENT_SESSION_COOKIE, session_token, path="/client-app")
    return client, account_id, device_id, binding_id


def _pair_agent(client, private_key):
    response = client.post("/client-app/api/agent/pairing-grant")
    assert response.status_code == 200, response.text
    deep = urllib.parse.urlsplit(response.json()["deep_link"])
    params = urllib.parse.parse_qs(deep.query)
    token = params["token"][0]
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    paired = client.post(
        "/api/client-agent/pair",
        json={
            "pairing_token": token,
            "public_key": _b64url(public_raw),
            "agent_version": "0.1.0-test",
            "platform": "windows-amd64",
        },
    )
    assert paired.status_code == 200, paired.text
    assert paired.json()["key_type"] == "ed25519"
    return token


def test_agent_pairing_token_is_one_time_and_public_key_is_bound(tmp_path, monkeypatch):
    client, account_id, device_id, _ = _setup(tmp_path, monkeypatch)
    private = Ed25519PrivateKey.generate()
    pairing_token = _pair_agent(client, private)

    with db.connect() as con:
        device = con.execute(
            "SELECT public_key,agent_version,agent_platform,agent_paired_at FROM client_devices WHERE id=?",
            (device_id,),
        ).fetchone()
        grant = con.execute(
            "SELECT token_hash,used_at FROM client_agent_pairing_grants WHERE device_id=?",
            (device_id,),
        ).fetchone()
    assert device["public_key"]
    assert device["agent_version"] == "0.1.0-test"
    assert device["agent_platform"] == "windows-amd64"
    assert device["agent_paired_at"]
    assert grant["token_hash"] != pairing_token
    assert grant["used_at"] > 0

    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    replay = client.post(
        "/api/client-agent/pair",
        json={
            "pairing_token": pairing_token,
            "public_key": _b64url(public_raw),
            "agent_version": "0.1.0-test",
            "platform": "windows-amd64",
        },
    )
    assert replay.status_code == 410


def test_signed_connect_grant_is_device_bound_and_single_use(tmp_path, monkeypatch):
    client, _, device_id, binding_id = _setup(tmp_path, monkeypatch)
    private = Ed25519PrivateKey.generate()
    _pair_agent(client, private)

    grant_response = client.post(f"/client-app/api/access/{binding_id}/grant")
    assert grant_response.status_code == 200, grant_response.text
    deep = urllib.parse.urlsplit(grant_response.json()["deep_link"])
    params = urllib.parse.parse_qs(deep.query)
    grant = params["grant"][0]

    nonce = "nonce-phase-b-001"
    timestamp = int(time.time())
    signature = private.sign(client_portal._agent_signature_message(grant, nonce, timestamp))
    redeem = client.post(
        "/api/client-agent/redeem",
        json={
            "grant": grant,
            "nonce": nonce,
            "timestamp": timestamp,
            "signature": _b64url(signature),
        },
    )
    assert redeem.status_code == 200, redeem.text
    body = redeem.json()
    assert body["grant"]["one_time"] is True
    assert body["access"]["kind"] == "wireguard"
    assert body["access"]["protocol"] == "wireguard"
    assert body["access"]["native_filename"].endswith(".conf")
    native = base64.b64decode(body["access"]["native_content_b64"]).decode("utf-8")
    assert "PrivateKey = test-private" in native
    assert "Endpoint = vpn.example.test:51820" in native

    replay = client.post(
        "/api/client-agent/redeem",
        json={
            "grant": grant,
            "nonce": "nonce-phase-b-002",
            "timestamp": int(time.time()),
            "signature": _b64url(
                private.sign(
                    client_portal._agent_signature_message(
                        grant, "nonce-phase-b-002", int(time.time())
                    )
                )
            ),
        },
    )
    assert replay.status_code == 410

    with db.connect() as con:
        row = con.execute(
            "SELECT redeemed_at,device_id FROM client_agent_action_grants WHERE binding_id=?",
            (binding_id,),
        ).fetchone()
    assert row["redeemed_at"] > 0
    assert row["device_id"] == device_id


def test_wrong_device_key_cannot_redeem_connect_grant(tmp_path, monkeypatch):
    client, _, _, binding_id = _setup(tmp_path, monkeypatch)
    private = Ed25519PrivateKey.generate()
    _pair_agent(client, private)
    grant_response = client.post(f"/client-app/api/access/{binding_id}/grant")
    deep = urllib.parse.urlsplit(grant_response.json()["deep_link"])
    grant = urllib.parse.parse_qs(deep.query)["grant"][0]

    attacker = Ed25519PrivateKey.generate()
    nonce = "attacker-nonce-001"
    timestamp = int(time.time())
    response = client.post(
        "/api/client-agent/redeem",
        json={
            "grant": grant,
            "nonce": nonce,
            "timestamp": timestamp,
            "signature": _b64url(
                attacker.sign(client_portal._agent_signature_message(grant, nonce, timestamp))
            ),
        },
    )
    assert response.status_code == 403


def test_phase_b_grants_store_hashes_not_raw_tokens(tmp_path, monkeypatch):
    client, _, device_id, binding_id = _setup(tmp_path, monkeypatch)
    private = Ed25519PrivateKey.generate()
    pairing_token = _pair_agent(client, private)
    grant_response = client.post(f"/client-app/api/access/{binding_id}/grant")
    grant = urllib.parse.parse_qs(
        urllib.parse.urlsplit(grant_response.json()["deep_link"]).query
    )["grant"][0]
    with db.connect() as con:
        pairing = con.execute(
            "SELECT token_hash FROM client_agent_pairing_grants WHERE device_id=?",
            (device_id,),
        ).fetchone()
        action = con.execute(
            "SELECT token_hash FROM client_agent_action_grants WHERE binding_id=?",
            (binding_id,),
        ).fetchone()
    assert pairing["token_hash"] == client_portal._token_hash(pairing_token)
    assert action["token_hash"] == client_portal._token_hash(grant)
    assert pairing["token_hash"] != pairing_token
    assert action["token_hash"] != grant


def test_connect_grant_requires_paired_device(tmp_path, monkeypatch):
    client, _, _, binding_id = _setup(tmp_path, monkeypatch)
    response = client.post(f"/client-app/api/access/{binding_id}/grant")
    assert response.status_code == 409
    assert "not paired" in response.json()["detail"].lower()


def test_phase_b_refuses_non_wireguard_native_grants(tmp_path, monkeypatch):
    client, account_id, _, _ = _setup(tmp_path, monkeypatch)
    private = Ed25519PrivateKey.generate()
    _pair_agent(client, private)
    ts = db.now()
    with db.connect() as con:
        payload = access_ops.xray_payload(
            "alice-xray",
            "vless",
            "vless://example-credential@example.test:443?type=tcp&security=none#alice-xray",
        )
        con.execute(
            """INSERT INTO access_artifacts
               (kind,external_key,display_name,protocol,native_filename,payload_enc,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                "xray",
                "xray-alice",
                "Alice Xray",
                "vless",
                payload["native_filename"],
                access_ops.seal_payload(payload),
                "{}",
                ts,
                ts,
            ),
        )
        binding_id = con.execute(
            """INSERT INTO client_access_bindings(account_id,kind,external_key,active,created_at)
               VALUES(?,?,?,1,?)""",
            (account_id, "xray", "xray-alice", ts),
        ).lastrowid
    response = client.post(f"/client-app/api/access/{binding_id}/grant")
    assert response.status_code == 409
    assert "adapter" in response.json()["detail"].lower()
