# ⚡ Makia VPS Manager

Modern web-first VPS and access-infrastructure control center for Ubuntu.

**[راهنمای کامل فارسی](README_FA.md)** · **[راهنمای اتصال کاربران](docs/CLIENT-GUIDE-FA.md)**

> **Current release candidate:** `v0.17.0-rc2`  
> CI validation is required before merge; a real-host UAT is still required before any Stable designation.

## v0.17.0-rc2 WireGuard runtime + endpoint verification
- WireGuard peer issuance now preflights the real server runtime (service, interface, UDP listener, IPv4 forwarding, FORWARD and NAT) and uses the guarded repair path when required.
- DNS-only WireGuard domains must resolve directly to the VPS IPv4. Domain exports also include a direct-IP fallback `.conf` and QR when a matching public IPv4 is available.
- The IP / Domain Readiness matrix now requires real SSH and Xray listeners instead of treating a green systemd unit as sufficient.
- CI includes a Linux network-namespace WireGuard handshake test for both direct IPv4 and hostname endpoints.
- A healthy VPS runtime does **not** prove that a carrier/ISP permits WireGuard UDP. Final Stable still requires an external-client UAT over the real network path.

## v0.16 Owner Control Center & consent-based Remote Support
- A separate Owner Control Center manages customers, installations, signed licenses, renewals, revocations, support tickets and owner audit history.
- Commercial licenses use signed online leases: revocation is enforced on sync, while temporary outages use a bounded offline grace period.
- Renewals are delivered automatically as a higher signed license revision; the customer does not need to paste a new code.
- Offline licenses remain available for owner/self-hosted installations.
- Customer admins can create a one-time Remote Support grant (15–120 minutes, Read-only or Operator). There is no master password or permanent backdoor.
- Sensitive identity and export operations stay local-admin-only even during an Operator support session.
- Owner Control Center is deployed separately and keeps the Ed25519 private signing key outside the customer package and outside GitHub.
- Persian deployment guide: `docs/OWNER-CONTROL-CENTER-FA.md`.
- Remote Support threat model: `docs/REMOTE-SUPPORT-SECURITY-FA.md`.

## v0.14 Glass Aurora & OpenVPN domain reliability
- Glass Aurora is the new default panel experience, with a glass sidebar/topbar, translucent blue-violet surfaces, responsive service cards, live resource rings and a reorganized operational dashboard.
- Existing installations migrate once to the Glass theme; Midnight, AMOLED and Graphite remain selectable.
- OpenVPN domain profiles now use explicit IPv4 transports (`udp4` / `tcp4-client`) so an unrelated AAAA record cannot silently divert a profile away from the IPv4 server.
- OpenVPN exports are regenerated against the current panel domain and current server transport, preserving existing EasyRSA client credentials.
- Domain Diagnostics checks A/AAAA resolution, whether the A record reaches this VPS, the OpenVPN listener and service state, and warns about CDN/proxy records.
- Panel HTTPS/Let's Encrypt is not the OpenVPN tunnel certificate: OpenVPN continues to use its own EasyRSA PKI.
- A proxied Cloudflare/CDN record is not a raw OpenVPN transport. Use a DNS-only A record that resolves directly to the VPS.
- OpenVPN TCP/443 cannot directly share the same IP:port with Nginx HTTPS/TCP 443; UDP/443 can coexist with HTTPS/TCP 443.

## v0.13.1 Xray runtime reliability & user guides
- Xray config mutations preserve access for the actual systemd service user instead of leaving root-only `0600` files behind.
- Xray Diagnostics compares root validation with service-user validation and surfaces recent `journalctl -u xray` output.
- Repair & Restart creates a backup, repairs ownership/TLS runtime files, validates as the service user and restarts only after validation.
- Xray installation is pinned to the same Core version validated in CI: `26.3.27`.
- Let's Encrypt certificates used by Xray are materialized under an Xray-readable `0600` runtime path and refreshed by a Certbot deploy hook.
- A public Persian client guide is available at `/help/connect`, and protected delivery bundles include `connection-guide-fa.txt`.
- The admin panel has a dedicated Client Guides view with per-protocol links that can be sent to end users.

## What Makia manages today

### v0.12 QR, NPV and Settings Center
- Xray profiles now have an in-panel QR/Share Center, direct profile QR, subscription QR, Copy Link and QR download
- The public Xray client page shows both direct-profile and subscription QR cards
- SSH delivery can generate an `npvt-ssh://` import link plus QR for NPV Tunnel/NapsternetV-compatible clients, alongside the normal OpenSSH config
- SSH NPV delivery is included inside the encrypted Protected ZIP when enabled
- The proprietary locked `.npv4/.npvt` container format is not fabricated; Makia uses the interoperable share-link/QR path instead
- Settings is now a categorized control center for Panel UI, Domain/TLS, Delivery, Provisioning Defaults, Security/Session and Scoped API tokens
- Provisioning Wizard defaults are stored server-side and loaded from Settings rather than being hard-coded in the browser
- Admin signed-session lifetime is configurable (5 minutes to 30 days) and applies to subsequent logins


