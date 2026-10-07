# Makia VPS Manager 1.6.4 — Release / UAT Gate

Release focus: **WireGuard restricted-network compatibility and HTTPS reliability**, while preserving the stable 1.6.3 WStunnel 443, Stealth, Browser Gateway and Client Platform contracts.

## 1.6.4 WireGuard compatibility closure

- Existing WireGuard peers, public/private keys, tunnel addresses and active listen port are preserved.
- New client defaults use MTU 1280, PersistentKeepalive 15, full IPv4 routing and DNS fallback `1.1.1.1, 8.8.8.8`.
- Server-side WireGuard forwarding installs bidirectional TCP MSS clamping with `--clamp-mss-to-pmtu` to reduce HTTPS stalls on lower-MTU paths.
- The restricted-network profile is opt-in from the panel and creates a backup before changing `wg0.conf`.
- The profile must never silently move an existing WireGuard listen port because that would invalidate already-issued client profiles.
- UDP/443 remains the recommended raw-WireGuard port for new deployments where available.
- Raw WireGuard cannot be claimed to bypass protocol-level UDP/WireGuard blocking. WStunnel 443 is the fallback when the access network blocks raw WireGuard.

## Release invariants

- Existing Xray UUIDs, Outline keys, WireGuard keys, SSH credentials and OpenVPN certificates are not rotated by upgrade.
- Existing WStunnel 443 and Stealth configuration is preserved.
- Nginx remains the only public TCP/443 owner for panel/WStunnel HTTPS.
- Browser Gateway remains independent on its configured TLS listener.
- WireGuard server tuning changes only MTU/firewall compatibility rules; it does not recreate peers or address pools.
- A failed WireGuard compatibility apply restores the prior `wg0.conf` and sysctl state.

## Repository gates

Required on the exact candidate SHA:

- CI: PASS
- Python/JS/Bash syntax: PASS
- Unit tests: PASS
- Ubuntu 22.04 Clean Install: PASS
- Ubuntu 24.04 Clean Install: PASS
- Upgrade from exact stable 1.5.1: PASS
- Upgrade from 1.3.0: PASS
- Existing-user/credential preservation: PASS
- Windows Connector Build: PASS
- Browser Extension Build: PASS
- Android Connector regression Build: PASS or explicitly documented non-server blocker if only release packaging is affected
- WireGuard restricted-network contract tests: PASS
- WStunnel 443 regression tests: PASS

## Real-host UAT

1. Create a Full Migration backup.
2. Run `sudo makia-upgrade`.
3. Run `sudo makia-doctor` and `sudo makia-uat-smoke`.
4. Confirm existing users still connect before changing WireGuard runtime tuning.
5. Open **Settings → WG / OpenVPN → WireGuard · Restricted Network**.
6. Apply **Server tuning**.
7. Confirm diagnostics show:
   - WireGuard service/interface/listener READY;
   - forwarding + NAT READY;
   - MTU = 1280;
   - TCP MSS clamp IN = READY;
   - TCP MSS clamp OUT = READY.
8. Confirm existing peer public keys and tunnel addresses did not change.
9. Test at least one existing WireGuard client on the intended mobile/fixed access network.
10. Test HTTPS-heavy sites and large downloads for stalls/timeouts.
11. Create one new peer and confirm defaults: MTU 1280, Keepalive 15, full IPv4 route, DNS fallback.
12. If the access network blocks raw WireGuard/UDP, test the same account with WStunnel 443 instead of repeatedly changing MTU/ports.
13. Confirm Xray/OpenVPN/WStunnel/Browser Gateway remain operational.

## Scope note

This release improves server/client compatibility for constrained NAT/MTU paths. It does **not** claim that raw WireGuard can always cross every ISP or national filtering policy.
