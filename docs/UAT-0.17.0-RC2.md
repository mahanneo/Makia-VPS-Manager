# Makia v0.17.0-rc2 — Protocol Runtime / WireGuard External UAT

## هدف

این RC روی Root Causeهای «Service Running ولی Client وصل نمی‌شود» تمرکز دارد. معیار PASS فقط Syntax یا systemd نیست؛ Runtime، Listener، DNS، Forwarding، NAT و خروجی Client بررسی می‌شوند.

## Automated CI Gates

- Python compile + Unit tests
- Bash syntax including `tests/*.sh`
- JavaScript syntax
- Playwright browser smoke
- Xray Core `26.3.27` guided matrix
- OpenVPN domain regression
- Licensing / Owner Control Center / consent-based Remote Support regression
- WireGuard runtime/repair regression
- WireGuard dual Domain/IP delivery regression
- Linux network-namespace WireGuard handshake:
  - direct IPv4 endpoint
  - hostname endpoint resolving to the same IPv4

## Protocol IP / Domain Matrix

از Protocol Hub → **IP / Domain Readiness**، IPv4 عمومی VPS و سپس دامنه مستقیم همان VPS را جداگانه بررسی کنید.

| Protocol | IP | Domain | Runtime gate |
| --- | --- | --- | --- |
| SSH / NPV | Required | Required | ssh service + effective TCP listener |
| Xray | Required where profile supports it | Required for TLS/SNI and supported transports | service + every configured inbound listener |
| WireGuard | Required | Required when DNS-only A points directly to VPS | wg0 + UDP listener + forwarding + FORWARD + NAT |
| OpenVPN | Required | Required when DNS-only A points directly to VPS | service + correct TCP/UDP listener + IPv4-safe profile |

## WireGuard Server

- `wg-quick@wg0` active.
- `wg show interfaces` contains `wg0`.
- Config has valid `Address`, `ListenPort`, optional MTU and preserved peer keys.
- `net.ipv4.ip_forward=1`.
- FORWARD rules for input/output `wg0` exist.
- Source-scoped MASQUERADE exists for the WireGuard subnet on the actual uplink.
- UFW, when active, allows the configured WireGuard UDP port.
- Repair creates a backup before mutation and rolls back if post-restart runtime validation fails.

## WireGuard Peer / Delivery

Create one peer with the VPS public IPv4:
- Endpoint is direct IPv4.
- MTU, DNS, PersistentKeepalive and AllowedIPs match the requested/default settings.
- Import QR/config into an external client and verify handshake, DNS and routed Internet.

Create one peer with the VPS domain:
- Domain must have a usable A record that resolves directly to this VPS.
- HTTP/CDN proxy is not accepted for raw WireGuard.
- Package contains the domain `.conf` + QR.
- Package also contains direct-IP fallback `-ip.conf` + `-ip-qr.svg` when a matching VPS IPv4 is available.
- Test both domain and direct-IP fallback from the external client.

## External UDP Limitation

A PASS on server Runtime and CI does **not** prove that WireGuard UDP is permitted by the user's ISP, carrier, enterprise network or upstream firewall. Makia must not claim that WireGuard is guaranteed to work in Iran or any specific network.

If server Runtime is healthy but peers show no recent handshake:
- test the same peer from another network;
- test the direct-IP fallback;
- verify provider/security-group UDP rules;
- verify the VPS UDP port externally;
- treat ISP/carrier/upstream UDP filtering as a possible cause.

Stable is blocked until at least one real external-client handshake is confirmed on the target VPS.

## OpenVPN

- Verify service and transport-specific listener.
- Domain A record must point directly to VPS for raw VPN.
- Test both Domain and direct IPv4/hybrid fallback externally.
- TCP 443 must not collide with Nginx HTTPS on the same IP:port.

## Xray

- Xray Core validation must PASS with 26.3.27.
- Service must stay active after client/profile creation.
- Every configured inbound must have a real TCP or UDP listener.
- Test representative direct-IP profile where applicable.
- Test domain/TLS/SNI/REALITY profile according to its transport constraints.

## SSH / NPV

- Verify effective SSH port and TCP listener.
- Test login by public IPv4.
- Test login by direct domain.
- Verify NPV import/link still points to the selected public endpoint and existing session/device policy is preserved.

## UI / Sidebar

- All sidebar views open without JavaScript errors.
- All rendered `data-action` controls have a handler.
- Glass Aurora scrollbar is thin, transparent-track and non-native-white.
- RTL and LTR layouts remain usable on desktop and mobile.
- Diagnostics/Repair actions remain visible only where the protocol/runtime supports them.

## Release Decision

This is **Release Candidate only**.

Do not mark Stable until:
1. GitHub CI is fully green on the PR head.
2. Upgrade succeeds on the real VPS.
3. `makia-doctor` and `makia-uat-smoke` pass.
4. External-client IP and Domain tests pass for WireGuard and the required protocol set.
