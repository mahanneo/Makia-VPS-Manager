# Makia VPS Manager v1.2.3 — MTProxy Runtime Hotfix UAT

Date: 2026-09-29
Target: `1.2.3`

## Scope

This hotfix addresses real-host MTProxy startup failures that surfaced as the generic browser error `MTProxy did not reach an active TCP listener`.

## Changes

- Removed `MemoryDenyWriteExecute=true` from the dedicated mtg systemd unit. mtg is a Go binary and this W^X sandboxing directive is not required by the upstream service example and can be incompatible with some Go/runtime/architecture combinations.
- Retained the remaining service isolation: unprivileged `makia-mtproxy` user, `CAP_NET_BIND_SERVICE`, `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, kernel/control-group protection and file-descriptor limits.
- Increased the post-restart listener readiness window from 8 seconds to 25 seconds.
- Runtime failures now collect bounded `systemctl status` and `journalctl -u makia-mtproxy` diagnostics and redact the configured secret before returning an error to the panel.
- Existing v1.2.1 update-state preservation and v1.2.2 non-destructive firewall behavior remain active.

## Host acceptance

- [ ] Upgrade with `sudo makia-upgrade`.
- [ ] Confirm installed version is 1.2.3.
- [ ] Configure `tg.mahinet.shop` and preferred port 443.
- [ ] Makia may choose another free managed TCP port if 443 is owned by Nginx.
- [ ] Verify Installed=YES, Configured=YES, Service=ACTIVE, Listener=TCP/<selected-port>.
- [ ] Refresh the page several times and verify hostname/port/link remain stable.
- [ ] Verify the generated t.me link connects from an external Telegram client.
- [ ] If startup still fails, the browser error must now include the actual systemd/journal reason with the secret redacted.

## Promotion rule

CI validates code, browser and Xray regressions. External Telegram connectivity remains a real-host/client UAT item.
