import time

from app import client_portal, db
from app.security import hash_password


def _setup_db(tmp_path, monkeypatch):
    path = tmp_path / "client-control-plane.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD", "ClientPortalAdminPass!123")
    db.init_db()
    return path


def test_client_app_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MAKIA_CLIENT_APP_ENABLED", raising=False)
    assert client_portal._enabled() is False
    monkeypatch.setenv("MAKIA_CLIENT_APP_ENABLED", "1")
    assert client_portal._enabled() is True


def test_client_control_plane_schema_is_additive(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    with db.connect() as con:
        tables = {
            row["name"]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {
        "client_accounts",
        "client_devices",
        "client_sessions",
        "client_access_bindings",
    }.issubset(tables)
    # Existing runtime/control-plane tables must remain intact.
    assert {"protocol_clients", "account_profiles", "access_artifacts", "admins"}.issubset(tables)


def test_effective_client_policy_reuses_existing_account_profile(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    db.upsert_profile(
        "alice",
        plan="Pro 30",
        expire_date="2099-12-31",
        connection_limit=2,
        device_limit=3,
        quota_mb=102400,
        enabled=1,
    )
    account = {
        "id": 1,
        "username": "alice",
        "display_name": "Alice",
        "profile_username": "alice",
        "active": 1,
    }
    policy = client_portal._effective_policy(account)
    assert policy["enabled"] is True
    assert policy["expired"] is False
    assert policy["device_limit"] == 3
    assert policy["session_limit"] == 2
    assert policy["quota_mb"] == 102400
    assert policy["plan"] == "Pro 30"


def test_client_session_is_server_revocable_and_device_scoped(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    ts = db.now()
    with db.connect() as con:
        cur = con.execute(
            """INSERT INTO client_accounts
               (username,password_hash,display_name,profile_username,active,created_at,updated_at)
               VALUES(?,?,?,?,1,?,?)""",
            ("alice", hash_password("StrongClientPass!123"), "Alice", "alice", ts, ts),
        )
        account_id = int(cur.lastrowid)
        dev = con.execute(
            """INSERT INTO client_devices
               (account_id,device_hash,label,platform,first_seen_at,last_seen_at,last_ip,active)
               VALUES(?,?,?,?,?,?,?,1)""",
            (account_id, "devicehash", "Windows", "Windows", ts, ts, "192.0.2.10"),
        )
        device_id = int(dev.lastrowid)
        token = "mkc_test_session_token"
        con.execute(
            """INSERT INTO client_sessions
               (account_id,device_id,token_hash,created_at,last_seen_at,expires_at,revoked_at,ip,user_agent)
               VALUES(?,?,?,?,?,?,0,?,?)""",
            (
                account_id,
                device_id,
                client_portal._token_hash(token),
                ts,
                ts,
                int(time.time()) + 3600,
                "192.0.2.10",
                "test",
            ),
        )
        row = con.execute(
            "SELECT token_hash,account_id,device_id,revoked_at FROM client_sessions"
        ).fetchone()
    assert row["token_hash"] != token
    assert row["account_id"] == account_id
    assert row["device_id"] == device_id
    assert row["revoked_at"] == 0


def test_client_binding_references_existing_artifact_without_copying_secret(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    ts = db.now()
    with db.connect() as con:
        account_id = con.execute(
            """INSERT INTO client_accounts
               (username,password_hash,display_name,profile_username,active,created_at,updated_at)
               VALUES(?,?,?,?,1,?,?)""",
            ("bob", hash_password("StrongClientPass!456"), "Bob", "bob", ts, ts),
        ).lastrowid
        con.execute(
            """INSERT INTO access_artifacts
               (kind,external_key,display_name,protocol,native_filename,payload_enc,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            ("wireguard", "wg-bob", "Bob WireGuard", "wireguard", "bob.conf", "encrypted-secret-payload", "{}", ts, ts),
        )
        con.execute(
            """INSERT INTO client_access_bindings(account_id,kind,external_key,active,created_at)
               VALUES(?,?,?,?,?)""",
            (account_id, "wireguard", "wg-bob", 1, ts),
        )
    bindings = client_portal._list_bindings(account_id)
    assert len(bindings) == 1
    assert bindings[0]["kind"] == "wireguard"
    assert bindings[0]["display_name"] == "Bob WireGuard"
    assert "payload_enc" not in bindings[0]
    assert "credential" not in bindings[0]


def test_phase_a_has_no_protocol_runtime_mutation_paths():
    source = (client_portal.BASE_DIR / "app" / "client_portal.py").read_text(encoding="utf-8")
    assert "protocol_ops" not in source
    assert "network_services" not in source
    assert "systemctl" not in source
    assert "wg " not in source
    assert "openvpn" in source  # catalog/binding kind only
    assert "subprocess" not in source


def test_client_pwa_assets_and_feature_flag_contract():
    base = client_portal.BASE_DIR
    assert (base / "app/templates/client_app_login.html").is_file()
    assert (base / "app/templates/client_app.html").is_file()
    assert (base / "app/static/client-app.css").is_file()
    assert (base / "app/static/client-app.js").is_file()
    assert (base / "app/static/client-app-sw.js").is_file()
    env = (base / ".env.example").read_text(encoding="utf-8")
    assert "MAKIA_CLIENT_APP_ENABLED=0" in env
    main = (base / "app/main.py").read_text(encoding="utf-8")
    assert 'request.url.path.startswith("/client-app")' in main
