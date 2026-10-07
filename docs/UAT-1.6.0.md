# Makia VPS Manager 1.6.0 — Release / UAT Gate

Release focus: **OpenVPN over WebSocket/TLS on HTTPS TCP/443**, while preserving all 1.5.1 Browser Gateway, Windows Full Device, Android UAT, Client Platform and disaster-recovery contracts.

## Release invariants

- Existing Xray UUIDs, Outline keys, WireGuard keys, SSH credentials and OpenVPN certificates are not rotated by upgrade.
- Existing OpenVPN UDP/TCP, Stealth/Stunnel and WireGuard-over-WSS modes remain unchanged unless the operator explicitly configures the new mode.
- Nginx remains the only public TCP/443 listener. OpenVPN WStunnel shares HTTPS/443 through a managed secret WebSocket path; it does not bind a second public 443 socket.
- The WStunnel backend is loopback-only and destination-restricted to the dedicated loopback OpenVPN backend.
- Every WStunnel OpenVPN user receives an isolated certificate identity that can be revoked without revoking a same-named ordinary OpenVPN profile.
- WStunnel Client Platform bindings enforce account enable/disable, expiry and quota on the dedicated OpenVPN backend; concurrent sessions are enforced through the root-only Unix OpenVPN management socket.
- WStunnel traffic accounting tracks each concurrent OpenVPN session independently before aggregating usage, so one reconnect/disconnect cannot reset another session's counter.
- Client Platform device/session registration limits remain part of the authenticated Makia client flow; an exported static OVPN package is a credential and must not be described as hardware-bound.
- The public WStunnel path has per-IP Nginx request/connection abuse guards in addition to the unguessable path and per-user OpenVPN certificate.
- Full Migration must preserve the Nginx route, WStunnel env, dedicated OpenVPN backend and systemd unit.

## Repository gates

Required on the exact candidate SHA:

- CI: PASS
- Bash syntax: PASS
- Python/JS compile: PASS
- Ubuntu 22.04 Clean Install: PASS
- Ubuntu 24.04 Clean Install: PASS
- Upgrade from 1.3.0: PASS
- Upgrade from exact stable 1.5.1 (`13c45ed90e32db39dc2dd10e0a3964fb193fa9d6`): PASS
- Existing-user/identity preservation across the 1.5.1 upgrade: PASS
- Windows Full Device Connector Build: PASS
- Android Connector regression Build: PASS
- Browser Extension Build: PASS
- OpenVPN WStunnel unit/contract tests: PASS
- Portable migration tests: PASS

## Real-host UAT

Before enabling the mode on a production VPS:

1. Create and copy off-host a Full Migration backup.
2. Verify existing users can connect before update.
3. Upgrade with `sudo makia-upgrade`.
4. Run `sudo makia-doctor` and `sudo makia-uat-smoke`.
5. Confirm the panel HTTPS/443 remains reachable.
6. In **Network / Ports → WStunnel 443**, configure the existing panel domain.
7. Confirm:
   - `nginx -t` PASS;
   - Nginx remains the only public TCP/443 listener;
   - `makia-openvpn-wstunnel` active;
   - `openvpn-server@makia-ws` active;
   - loopback bridge/backend listeners are not public.
8. Create one disposable Client Platform account and one WStunnel access, then bind that artifact to the account.
9. Set a small test quota, short expiry window and concurrent limit; confirm usage appears and excess concurrent sessions are disconnected.
10. Disable the account and verify the active WStunnel session is disconnected and reconnect is denied; re-enable it and verify access returns without issuing a new certificate.
11. Windows: install the current Makia Windows package plus OpenVPN runtime, then use Direct Connect.
12. Verify public IP, DNS and reconnect over a restrictive network.
13. Revoke the disposable WStunnel access and verify reconnect fails permanently.
14. Verify ordinary OpenVPN/WireGuard/Xray/Outline users remain unchanged.
15. Create a Full Migration bundle and perform restore proof on a disposable replacement host when practical.

## Mobile scope

- Windows: Direct Connect supported by Makia Connector.
- Android: 1.6.0 build regression is required, but OpenVPN WStunnel Direct Connect is **not** claimed yet; deliver the OVPN + WStunnel command for manual compatible clients.
- iOS/iPadOS: PWA/import only; no native WStunnel claim.
- Browser VPN: separate Makia Browser Gateway product; this full-device transport does not replace it.

See [WSTUNNEL-OPENVPN-443.md](WSTUNNEL-OPENVPN-443.md).
