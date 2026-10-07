import json
import secrets
import time

from .db import connect
from . import client_store

TICKET_TTL=60


def _ensure_schema():
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS client_connector_tickets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token_hash TEXT UNIQUE NOT NULL,
              account_id INTEGER NOT NULL,
              device_id INTEGER NOT NULL,
              delivery_kind TEXT NOT NULL,
              delivery_id INTEGER NOT NULL,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              redeemed_at INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(account_id) REFERENCES client_accounts(id),
              FOREIGN KEY(device_id) REFERENCES client_devices(id)
            );
            CREATE INDEX IF NOT EXISTS idx_client_connector_tickets_expiry
              ON client_connector_tickets(expires_at,redeemed_at);
            """
        )


def _hash(token):
    import hashlib
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def issue_ticket(account_id,device_id,delivery_kind,delivery_id,ttl=TICKET_TTL):
    _ensure_schema()
    kind=str(delivery_kind or "").lower()
    if kind not in {"protocol","artifact"}:
        raise ValueError("unsupported delivery kind")
    ttl=max(15,min(120,int(ttl or TICKET_TTL)))
    now=int(time.time())
    token=secrets.token_urlsafe(32)
    with connect() as con:
        con.execute(
            "DELETE FROM client_connector_tickets WHERE expires_at<? OR redeemed_at>0",
            (now-300,),
        )
        con.execute(
            """INSERT INTO client_connector_tickets(
                 token_hash,account_id,device_id,delivery_kind,delivery_id,created_at,expires_at,redeemed_at
               ) VALUES(?,?,?,?,?,?,?,0)""",
            (_hash(token),int(account_id),int(device_id),kind,int(delivery_id),now,now+ttl),
        )
    return {"ticket":token,"expires_at":now+ttl,"ttl":ttl}


def redeem_ticket(token):
    _ensure_schema()
    now=int(time.time())
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row=con.execute(
            """SELECT id,account_id,device_id,delivery_kind,delivery_id,expires_at,redeemed_at
               FROM client_connector_tickets WHERE token_hash=?""",
            (_hash(token),),
        ).fetchone()
        if not row or int(row["redeemed_at"] or 0)>0 or int(row["expires_at"] or 0)<now:
            con.rollback()
            raise PermissionError("connector ticket is invalid or expired")
        account=client_store.get_account(row["account_id"])
        ok,reason=client_store.account_available(account,now) if account else (False,"missing")
        device=con.execute(
            "SELECT id,active,platform FROM client_devices WHERE id=? AND account_id=?",
            (int(row["device_id"]),int(row["account_id"])),
        ).fetchone()
        if not ok or not device or not int(device["active"] or 0):
            con.rollback()
            raise PermissionError("client account or device is unavailable")
        changed=con.execute(
            "UPDATE client_connector_tickets SET redeemed_at=? WHERE id=? AND redeemed_at=0",
            (now,int(row["id"])),
        )
        if changed.rowcount!=1:
            con.rollback()
            raise PermissionError("connector ticket was already redeemed")
        con.commit()
    if row["delivery_kind"]=="protocol":
        delivery=client_store.protocol_delivery(row["account_id"],row["delivery_id"])
    else:
        delivery=client_store.artifact_delivery(row["account_id"],row["delivery_id"],platform=str(device["platform"] or ""))
    return {
        "account_id":int(row["account_id"]),
        "device_id":int(row["device_id"]),
        "delivery_kind":row["delivery_kind"],
        "delivery_id":int(row["delivery_id"]),
        "delivery":delivery,
    }
