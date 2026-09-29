import hashlib
import secrets
import time
from datetime import datetime, timezone

from .db import connect
from .security import hash_password, verify_password


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
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(protocol_client_id) REFERENCES protocol_clients(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_protocol_bindings_account
              ON client_protocol_bindings(account_id,enabled,priority);
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
    used=account_usage_bytes(int(account["id"]))
    quota=int(account.get("quota_bytes") or 0)
    if quota and used>=quota:
        return False,"quota"
    return True,"ok"


def account_usage_bytes(account_id):
    with connect() as con:
        row=con.execute(
            """SELECT COALESCE(SUM(pc.used_up_bytes + pc.used_down_bytes),0) AS used
               FROM client_protocol_bindings b
               JOIN protocol_clients pc ON pc.id=b.protocol_client_id
               WHERE b.account_id=? AND b.enabled=1""",
            (int(account_id),),
        ).fetchone()
        return int(row["used"] or 0) if row else 0


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
    with connect() as con:
        con.execute(
            "UPDATE client_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at=0",
            (int(time.time()),_token_hash(token)),
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


def bind_protocol_client(account_id,protocol_client_id,label="",priority=100,enabled=True):
    ts=now_iso()
    with connect() as con:
        exists=con.execute("SELECT id FROM protocol_clients WHERE id=?",(int(protocol_client_id),)).fetchone()
        if not exists:
            raise ValueError("protocol client not found")
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


def protocol_delivery(account_id,protocol_client_id):
    rows=list_protocols(account_id,include_secrets=True)
    for item in rows:
        if int(item["protocol_client_id"])==int(protocol_client_id):
            if not item.get("available"):
                raise PermissionError("protocol access is not available")
            return {
                "id":item["protocol_client_id"],
                "name":item.get("label") or item.get("name") or "",
                "engine":item.get("engine") or "",
                "protocol":item.get("protocol") or "",
                "share_link":item.get("share_link") or "",
                "subscription_id":item.get("subscription_id") or "",
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
    account["protocols"]=list_protocols(account_id,include_secrets=False)
    return account
