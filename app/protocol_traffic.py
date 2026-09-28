import time
from .db import list_protocol_clients, add_protocol_traffic, reset_protocol_traffic, advance_protocol_reset, set_protocol_client_enabled, audit
from . import protocol_ops

POLL_SECONDS=30

def collect_once():
    now=int(time.time())
    for client in list_protocol_clients():
        if client.get("engine")!="xray" or client.get("protocol") not in {"vless","vmess","trojan","hysteria2","outline"}:
            continue

        reset_days=max(0,int(client.get("reset_days") or 0))
        next_reset_at=max(0,int(client.get("next_reset_at") or 0))
        enabled=bool(int(client.get("enabled",1) or 0))
        disabled_reason=str(client.get("disabled_reason") or "")

        # A quota-suspended client renews automatically at its reset boundary.
        if not enabled:
            if disabled_reason=="quota" and reset_days and next_reset_at and now>=next_reset_at:
                try:
                    if client.get("protocol")=="outline":
                        protocol_ops.xray_inbound_traffic(client["inbound_tag"],reset=True)
                        reset_protocol_traffic(client["id"])
                        protocol_ops.set_outline_inbound_enabled(client["inbound_tag"],True)
                    else:
                        protocol_ops.reset_xray_client_traffic(client["name"])
                        reset_protocol_traffic(client["id"])
                        protocol_ops.enable_xray_client(
                            client["inbound_tag"],client["name"],client["protocol"],client["credential"]
                        )
                    set_protocol_client_enabled(client["id"],True)
                    advance_protocol_reset(client["id"],reset_days)
                    audit("system","protocol_client_auto_renew",client["name"],f"reset_days={reset_days}")
                except Exception as exc:
                    audit("system","protocol_client_auto_renew_failed",client["name"],str(exc)[:240])
            continue

        # Active recurring plans reset counters on schedule.
        if reset_days and next_reset_at and now>=next_reset_at:
            try:
                if client.get("protocol")=="outline":
                    protocol_ops.xray_inbound_traffic(client["inbound_tag"],reset=True)
                else:
                    protocol_ops.xray_client_traffic(client["name"],reset=True)
                reset_protocol_traffic(client["id"])
                advance_protocol_reset(client["id"],reset_days)
                audit("system","protocol_client_period_reset",client["name"],f"reset_days={reset_days}")
                continue
            except Exception as exc:
                audit("system","protocol_client_period_reset_failed",client["name"],str(exc)[:240])

        try:
            stats=(protocol_ops.xray_inbound_traffic(client["inbound_tag"],reset=True)
                   if client.get("protocol")=="outline"
                   else protocol_ops.xray_client_traffic(client["name"],reset=True))
        except Exception as exc:
            audit("system","traffic_collect_failed",client.get("name"),str(exc)[:240])
            continue
        if not stats.get("available"):
            continue

        add_protocol_traffic(client["id"],stats.get("uplink",0),stats.get("downlink",0))
        total=int(client.get("used_up_bytes") or 0)+int(client.get("used_down_bytes") or 0)+int(stats.get("total") or 0)
        quota=int(client.get("quota_bytes") or 0)
        expire_at=int(client.get("expire_at") or 0)

        reason=None
        disable_reason=""
        if quota and total>=quota:
            reason=f"quota exhausted: {total}/{quota}"
            disable_reason="quota"
        elif expire_at and now>=expire_at:
            reason=f"expired at {expire_at}"
            disable_reason="expiry"

        if reason:
            try:
                result=(protocol_ops.set_outline_inbound_enabled(client["inbound_tag"],False)
                        if client.get("protocol")=="outline"
                        else protocol_ops.disable_xray_client(client["inbound_tag"],client["name"]))
                set_protocol_client_enabled(client["id"],False,disable_reason)
                audit("system","protocol_client_auto_disable",client["name"],reason+"; "+str(result)[:180])
            except Exception as exc:
                audit("system","protocol_client_auto_disable_failed",client["name"],str(exc)[:240])

def main():
    while True:
        try:
            collect_once()
        except Exception as exc:
            audit("system","traffic_collector_error",detail=str(exc)[:240])
        time.sleep(POLL_SECONDS)

if __name__=="__main__":
    main()
