# Makia 0.18.0 — IP / Domain and host UAT

This document separates the repository release gate from real network validation on the installed VPS.

## Upgrade gate

Update the existing installation with `sudo makia-upgrade`. Confirm `/opt/makia-vps-manager/VERSION` is `0.18.0`, run `sudo makia-doctor` and `sudo makia-uat-smoke`, and preserve the updater backup until client UAT passes. Do not reinstall over the active instance.

## Access Center choice

For each new SSH/NPV, Xray, WireGuard or OpenVPN access, select **Domain** or **Public IPv4** and review the exact endpoint before creation. Public IPv4 mode rejects private addresses. Domain mode requires an A record. Direct SSH/OpenVPN/WireGuard domains are checked against a VPS public IPv4 when it is visible locally; VPS instances behind provider NAT require a separate comparison to the provider's public IP. SSH also rejects an AAAA record that does not match a public IPv6 configured on the VPS. OpenVPN client transport is explicitly IPv4. Xray may intentionally use a supported proxy transport, so its DNS record is not required to match a locally assigned VPS IP.

An exported QR/profile keeps the selected endpoint. Changing the panel domain does not alter a profile already imported on a client. WireGuard saved peers can change Endpoint in Access Center without rotating keys; import the refreshed profile afterwards. Legacy peers without a retained private key require reissue.

| Protocol | IP profile | Domain profile | External client pass condition |
|---|---|---|---|
| SSH / NPV | Connect to selected IPv4 | Direct A record and connect | Login and application traffic |
| Xray | Supported transport with IPv4; TLS needs valid SNI/certificate | Transport, SNI and certificate as configured | Client handshake and traffic |
| WireGuard | Public IPv4 and UDP port | Direct DNS-only A; AAAA only with a working VPS IPv6/UDP path | Fresh handshake, RX/TX, DNS and routed internet |
| OpenVPN | IPv4 client transport | Direct DNS-only A; IPv4 client transport | TLS connection, tunnel traffic and DNS |

Test from a device outside the VPS on both Wi-Fi and mobile data. If server-side WireGuard checks pass but there is no handshake, inspect the client endpoint/key, provider security group, upstream NAT, UDP firewall and network filtering. No repository test can guarantee that raw UDP works on every network.

## Code release gate

The exact PR commit must pass unit/regression, Python compile, Bash/JS checks, Playwright Browser Smoke, Xray Core 26.3.27 and existing licensing/owner/remote-support contracts. Repeat CI on `main` after merge. Host UAT above remains separate and must be reported honestly.