### v0.11 Control Center UX
- Rebuilt application shell/sidebar with a dedicated Create Access action and safer event handling
- New Operations Cockpit dashboard with live host, service, access and session data
- New multi-step provisioning wizard: Protocol → Identity → Policy → Review/Delivery
- Access Directory uses delegated `data-action` handlers instead of dynamic inline JavaScript
- Protected ZIP and Native downloads surface backend errors instead of silently failing
- Runtime Self-Test verifies SQLite, server-secret permissions, encrypted artifacts, AES delivery packages and protocol catalog
- Browser CI actually logs in, opens Access Center, downloads/decrypts Protected ZIP, downloads Native config and opens the provisioning wizard
- `makia-uat-smoke` provides a non-destructive real-host verification gate


### Unified Access Center
- Single management surface for SSH, Xray, WireGuard and OpenVPN access profiles
- Create SSH users, Xray clients, WireGuard peers and OpenVPN clients from one place
- Xray Core can be installed from the panel using the official XTLS installer
- Native export per protocol: SSH config fragment, WireGuard `.conf`, OpenVPN `.ovpn`, Xray share/profile files
- AES-256 password-protected delivery ZIP for every newly created access profile
- Encrypted-at-rest access artifacts use the server's Makia secret; raw credentials are not stored as plaintext
- Existing Xray and OpenVPN profiles can be re-exported; legacy WireGuard peers without retained private keys are explicitly marked for reissue
- Central revoke flow for SSH, Xray, WireGuard and OpenVPN


### SSH Account Center
- Server-side PIN 4 / PIN 6 / Easy-8 / strong-password generation
- 1 / 3 / 7 / 15 / 30 / 60 / 90 day presets and custom date
- Extend from the existing future expiry date
- Unlimited-expiry mode
- **Session Limit** and **Device/IP Limit** as separate policies
- Real background enforcement for expiry, concurrent sessions and distinct SSH source IPs
- Search, filters, bulk lock/unlock/disconnect and bulk renewal
- Live source-IP visibility
- Fail2ban baseline on fresh installs/upgrades

> SSH traffic quota is deliberately **not presented as enforced** until a reliable per-user host accounting layer is available.

### Protocol Hub
Guided, operational adapters:
- Xray guided: VLESS, VMess, Trojan, Shadowsocks, Hysteria2, HTTP Proxy, SOCKS5 and Dokodemo/Tunnel
- WireGuard
- OpenVPN
- SSH
- Stunnel

Validated Xray transports:
- RAW/TCP
- WebSocket
- gRPC
- HTTPUpgrade
- XHTTP
- mKCP

Xray security:
- None
- TLS using the panel-managed Let's Encrypt certificate
- VLESS REALITY with generated X25519 keys and Short ID

Advanced Xray JSON editor:
- Read the live config
- Validate with the installed Xray binary before apply
- Backup before change
- Restart/health gate
- Automatic rollback on failed apply

This advanced surface remains available for routing, outbounds, fallbacks, TUN and other engine-level configuration. HTTP Proxy, SOCKS5 and Tunnel/Dokodemo now have dedicated guided workflows.

### Protocol Clients
- First-class protocol-client records
- Secure subscription IDs with Base64, raw and JSON outputs
- Public `/client/<id>` status page for usage, expiry and device policy
- QR/share links
- Expiry
- Traffic quota for Xray clients with per-user stats support
- Persistent cumulative traffic counters across Xray restarts
- Manual traffic reset
- Recurring 7/30/60/90/custom-day traffic reset cycles
- Automatic quota suspension
- Automatic reactivation at the next quota-reset boundary
- Live Xray online-IP/device visibility where supported by the installed Xray core
- IP-limit violation visibility
- Manual suspend/reactivate that actually modifies the Xray config

Per-client traffic enforcement currently applies to VLESS, VMess, Trojan and Hysteria2. Shadowsocks quick profiles are clearly marked as not having independent per-client accounting in this RC.

### WireGuard
- Package install
- Server bootstrap
- IP forwarding/NAT
- Peer provisioning
- Downloadable client configuration

### OpenVPN
- Package/Easy-RSA install
- CA and server PKI bootstrap
- Server configuration
- UDP or TCP-server mode
- NAT/IP forwarding
- Client certificate generation
- Downloadable inline `.ovpn` profile

### Infrastructure / Admin
- CPU/RAM/disk/swap/load/network telemetry
- 24-hour metrics history
- Service health/control allowlist
- Audit log
- Backups
- Update Center
- Multi-node heartbeat foundation
- Admin 2FA
- Scoped API tokens for status, accounts, protocol clients and nodes
- Persistent login-rate limiting
- Owner-only SQLite permissions
- Domain management + Nginx validation/rollback
- Let's Encrypt via Certbot
- Persian / English shell
- Midnight / AMOLED / Graphite themes
- Comfortable / Compact density
- Installable PWA shell
- `makia-doctor` host diagnostics

