import base64
import hashlib
import secrets
import time
from datetime import datetime, timezone

from .db import connect, get_access_artifact
from .security import hash_password, verify_password
from . import access_ops


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _token_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def init_client_db():
    """Additive-only schema for the end-user client plane.

    These tables do not alter protocol_clients, account_profiles, admins, or
    any live protocol runtime state.
    """
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS client_accounts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              display_name TEXT NOT NULL DEFAULT '',
              plan_name TEXT NOT NULL DEFAULT '',
              enabled INTEGER NOT NULL DEFAULT 1,
              expire_at INTEGER NOT NULL DEFAULT 0,
              quota_bytes INTEGER NOT NULL DEFAULT 0,
              device_limit INTEGER NOT NULL DEFAULT 1,
              concurrent_device_limit INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_client_accounts_enabled
              ON client_accounts(enabled);

            CREATE TABLE IF NOT EXISTS client_devices (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              account_id INTEGER NOT NULL,
              device_key_hash TEXT UNIQUE NOT NULL,
              device_key_last4 TEXT NOT NULL,
              label TEXT NOT NULL DEFAULT '',
              platform TEXT NOT NULL DEFAULT 'web',
              user_agent_hash TEXT NOT NULL DEFAULT '',
              active INTEGER NOT NULL DEFAULT 1,
              registered_at TEXT NOT NULL,
              last_seen_at TEXT,
              last_ip TEXT NOT NULL DEFAULT '',
              revoked_at TEXT,
              FOREIGN KEY(account_id) REFERENCES client_accounts(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_devices_account
              ON client_devices(account_id,active);

            CREATE TABLE IF NOT EXISTS client_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              account_id INTEGER NOT NULL,
              device_id INTEGER NOT NULL,
              token_hash TEXT UNIQUE NOT NULL,
              expires_at INTEGER NOT NULL,
              revoked_at INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              last_seen_at TEXT,
              last_ip TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(device_id) REFERENCES client_devices(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_sessions_account
              ON client_sessions(account_id,revoked_at,expires_at);
            CREATE INDEX IF NOT EXISTS idx_client_sessions_device
              ON client_sessions(device_id,revoked_at,expires_at);

            CREATE TABLE IF NOT EXISTS client_protocol_bindings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              account_id INTEGER NOT NULL,
              protocol_client_id INTEGER NOT NULL,
              label TEXT NOT NULL DEFAULT '',
              priority INTEGER NOT NULL DEFAULT 100,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              UNIQUE(account_id,protocol_client_id),
              UNIQUE(protocol_client_id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(protocol_client_id) REFERENCES protocol_clients(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_protocol_bindings_account
              ON client_protocol_bindings(account_id,enabled,priority);

            CREATE TABLE IF NOT EXISTS client_artifact_bindings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              account_id INTEGER NOT NULL,
              artifact_id INTEGER NOT NULL UNIQUE,
              label TEXT NOT NULL DEFAULT '',
              priority INTEGER NOT NULL DEFAULT 100,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(artifact_id) REFERENCES access_artifacts(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_artifact_bindings_account
              ON client_artifact_bindings(account_id,enabled,priority);

            CREATE TABLE IF NOT EXISTS client_usage_baselines (
              account_id INTEGER NOT NULL,
              protocol_client_id INTEGER NOT NULL,
              baseline_bytes INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(account_id,protocol_client_id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(protocol_client_id) REFERENCES protocol_clients(id)
            );

            CREATE TABLE IF NOT EXISTS client_artifact_usage (
              account_id INTEGER NOT NULL,
              artifact_id INTEGER NOT NULL,
              used_bytes INTEGER NOT NULL DEFAULT 0,
              last_counter INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(account_id,artifact_id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(artifact_id) REFERENCES access_artifacts(id)
            );

            CREATE TABLE IF NOT EXISTS client_artifact_policy_state (
              account_id INTEGER NOT NULL,
              artifact_id INTEGER NOT NULL,
              suspended_reason TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL,
              PRIMARY KEY(account_id,artifact_id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(artifact_id) REFERENCES access_artifacts(id)
            );

            CREATE TABLE IF NOT EXISTS client_browser_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id INTEGER NOT NULL,
              account_id INTEGER NOT NULL,
              device_id INTEGER NOT NULL,
              token_hash TEXT UNIQUE NOT NULL,
              token_last4 TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              revoked_at INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              last_used_at TEXT,
              last_ip TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(session_id) REFERENCES client_sessions(id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(device_id) REFERENCES client_devices(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_browser_tokens_account
              ON client_browser_tokens(account_id,revoked_at,expires_at);
            CREATE INDEX IF NOT EXISTS idx_client_browser_tokens_session
              ON client_browser_tokens(session_id,revoked_at,expires_at);

            CREATE TABLE IF NOT EXISTS client_browser_usage (
              account_id INTEGER PRIMARY KEY,
              used_bytes INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(account_id) REFERENCES client_accounts(id)
            );
            """
        )


def create_account(
    username,
    password,
    display_name="",
    plan_name="",
    expire_at=0,
    quota_bytes=0,
    device_limit=1,
    concurrent_device_limit=1,
    enabled=True,
):
    username=str(username or "").strip()
    if len(username)<3 or len(username)>64:
        raise ValueError("username must be between 3 and 64 characters")
    if len(str(password or ""))<8:
        raise ValueError("password must be at least 8 characters")
    ts=now_iso()
    with connect() as con:
        cur=con.execute(
            """INSERT INTO client_accounts(
                 username,password_hash,display_name,plan_name,enabled,expire_at,
                 quota_bytes,device_limit,concurrent_device_limit,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                username,hash_password(str(password)),str(display_name or "")[:120],
                str(plan_name or "")[:120],1 if enabled else 0,max(0,int(expire_at or 0)),
                max(0,int(quota_bytes or 0)),max(1,int(device_limit or 1)),
                max(1,int(concurrent_device_limit or 1)),ts,ts,
            ),
        )
        return int(cur.lastrowid)


def get_account(account_id):
    with connect() as con:
        row=con.execute(
            """SELECT id,username,display_name,plan_name,enabled,expire_at,quota_bytes,
                      device_limit,concurrent_device_limit,created_at,updated_at
               FROM client_accounts WHERE id=?""",
            (int(account_id),),
        ).fetchone()
        return dict(row) if row else None


def account_by_username(username, include_password=False):
    columns="*" if include_password else (
        "id,username,display_name,plan_name,enabled,expire_at,quota_bytes,"
        "device_limit,concurrent_device_limit,created_at,updated_at"
    )
    with connect() as con:
        row=con.execute(
            f"SELECT {columns} FROM client_accounts WHERE username=?",
            (str(username or "").strip(),),
        ).fetchone()
        return dict(row) if row else None


def verify_account_password(username,password):
    row=account_by_username(username,include_password=True)
    if not row or not row.get("enabled"):
        return None
    if not verify_password(str(password or ""),row.get("password_hash") or ""):
        return None
    row.pop("password_hash",None)
    return row


def account_available(account, now_ts=None):
    if not account or not account.get("enabled"):
        return False,"disabled"
    now_ts=int(now_ts or time.time())
    expire_at=int(account.get("expire_at") or 0)
    if expire_at and expire_at<=now_ts:
        return False,"expired"
    account_id=int(account.get("id") or account.get("account_id") or 0)
    if not account_id:
        return False,"invalid"
    used=account_usage_bytes(account_id)
    quota=int(account.get("quota_bytes") or 0)
    if quota and used>=quota:
        return False,"quota"
    return True,"ok"


def account_usage_bytes(account_id):
    account_id=int(account_id)
    with connect() as con:
        row=con.execute(
            """SELECT COALESCE(SUM(
                    MAX(0,(pc.used_up_bytes + pc.used_down_bytes)-COALESCE(u.baseline_bytes,0))
                 ),0) AS used
               FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               LEFT JOIN client_usage_baselines u
                 ON u.account_id=b.account_id AND u.protocol_client_id=b.protocol_client_id
               WHERE b.account_id=? AND b.enabled=1""",
            (account_id,),
        ).fetchone()
        artifact=con.execute(
            """SELECT COALESCE(SUM(u.used_bytes),0) AS used
               FROM client_artifact_bindings b
               JOIN client_artifact_usage u
                 ON u.account_id=b.account_id AND u.artifact_id=b.artifact_id
               WHERE b.account_id=? AND b.enabled=1""",
            (account_id,),
        ).fetchone()
        browser=con.execute(
            "SELECT COALESCE(used_bytes,0) AS used FROM client_browser_usage WHERE account_id=?",
            (account_id,),
        ).fetchone()
        return int(row["used"] or 0)+int(artifact["used"] or 0)+int(browser["used"] or 0 if browser else 0)


def _active_devices_count(con,account_id):
    row=con.execute(
        "SELECT COUNT(*) AS n FROM client_devices WHERE account_id=? AND active=1",
        (int(account_id),),
    ).fetchone()
    return int(row["n"] or 0)


def register_or_get_device(account_id,device_key=None,label="",platform="web",user_agent="",ip=""):
    """Return (device, plaintext_device_key_or_None).

    Browser device binding is an opaque secret cookie. Native agents can later
    replace this with a hardware-backed asymmetric device key without changing
    the account/binding model.
    """
    account=get_account(account_id)
    if not account:
        raise ValueError("account not found")
    raw=str(device_key or "").strip()
    ts=now_iso()
    ua_hash=_token_hash(user_agent or "") if user_agent else ""
    with connect() as con:
        if raw:
            row=con.execute(
                """SELECT * FROM client_devices
                   WHERE account_id=? AND device_key_hash=? AND active=1""",
                (int(account_id),_token_hash(raw)),
            ).fetchone()
            if row:
                con.execute(
                    "UPDATE client_devices SET last_seen_at=?,last_ip=?,user_agent_hash=? WHERE id=?",
                    (ts,str(ip or "")[:96],ua_hash,row["id"]),
                )
                return dict(row),None
        if _active_devices_count(con,account_id)>=int(account.get("device_limit") or 1):
            raise PermissionError("device limit reached")
        raw="md_"+secrets.token_urlsafe(32)
        cur=con.execute(
            """INSERT INTO client_devices(
                 account_id,device_key_hash,device_key_last4,label,platform,user_agent_hash,
                 active,registered_at,last_seen_at,last_ip
               ) VALUES(?,?,?,?,?,?,1,?,?,?)""",
            (
                int(account_id),_token_hash(raw),raw[-4:],str(label or "")[:120],
                str(platform or "web")[:32],ua_hash,ts,ts,str(ip or "")[:96],
            ),
        )
        row=con.execute("SELECT * FROM client_devices WHERE id=?",(cur.lastrowid,)).fetchone()
        return dict(row),raw


def device_for_key(account_id,device_key):
    if not device_key:
        return None
    with connect() as con:
        row=con.execute(
            """SELECT * FROM client_devices
               WHERE account_id=? AND device_key_hash=? AND active=1""",
            (int(account_id),_token_hash(device_key)),
        ).fetchone()
        return dict(row) if row else None


def create_session(account_id,device_id,ip="",ttl_seconds=43200):
    account=get_account(account_id)
    ok,reason=account_available(account)
    if not ok:
        raise PermissionError(reason)
    now_ts=int(time.time())
    ttl=max(300,min(int(ttl_seconds or 43200),30*86400))
    with connect() as con:
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE expires_at<=? AND revoked_at=0",
            (now_ts,now_ts),
        )
        active=con.execute(
            """SELECT COUNT(DISTINCT device_id) AS n FROM client_sessions
               WHERE account_id=? AND revoked_at=0 AND expires_at>?""",
            (int(account_id),now_ts),
        ).fetchone()
        device_has=con.execute(
            """SELECT 1 FROM client_sessions
               WHERE account_id=? AND device_id=? AND revoked_at=0 AND expires_at>? LIMIT 1""",
            (int(account_id),int(device_id),now_ts),
        ).fetchone()
        limit=int(account.get("concurrent_device_limit") or 1)
        if not device_has and int(active["n"] or 0)>=limit:
            raise PermissionError("concurrent device limit reached")
        token="ms_"+secrets.token_urlsafe(40)
        con.execute(
            """INSERT INTO client_sessions(
                 account_id,device_id,token_hash,expires_at,revoked_at,created_at,last_seen_at,last_ip
               ) VALUES(?,?,?,?,0,?,?,?)""",
            (int(account_id),int(device_id),_token_hash(token),now_ts+ttl,now_iso(),now_iso(),str(ip or "")[:96]),
        )
        return token,now_ts+ttl


def session_by_token(token,ip=""):
    if not token:
        return None
    now_ts=int(time.time())
    with connect() as con:
        row=con.execute(
            """SELECT s.id AS session_id,s.account_id,s.device_id,s.expires_at,
                      a.username,a.display_name,a.plan_name,a.enabled,a.expire_at,a.quota_bytes,
                      a.device_limit,a.concurrent_device_limit,d.label AS device_label,d.platform
               FROM client_sessions s
               JOIN client_accounts a ON a.id=s.account_id
               JOIN client_devices d ON d.id=s.device_id
               WHERE s.token_hash=? AND s.revoked_at=0 AND s.expires_at>?
                 AND a.enabled=1 AND d.active=1""",
            (_token_hash(token),now_ts),
        ).fetchone()
        if not row:
            return None
        account=dict(row)
        ok,_=account_available(account,now_ts)
        if not ok:
            con.execute("UPDATE client_sessions SET revoked_at=? WHERE id=?",(now_ts,row["session_id"]))
            return None
        con.execute(
            "UPDATE client_sessions SET last_seen_at=?,last_ip=? WHERE id=?",
            (now_iso(),str(ip or "")[:96],row["session_id"]),
        )
        return account


def revoke_session(token):
    if not token:
        return
    now_ts=int(time.time())
    with connect() as con:
        row=con.execute(
            "SELECT id FROM client_sessions WHERE token_hash=?",
            (_token_hash(token),),
        ).fetchone()
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at=0",
            (now_ts,_token_hash(token)),
        )
        if row:
            con.execute(
                "UPDATE client_browser_tokens SET revoked_at=? WHERE session_id=? AND revoked_at=0",
                (now_ts,int(row["id"])),
            )


def list_devices(account_id):
    with connect() as con:
        rows=con.execute(
            """SELECT id,label,platform,device_key_last4,active,registered_at,last_seen_at,last_ip,revoked_at
               FROM client_devices WHERE account_id=? ORDER BY id DESC""",
            (int(account_id),),
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_device(account_id,device_id):
    now_ts=int(time.time())
    ts=now_iso()
    with connect() as con:
        con.execute(
            "UPDATE client_devices SET active=0,revoked_at=? WHERE id=? AND account_id=?",
            (ts,int(device_id),int(account_id)),
        )
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE device_id=? AND account_id=? AND revoked_at=0",
            (now_ts,int(device_id),int(account_id)),
        )
        con.execute(
            "UPDATE client_browser_tokens SET revoked_at=? WHERE device_id=? AND account_id=? AND revoked_at=0",
            (now_ts,int(device_id),int(account_id)),
        )


def bind_protocol_client(account_id,protocol_client_id,label="",priority=100,enabled=True):
    ts=now_iso()
    with connect() as con:
        exists=con.execute("SELECT id FROM protocol_clients WHERE id=?",(int(protocol_client_id),)).fetchone()
        if not exists:
            raise ValueError("protocol client not found")
        bound=con.execute(
            "SELECT account_id FROM client_protocol_bindings WHERE protocol_client_id=?",
            (int(protocol_client_id),),
        ).fetchone()
        if bound and int(bound["account_id"])!=int(account_id):
            raise ValueError("protocol client is already bound to another client account")
        con.execute(
            """INSERT INTO client_protocol_bindings(account_id,protocol_client_id,label,priority,enabled,created_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(account_id,protocol_client_id) DO UPDATE SET
                 label=excluded.label,priority=excluded.priority,enabled=excluded.enabled""",
            (
                int(account_id),int(protocol_client_id),str(label or "")[:120],
                int(priority or 100),1 if enabled else 0,ts,
            ),
        )
        current=con.execute(
            "SELECT used_up_bytes+used_down_bytes AS used FROM protocol_clients WHERE id=?",
            (int(protocol_client_id),),
        ).fetchone()
        con.execute(
            """INSERT OR IGNORE INTO client_usage_baselines(account_id,protocol_client_id,baseline_bytes,updated_at)
               VALUES(?,?,?,?)""",
            (int(account_id),int(protocol_client_id),int(current["used"] or 0),ts),
        )


def list_protocols(account_id, include_secrets=False):
    with connect() as con:
        rows=con.execute(
            """SELECT b.id AS binding_id,b.label,b.priority,b.enabled AS binding_enabled,
                      pc.id AS protocol_client_id,pc.name,pc.engine,pc.protocol,pc.inbound_tag,
                      pc.share_link,pc.quota_bytes,pc.used_up_bytes,pc.used_down_bytes,
                      pc.expire_at,pc.ip_limit,pc.enabled,pc.disabled_reason,pc.subscription_id
               FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=? AND b.enabled=1
               ORDER BY b.priority ASC,b.id ASC""",
            (int(account_id),),
        ).fetchall()
        out=[]
        now_ts=int(time.time())
        for raw in rows:
            item=dict(raw)
            item["used_bytes"]=int(item.get("used_up_bytes") or 0)+int(item.get("used_down_bytes") or 0)
            expire=int(item.get("expire_at") or 0)
            quota=int(item.get("quota_bytes") or 0)
            item["available"]=bool(
                item.get("enabled") and
                not item.get("disabled_reason") and
                (not expire or expire>now_ts) and
                (not quota or item["used_bytes"]<quota)
            )
            if not include_secrets:
                item.pop("share_link",None)
                item.pop("subscription_id",None)
            out.append(item)
        return out


def bind_access_artifact(account_id,artifact_id,label="",priority=100,enabled=True):
    ts=now_iso()
    with connect() as con:
        artifact=con.execute(
            "SELECT id,kind,external_key,display_name,protocol FROM access_artifacts WHERE id=?",
            (int(artifact_id),),
        ).fetchone()
        if not artifact:
            raise ValueError("access artifact not found")
        existing=con.execute(
            "SELECT account_id FROM client_artifact_bindings WHERE artifact_id=?",
            (int(artifact_id),),
        ).fetchone()
        if existing and int(existing["account_id"])!=int(account_id):
            raise ValueError("access artifact is already bound to another client account")
        con.execute(
            """INSERT INTO client_artifact_bindings(account_id,artifact_id,label,priority,enabled,created_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(artifact_id) DO UPDATE SET
                 label=excluded.label,priority=excluded.priority,enabled=excluded.enabled""",
            (
                int(account_id),int(artifact_id),str(label or "")[:120],
                int(priority or 100),1 if enabled else 0,ts,
            ),
        )
        con.execute(
            """INSERT OR IGNORE INTO client_artifact_usage(account_id,artifact_id,used_bytes,last_counter,updated_at)
               VALUES(?,?,0,0,?)""",
            (int(account_id),int(artifact_id),ts),
        )
        con.execute(
            """INSERT OR IGNORE INTO client_artifact_policy_state(account_id,artifact_id,suspended_reason,updated_at)
               VALUES(?,?,?,?)""",
            (int(account_id),int(artifact_id),"",ts),
        )


def list_artifact_bindings(account_id):
    with connect() as con:
        rows=con.execute(
            """SELECT b.id AS binding_id,b.label,b.priority,b.enabled AS binding_enabled,
                      a.id AS artifact_id,a.kind,a.external_key,a.display_name,a.protocol,a.native_filename
               FROM client_artifact_bindings b
               JOIN access_artifacts a ON a.id=b.artifact_id
               WHERE b.account_id=? AND b.enabled=1
               ORDER BY b.priority ASC,b.id ASC""",
            (int(account_id),),
        ).fetchall()
        return [dict(r) for r in rows]


def unbind_access_artifact(account_id,artifact_id):
    with connect() as con:
        state=con.execute(
            "SELECT suspended_reason FROM client_artifact_policy_state WHERE account_id=? AND artifact_id=?",
            (int(account_id),int(artifact_id)),
        ).fetchone()
        if state and str(state["suspended_reason"] or "").startswith("client_account_"):
            raise PermissionError("restore the Client account policy before unbinding this managed credential")
        con.execute(
            "DELETE FROM client_artifact_bindings WHERE account_id=? AND artifact_id=?",
            (int(account_id),int(artifact_id)),
        )
        con.execute(
            "DELETE FROM client_artifact_usage WHERE account_id=? AND artifact_id=?",
            (int(account_id),int(artifact_id)),
        )
        con.execute(
            "DELETE FROM client_artifact_policy_state WHERE account_id=? AND artifact_id=?",
            (int(account_id),int(artifact_id)),
        )


def artifact_delivery(account_id,artifact_id):
    allowed=None
    for item in list_artifact_bindings(account_id):
        if int(item["artifact_id"])==int(artifact_id):
            allowed=item
            break
    if not allowed:
        raise ValueError("artifact binding not found")
    artifact=get_access_artifact(artifact_id)
    if not artifact:
        raise ValueError("access artifact not found")
    payload=access_ops.open_payload(artifact["payload_enc"])
    primary=str(payload.get("share_text") or payload.get("primary_text") or "")
    if not primary:
        raise ValueError("artifact has no client-deliverable payload")
    filename=artifact.get("native_filename") or payload.get("native_filename") or ""
    files=payload.get("files") or {}
    native=files.get(filename) if filename else None
    if isinstance(native,str):
        native=native.encode("utf-8")
    native_b64=base64.b64encode(bytes(native)).decode("ascii") if isinstance(native,(bytes,bytearray)) else ""
    qr_svg=""
    kind=str(artifact.get("kind") or "").lower()
    if kind in {"wireguard","outline","xray","ssh"} and primary:
        try:
            qr_svg="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(primary)).decode("ascii")
        except Exception:
            qr_svg=""
    return {
        "id":int(artifact_id),
        "name":allowed.get("label") or artifact.get("display_name") or "",
        "engine":artifact.get("kind") or "",
        "protocol":artifact.get("protocol") or artifact.get("kind") or "",
        "share_link":primary,
        "native_filename":filename,
        "native_base64":native_b64,
        "qr":qr_svg,
        "source":"artifact",
    }


def client_access_list(account_id):
    items=[]
    for item in list_protocols(account_id,include_secrets=False):
        item=dict(item)
        item["source"]="protocol"
        item["delivery_id"]=int(item["protocol_client_id"])
        item["delivery_kind"]="protocol"
        engine=str(item.get("engine") or "").lower()
        item["accounting_supported"]=engine in {"xray","outline"}
        item["enforcement_level"]="hard" if engine in {"xray","outline"} else "delivery"
        item["enforcement_text"]="expiry + quota" if engine in {"xray","outline"} else "delivery only"
        item["account_used_bytes"]=protocol_usage_for_account(account_id,item["protocol_client_id"])
        items.append(item)
    for item in list_artifact_bindings(account_id):
        items.append({
            "binding_id":item["binding_id"],
            "label":item.get("label") or item.get("display_name") or "",
            "name":item.get("display_name") or "",
            "engine":item.get("kind") or "",
            "protocol":item.get("protocol") or item.get("kind") or "",
            "available":True,
            "source":"artifact",
            "delivery_id":int(item["artifact_id"]),
            "delivery_kind":"artifact",
            "native_filename":item.get("native_filename") or "",
            "used_bytes":0,
            "quota_bytes":0,
            "accounting_supported":str(item.get("kind") or "").lower()=="wireguard",
            "enforcement_level":"hard" if str(item.get("kind") or "").lower() in {"wireguard","ssh"} else "delivery",
            "enforcement_text":(
                "expiry + quota" if str(item.get("kind") or "").lower()=="wireguard"
                else "expiry + device/session" if str(item.get("kind") or "").lower()=="ssh"
                else "delivery only"
            ),
        })
    return sorted(items,key=lambda x:(int(x.get("priority") or 100),str(x.get("label") or x.get("name") or "")))


def protocol_delivery(account_id,protocol_client_id):
    rows=list_protocols(account_id,include_secrets=True)
    for item in rows:
        if int(item["protocol_client_id"])==int(protocol_client_id):
            if not item.get("available"):
                raise PermissionError("protocol access is not available")
            share=item.get("share_link") or ""
            qr_svg=""
            if share:
                try:
                    qr_svg="data:image/svg+xml;base64,"+base64.b64encode(access_ops.make_qr_svg(share)).decode("ascii")
                except Exception:
                    qr_svg=""
            return {
                "id":item["protocol_client_id"],
                "name":item.get("label") or item.get("name") or "",
                "engine":item.get("engine") or "",
                "protocol":item.get("protocol") or "",
                "share_link":share,
                "subscription_id":item.get("subscription_id") or "",
                "qr":qr_svg,
                "source":"protocol",
            }
    raise ValueError("protocol binding not found")


def account_snapshot(account_id):
    account=get_account(account_id)
    if not account:
        return None
    used=account_usage_bytes(account_id)
    quota=int(account.get("quota_bytes") or 0)
    account["used_bytes"]=used
    account["remaining_bytes"]=max(0,quota-used) if quota else 0
    account["quota_percent"]=round((used/quota)*100,1) if quota else 0
    ok,reason=account_available(account)
    account["available"]=ok
    account["status_reason"]=reason
    account["devices"]=list_devices(account_id)
    account["protocols"]=client_access_list(account_id)
    return account


def list_accounts():
    with connect() as con:
        rows=con.execute(
            """SELECT id,username,display_name,plan_name,enabled,expire_at,quota_bytes,
                      device_limit,concurrent_device_limit,created_at,updated_at
               FROM client_accounts ORDER BY id DESC"""
        ).fetchall()
    out=[]
    for row in rows:
        item=dict(row)
        item["used_bytes"]=account_usage_bytes(item["id"])
        with connect() as con:
            device_count=con.execute(
                "SELECT COUNT(*) AS n FROM client_devices WHERE account_id=? AND active=1",
                (item["id"],),
            ).fetchone()
            protocol_count=con.execute(
                "SELECT COUNT(*) AS n FROM client_protocol_bindings WHERE account_id=? AND enabled=1",
                (item["id"],),
            ).fetchone()
            artifact_count=con.execute(
                "SELECT COUNT(*) AS n FROM client_artifact_bindings WHERE account_id=? AND enabled=1",
                (item["id"],),
            ).fetchone()
        item["active_devices"]=int(device_count["n"] or 0)
        item["protocol_bindings"]=int(protocol_count["n"] or 0)
        item["artifact_bindings"]=int(artifact_count["n"] or 0)
        item["bindings"]=item["protocol_bindings"]+item["artifact_bindings"]
        out.append(item)
    return out


def update_account(
    account_id,
    display_name=None,
    plan_name=None,
    expire_at=None,
    quota_bytes=None,
    device_limit=None,
    concurrent_device_limit=None,
    enabled=None,
):
    account=get_account(account_id)
    if not account:
        raise ValueError("account not found")
    values={
        "display_name":account.get("display_name") or "",
        "plan_name":account.get("plan_name") or "",
        "expire_at":int(account.get("expire_at") or 0),
        "quota_bytes":int(account.get("quota_bytes") or 0),
        "device_limit":int(account.get("device_limit") or 1),
        "concurrent_device_limit":int(account.get("concurrent_device_limit") or 1),
        "enabled":1 if account.get("enabled") else 0,
    }
    if display_name is not None: values["display_name"]=str(display_name or "")[:120]
    if plan_name is not None: values["plan_name"]=str(plan_name or "")[:120]
    if expire_at is not None: values["expire_at"]=max(0,int(expire_at or 0))
    if quota_bytes is not None: values["quota_bytes"]=max(0,int(quota_bytes or 0))
    if device_limit is not None: values["device_limit"]=max(1,int(device_limit or 1))
    if concurrent_device_limit is not None: values["concurrent_device_limit"]=max(1,int(concurrent_device_limit or 1))
    if enabled is not None: values["enabled"]=1 if enabled else 0
    if values["concurrent_device_limit"]>values["device_limit"]:
        values["concurrent_device_limit"]=values["device_limit"]
    with connect() as con:
        con.execute(
            """UPDATE client_accounts
               SET display_name=?,plan_name=?,expire_at=?,quota_bytes=?,device_limit=?,
                   concurrent_device_limit=?,enabled=?,updated_at=?
               WHERE id=?""",
            (
                values["display_name"],values["plan_name"],values["expire_at"],values["quota_bytes"],
                values["device_limit"],values["concurrent_device_limit"],values["enabled"],now_iso(),
                int(account_id),
            ),
        )
        if not values["enabled"]:
            con.execute(
                "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND revoked_at=0",
                (int(time.time()),int(account_id)),
            )
    return get_account(account_id)


def set_account_password(account_id,password):
    if len(str(password or ""))<8:
        raise ValueError("password must be at least 8 characters")
    if not get_account(account_id):
        raise ValueError("account not found")
    with connect() as con:
        con.execute(
            "UPDATE client_accounts SET password_hash=?,updated_at=? WHERE id=?",
            (hash_password(str(password)),now_iso(),int(account_id)),
        )
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND revoked_at=0",
            (int(time.time()),int(account_id)),
        )


def list_bindings(account_id):
    with connect() as con:
        rows=con.execute(
            """SELECT b.id,b.account_id,b.protocol_client_id,b.label,b.priority,b.enabled,b.created_at,
                      pc.name AS protocol_name,pc.engine,pc.protocol,pc.enabled AS protocol_enabled,
                      pc.expire_at,pc.quota_bytes
               FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=? ORDER BY b.priority ASC,b.id ASC""",
            (int(account_id),),
        ).fetchall()
        return [dict(r) for r in rows]


def unbind_protocol_client(account_id,protocol_client_id):
    with connect() as con:
        row=con.execute(
            """SELECT pc.disabled_reason FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=? AND b.protocol_client_id=?""",
            (int(account_id),int(protocol_client_id)),
        ).fetchone()
        if row and str(row["disabled_reason"] or "").startswith("client_account_"):
            raise PermissionError("restore the Client account policy before unbinding this managed credential")
        con.execute(
            "DELETE FROM client_protocol_bindings WHERE account_id=? AND protocol_client_id=?",
            (int(account_id),int(protocol_client_id)),
        )
        con.execute(
            "DELETE FROM client_usage_baselines WHERE account_id=? AND protocol_client_id=?",
            (int(account_id),int(protocol_client_id)),
        )


def account_admin_snapshot(account_id):
    account=account_snapshot(account_id)
    if not account:
        return None
    account["bindings_detail"]=list_bindings(account_id)
    account["artifact_bindings_detail"]=list_artifact_bindings(account_id)
    return account


def delete_account(account_id):
    """Delete only client-plane ownership/session metadata.

    Existing protocol_clients, access_artifacts and live protocol runtime state
    are deliberately left untouched. A policy-suspended credential must first
    be restored so deletion can never strand a runtime in a disabled state.
    """
    account_id=int(account_id)
    if not get_account(account_id):
        raise ValueError("account not found")
    with connect() as con:
        protocol_hold=con.execute(
            """SELECT 1 FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=? AND pc.disabled_reason LIKE 'client_account_%' LIMIT 1""",
            (account_id,),
        ).fetchone()
        artifact_hold=con.execute(
            """SELECT 1 FROM client_artifact_policy_state
               WHERE account_id=? AND suspended_reason LIKE 'client_account_%' LIMIT 1""",
            (account_id,),
        ).fetchone()
        if protocol_hold or artifact_hold:
            raise PermissionError("restore the Client account policy before deleting this account")
        con.execute("DELETE FROM client_sessions WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_devices WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_usage_baselines WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_artifact_usage WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_artifact_policy_state WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_protocol_bindings WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_artifact_bindings WHERE account_id=?",(account_id,))
        con.execute("DELETE FROM client_accounts WHERE id=?",(account_id,))


def protocol_binding_owners():
    with connect() as con:
        rows=con.execute(
            """SELECT b.protocol_client_id,b.account_id,a.username
               FROM client_protocol_bindings b
               JOIN client_accounts a ON a.id=b.account_id"""
        ).fetchall()
        return {int(r["protocol_client_id"]):{"account_id":int(r["account_id"]),"username":r["username"]} for r in rows}


def artifact_binding_owners():
    with connect() as con:
        rows=con.execute(
            """SELECT b.artifact_id,b.account_id,a.username
               FROM client_artifact_bindings b
               JOIN client_accounts a ON a.id=b.account_id"""
        ).fetchall()
        return {int(r["artifact_id"]):{"account_id":int(r["account_id"]),"username":r["username"]} for r in rows}


def revoke_all_devices(account_id):
    account_id=int(account_id)
    now_ts=int(time.time())
    ts=now_iso()
    with connect() as con:
        con.execute(
            "UPDATE client_devices SET active=0,revoked_at=? WHERE account_id=? AND active=1",
            (ts,account_id),
        )
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND revoked_at=0",
            (now_ts,account_id),
        )


def revoke_all_sessions(account_id):
    with connect() as con:
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE account_id=? AND revoked_at=0",
            (int(time.time()),int(account_id)),
        )


def reset_account_usage(account_id):
    account_id=int(account_id)
    if not get_account(account_id):
        raise ValueError("account not found")
    ts=now_iso()
    with connect() as con:
        rows=con.execute(
            """SELECT b.protocol_client_id,pc.used_up_bytes+pc.used_down_bytes AS used
               FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=?""",
            (account_id,),
        ).fetchall()
        for row in rows:
            con.execute(
                """INSERT INTO client_usage_baselines(account_id,protocol_client_id,baseline_bytes,updated_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(account_id,protocol_client_id) DO UPDATE SET
                     baseline_bytes=excluded.baseline_bytes,updated_at=excluded.updated_at""",
                (account_id,int(row["protocol_client_id"]),int(row["used"] or 0),ts),
            )
        con.execute(
            "UPDATE client_artifact_usage SET used_bytes=0,updated_at=? WHERE account_id=?",
            (ts,account_id),
        )
    return {"ok":True,"used_bytes":0}


def add_artifact_counter_sample(account_id,artifact_id,counter):
    account_id=int(account_id); artifact_id=int(artifact_id); counter=max(0,int(counter or 0))
    ts=now_iso()
    with connect() as con:
        row=con.execute(
            "SELECT used_bytes,last_counter FROM client_artifact_usage WHERE account_id=? AND artifact_id=?",
            (account_id,artifact_id),
        ).fetchone()
        if not row:
            con.execute(
                """INSERT INTO client_artifact_usage(account_id,artifact_id,used_bytes,last_counter,updated_at)
                   VALUES(?,?,0,?,?)""",
                (account_id,artifact_id,counter,ts),
            )
            return 0
        last=max(0,int(row["last_counter"] or 0))
        previous_used=max(0,int(row["used_bytes"] or 0))
        # The first runtime sample establishes a baseline so traffic consumed
        # before the credential was bound to this Client account is not billed.
        if last==0 and previous_used==0:
            con.execute(
                """UPDATE client_artifact_usage SET last_counter=?,updated_at=?
                   WHERE account_id=? AND artifact_id=?""",
                (counter,ts,account_id,artifact_id),
            )
            return 0
        delta=counter-last if counter>=last else counter
        used=previous_used+max(0,delta)
        con.execute(
            """UPDATE client_artifact_usage SET used_bytes=?,last_counter=?,updated_at=?
               WHERE account_id=? AND artifact_id=?""",
            (used,counter,ts,account_id,artifact_id),
        )
        return used


def get_artifact_policy_state(account_id,artifact_id):
    with connect() as con:
        row=con.execute(
            "SELECT suspended_reason,updated_at FROM client_artifact_policy_state WHERE account_id=? AND artifact_id=?",
            (int(account_id),int(artifact_id)),
        ).fetchone()
        return dict(row) if row else {"suspended_reason":"","updated_at":""}


def set_artifact_policy_state(account_id,artifact_id,reason=""):
    ts=now_iso()
    with connect() as con:
        con.execute(
            """INSERT INTO client_artifact_policy_state(account_id,artifact_id,suspended_reason,updated_at)
               VALUES(?,?,?,?)
               ON CONFLICT(account_id,artifact_id) DO UPDATE SET
                 suspended_reason=excluded.suspended_reason,updated_at=excluded.updated_at""",
            (int(account_id),int(artifact_id),str(reason or ""),ts),
        )


def client_policy_reason(account,now_ts=None):
    if not account or not int(account.get("enabled") or 0):
        return "disabled"
    now_ts=int(now_ts or time.time())
    expire_at=int(account.get("expire_at") or 0)
    if expire_at and now_ts>=expire_at:
        return "expiry"
    quota=int(account.get("quota_bytes") or 0)
    if quota and account_usage_bytes(int(account["id"]))>=quota:
        return "quota"
    return ""


def protocol_usage_for_account(account_id,protocol_client_id):
    with connect() as con:
        row=con.execute(
            """SELECT pc.used_up_bytes+pc.used_down_bytes AS raw,COALESCE(u.baseline_bytes,0) AS baseline
               FROM protocol_clients pc
               LEFT JOIN client_usage_baselines u
                 ON u.protocol_client_id=pc.id AND u.account_id=?
               WHERE pc.id=?""",
            (int(account_id),int(protocol_client_id)),
        ).fetchone()
        if not row:
            return 0
        return max(0,int(row["raw"] or 0)-int(row["baseline"] or 0))


def issue_browser_proxy_token(session, ttl_seconds=1800):
    """Issue a short-lived proxy credential bound to an active Client session."""
    if not session:
        raise PermissionError("client session required")
    account_id=int(session.get("account_id") or 0)
    device_id=int(session.get("device_id") or 0)
    session_id=int(session.get("session_id") or 0)
    if not account_id or not device_id or not session_id:
        raise PermissionError("invalid client session")
    account=get_account(account_id)
    ok,reason=account_available(account)
    if not ok:
        raise PermissionError(reason)
    now_ts=int(time.time())
    ttl=max(300,min(int(ttl_seconds or 1800),12*60*60))
    token="bp_"+secrets.token_urlsafe(36)
    with connect() as con:
        con.execute(
            "UPDATE client_browser_tokens SET revoked_at=? WHERE expires_at<=? AND revoked_at=0",
            (now_ts,now_ts),
        )
        con.execute(
            """INSERT INTO client_browser_tokens(
                 session_id,account_id,device_id,token_hash,token_last4,expires_at,
                 revoked_at,created_at,last_used_at,last_ip
               ) VALUES(?,?,?,?,?,?,0,?,?,?)""",
            (
                session_id,account_id,device_id,_token_hash(token),token[-4:],
                now_ts+ttl,now_iso(),None,"",
            ),
        )
    return {
        "username":str(session.get("username") or ""),
        "password":token,
        "expires_at":now_ts+ttl,
    }


def browser_proxy_auth(username, token, ip=""):
    """Validate a Browser Gateway Basic-auth credential without exposing secrets."""
    username=str(username or "").strip()
    token=str(token or "").strip()
    if not username or not token:
        return None
    now_ts=int(time.time())
    with connect() as con:
        row=con.execute(
            """SELECT t.id AS browser_token_id,t.session_id,t.account_id,t.device_id,t.expires_at,
                      a.username,a.display_name,a.plan_name,a.enabled,a.expire_at,a.quota_bytes,
                      a.device_limit,a.concurrent_device_limit
               FROM client_browser_tokens t
               JOIN client_sessions s ON s.id=t.session_id
               JOIN client_accounts a ON a.id=t.account_id
               JOIN client_devices d ON d.id=t.device_id
               WHERE t.token_hash=? AND t.revoked_at=0 AND t.expires_at>?
                 AND s.revoked_at=0 AND s.expires_at>?
                 AND a.enabled=1 AND d.active=1 AND a.username=?""",
            (_token_hash(token),now_ts,now_ts,username),
        ).fetchone()
        if not row:
            return None
        account=dict(row)
        ok,_=account_available(account,now_ts)
        if not ok:
            con.execute(
                "UPDATE client_browser_tokens SET revoked_at=? WHERE id=?",
                (now_ts,int(row["browser_token_id"])),
            )
            return None
        con.execute(
            "UPDATE client_browser_tokens SET last_used_at=?,last_ip=? WHERE id=?",
            (now_iso(),str(ip or "")[:96],int(row["browser_token_id"])),
        )
        return account


def add_browser_usage(account_id, byte_count):
    byte_count=max(0,int(byte_count or 0))
    if not byte_count:
        return
    with connect() as con:
        con.execute(
            """INSERT INTO client_browser_usage(account_id,used_bytes,updated_at)
               VALUES(?,?,?)
               ON CONFLICT(account_id) DO UPDATE SET
                 used_bytes=client_browser_usage.used_bytes+excluded.used_bytes,
                 updated_at=excluded.updated_at""",
            (int(account_id),byte_count,now_iso()),
        )


def browser_usage_bytes(account_id):
    with connect() as con:
        row=con.execute(
            "SELECT used_bytes FROM client_browser_usage WHERE account_id=?",
            (int(account_id),),
        ).fetchone()
        return int(row["used_bytes"] or 0) if row else 0
