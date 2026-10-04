import hashlib
import secrets
import time

from .db import connect
from . import client_store

PAIR_TTL=5*60
SESSION_TTL=30*24*60*60


def _hash(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _ensure_schema():
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS client_browser_pair_tickets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token_hash TEXT UNIQUE NOT NULL,
              account_id INTEGER NOT NULL,
              device_id INTEGER NOT NULL,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              redeemed_at INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(device_id) REFERENCES client_devices(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_browser_pair_tickets_expiry
              ON client_browser_pair_tickets(expires_at,redeemed_at);
            """
        )


def issue_pair_code(account_id,device_id,ttl=PAIR_TTL):
    _ensure_schema()
    account=client_store.get_account(account_id)
    ok,reason=client_store.account_available(account)
    if not ok:
        raise PermissionError(reason)
    now=int(time.time())
    ttl=max(60,min(int(ttl or PAIR_TTL),10*60))
    code="mbp_"+secrets.token_urlsafe(24)
    with connect() as con:
        device=con.execute(
            "SELECT id,active FROM client_devices WHERE id=? AND account_id=?",
            (int(device_id),int(account_id)),
        ).fetchone()
        if not device or not int(device["active"] or 0):
            raise PermissionError("client device is unavailable")
        con.execute(
            "DELETE FROM client_browser_pair_tickets WHERE expires_at<? OR redeemed_at>0",
            (now-3600,),
        )
        con.execute(
            """INSERT INTO client_browser_pair_tickets(
                 token_hash,account_id,device_id,created_at,expires_at,redeemed_at
               ) VALUES(?,?,?,?,?,0)""",
            (_hash(code),int(account_id),int(device_id),now,now+ttl),
        )
    return {"code":code,"expires_at":now+ttl,"ttl":ttl}


def redeem_pair_code(code,ip=""):
    _ensure_schema()
    raw=str(code or "").strip()
    if not raw.startswith("mbp_") or len(raw)>128:
        raise PermissionError("browser pairing code is invalid")
    now=int(time.time())
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row=con.execute(
            """SELECT id,account_id,device_id,expires_at,redeemed_at
               FROM client_browser_pair_tickets WHERE token_hash=?""",
            (_hash(raw),),
        ).fetchone()
        if not row or int(row["redeemed_at"] or 0)>0 or int(row["expires_at"] or 0)<now:
            con.rollback()
            raise PermissionError("browser pairing code is invalid or expired")
        account=client_store.get_account(row["account_id"])
        ok,reason=client_store.account_available(account,now)
        device=con.execute(
            "SELECT id,active FROM client_devices WHERE id=? AND account_id=?",
            (int(row["device_id"]),int(row["account_id"])),
        ).fetchone()
        if not ok or not device or not int(device["active"] or 0):
            con.rollback()
            raise PermissionError(reason if not ok else "client device is unavailable")
        changed=con.execute(
            "UPDATE client_browser_pair_tickets SET redeemed_at=? WHERE id=? AND redeemed_at=0",
            (now,int(row["id"])),
        )
        if changed.rowcount!=1:
            con.rollback()
            raise PermissionError("browser pairing code was already redeemed")
        con.commit()
    token,expires_at=client_store.create_session(
        int(row["account_id"]),int(row["device_id"]),str(ip or "")[:96],SESSION_TTL
    )
    return {
        "token":token,
        "expires_at":expires_at,
        "account_id":int(row["account_id"]),
        "device_id":int(row["device_id"]),
    }