## Capability honesty

Makia does not render an unimplemented feature as a working button.

The Protocol Hub labels capabilities as:
- **Guided** — dedicated tested Makia workflow exists.
- **Advanced** — supported through the validated Xray configuration editor.
- **Unavailable** — no tested adapter exists in this release.

TUIC v5, AmneziaWG and MTProto are currently listed as unavailable rather than being simulated because they require dedicated sidecar/runtime adapters. See `docs/PARITY-3XUI.md` for the explicit parity matrix.

## Quick install

Run as root on a **fresh Ubuntu 22.04 or 24.04 VPS**:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/install.sh)
```

The installer prints a unique administrator bootstrap password. Change it immediately.

## Update

For installations already using the Makia bootstrap updater:

```bash
sudo makia-upgrade
```

`makia-upgrade` first fetches the newest updater from GitHub, then executes it. This prevents an older local updater from missing newly introduced service units.

### One-time upgrade from v0.7.x or older

Use the bootstrap updater once:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/upgrade.sh)
```

After that, future updates can use `sudo makia-upgrade`.

The updater:
1. creates a backup;
2. downloads the current `main`;
3. updates application and all service units;
4. restarts Makia workers;
5. performs a backend health check;
6. runs `makia-doctor`.

## Diagnostics

```bash
sudo makia-doctor
sudo makia-uat-smoke
```

It checks the Makia backend, Nginx, Policy Enforcer, Metrics Sampler, Protocol Traffic Collector, Fail2ban and installed optional protocol tooling.

## Other commands

```bash
sudo makia-backup
sudo makia-uninstall
```

## Runtime layout

```text
/opt/makia-vps-manager
├── app
├── data
├── .venv
└── VERSION

/etc/systemd/system/
├── makia-vps-manager.service
├── makia-policy-enforcer.service
├── makia-metrics-sampler.service
└── makia-protocol-traffic.service

/etc/nginx/sites-available/makia-vps-manager
/var/backups/makia-vps-manager
```

## Security design

The browser is not given a generic root-shell endpoint. Privileged operations are explicit and validated.

Important:
- Admin passwords remain stronger than SSH user PINs.
- Four-digit SSH PINs are optional and intentionally labelled low-security.
- Use HTTPS before exposing the admin panel publicly.
- Keep Fail2ban active.
- Prefer trusted admin IPs/VPN access where possible.
- Test Xray/WireGuard/OpenVPN changes on a disposable VPS before production.

## Release gate

`v0.10.0-rc1` must pass:
- Python compilation
- unit tests
- Bash syntax
- JavaScript syntax
- dangerous-pattern guard
- packaging contract
- real Ubuntu 22.04/24.04 host UAT

See `docs/UAT-0.12.0-RC1.md` and `docs/PARITY-3XUI.md`.

## License

GPL-3.0-or-later. Third-party source is only incorporated where its license and attribution requirements are compatible.

## Recovery

If Nginx shows `502 Bad Gateway`, check the backend first:

```bash
sudo systemctl status makia-vps-manager --no-pager -l
sudo journalctl -u makia-vps-manager -n 120 --no-pager
curl -v http://127.0.0.1:8787/healthz
```

Reset a forgotten administrator password locally on the VPS:

```bash
sudo makia-reset-admin --generate
```

Or choose the password interactively:

```bash
sudo makia-reset-admin
```

If the TOTP secret is also unavailable:

```bash
sudo makia-reset-admin --generate --disable-2fa
```

From v0.9.1-rc1 onward, the updater creates a runtime rollback point before replacing the application and automatically restores the previous runtime when the new backend fails its health check.


## NPV / QR security note
A QR code or `npvt-ssh://` / Xray share URI contains credentials needed by the client application. Once a user imports a working profile, no panel can cryptographically prevent that authorized user from extracting or forwarding those credentials. Makia therefore combines easy import with server-side expiry, concurrent-session/IP limits, quota where supported, revocation, and encrypted operator delivery packages.

## Portable VPS migration

For migration-safe deployments, configure a stable panel/domain name and provision clients with that domain instead of a server IP. In **Backups → Portable Migration**, Makia can build an AES-256 encrypted migration bundle containing application data and the protocol/service state required to preserve credentials. On a freshly installed destination VPS, validate and restore it with:

```bash
sudo makia-restore-portable /path/to/makia-portable-....zip
sudo makia-restore-portable /path/to/makia-portable-....zip --apply
sudo makia-uat-smoke
```

The restore preserves Xray/REALITY keys, WireGuard keys, OpenVPN PKI, the Makia server secret and managed SSH password hashes. After restore and validation, move the domain's DNS A/AAAA record to the destination VPS. DNS propagation can still cause a short cutover window; the goal is credential continuity, not an impossible zero-packet-loss guarantee.

WireGuard compatibility defaults (UDP/443, MTU 1280, keepalive 15) address common NAT/MTU issues but cannot guarantee operation on networks that filter WireGuard itself. Use the validated Xray/REALITY path where a different transport is required.
