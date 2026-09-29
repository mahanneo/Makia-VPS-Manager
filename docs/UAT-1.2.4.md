# Makia VPS Manager v1.2.4 — MTProxy Permission + Auto Port UAT

Date: 2026-09-29
Target: `1.2.4`

## Root cause fixed

The dedicated `makia-mtproxy` service runs unprivileged. Its config file was correctly owned as `root:makia-mtproxy` with mode `0640`, but the parent directory `/etc/makia-vps-manager` was created as `0700 root:root`. The service user therefore could not traverse the directory to read `mtproxy.toml`, so mtg exited before binding a listener.

v1.2.4 repairs the parent directory to `0710 root:makia-mtproxy`: the service group receives execute/traverse only, not directory-listing permission. Other Makia secrets remain protected by their own root-only file modes.

## Port behavior

- Telegram Proxy port is AUTO by default.
- 443 is no longer preferred.
- Makia tries managed high TCP ports: 8443, 9443, 10443, 11443, 12443, 13010, 18080, 24443, 30443, 40443, 50443.
- If all managed candidates are occupied, the kernel selects a free high TCP port.
- Safe retries preserve the existing configured port when it is still usable.
- The browser no longer asks the operator to choose a port.

## Failure behavior

- Before service start Makia verifies that the real `makia-mtproxy` account can traverse and read the generated config.
- On a first-start runtime failure, the attempted hostname/secret/port are kept for diagnostics and retry instead of being deleted.
- Existing valid configuration still rolls back if a reconfiguration fails.
- v1.2.1 update preservation, v1.2.2 firewall non-destructive behavior and v1.2.3 runtime diagnostics remain active.

## Host acceptance

- [ ] Run `sudo makia-upgrade`.
- [ ] Confirm version 1.2.4.
- [ ] Check `stat -c '%a %U %G' /etc/makia-vps-manager` returns `710 root makia-mtproxy`.
- [ ] Open Telegram Proxy and enter only the FakeTLS hostname.
- [ ] Save/start with AUTO port.
- [ ] Verify Configured=YES, Service=ACTIVE and Listener=TCP/<auto-port>.
- [ ] Refresh repeatedly; hostname, port and links remain stable.
- [ ] Verify generated t.me/tg:// link on an external Telegram client.
- [ ] Run another `sudo makia-upgrade` and verify the same working proxy state survives.

## Promotion rule

CI validates syntax, unit regressions, browser behavior and Xray compatibility. Final Telegram reachability remains a real VPS/client UAT item.
