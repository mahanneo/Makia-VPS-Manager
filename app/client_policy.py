import subprocess
import time
from collections import defaultdict

from . import client_store, protocol_ops, integration_ops, system_ops
from .db import audit, get_protocol_client, set_protocol_client_enabled


CLIENT_REASON_PREFIX="client_account_"


def _reason(account,now_ts=None):
    return client_store.client_policy_reason(account,now_ts)


def _managed_reason(reason):
    return CLIENT_REASON_PREFIX+str(reason or "policy")


def enforce_managed_protocols(now_ts=None):
    """Enforce Client-account state on bound Xray/Outline credentials only.

    Existing unbound protocol identities are never touched. A credential that
    was disabled for a pre-existing protocol-level reason (manual/quota/expiry)
    is never auto-enabled by this layer.
    """
    now_ts=int(now_ts or time.time())
    result={"checked":0,"suspended":0,"restored":0,"errors":0}
    for account in client_store.list_accounts():
        reason=_reason(account,now_ts)
        bindings=client_store.list_bindings(account["id"])
        for binding in bindings:
            if not int(binding.get("enabled") or 0):
                continue
            row=get_protocol_client(binding["protocol_client_id"])
            if not row:
                continue
            engine=str(row.get("engine") or "").lower()
            if engine not in {"xray","outline"}:
                continue
            result["checked"]+=1
            disabled_reason=str(row.get("disabled_reason") or "")
            try:
                if engine=="xray":
                    supported=str(row.get("protocol") or "").lower() in {"vless","vmess","trojan","hysteria2"}
                    if not supported:
                        continue
                    if reason:
                        if int(row.get("enabled") or 0):
                            changed=protocol_ops.disable_xray_client(row["inbound_tag"],row["name"])
                            if changed.get("disabled") or changed.get("reason")=="client not found in config":
                                set_protocol_client_enabled(row["id"],False,_managed_reason(reason))
                                audit("system","client_policy_xray_suspend",row["name"],f"account={account['username']}; reason={reason}")
                                result["suspended"]+=1
                    elif not int(row.get("enabled") or 0) and disabled_reason.startswith(CLIENT_REASON_PREFIX):
                        protocol_ops.enable_xray_client(
                            row["inbound_tag"],row["name"],row["protocol"],row["credential"]
                        )
                        set_protocol_client_enabled(row["id"],True)
                        audit("system","client_policy_xray_restore",row["name"],f"account={account['username']}")
                        result["restored"]+=1
                elif engine=="outline":
                    key_id=str(row.get("inbound_tag") or "")
                    if not key_id:
                        continue
                    raw_used=max(0,int(row.get("used_up_bytes") or 0)+int(row.get("used_down_bytes") or 0))
                    if reason:
                        # Freeze the existing key non-destructively at its current
                        # transfer counter instead of deleting/reissuing it.
                        if int(row.get("enabled") or 0):
                            integration_ops.outline_set_limit(key_id,max(1,raw_used))
                            set_protocol_client_enabled(row["id"],False,_managed_reason(reason))
                            audit("system","client_policy_outline_suspend",row["name"],f"account={account['username']}; reason={reason}")
                            result["suspended"]+=1
                    elif not int(row.get("enabled") or 0) and disabled_reason.startswith(CLIENT_REASON_PREFIX):
                        integration_ops.outline_set_limit(key_id,max(0,int(row.get("quota_bytes") or 0)))
                        set_protocol_client_enabled(row["id"],True)
                        audit("system","client_policy_outline_restore",row["name"],f"account={account['username']}")
                        result["restored"]+=1
            except Exception as exc:
                result["errors"]+=1
                audit("system","client_policy_protocol_error",row.get("name"),f"account={account['username']}; {str(exc)[:300]}")
    return result


def _ssh_is_locked(username):
    try:
        p=subprocess.run(["passwd","-S",str(username)],text=True,capture_output=True,timeout=5,check=False)
        if p.returncode!=0:
            return None
        parts=(p.stdout or "").split()
        return len(parts)>=2 and parts[1].upper() in {"L","LK"}
    except Exception:
        return None


def _ssh_disconnect_limits(account,username,sessions):
    rows=[s for s in sessions if s.get("username")==username]
    if not rows:
        return 0
    removed=0
    # Concurrent sessions are a hard ceiling.
    concurrent=max(1,int(account.get("concurrent_device_limit") or 1))
    for session in rows[concurrent:]:
        tty=session.get("tty")
        if tty:
            try:
                system_ops.disconnect_session(tty);removed+=1
            except system_ops.OperationError:
                pass
    # Device limit is represented by distinct observed source IPs for SSH.
    limit=max(1,int(account.get("device_limit") or 1))
    allowed=[]
    for session in rows:
        remote=str(session.get("remote") or "").strip()
        if remote and remote not in allowed:
            allowed.append(remote)
    keep=set(allowed[:limit])
    if len(allowed)>limit:
        for session in rows:
            remote=str(session.get("remote") or "").strip()
            tty=session.get("tty")
            if remote and remote not in keep and tty:
                try:
                    system_ops.disconnect_session(tty);removed+=1
                except system_ops.OperationError:
                    pass
    return removed


