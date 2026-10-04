import hashlib
import secrets
import time
from datetime import datetime, timezone

from .db import connect
from . import client_store


PROXY_SESSION_TTL=30*60


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _hash(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def init_browser_gateway_db():
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS browser_proxy_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_session_id INTEGER NOT NULL,
              account_id INTEGER NOT NULL,
              device_id INTEGER NOT NULL,
              proxy_username TEXT UNIQUE NOT NULL,
              secret_hash TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              revoked_at INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              last_seen_at TEXT,
              last_ip TEXT NOT NULL DEFAULT '',
              bytes_up INTEGER NOT NULL DEFAULT 0,
              bytes_down INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(client_session_id) REFERENCES client_sessions(id),
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(device_id) REFERENCES client_devices(id)
            );
            CREATE INDEX IF NOT EXISTS idx_browser_proxy_account
              ON browser_proxy_sessions(account_id,revoked_at,expires_at);
            CREATE INDEX IF NOT EXISTS idx_browser_proxy_device
              ON browser_proxy_sessions(device_id,revoked_at,expires_at);
            CREATE INDEX IF NOT EXISTS idx_browser_proxy_client_session
              ON browser_proxy_sessions(client_session_id,revoked_at,expires_at);
            """
        )


def issue(client_session, ttl_seconds=PROXY_SESSION_TTL):
    init_browser_gateway_db()
    account_id=int(client_session["account_id"])
    device_id=int(client_session["device_id"])
    client_session_id=int(client_session["session_id"])
    account=client_store.get_account(account_id)
    ok,reason=client_store.account_available(account)
    if not ok:
        raise PermissionError(reason)
    now_ts=int(time.time())
    parent_expiry=int(client_session.get("expires_at") or 0)
    ttl=max(300,min(int(ttl_seconds or PROXY_SESSION_TTL),PROXY_SESSION_TTL))
    expires_at=now_ts+ttl
    if parent_expiry:
        expires_at=min(expires_at,parent_expiry)
    if expires_at<=now_ts:
        raise PermissionError("client session expired")

    username="mbg_"+secrets.token_urlsafe(18)
    password=secrets.token_urlsafe(32)
    with connect() as con:
        con.execute(
            """UPDATE browser_proxy_sessions
               SET revoked_at=?
               WHERE device_id=? AND revoked_at=0""",
            (now_ts,device_id),
        )
        con.execute(
            """INSERT INTO browser_proxy_sessions(
                 client_session_id,account_id,device_id,proxy_username,secret_hash,
                 expires_at,revoked_at,created_at,last_seen_at,last_ip,bytes_up,bytes_down
               ) VALUES(?,?,?,?,?,?,0,?,?,?,0,0)""",
            (
                client_session_id,account_id,device_id,username,_hash(password),
                expires_at,now_iso(),now_iso(),str(client_session.get("last_ip") or "")[:96],
            ),
        )
    return {
        "username":username,
        "password":password,
        "expires_at":expires_at,
        "ttl":max(0,expires_at-now_ts),
    }


def validate(username,password,ip=""):
    init_browser_gateway_db()
    now_ts=int(time.time())
    with connect() as con:
        row=con.execute(
            """SELECT b.*,a.enabled,a.expire_at,a.quota_bytes,d.active AS device_active,
                      s.revoked_at AS client_revoked_at,s.expires_at AS client_expires_at
               FROM browser_proxy_sessions b
               JOIN client_accounts a ON a.id=b.account_id
               JOIN client_devices d ON d.id=b.device_id
               JOIN client_sessions s ON s.id=b.client_session_id
               WHERE b.proxy_username=? AND b.revoked_at=0 AND b.expires_at>?""",
            (str(username or ""),now_ts),
        ).fetchone()
        if not row:
            return None
        item=dict(row)
        if not secrets.compare_digest(item["secret_hash"],_hash(password)):
            return None
        if not item.get("enabled") or not item.get("device_active"):
            return None
        if int(item.get("client_revoked_at") or 0)!=0:
            return None
        if int(item.get("client_expires_at") or 0)<=now_ts:
            return None
        account=client_store.get_account(item["account_id"])
        ok,_=client_store.account_available(account,now_ts)
        if not ok:
            return None
        con.execute(
            "UPDATE browser_proxy_sessions SET last_seen_at=?,last_ip=? WHERE id=?",
            (now_iso(),str(ip or "")[:96],int(item["id"])),
        )
        return item


def add_usage(session_id,up=0,down=0):
    init_browser_gateway_db()
    up=max(0,int(up or 0))
    down=max(0,int(down or 0))
    if not up and not down:
        return True
    with connect() as con:
        row=con.execute(
            "SELECT account_id FROM browser_proxy_sessions WHERE id=? AND revoked_at=0",
            (int(session_id),),
        ).fetchone()
        if not row:
            return False
        con.execute(
            """UPDATE browser_proxy_sessions
               SET bytes_up=bytes_up+?,bytes_down=bytes_down+?,last_seen_at=?
               WHERE id=?""",
            (up,down,now_iso(),int(session_id)),
        )
        account_id=int(row["account_id"])
    account=client_store.get_account(account_id)
    ok,_=client_store.account_available(account)
    return bool(ok)


def revoke_for_client_session(client_session_id):
    init_browser_gateway_db()
    with connect() as con:
        con.execute(
            """UPDATE browser_proxy_sessions SET revoked_at=?
               WHERE client_session_id=? AND revoked_at=0""",
            (int(time.time()),int(client_session_id)),
        )


def revoke_for_device(account_id,device_id):
    init_browser_gateway_db()
    with connect() as con:
        con.execute(
            """UPDATE browser_proxy_sessions SET revoked_at=?
               WHERE account_id=? AND device_id=? AND revoked_at=0""",
            (int(time.time()),int(account_id),int(device_id)),
        )


def revoke_all_for_account(account_id):
    init_browser_gateway_db()
    with connect() as con:
        con.execute(
            """UPDATE browser_proxy_sessions SET revoked_at=?
               WHERE account_id=? AND revoked_at=0""",
            (int(time.time()),int(account_id)),
        )


def account_usage_bytes(account_id):
    init_browser_gateway_db()
    with connect() as con:
        row=con.execute(
            """SELECT COALESCE(SUM(bytes_up+bytes_down),0) AS used
               FROM browser_proxy_sessions WHERE account_id=?""",
            (int(account_id),),
        ).fetchone()
        return int(row["used"] or 0)


def active_session_count(account_id=None):
    init_browser_gateway_db()
    now_ts=int(time.time())
    with connect() as con:
        if account_id is None:
            row=con.execute(
                """SELECT COUNT(*) AS n FROM browser_proxy_sessions
                   WHERE revoked_at=0 AND expires_at>?""",
                (now_ts,),
            ).fetchone()
        else:
            row=con.execute(
                """SELECT COUNT(*) AS n FROM browser_proxy_sessions
                   WHERE account_id=? AND revoked_at=0 AND expires_at>?""",
                (int(account_id),now_ts),
            ).fetchone()
        return int(row["n"] or 0)
