# Makia v0.20.0 — open access validation

## Upgrade and installation

1. On an existing v0.19 server, save a backup and run `sudo makia-upgrade`. Confirm version 0.20.0 and run `sudo makia-uat-smoke`. The updater makes a runtime backup and rolls back after failed health checks.
2. On a clean Ubuntu 22.04/24.04 VPS, use the installation instructions in README, sign in as local admin and check `/healthz`.
3. On a previous installation with no license or an expired/revoked license, confirm all four protocol cards, Protocol Hub, WireGuard, Backups and Nodes load. No activation or Owner server is needed.
4. Check old accounts, client profiles and exports after upgrade. Legacy license data in the database must have no effect on access.

## Security

- Protected APIs require login. Mutations still require CSRF/request checks.
- Enable 2FA and reauthenticate. Create a short Remote Support grant under Support and confirm one-time use and revocation. A readonly grant cannot mutate; an Operator grant cannot change identity settings or export credentials.
- Verify support request delivery or copy the locally saved request if no webhook is configured.

## External client matrix

For each SSH/NPV, Xray, WireGuard and OpenVPN, create one profile with the public IPv4 and another with a direct DNS-only A record. Import the native profile into a real client outside the VPS network and confirm connection and internet traffic. Record DNS, listeners, provider firewall, WireGuard handshake, OpenVPN forwarding/NAT and Xray TLS/REALITY SNI or certificate as appropriate. CI cannot prove external client reachability.