def enforce_host_artifacts(now_ts=None):
    """Enforce host-safe Client policies for bound SSH and WireGuard artifacts.

    WireGuard contributes persistent traffic deltas to the account quota.
    SSH contributes time/device/session enforcement; byte quota accounting is
    intentionally not claimed for SSH. OpenVPN remains delivery-only until its
    non-destructive authorization hook is explicitly installed.
    """
    now_ts=int(now_ts or time.time())
    accounts={int(a["id"]):a for a in client_store.list_accounts()}
    sessions=system_ops.online_sessions()
    wg_runtime={str(p.get("name") or ""):p for p in protocol_ops._wireguard_peer_runtime()}
    wg_config={str(p.get("name") or ""):p for p in protocol_ops.list_wireguard_peers()}
    result={"checked":0,"samples":0,"suspended":0,"restored":0,"disconnected":0,"errors":0}

    # Sample WireGuard transfer counters before evaluating aggregate quota.
    for account_id,account in accounts.items():
        for binding in client_store.list_artifact_bindings(account_id):
            if str(binding.get("kind") or "").lower()!="wireguard":
                continue
            name=str(binding.get("external_key") or "")
            runtime=wg_runtime.get(name)
            if not runtime:
                continue
            try:
                client_store.add_artifact_counter_sample(
                    account_id,binding["artifact_id"],
                    int(runtime.get("rx") or 0)+int(runtime.get("tx") or 0),
                )
                result["samples"]+=1
            except Exception as exc:
                result["errors"]+=1
                audit("system","client_policy_wireguard_sample_failed",name,str(exc)[:300])

    # Re-read accounts because quota usage may have changed after WG sampling.
    accounts={int(a["id"]):a for a in client_store.list_accounts()}
    for account_id,account in accounts.items():
        reason=_reason(account,now_ts)
        for binding in client_store.list_artifact_bindings(account_id):
            kind=str(binding.get("kind") or "").lower()
            if kind not in {"wireguard","ssh"}:
                continue
            result["checked"]+=1
            artifact_id=int(binding["artifact_id"])
            name=str(binding.get("external_key") or "")
            state=client_store.get_artifact_policy_state(account_id,artifact_id)
            managed=str(state.get("suspended_reason") or "")
            try:
                if kind=="wireguard":
                    peer=wg_config.get(name)
                    if not peer:
                        continue
                    if reason:
                        if peer.get("enabled") and not managed:
                            protocol_ops.set_wireguard_peer_enabled(name,False)
                            client_store.set_artifact_policy_state(account_id,artifact_id,_managed_reason(reason))
                            audit("system","client_policy_wireguard_suspend",name,f"account={account['username']}; reason={reason}")
                            result["suspended"]+=1
                    elif managed.startswith(CLIENT_REASON_PREFIX):
                        # Re-enable only a peer that this policy layer suspended.
                        current=next((p for p in protocol_ops.list_wireguard_peers() if p.get("name")==name),None)
                        if current and not current.get("enabled"):
                            protocol_ops.set_wireguard_peer_enabled(name,True)
                        client_store.set_artifact_policy_state(account_id,artifact_id,"")
                        audit("system","client_policy_wireguard_restore",name,f"account={account['username']}")
                        result["restored"]+=1

                elif kind=="ssh":
                    if not name:
                        continue
                    if reason:
                        if not managed:
                            locked=_ssh_is_locked(name)
                            if locked is False:
                                system_ops.lock_user(name,True)
                                client_store.set_artifact_policy_state(account_id,artifact_id,_managed_reason(reason))
                                for s in sessions:
                                    if s.get("username")==name and s.get("tty"):
                                        try:
                                            system_ops.disconnect_session(s["tty"]);result["disconnected"]+=1
                                        except system_ops.OperationError:
                                            pass
                                audit("system","client_policy_ssh_suspend",name,f"account={account['username']}; reason={reason}")
                                result["suspended"]+=1
                            elif locked is True:
                                audit("system","client_policy_ssh_prelocked",name,f"account={account['username']}; reason={reason}")
                    else:
                        if managed.startswith(CLIENT_REASON_PREFIX):
                            if _ssh_is_locked(name) is True:
                                system_ops.lock_user(name,False)
                            client_store.set_artifact_policy_state(account_id,artifact_id,"")
                            audit("system","client_policy_ssh_restore",name,f"account={account['username']}")
                            result["restored"]+=1
                        removed=_ssh_disconnect_limits(account,name,sessions)
                        if removed:
                            result["disconnected"]+=removed
                            audit("system","client_policy_ssh_session_limit",name,f"account={account['username']}; disconnected={removed}")
            except Exception as exc:
                result["errors"]+=1
                audit("system","client_policy_artifact_error",name,f"account={account['username']}; kind={kind}; {str(exc)[:300]}")
    return result
