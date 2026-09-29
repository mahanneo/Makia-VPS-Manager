import os
import sqlite3
import hashlib, secrets, json
from datetime import datetime, timezone
from .config import DB_PATH
from .security import hash_password

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass
    con.row_factory = sqlite3.Row
    return con

def _columns(con, table):
    return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

def _add_column(con, table, definition):
    name = definition.split()[0]
    if name not in _columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

def init_db():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS admins (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          actor TEXT NOT NULL,
          action TEXT NOT NULL,
          target TEXT,
          detail TEXT,
          ip TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_rate_limits (
          ip TEXT PRIMARY KEY,
          failures INTEGER NOT NULL DEFAULT 0,
          window_started INTEGER NOT NULL DEFAULT 0,
          blocked_until INTEGER NOT NULL DEFAULT 0
        );
                CREATE TABLE IF NOT EXISTS metrics_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          cpu REAL NOT NULL,
          memory REAL NOT NULL,
          disk REAL NOT NULL,
          load1 REAL NOT NULL,
          rx INTEGER NOT NULL,
          tx INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_history_ts ON metrics_history(ts);
        CREATE TABLE IF NOT EXISTS api_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          token_hash TEXT UNIQUE NOT NULL,
          token_last4 TEXT NOT NULL,
          scopes TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          last_used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          token_hash TEXT UNIQUE NOT NULL,
          token_last4 TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          last_seen_at TEXT,
          hostname TEXT,
          version TEXT,
          cpu REAL,
          memory REAL,
          disk REAL
        );
        CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen_at);
        CREATE TABLE IF NOT EXISTS protocol_clients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          engine TEXT NOT NULL,
          protocol TEXT NOT NULL,
          inbound_tag TEXT NOT NULL,
          credential TEXT NOT NULL,
          share_link TEXT NOT NULL,
          subscription_id TEXT NOT NULL DEFAULT '',
          quota_bytes INTEGER NOT NULL DEFAULT 0,
          used_up_bytes INTEGER NOT NULL DEFAULT 0,
          used_down_bytes INTEGER NOT NULL DEFAULT 0,
          expire_at INTEGER NOT NULL DEFAULT 0,
          ip_limit INTEGER NOT NULL DEFAULT 1,
          reset_days INTEGER NOT NULL DEFAULT 0,
          next_reset_at INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          disabled_reason TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(engine,inbound_tag,name)
        );
        CREATE INDEX IF NOT EXISTS idx_protocol_clients_name ON protocol_clients(name);
        CREATE TABLE IF NOT EXISTS account_profiles (
          username TEXT PRIMARY KEY,
          plan TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          expire_date TEXT,
          connection_limit INTEGER NOT NULL DEFAULT 1,
          device_limit INTEGER NOT NULL DEFAULT 1,
          quota_mb INTEGER NOT NULL DEFAULT 0,
          renewal_days INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS access_artifacts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          external_key TEXT NOT NULL,
          display_name TEXT NOT NULL,
          protocol TEXT NOT NULL DEFAULT '',
          native_filename TEXT NOT NULL DEFAULT '',
          payload_enc TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(kind,external_key)
        );
        CREATE INDEX IF NOT EXISTS idx_access_artifacts_kind ON access_artifacts(kind);
        CREATE TABLE IF NOT EXISTS support_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          subject TEXT NOT NULL,
          message TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          delivery_status TEXT NOT NULL DEFAULT 'local',
          remote_ticket_id TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_support_requests_created_at ON support_requests(created_at);
        CREATE TABLE IF NOT EXISTS support_grants (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token_hash TEXT UNIQUE NOT NULL,
          token_last4 TEXT NOT NULL,
          scope TEXT NOT NULL DEFAULT 'operator',
          expires_at INTEGER NOT NULL,
          used_at INTEGER NOT NULL DEFAULT 0,
          revoked_at INTEGER NOT NULL DEFAULT 0,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_support_grants_expires_at ON support_grants(expires_at);
        CREATE TABLE IF NOT EXISTS service_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          kind TEXT NOT NULL,
          protocol TEXT NOT NULL DEFAULT '',
          duration_days INTEGER NOT NULL DEFAULT 30,
          quota_mb INTEGER NOT NULL DEFAULT 0,
          ip_limit INTEGER NOT NULL DEFAULT 1,
          connection_limit INTEGER NOT NULL DEFAULT 1,
          price REAL NOT NULL DEFAULT 0,
          config_json TEXT NOT NULL DEFAULT '{}',
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS backup_schedules (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          backup_type TEXT NOT NULL DEFAULT 'quick',
          interval_hours INTEGER NOT NULL DEFAULT 24,
          keep_last INTEGER NOT NULL DEFAULT 7,
          config_enc TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1,
          next_run_at INTEGER NOT NULL DEFAULT 0,
          last_run_at INTEGER NOT NULL DEFAULT 0,
          last_status TEXT NOT NULL DEFAULT '',
          last_message TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS backup_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          schedule_id INTEGER,
          backup_name TEXT NOT NULL DEFAULT '',
          backup_type TEXT NOT NULL DEFAULT '',
          remote_type TEXT NOT NULL DEFAULT '',
          remote_status TEXT NOT NULL DEFAULT '',
          sha256 TEXT NOT NULL DEFAULT '',
          size INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT '',
          message TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_backup_runs_created_at ON backup_runs(created_at);
        CREATE TABLE IF NOT EXISTS alert_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          severity TEXT NOT NULL DEFAULT 'info',
          title TEXT NOT NULL,
          message TEXT NOT NULL DEFAULT '',
          delivered INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alert_events_created_at ON alert_events(created_at);
        ''')
        # Migration-safe columns for future profile growth.
        _add_column(con, "account_profiles", "plan TEXT NOT NULL DEFAULT ''")
        _add_column(con, "account_profiles", "note TEXT NOT NULL DEFAULT ''")
        _add_column(con, "account_profiles", "expire_date TEXT")
        _add_column(con, "account_profiles", "connection_limit INTEGER NOT NULL DEFAULT 1")
        _add_column(con, "account_profiles", "device_limit INTEGER NOT NULL DEFAULT 1")
        _add_column(con, "account_profiles", "quota_mb INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "account_profiles", "renewal_days INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "account_profiles", "enabled INTEGER NOT NULL DEFAULT 1")
        _add_column(con, "account_profiles", "created_at TEXT NOT NULL DEFAULT ''")
        _add_column(con, "account_profiles", "updated_at TEXT NOT NULL DEFAULT ''")

        _add_column(con, "protocol_clients", "subscription_id TEXT NOT NULL DEFAULT ''")
        _add_column(con, "protocol_clients", "used_up_bytes INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "protocol_clients", "used_down_bytes INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "protocol_clients", "last_traffic_at TEXT")
        _add_column(con, "protocol_clients", "reset_days INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "protocol_clients", "next_reset_at INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "protocol_clients", "disabled_reason TEXT NOT NULL DEFAULT ''")
        _add_column(con, "admins", "totp_secret TEXT")
        _add_column(con, "admins", "totp_enabled INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "region TEXT NOT NULL DEFAULT ''")
        _add_column(con, "nodes", "public_url TEXT NOT NULL DEFAULT ''")
        _add_column(con, "nodes", "users INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "online_users INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "rx INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "tx INTEGER NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "latency_ms REAL NOT NULL DEFAULT 0")
        _add_column(con, "nodes", "services_json TEXT NOT NULL DEFAULT '{}'")

        rows_missing_sub=con.execute("SELECT id FROM protocol_clients WHERE subscription_id IS NULL OR subscription_id=''").fetchall()
        for item in rows_missing_sub:
            con.execute("UPDATE protocol_clients SET subscription_id=? WHERE id=?",(secrets.token_urlsafe(18),item["id"]))

        if not con.execute("SELECT 1 FROM admins LIMIT 1").fetchone():
            initial_password = os.getenv("DRAGON_INITIAL_ADMIN_PASSWORD") or os.getenv("MAKIA_INITIAL_ADMIN_PASSWORD")
            if not initial_password or len(initial_password) < 16:
                raise RuntimeError(
                    "Empty database requires MAKIA_INITIAL_ADMIN_PASSWORD (minimum 16 characters). "
                    "Use the official installer to bootstrap securely."
                )
            con.execute(
                "INSERT INTO admins(username,password_hash,created_at) VALUES(?,?,?)",
                ("admin", hash_password(initial_password), now())
            )

def now():
    return datetime.now(timezone.utc).isoformat()

def audit(actor, action, target=None, detail=None, ip=None):
    with connect() as con:
        con.execute(
            "INSERT INTO audit_logs(actor,action,target,detail,ip,created_at) VALUES(?,?,?,?,?,?)",
            (actor, action, target, detail, ip, now())
        )

def upsert_profile(username, plan="", note="", expire_date=None, connection_limit=1, quota_mb=0, enabled=1, device_limit=1, renewal_days=0):
    ts=now()
    with connect() as con:
        con.execute(
            """INSERT INTO account_profiles(username,plan,note,expire_date,connection_limit,device_limit,quota_mb,renewal_days,enabled,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(username) DO UPDATE SET
                 plan=excluded.plan,note=excluded.note,expire_date=excluded.expire_date,
                 connection_limit=excluded.connection_limit,device_limit=excluded.device_limit,
                 quota_mb=excluded.quota_mb,renewal_days=excluded.renewal_days,
                 enabled=excluded.enabled,updated_at=excluded.updated_at""",
            (username, plan or "", note or "", expire_date, max(1,int(connection_limit or 1)),
             max(1,int(device_limit or 1)), max(0,int(quota_mb or 0)), max(0,int(renewal_days or 0)),
             1 if enabled else 0, ts, ts)
        )

def get_profile(username):
    with connect() as con:
        row=con.execute("SELECT * FROM account_profiles WHERE username=?",(username,)).fetchone()
        return dict(row) if row else None

def all_profiles():
    with connect() as con:
        return {r["username"]:dict(r) for r in con.execute("SELECT * FROM account_profiles").fetchall()}

def delete_profile(username):
    with connect() as con:
        con.execute("DELETE FROM account_profiles WHERE username=?",(username,))


def add_metric(ts,cpu,memory,disk,load1,rx,tx):
    with connect() as con:
        con.execute("INSERT INTO metrics_history(ts,cpu,memory,disk,load1,rx,tx) VALUES(?,?,?,?,?,?,?)",
                    (int(ts),float(cpu),float(memory),float(disk),float(load1),int(rx),int(tx)))
        # Keep 7 days at one-minute sampling with a small safety margin.
        con.execute("DELETE FROM metrics_history WHERE ts < ?",(int(ts)-8*86400,))

def metrics_since(since_ts,limit=2000):
    with connect() as con:
        rows=con.execute(
            "SELECT ts,cpu,memory,disk,load1,rx,tx FROM metrics_history WHERE ts>=? ORDER BY ts ASC LIMIT ?",
            (int(since_ts),max(1,min(int(limit),10000)))
        ).fetchall()
        return [dict(r) for r in rows]


def get_admin_2fa(username):
    with connect() as con:
        row=con.execute("SELECT username,totp_secret,totp_enabled FROM admins WHERE username=?",(username,)).fetchone()
        return dict(row) if row else None

def set_admin_totp_secret(username,secret):
    with connect() as con:
        con.execute("UPDATE admins SET totp_secret=?,totp_enabled=0 WHERE username=?",(secret,username))

def set_admin_totp_enabled(username,enabled):
    with connect() as con:
        con.execute("UPDATE admins SET totp_enabled=? WHERE username=?",(1 if enabled else 0,username))

def clear_admin_totp(username):
    with connect() as con:
        con.execute("UPDATE admins SET totp_secret=NULL,totp_enabled=0 WHERE username=?",(username,))


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_api_token(name,scopes):
    token="mk_"+secrets.token_urlsafe(32)
    ts=now()
    scopes_text=",".join(sorted(set(scopes)))
    with connect() as con:
        cur=con.execute(
            "INSERT INTO api_tokens(name,token_hash,token_last4,scopes,active,created_at) VALUES(?,?,?,?,1,?)",
            (name,_token_hash(token),token[-4:],scopes_text,ts)
        )
        token_id=cur.lastrowid
    return {"id":token_id,"token":token,"name":name,"scopes":scopes_text.split(",") if scopes_text else []}

def list_api_tokens():
    with connect() as con:
        rows=con.execute("SELECT id,name,token_last4,scopes,active,created_at,last_used_at FROM api_tokens ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def revoke_api_token(token_id):
    with connect() as con:
        con.execute("UPDATE api_tokens SET active=0 WHERE id=?",(int(token_id),))

def verify_api_token(token,required_scope=None):
    h=_token_hash(token)
    with connect() as con:
        row=con.execute("SELECT * FROM api_tokens WHERE token_hash=? AND active=1",(h,)).fetchone()
        if not row:
            return None
        scopes={s for s in (row["scopes"] or "").split(",") if s}
        if required_scope and required_scope not in scopes and "*" not in scopes:
            return None
        con.execute("UPDATE api_tokens SET last_used_at=? WHERE id=?",(now(),row["id"]))
        return {"id":row["id"],"name":row["name"],"scopes":sorted(scopes)}

def create_node(name):
    token="mn_"+secrets.token_urlsafe(32)
    ts=now()
    with connect() as con:
        cur=con.execute(
            "INSERT INTO nodes(name,token_hash,token_last4,active,created_at) VALUES(?,?,?,1,?)",
            (name,_token_hash(token),token[-4:],ts)
        )
        node_id=cur.lastrowid
    return {"id":node_id,"name":name,"token":token}

def list_nodes():
    with connect() as con:
        rows=con.execute("SELECT id,name,token_last4,active,created_at,last_seen_at,hostname,version,cpu,memory,disk,region,public_url,users,online_users,rx,tx,latency_ms,services_json FROM nodes ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def revoke_node(node_id):
    with connect() as con:
        con.execute("UPDATE nodes SET active=0 WHERE id=?",(int(node_id),))

def node_by_token(token):
    h=_token_hash(token)
    with connect() as con:
        row=con.execute("SELECT id,name,active FROM nodes WHERE token_hash=? AND active=1",(h,)).fetchone()
        return dict(row) if row else None

def update_node_heartbeat(node_id,hostname,version,cpu,memory,disk,region="",public_url="",users=0,online_users=0,rx=0,tx=0,latency_ms=0,services=None):
    with connect() as con:
        con.execute(
            """UPDATE nodes SET last_seen_at=?,hostname=?,version=?,cpu=?,memory=?,disk=?,
               region=?,public_url=?,users=?,online_users=?,rx=?,tx=?,latency_ms=?,services_json=? WHERE id=?""",
            (now(),hostname,version,float(cpu),float(memory),float(disk),str(region or "")[:80],
             str(public_url or "")[:255],max(0,int(users or 0)),max(0,int(online_users or 0)),
             max(0,int(rx or 0)),max(0,int(tx or 0)),max(0,float(latency_ms or 0)),
             json.dumps(services or {},ensure_ascii=False,separators=(",",":")),int(node_id))
        )


def get_setting(key, default=None):
    with connect() as con:
        row=con.execute("SELECT value FROM settings WHERE key=?",(str(key),)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with connect() as con:
        con.execute(
            """INSERT INTO settings(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (str(key), str(value))
        )

def all_settings():
    with connect() as con:
        return {r["key"]:r["value"] for r in con.execute("SELECT key,value FROM settings").fetchall()}


def create_protocol_client(name,engine,protocol,inbound_tag,credential,share_link,quota_bytes=0,expire_at=0,ip_limit=1,reset_days=0):
    ts=now()
    sub_id=secrets.token_urlsafe(18)
    reset_days=max(0,int(reset_days or 0))
    next_reset_at=int(datetime.now(timezone.utc).timestamp())+reset_days*86400 if reset_days else 0
    with connect() as con:
        cur=con.execute(
            """INSERT INTO protocol_clients(name,engine,protocol,inbound_tag,credential,share_link,subscription_id,quota_bytes,expire_at,ip_limit,reset_days,next_reset_at,enabled,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
            (name,engine,protocol,inbound_tag,credential,share_link,sub_id,max(0,int(quota_bytes or 0)),
             max(0,int(expire_at or 0)),max(1,int(ip_limit or 1)),reset_days,next_reset_at,ts,ts)
        )
        return cur.lastrowid

def list_protocol_clients():
    with connect() as con:
        rows=con.execute("SELECT * FROM protocol_clients ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def get_protocol_client(client_id):
    with connect() as con:
        row=con.execute("SELECT * FROM protocol_clients WHERE id=?",(int(client_id),)).fetchone()
        return dict(row) if row else None


def protocol_client_by_subscription(subscription_id):
    with connect() as con:
        row=con.execute(
            "SELECT * FROM protocol_clients WHERE subscription_id=?",
            (str(subscription_id),)
        ).fetchone()
        return dict(row) if row else None

def update_protocol_client_state(client_id,enabled=None,quota_bytes=None,expire_at=None,ip_limit=None,reset_days=None):
    fields=[]; values=[]
    if enabled is not None:
        fields.append("enabled=?"); values.append(1 if enabled else 0)
        fields.append("disabled_reason=?"); values.append("" if enabled else "manual")
    if quota_bytes is not None: fields.append("quota_bytes=?"); values.append(max(0,int(quota_bytes)))
    if expire_at is not None: fields.append("expire_at=?"); values.append(max(0,int(expire_at)))
    if ip_limit is not None: fields.append("ip_limit=?"); values.append(max(1,int(ip_limit)))
    if reset_days is not None:
        reset_days=max(0,int(reset_days))
        fields.append("reset_days=?"); values.append(reset_days)
        fields.append("next_reset_at=?"); values.append(int(datetime.now(timezone.utc).timestamp())+reset_days*86400 if reset_days else 0)
    if not fields: return
    fields.append("updated_at=?"); values.append(now()); values.append(int(client_id))
    with connect() as con:
        con.execute("UPDATE protocol_clients SET "+",".join(fields)+" WHERE id=?",values)

def delete_protocol_client(client_id):
    with connect() as con:
        con.execute("DELETE FROM protocol_clients WHERE id=?",(int(client_id),))


def add_protocol_traffic(client_id,uplink,downlink):
    up=max(0,int(uplink or 0)); down=max(0,int(downlink or 0))
    with connect() as con:
        con.execute(
            """UPDATE protocol_clients
               SET used_up_bytes=used_up_bytes+?,
                   used_down_bytes=used_down_bytes+?,
                   last_traffic_at=?,
                   updated_at=?
               WHERE id=?""",
            (up,down,now(),now(),int(client_id))
        )

def reset_protocol_traffic(client_id):
    with connect() as con:
        con.execute(
            "UPDATE protocol_clients SET used_up_bytes=0,used_down_bytes=0,last_traffic_at=?,updated_at=? WHERE id=?",
            (now(),now(),int(client_id))
        )

def set_protocol_client_enabled(client_id,enabled,reason=""):
    with connect() as con:
        con.execute(
            "UPDATE protocol_clients SET enabled=?,disabled_reason=?,updated_at=? WHERE id=?",
            (1 if enabled else 0,"" if enabled else str(reason or "manual"),now(),int(client_id))
        )

def advance_protocol_reset(client_id,reset_days):
    reset_days=max(0,int(reset_days or 0))
    next_at=int(datetime.now(timezone.utc).timestamp())+reset_days*86400 if reset_days else 0
    with connect() as con:
        con.execute(
            "UPDATE protocol_clients SET next_reset_at=?,updated_at=? WHERE id=?",
            (next_at,now(),int(client_id))
        )

def login_rate_state(ip, now_ts):
    with connect() as con:
        row=con.execute("SELECT * FROM login_rate_limits WHERE ip=?",(str(ip),)).fetchone()
        if not row:
            return {"failures":0,"window_started":0,"blocked_until":0}
        data=dict(row)
        if int(data.get("blocked_until") or 0)>int(now_ts):
            return data
        if int(now_ts)-int(data.get("window_started") or 0)>900:
            con.execute("DELETE FROM login_rate_limits WHERE ip=?",(str(ip),))
            return {"failures":0,"window_started":0,"blocked_until":0}
        return data

def record_login_failure(ip, now_ts, max_failures=6, window_seconds=900, block_seconds=900):
    ip=str(ip)
    with connect() as con:
        row=con.execute("SELECT * FROM login_rate_limits WHERE ip=?",(ip,)).fetchone()
        if not row or int(now_ts)-int(row["window_started"] or 0)>window_seconds:
            failures=1; started=int(now_ts); blocked=0
        else:
            failures=int(row["failures"] or 0)+1; started=int(row["window_started"] or now_ts); blocked=int(row["blocked_until"] or 0)
        if failures>=max_failures:
            blocked=max(blocked,int(now_ts)+block_seconds)
        con.execute(
            """INSERT INTO login_rate_limits(ip,failures,window_started,blocked_until)
               VALUES(?,?,?,?)
               ON CONFLICT(ip) DO UPDATE SET failures=excluded.failures,window_started=excluded.window_started,blocked_until=excluded.blocked_until""",
            (ip,failures,started,blocked)
        )
        return {"failures":failures,"window_started":started,"blocked_until":blocked}

def clear_login_failures(ip):
    with connect() as con:
        con.execute("DELETE FROM login_rate_limits WHERE ip=?",(str(ip),))


def create_support_request(subject,message,delivery_status="local",remote_ticket_id=""):
    ts=now()
    subject=str(subject or "").strip()[:160]
    message=str(message or "").strip()[:5000]
    if not subject or not message:
        raise ValueError("subject and message are required")
    with connect() as con:
        cur=con.execute(
            "INSERT INTO support_requests(subject,message,status,delivery_status,remote_ticket_id,created_at,updated_at) VALUES(?,?, 'open', ?, ?, ?, ?)",
            (subject,message,str(delivery_status or "local")[:40],str(remote_ticket_id or "")[:160],ts,ts)
        )
        return int(cur.lastrowid)

def list_support_requests(limit=100):
    with connect() as con:
        rows=con.execute(
            "SELECT id,subject,message,status,delivery_status,remote_ticket_id,created_at,updated_at FROM support_requests ORDER BY id DESC LIMIT ?",
            (max(1,min(int(limit),500)),)
        ).fetchall()
        return [dict(r) for r in rows]

def update_support_request_delivery(request_id,delivery_status,remote_ticket_id=""):
    with connect() as con:
        con.execute(
            "UPDATE support_requests SET delivery_status=?,remote_ticket_id=?,updated_at=? WHERE id=?",
            (str(delivery_status or "local")[:40],str(remote_ticket_id or "")[:160],now(),int(request_id))
        )

def upsert_access_artifact(kind,external_key,display_name,protocol,native_filename,payload_enc,metadata_json="{}"):
    ts=now()
    with connect() as con:
        con.execute(
            """INSERT INTO access_artifacts(kind,external_key,display_name,protocol,native_filename,payload_enc,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(kind,external_key) DO UPDATE SET
                 display_name=excluded.display_name,
                 protocol=excluded.protocol,
                 native_filename=excluded.native_filename,
                 payload_enc=excluded.payload_enc,
                 metadata_json=excluded.metadata_json,
                 updated_at=excluded.updated_at""",
            (str(kind),str(external_key),str(display_name),str(protocol or ""),str(native_filename or ""),
             str(payload_enc),str(metadata_json or "{}"),ts,ts)
        )
        row=con.execute("SELECT id FROM access_artifacts WHERE kind=? AND external_key=?",(str(kind),str(external_key))).fetchone()
        return int(row["id"])

def list_access_artifacts():
    with connect() as con:
        rows=con.execute(
            "SELECT id,kind,external_key,display_name,protocol,native_filename,metadata_json,created_at,updated_at FROM access_artifacts ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

def get_access_artifact(artifact_id):
    with connect() as con:
        row=con.execute("SELECT * FROM access_artifacts WHERE id=?",(int(artifact_id),)).fetchone()
        return dict(row) if row else None

def get_access_artifact_by_key(kind,external_key):
    with connect() as con:
        row=con.execute("SELECT * FROM access_artifacts WHERE kind=? AND external_key=?",(str(kind),str(external_key))).fetchone()
        return dict(row) if row else None

def delete_access_artifact(artifact_id):
    with connect() as con:
        con.execute("DELETE FROM access_artifacts WHERE id=?",(int(artifact_id),))

def delete_access_artifact_by_key(kind,external_key):
    with connect() as con:
        con.execute("DELETE FROM access_artifacts WHERE kind=? AND external_key=?",(str(kind),str(external_key)))


def create_support_grant(created_by,minutes=30,scope="operator"):
    scope=str(scope or "operator").strip().lower()
    if scope not in {"readonly","operator"}:
        raise ValueError("invalid support scope")
    minutes=max(5,min(int(minutes or 30),120))
    alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw="SUP-"+"-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4))
    token_hash=_token_hash(raw)
    expires_at=int(datetime.now(timezone.utc).timestamp())+minutes*60
    with connect() as con:
        con.execute("UPDATE support_grants SET revoked_at=? WHERE revoked_at=0 AND expires_at>?",(int(datetime.now(timezone.utc).timestamp()),int(datetime.now(timezone.utc).timestamp())))
        cur=con.execute(
            "INSERT INTO support_grants(token_hash,token_last4,scope,expires_at,used_at,revoked_at,created_by,created_at) VALUES(?,?,?,?,0,0,?,?)",
            (token_hash,raw[-4:],scope,expires_at,str(created_by),now())
        )
        grant_id=int(cur.lastrowid)
    return {"id":grant_id,"code":raw,"scope":scope,"expires_at":expires_at}

def consume_support_grant(code):
    token_hash=_token_hash(str(code or "").strip().upper())
    now_ts=int(datetime.now(timezone.utc).timestamp())
    with connect() as con:
        row=con.execute("SELECT * FROM support_grants WHERE token_hash=?",(token_hash,)).fetchone()
        if not row:
            return None
        item=dict(row)
        if int(item.get("revoked_at") or 0)>0 or int(item.get("expires_at") or 0)<=now_ts or int(item.get("used_at") or 0)>0:
            return None
        con.execute("UPDATE support_grants SET used_at=? WHERE id=?",(now_ts,int(item["id"])))
        item["used_at"]=now_ts
        return item

def support_grant_by_id(grant_id):
    now_ts=int(datetime.now(timezone.utc).timestamp())
    with connect() as con:
        row=con.execute("SELECT * FROM support_grants WHERE id=?",(int(grant_id),)).fetchone()
        if not row:
            return None
        item=dict(row)
        item["active"]=bool(int(item.get("revoked_at") or 0)==0 and int(item.get("expires_at") or 0)>now_ts and int(item.get("used_at") or 0)>0)
        return item

def list_support_grants(limit=20):
    now_ts=int(datetime.now(timezone.utc).timestamp())
    with connect() as con:
        rows=con.execute(
            "SELECT id,token_last4,scope,expires_at,used_at,revoked_at,created_by,created_at FROM support_grants ORDER BY id DESC LIMIT ?",
            (max(1,min(int(limit),100)),)
        ).fetchall()
        out=[]
        for row in rows:
            item=dict(row)
            item["active"]=bool(int(item.get("revoked_at") or 0)==0 and int(item.get("expires_at") or 0)>now_ts)
            out.append(item)
        return out

def revoke_support_grant(grant_id):
    now_ts=int(datetime.now(timezone.utc).timestamp())
    with connect() as con:
        con.execute("UPDATE support_grants SET revoked_at=? WHERE id=?",(now_ts,int(grant_id)))
    return {"ok":True,"id":int(grant_id)}


def create_plan(name,kind,protocol="",duration_days=30,quota_mb=0,ip_limit=1,connection_limit=1,price=0,config=None,active=True):
    ts=now()
    with connect() as con:
        cur=con.execute(
            """INSERT INTO service_plans(name,kind,protocol,duration_days,quota_mb,ip_limit,connection_limit,price,config_json,active,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(name).strip(),str(kind).strip().lower(),str(protocol or "").strip().lower(),
             max(0,int(duration_days or 0)),max(0,int(quota_mb or 0)),max(1,int(ip_limit or 1)),
             max(1,int(connection_limit or 1)),max(0,float(price or 0)),
             json.dumps(config or {},ensure_ascii=False,separators=(",",":")),1 if active else 0,ts,ts)
        )
        return int(cur.lastrowid)

def update_plan(plan_id,**values):
    allowed={"name","kind","protocol","duration_days","quota_mb","ip_limit","connection_limit","price","config_json","active"}
    fields=[];params=[]
    for key,val in values.items():
        if key not in allowed: continue
        if key=="config_json" and not isinstance(val,str):
            val=json.dumps(val or {},ensure_ascii=False,separators=(",",":"))
        if key=="active": val=1 if val else 0
        fields.append(f"{key}=?");params.append(val)
    if not fields:return
    fields.append("updated_at=?");params.append(now());params.append(int(plan_id))
    with connect() as con: con.execute("UPDATE service_plans SET "+",".join(fields)+" WHERE id=?",params)

def list_plans(active_only=False):
    with connect() as con:
        sql="SELECT * FROM service_plans"+(" WHERE active=1" if active_only else "")+" ORDER BY id DESC"
        rows=con.execute(sql).fetchall()
        out=[]
        for row in rows:
            item=dict(row)
            try:item["config"]=json.loads(item.pop("config_json") or "{}")
            except Exception:item["config"]={}
            out.append(item)
        return out

def delete_plan(plan_id):
    with connect() as con: con.execute("DELETE FROM service_plans WHERE id=?",(int(plan_id),))

def create_backup_schedule(name,backup_type,interval_hours,keep_last,config_enc,enabled=True,next_run_at=0):
    ts=now()
    with connect() as con:
        cur=con.execute(
            """INSERT INTO backup_schedules(name,backup_type,interval_hours,keep_last,config_enc,enabled,next_run_at,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (str(name).strip(),str(backup_type),max(1,int(interval_hours)),max(1,min(int(keep_last),100)),
             str(config_enc or ""),1 if enabled else 0,max(0,int(next_run_at)),ts,ts)
        )
        return int(cur.lastrowid)

def list_backup_schedules():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM backup_schedules ORDER BY id DESC").fetchall()]

def due_backup_schedules(now_ts):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM backup_schedules WHERE enabled=1 AND (next_run_at=0 OR next_run_at<=?) ORDER BY id ASC",
            (int(now_ts),)
        ).fetchall()]

def update_backup_schedule_state(schedule_id,next_run_at,last_status,last_message,last_run_at=None):
    with connect() as con:
        con.execute(
            "UPDATE backup_schedules SET next_run_at=?,last_run_at=?,last_status=?,last_message=?,updated_at=? WHERE id=?",
            (int(next_run_at),int(last_run_at or 0),str(last_status or ""),str(last_message or "")[:1000],now(),int(schedule_id))
        )

def delete_backup_schedule(schedule_id):
    with connect() as con: con.execute("DELETE FROM backup_schedules WHERE id=?",(int(schedule_id),))

def add_backup_run(schedule_id,backup_name,backup_type,remote_type,remote_status,sha256,size,status,message):
    with connect() as con:
        cur=con.execute(
            """INSERT INTO backup_runs(schedule_id,backup_name,backup_type,remote_type,remote_status,sha256,size,status,message,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (schedule_id,str(backup_name or ""),str(backup_type or ""),str(remote_type or ""),str(remote_status or ""),
             str(sha256 or ""),max(0,int(size or 0)),str(status or ""),str(message or "")[:1200],now())
        )
        return int(cur.lastrowid)

def list_backup_runs(limit=50):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM backup_runs ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),500)),)
        ).fetchall()]

def add_alert_event(kind,severity,title,message="",delivered=False):
    with connect() as con:
        cur=con.execute(
            "INSERT INTO alert_events(kind,severity,title,message,delivered,created_at) VALUES(?,?,?,?,?,?)",
            (str(kind),str(severity),str(title)[:160],str(message)[:2000],1 if delivered else 0,now())
        )
        return int(cur.lastrowid)

def list_alert_events(limit=100):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM alert_events ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),500)),)
        ).fetchall()]
