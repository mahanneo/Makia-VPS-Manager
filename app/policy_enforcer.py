import time
from collections import defaultdict
from datetime import date
from .db import all_profiles, audit
from .system_ops import online_sessions, disconnect_session, lock_user, OperationError
from . import client_policy

POLL_SECONDS=12

def _expired(expire_date):
    if not expire_date:
        return False
    try:
        return date.fromisoformat(str(expire_date)) < date.today()
    except Exception:
        return False

def enforce_once():
    profiles=all_profiles()
    sessions=online_sessions()
    grouped=defaultdict(list)
    for s in sessions:
        grouped[s.get("username","")].append(s)

    # Expiry is a host-level rule: expired SSH accounts are locked and active sessions are closed.
    for username,p in profiles.items():
        if not int(p.get("enabled",1)):
            continue
        if _expired(p.get("expire_date")):
            try:
                lock_user(username,True)
                for s in grouped.get(username,[]):
                    tty=s.get("tty")
                    if tty:
                        try: disconnect_session(tty)
                        except OperationError: pass
                audit("system","policy_expiry_lock",username,f"expire={p.get('expire_date')}")
            except OperationError as exc:
                audit("system","policy_expiry_lock_failed",username,str(exc)[:240])

    for username,sessions_for_user in grouped.items():
        p=profiles.get(username)
        if not p or not int(p.get("enabled",1)) or _expired(p.get("expire_date")):
            continue

        # Session limit: cap total concurrent login/tunnel sessions.
        session_limit=max(1,int(p.get("connection_limit",1) or 1))
        if len(sessions_for_user)>session_limit:
            for s in sessions_for_user[session_limit:]:
                tty=s.get("tty")
                if not tty: continue
                try:
                    disconnect_session(tty)
                    audit("system","policy_session_disconnect",username,f"tty={tty}; limit={session_limit}")
                except OperationError as exc:
                    audit("system","policy_session_disconnect_failed",username,str(exc)[:240])

        # Device/IP limit: keep only the first N distinct source addresses.
        device_limit=max(1,int(p.get("device_limit",1) or 1))
        allowed_ips=[]
        for s in sessions_for_user:
            remote=(s.get("remote") or "").strip()
            if remote and remote not in allowed_ips:
                allowed_ips.append(remote)
        allowed=set(allowed_ips[:device_limit])
        if len(allowed_ips)>device_limit:
            for s in sessions_for_user:
                remote=(s.get("remote") or "").strip()
                tty=s.get("tty")
                if remote and remote not in allowed and tty:
                    try:
                        disconnect_session(tty)
                        audit("system","policy_device_disconnect",username,f"tty={tty}; ip={remote}; device_limit={device_limit}")
                    except OperationError as exc:
                        audit("system","policy_device_disconnect_failed",username,str(exc)[:240])

    try:
        client_policy.enforce_host_artifacts()
    except Exception as exc:
        audit("system","client_policy_host_cycle_failed",detail=str(exc)[:300])

def main():
    while True:
        try:
            enforce_once()
        except Exception as exc:
            audit("system","policy_enforcer_error",detail=str(exc)[:240])
        time.sleep(POLL_SECONDS)

if __name__=="__main__":
    main()
