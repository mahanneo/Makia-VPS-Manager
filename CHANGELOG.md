# Changelog

## [0.17.0-rc2] - 2026-09-26

### WireGuard Repair Hardening
- Fixed a legacy-config repair bug where missing `PostUp` / `PostDown` directives could be appended after the first `[Peer]` block, producing an invalid wg-quick configuration.
- Repair now inserts missing runtime directives inside the `[Interface]` section before any peer blocks.
- WireGuard sysctl state is restored when runtime repair fails and rolls back.
- Diagnostics now explicitly distinguish server-side health from real external UDP reachability. If peers exist but no recent handshake is observed, Makia warns about endpoint/key mismatch, upstream firewall/NAT, ISP/network UDP filtering, or datacenter filtering.
- This release candidate still requires real external-client VPS UAT before Stable.


## [0.17.0-rc1] - 2026-09-26

### WireGuard Reliability
- Added deep WireGuard diagnostics for service state, wg0 presence, UDP listener, IPv4 forwarding, FORWARD rules, source-scoped NAT, endpoint DNS/IP readiness and peer handshake/traffic state.
- Added safe WireGuard Repair Runtime with pre-change backup, idempotent top-priority FORWARD rules, source-scoped MASQUERADE, UFW UDP allowance, restart validation and rollback on failure.
- New WireGuard bootstraps use the hardened forwarding/NAT rules by default.
- Safe updater now detects legacy wg0, attempts runtime repair before the final host smoke gate and rolls back when an already-healthy WireGuard runtime is broken by the update.
- makia-doctor and makia-uat-smoke now gate WireGuard forwarding, NAT and UDP listener health.

### IP / Domain Compatibility
- Added Protocol Hub IP / Domain Readiness Matrix for SSH, Xray, WireGuard and OpenVPN.
- WireGuard now diagnoses direct-IP and DNS-only domain endpoints and flags wrong/proxied A records and incompatible IPv6-only paths.
- Existing OpenVPN domain/IP diagnostics remain integrated.
- Added regression tests for WireGuard client profiles using both IPv4 and domain endpoints and for endpoint readiness aggregation.

### UI
- Replaced the browser-native white sidebar scrollbar with a thin Glass-style scrollbar and matching scroll surfaces.
- Added WireGuard Diagnostics / Repair actions and peer handshake telemetry in Protocol Hub.

### Update Safety
- Preserved MAKIA_SUPPORT_WEBHOOK_TOKEN when loading owner/support configuration during updates.
- Updated version and client shell cache to v0.17.0-rc1.

### Release status
Release candidate. CI validates runtime contracts and config generation; final Stable still requires one real external-client UAT for WireGuard/OpenVPN/Xray/SSH over both the public IPv4 and the direct DNS-only domain.

## [0.16.0-rc1] - 2026-09-26

### Owner Control Center
- Added a separate owner-only FastAPI control plane that is not installed on customer VPS instances.
- Customer, Installation, License, Ticket and Owner Audit management now have a dedicated Glass-style console.
- Commercial licenses are Ed25519-signed, bound to the customer's Installation ID and issued with a per-license synchronization secret.
- Renewing a license increments its revision; customer panels obtain the replacement signed code automatically during lease synchronization.
- Revocation is enforced through a signed online lease. Client panels retain a bounded offline grace period during temporary control-plane outages.
- Offline signed licenses remain supported for Owner/self-hosted use where online revocation is not desired.
- Owner Control Center requires both a strong password and TOTP, includes login throttling, keeps the private signing key outside the repository and binds only to 127.0.0.1 behind a hardened systemd service.

### Consent-based Remote Support
- Added customer-generated one-time support grants with 15–120 minute lifetime and Read-only or Operator scope.
- No global master password or permanent support backdoor exists.
- Support codes are stored only as hashes, are single-use for login and the resulting session is revalidated against the active grant on every request.
- Local administrator can revoke the grant immediately; creating a new grant invalidates the previous active grant.
- Remote support cannot change administrator identity controls, manage API tokens, remove licenses, create support grants, export credentials or download backups.
- Remote support activity uses a distinct audited actor identity.
- Valid support grants can temporarily bypass an admin CIDR allowlist without weakening that policy for normal logins.

### Central Support Inbox
- Customer ticket delivery can now authenticate to Owner Control Center using a root-only bearer token.
- makia-owner-config supports --control-plane and --support-token.
- Owner Console stores and manages incoming support tickets.

### Verification
- Added unit coverage for online active/revoked/grace license states, automatic renewal revisions and remote-support grant lifecycle.
- Browser smoke now exercises one-time Remote Support login.
- Added v0.16 Owner Control Center / Remote Support UAT contract.

### Release status
Release candidate only. Stable requires a real Owner Control Center deployment with HTTPS, customer license renewal/revocation rehearsal and a real remote-support session UAT.

## [0.14.0-rc1] - 2026-09-26

### Glass Aurora interface
- Replaced the default panel shell with the Glass Aurora visual system selected for Makia: translucent blue/violet surfaces, cyan highlights, atmospheric background, glass sidebar/topbar, responsive cards and modal surfaces.
- Rebuilt the dashboard structure around live service health, four operational summary cards, real CPU/RAM/Disk rings, live network history, access mix and current sessions.
- Added a one-time UI generation migration so existing installations switch to Glass Aurora after upgrade while Midnight, AMOLED and Graphite remain selectable.
- Extended the glass treatment to Login/2FA, Settings, Access, Protocol, Guide and modal surfaces without changing backend action ownership.
- Bumped the service-worker shell cache generation so upgraded browsers do not retain the previous visual shell.

### OpenVPN domain reliability
- Clarified that panel HTTPS/Let's Encrypt and OpenVPN TLS are separate: OpenVPN uses its own EasyRSA CA/PKI and the domain is the transport endpoint.
- New and re-rendered OpenVPN profiles now use explicit IPv4 transports (`udp4` / `tcp4-client`) to avoid a bad AAAA/IPv6 preference breaking a domain that otherwise works by IPv4.
- Added `auth-nocache`, retry behavior and server certificate-name verification to generated OpenVPN profiles.
- Existing OpenVPN artifacts are re-rendered at export time using the current panel domain, so users do not need new client certificates after a domain/IP migration.
- Added OpenVPN Domain Diagnostics for A/AAAA resolution, VPS IPv4 matching, systemd state, socket listener, transport/port and PKI certificate metadata.
- Added guarded OpenVPN IPv4 runtime normalization with backup and rollback.
- Added explicit warnings for proxied/CDN DNS records and for OpenVPN TCP/443 colliding with Nginx HTTPS on the same IP; UDP/443 can coexist with HTTPS/TCP 443.
- Added OpenVPN and WireGuard to the allowlisted Services control surface.

### Verification
- Added unit coverage for domain-based OpenVPN rendering, IPv4 transport selection, DNS mismatch detection, TCP/443 collision warning, runtime normalization and current-domain re-export.
- Browser smoke now asserts the Glass Aurora dashboard structure and OpenVPN Domain Diagnostics modal.
- Existing Xray 26.3.27 real-core matrix remains mandatory.

### Release status
Release candidate only. Stable requires real VPS visual/UAT validation and a real OpenVPN domain test with a DNS-only A record pointing directly to the VPS.

## [0.13.1-rc1] - 2026-09-26

### Xray runtime failure repair
- Fixed a service-permission mismatch where Makia could replace `config.json` as root-only `0600` while the official Xray systemd unit runs as a non-root install user.
- Every Makia-owned Xray config mutation now preserves secure ownership for the actual systemd user and validates the active config as that user before restart.
- Added authenticated Xray Diagnostics with root-vs-service-user config validation, Core version checks, service state, permission hints and recent systemd journal output.
- Added guarded Repair & Restart with pre-repair backup and rollback.
- Xray installation is pinned to Core `v26.3.27`, matching the CI validation target.
- TLS certificates used directly by Xray are copied to a dedicated `0600` runtime directory owned by the Xray service user.
- Added a Certbot deploy hook so renewed Let's Encrypt certificates are synchronized, validated and picked up by Xray.

### Client education
- Added the public Persian `/help/connect` page for Xray, WireGuard, OpenVPN and SSH/NPV import workflows.
- Added a Client Guides view to the admin sidebar with per-protocol shareable guide URLs.
- Public Xray client pages link directly to the Xray guide.
- Protected delivery packages now include `connection-guide-fa.txt`.
- Added comprehensive Persian GitHub documentation in `README_FA.md` and `docs/CLIENT-GUIDE-FA.md`.

### Runtime audit
- Self-Test now treats an installed Xray Core with invalid config, unreadable service-user config or inactive runtime as an explicit failure.
- Services and Protocol Hub expose Xray Diagnose/Repair actions instead of showing only a generic failed state.

### Release status
Release candidate only. Stable still requires real-host upgrade/repair UAT, external client connectivity, TLS renewal rehearsal and the existing migration/network gates.

## [0.13.0-rc1] - 2026-09-26

### WireGuard compatibility controls
- Added configurable WireGuard UDP port, MTU, PersistentKeepalive, AllowedIPs and tunnel CIDR.
- New compatibility defaults use UDP/443, MTU 1280, 15-second keepalive and IPv4 full-tunnel to reduce common NAT/MTU failures.
- WireGuard client profiles prefer the configured panel domain as their endpoint, supporting DNS-based VPS cutover without changing client credentials.
- The panel explicitly warns that these settings cannot guarantee connectivity where the WireGuard protocol itself is filtered; Xray/REALITY remains the alternative transport path.

### Xray full-core administration
- Promoted the existing validated Advanced JSON editor into Settings as the official full-core path.
- Guided provisioning remains a safe subset, while administrators can apply any configuration supported by the installed Xray Core through JSON validation.
- Advanced apply continues to run Xray's own config test and rollback on failure.
- Domain/TLS provisioning remains backed by Nginx and Certbot/Let's Encrypt.

### Portable VPS migration
- Added an AES-256 password-protected Portable Migration Bundle downloadable from the panel.
- The bundle carries a consistent Makia data/SQLite snapshot, the server .secret, Xray configuration/REALITY keys, WireGuard server and peer keys, OpenVPN PKI, Nginx config, Let's Encrypt state and managed SSH password hashes.
- Added `makia-restore-portable` for restoring the bundle onto a fresh Makia VPS while preserving user credentials.
- Restore validates bundle format and archive paths, installs missing protocol engines when needed, restores services and runs backend/Xray/WireGuard health checks.
- Existing client credentials remain valid after migration when the same domain is retained and DNS is cut over to the destination VPS.

### Verification
- Added unit coverage for WireGuard compatibility validation/profile generation and portable migration bundle contents.
- Browser smoke now covers WireGuard Settings V2 persistence and encrypted Portable Migration download.
- Host UAT now verifies WireGuard runtime when configured and the portable restore command installation.

### Release status
Release candidate only. Stable requires a real two-VPS migration rehearsal, DNS/TLS cutover, external Xray client tests and WireGuard tests on target networks.

## [0.12.0-rc1] - 2026-09-26

### Xray QR and subscriptions
- Added an authenticated QR/Share Center for managed Xray access profiles.
- Added direct connection QR, Copy Link, downloadable SVG QR and downloadable subscription QR.
- Share Center now shows parsed connection metadata for VLESS, VMess, Trojan, Shadowsocks and Hysteria2 without exposing unrelated server secrets.
- Protected Xray delivery packages now include direct QR, profile metadata, subscription URL text and subscription QR when subscription delivery is enabled.
- Public client access pages now render direct-profile and subscription QR cards, direct Copy Link and QR download actions.
- Added persisted controls for Subscription endpoint, public Client Page and generated Subscription format (`base64` or `raw`).
- Subscription QR URLs are generated from the current panel origin so a later domain change does not leave the admin Share Center using a stale URL.

### SSH → NPV Tunnel delivery
- Added `npvt-ssh://` share-link generation for SSH-Direct profiles.
- Added NPV QR and import-link text files to SSH encrypted delivery artifacts.
- Added configurable profile prefix, NPV DNS mode, UDPGW port and transparent-DNS flag.
- Existing SSH artifacts with retained encrypted credentials can be upgraded to NPV delivery on demand.
- The proprietary locked `.npv4/.npvt` file container is intentionally not fabricated; Makia uses the share URI / QR import path.

### Settings Center V2
- Rebuilt Settings into Panel General, Domain/Nginx/HTTPS, SSH Defaults, Xray Defaults, WireGuard/OpenVPN Defaults, Delivery/NPV, Subscription, Admin Security, API Tokens and Backup/Recovery categories.
- Added server-persisted provisioning defaults for SSH, Xray, WireGuard and OpenVPN.
- Added configurable admin session lifetime.
- Added QR/NPV delivery settings and real backend validation.
- The provisioning wizard now reads defaults from the backend instead of hard-coded JavaScript values, including SSH selection from the generic wizard.
- Backup/Recovery exposes only implemented snapshot/list/self-test operations; no decorative restore action is presented.

### Verification
- Added NPV share-link round-trip and payload tests.
- Added Xray share-metadata regression coverage across VLESS, VMess, Trojan, Shadowsocks and Hysteria2.
- Added regression coverage for legacy encrypted SSH artifacts upgrading to NPV delivery.
- Browser CI verifies Xray QR/Share details, direct and subscription QR downloads, protected package contents, public QR portal, all Settings V2 tabs and persisted operator/subscription settings.
- Existing Xray 26.3.27 real-core smoke remains required.

### Release status
Release candidate. Stable still requires real NPV mobile import, external Xray QR connection, and host UAT.

## [0.11.2-rc1] - 2026-09-26

### Xray 26.3.27 config-format hotfix
- Fixed Xray validation failures where Makia generated temporary names such as `config.json.makia-tmp`; current Xray infers config format from the final extension and rejected those files before parsing JSON.
- All Xray mutation paths now create unique same-directory temporary files ending in `.json`.
- Makia now also passes `-format=json` explicitly to every Xray config validation call.
- The fix covers guided inbound creation, tunnels, inbound removal, client disable/enable, manual validation and advanced config apply.

### Regression protection
- Added unit coverage for JSON temp suffixes, uniqueness and explicit Xray CLI format selection.
- Added a CI job that downloads official Xray Core `v26.3.27` and validates a Makia-generated VLESS + XHTTP + REALITY configuration with the real Xray binary.
- Host `makia-uat-smoke` now validates the currently installed Xray configuration when Xray is present.

### Release status
Hotfix release candidate. Real-host creation and an external-client connection remain the final Xray UAT steps before Stable.

## [0.11.1-rc1] - 2026-09-26

### Xray endpoint hotfix
- Fixed the malformed endpoint-validation character class that rejected valid IPv4 addresses and hostnames such as `178.83.45.215`.
- Replaced ad-hoc endpoint regexes with canonical IPv4/IPv6/IDNA hostname validation shared by Xray, WireGuard, OpenVPN and Xray Tunnel targets.
- IPv6 endpoints are normalized correctly and bracketed only when serialized into URI/host:port forms.

### Guided Xray safety
- Guided VLESS now defaults to XHTTP + REALITY instead of public VLESS with `security=none`.
- Public VLESS/Trojan profiles using `security=none` are rejected with an actionable REALITY/TLS message instead of creating a profile that will not work reliably on the public Internet.
- REALITY server config now emits the current canonical `target` field instead of legacy `dest`.

### Tests
- Added IPv4/domain/IPv6 endpoint validation coverage.
- Added public/private endpoint classification coverage.
- Added a regression test for the exact public-IP VLESS failure path.
- Added XHTTP + REALITY schema coverage.

### Release status
Hotfix release candidate. Real-host Xray creation and client connection UAT is still required before Stable.

## [0.11.0-rc1] - 2026-09-26

### Functional UI repair
- Fixed the Protected ZIP/Native/Manage/Revoke button class of failures caused by dynamic JSON strings being injected into quoted inline `onclick` attributes.
- Access actions now use encoded `data-*` attributes plus one delegated action dispatcher.
- Native and protected downloads now use fetch/blob handling with visible backend errors and no-store/nosniff response headers.
- Protected ZIP is verified in memory on the server before being returned.

### UX redesign
- Rebuilt sidebar/application shell.
- Replaced the old Access Center table with a responsive Access Directory and protocol launch cards.
- Added a four-step provisioning wizard: Protocol, Identity, Policy, Review/Delivery.
- Rebuilt Overview as an Operations Cockpit using live server, access, protocol, service and session data.
- Added modern success/delivery, protocol setup and diagnostics modals.

### Verification
- Added `/api/diagnostics/self-test` for DB, secret mode, artifact decryption, AES ZIP and protocol/service checks.
- Added `/api/access/{kind}/{key}/manifest`.
- Added endpoint-level AES ZIP tests including wrong-password behavior.
- Added static UI action contracts.
- Added Playwright browser smoke that logs in and proves Protected ZIP + Native downloads through the real browser UI.
- Added `makia-uat-smoke` and comprehensive `docs/UAT-0.11.0-RC1.md`.

### Release status
Release candidate. Automated CI is necessary but Stable still requires the real-host/client UAT matrix.

## [0.10.0-rc1] - 2026-09-26

### Unified Access Center
- Promoted a single Access Center to the main sidebar for SSH, Xray, WireGuard and OpenVPN.
- Added unified search/filter and management actions across access types.
- Added central revoke flows for SSH users, Xray clients, WireGuard peers and OpenVPN clients.

### Client delivery and exports
- Added encrypted-at-rest access artifact storage derived from the Makia server secret.
- Added native exports: SSH config fragment, WireGuard `.conf`, OpenVPN `.ovpn`, Xray share/profile files and QR.
- Added AES-256 password-protected ZIP delivery packages using a separate operator-selected/package PIN.
- Newly created SSH credentials can be re-exported securely; legacy SSH accounts require one password reset before secure export.
- Existing OpenVPN profiles can be regenerated from PKI; legacy WireGuard peers without their original private key are explicitly marked for reissue.

### Xray onboarding
- Added an in-panel Xray Core install path using the official XTLS installer.
- After installation, guided VLESS/VMess/Trojan/Shadowsocks/Hysteria2/HTTP/SOCKS workflows become available directly in Makia.

### Reliability
- Added binary-safe encrypted artifact serialization.
- Added unit tests for encrypted payload round-trip, AES ZIP protection, SSH package behavior and Xray export content.
- Existing application-import CI smoke gate remains required.

### Release status
Release candidate. Real-host import/export and client-connection UAT is required before Stable.

## [0.9.3-rc1] - 2026-09-26

### Bootstrap recovery
- The downloaded updater no longer calls the possibly outdated `makia-backup` installed on the host.
- The updater performs its own SQLite-consistent live data snapshot before downloading/applying the new runtime.
- This allows a broken v0.9.0/v0.9.1 host to self-recover through the bootstrap `upgrade.sh` command.

### Release status
Recovery release candidate. Host validation is required before Stable.

## [0.9.2-rc1] - 2026-09-26

### Backend startup hotfix
- Restored the missing `protocol_client_by_subscription()` database helper required by `app.main`.
- Added a CI application-import smoke test so missing runtime imports fail before merge.

### Backup/update reliability
- Replaced live tar copying of SQLite with the SQLite online-backup API.
- Backup archives now exclude live DB/WAL/SHM files and include a consistent SQLite snapshot.
- Prevents `tar: data: file changed as we read it` from aborting normal upgrades while metrics/policy workers are writing.

### Release status
Recovery/startup release candidate. Real-host upgrade validation remains required before Stable.

## [0.9.1-rc1] - 2026-09-26

### Recovery hotfix
- Added `makia-reset-admin` for local administrator password recovery without panel access.
- Added optional `--generate`, `--user` and `--disable-2fa` recovery modes.
- Admin recovery clears login throttling state and reactivates the selected administrator.
- Installer/updater now deploy the recovery command; uninstaller removes it.
- Updater now creates a complete runtime rollback point before replacing application code.
- Any failed update, command failure after the rollback point, or failed backend health gate automatically restores the previous application/runtime files.
- Rollback restarts the backend and reports whether the previous runtime recovered successfully.

### Release status
Recovery release candidate. Host UAT is still required before Stable.

## [0.9.0-rc1] - 2026-09-26

### Account and client policy UX
- Standardized quota presets, expiry presets, device/IP presets and reset-cycle presets across protocol-client creation and editing.
- Preserved the distinction between SSH Session Limit and SSH Device/IP Limit.
- Kept SSH traffic quota explicitly non-enforced until a reliable per-user host accounting layer exists.

### Xray guided parity
- Promoted HTTP Proxy and SOCKS5 from Advanced-only to guided profiles with real Xray account credentials.
- Added guided Dokodemo/Tunnel port forwarding for TCP, UDP or TCP+UDP with port validation, config test, backup, restart gate and rollback.
- Kept VLESS, VMess, Trojan, Shadowsocks and Hysteria2 guided workflows plus TLS/REALITY and current transport options.
- Kept routing, outbounds, fallbacks and TUN available through the validated Advanced Xray editor.

### Subscription and API
- Added JSON subscription output in addition to Base64 and raw formats.
- Added a public per-client status page with quota, usage, expiry and device-limit information.
- Inactive, expired or quota-exhausted clients no longer receive active subscription payloads.
- Added `protocols:read` and `nodes:read` API token scopes and read endpoints.
- Replaced the prompt-based API token flow with a scoped selector UI.

### Product governance
- Added an explicit 3x-ui parity matrix.
- TUIC v5, AmneziaWG and MTProto remain intentionally unavailable until dedicated sidecar/runtime adapters have deterministic install, validation, health, recovery and host UAT.

### Quality
- Added v0.9 host UAT matrix.
- Added protocol catalog tests for guided HTTP/SOCKS/Tunnel capabilities.
- CI continues to gate Python, unit tests, Bash, JavaScript, dangerous patterns, naming and packaging contracts.

### Release status
Release candidate only. Stable promotion requires the real-host matrix in `docs/UAT-0.9.0-RC1.md`.

## [0.8.0-rc2] - 2026-09-26

### Upgrade reliability
- Added root `upgrade.sh` bootstrap updater.
- Added installed `makia-upgrade` command that always downloads the latest updater before applying an upgrade.
- This closes the old-updater/new-service gap when upgrading from releases that predate `makia-protocol-traffic.service`.
- Update Center now recommends `makia-upgrade`.
- Installer and updater keep `makia-upgrade` current.
- Uninstaller removes the bootstrap command.

### Release status
RC2 supersedes RC1 for host testing. It contains the same v0.8 capability set plus the safe transition path from older installed updaters.


## [0.8.0-rc1] - 2026-09-26

### Account Center V3
- Separated SSH Session Limit from Device/IP Limit.
- Added real enforcement for account expiry, concurrent sessions and distinct source IPs.
- Added 1/3/7/15/30/60/90-day presets, unlimited expiry and extend-from-existing-expiry behavior.
- Removed misleading enforced-traffic claims from SSH accounts where reliable per-user accounting is not available.

### Xray / Protocol Clients
- Added first-class protocol client records with secure subscription IDs.
- Added cumulative persistent traffic accounting for VLESS, VMess, Trojan and Hysteria2 using Xray Stats API.
- Added real manual and recurring traffic resets.
- Added automatic quota suspension and automatic reactivation at the next reset boundary.
- Added expiry enforcement and manual suspend/reactivate against the live Xray config.
- Added online Xray IP/device visibility and IP-limit violation state when supported by the installed Xray core.
- Added generated subscription endpoint in Base64 or raw format.
- Added Hysteria2 guided provisioning.
- Added RAW/TCP, WebSocket, gRPC, HTTPUpgrade, XHTTP and mKCP transport options.
- Added TLS certificate-backed profiles.
- Added VLESS REALITY with generated X25519 key material and Short ID.
- Added validated Advanced Xray JSON editor for routing, outbounds, fallbacks and other advanced features.
- Xray config mutations use test-before-apply, backup, restart validation and rollback.

### WireGuard / OpenVPN
- Kept guided WireGuard bootstrap and peer configuration workflow.
- Modernized OpenVPN TCP server/client mode and data cipher configuration.

### Admin / Security
- Added persistent admin login throttling.
- Hardened SQLite database file permission to 0600.
- Added disable-reason tracking for reliable protocol renewal.
- Added host diagnostic command: `makia-doctor`.

### UI / PWA
- Added Midnight, AMOLED and Graphite themes.
- Added Comfortable and Compact density.
- Added installable PWA manifest/service worker shell.
- Added live Protocol Client usage, quota, expiry, subscription and IP surfaces.
- Capability Matrix now distinguishes Guided, Advanced and Unavailable functionality.

### Packaging
- Added `makia-protocol-traffic.service`.
- Fixed updater to deploy the protocol traffic collector service unit.
- Installer/updater deploy `makia-doctor`.
- Uninstaller removes the new worker and diagnostic command.

### Explicitly not claimed as guided in this RC
- TUIC
- AmneziaWG
- MTProto
- automatic Xray over-limit IP banning

These remain unavailable or visibility-only until dedicated adapters and host UAT exist.

### Release status
Release candidate only. Promotion to Stable requires the host matrix in `docs/UAT-0.8.0-RC1.md`.


## [0.7.0-rc1] - 2026-09-26

### Protocol Hub
- Added real protocol catalog/status for Xray, WireGuard, OpenVPN, SSH and Stunnel.
- Added apt-backed installation for WireGuard, OpenVPN and Stunnel.
- Added WireGuard server bootstrap and peer provisioning with downloadable client configuration.
- Added OpenVPN PKI/server bootstrap and client `.ovpn` provisioning.
- Added Xray quick inbound provisioning for VLESS, VMess, Trojan and Shadowsocks with config validation, backup, restart health check, rollback, share links and QR.
- Xray is detected and managed when installed; Makia does not run an unverified remote installer for the Xray binary.

### Domain, TLS and language
- Added persistent Persian/English panel language preference with RTL/LTR shell behavior.
- Added validated panel-domain configuration.
- Added Nginx `server_name` apply with syntax validation and rollback.
- Added optional Let's Encrypt certificate issuance through Certbot after DNS is configured.

### UX
- Rebuilt Protocol Hub as a card-based operational surface.
- Added capability strip, status badges, configuration modals and one-click copy/download actions.
- Upgraded shell, top bar, responsive layout and domain/environment indicator.
- Removed fake protocol actions: unavailable operations are explicitly marked unavailable instead of rendering non-functional buttons.

### Quality
- Added domain and protocol validation unit tests.
- CI continues to enforce Python compile, unit tests, Bash syntax, JavaScript syntax and dangerous-pattern checks.

### Release status
This is a release candidate. Stable status requires host UAT on clean Ubuntu 22.04/24.04, protocol provisioning tests, update/rollback tests and TLS/domain tests.

## [0.6.0-alpha] - 2026-09-26

### Account Center V2
- Added server-side cryptographic generation for 4-digit PIN, 6-digit PIN, Easy-8 and strong user passwords.
- Added automatic username suggestion.
- Added 1/7/30/60/90-day expiry presets.
- Added account search and status filters.
- Added bulk expiry extension in addition to lock/unlock/disconnect.
- Added GB-oriented quota entry while preserving MB canonical storage.
- Added improved one-time credential card for copying account details to the user.

### UX
- Added global Makia command palette with Ctrl/Cmd + K.
- Added new provisioning, security and update surfaces.
- Added richer mobile behavior and visual hierarchy.

### Security
- Fresh installations now install and enable Fail2ban with an SSH brute-force baseline.
- Existing installations receive the same Fail2ban baseline through `makia-update`.
- 4-character user PINs remain optional; administrator password policy is unchanged.

### Update Center
- Added online VERSION comparison against the main GitHub repository.
- Web-triggered self-update remains intentionally disabled until atomic rollback/release verification is complete.


## [0.4.0-alpha] - 2026-09-26

### Protocol Center
- Added real Xray binary/version/service/config discovery.
- Added safe inbound summary with protocol, listen address, port and client count.
- Added Xray to the service allowlist.
- No fabricated protocol data or fake traffic metrics.

### Account policy enforcement
- Added `makia-policy-enforcer` systemd service.
- Connection limits are now actively enforced for SSH login sessions.
- Excess sessions are disconnected and recorded in the audit trail.

### Security
- State-changing API requests require the Makia management header.
- Session cookies become Secure automatically when served through HTTPS.
- User PINs may still be as short as four characters by operator choice; admin credentials remain stronger.

### UI
- Added Protocol Center navigation.
- Update Center now references `makia-update`.

## [0.3.0-alpha] - 2026-09-26

### Product
- Product/runtime identity migrated to **Makia VPS Manager**.
- New premium dark control center and responsive navigation.
- New `/opt/makia-vps-manager` runtime and `makia-vps-manager` systemd service.
- Legacy Dragon command aliases retained temporarily for migration compatibility.

### Accounts
- Professional account creation and editing.
- 4-digit PIN, 6-digit PIN and strong-password workflow.
- Expiry date, plan, internal note, connection-limit policy and traffic-quota policy.
- Lock/unlock/delete and disconnect-all actions.
- Dashboard counters for expiring accounts and connection-limit violations.

### Sessions
- Live SSH session list.
- Controlled per-terminal disconnect.

### Operations
- Security Center status for UFW, Fail2ban and OpenSSH.
- Controlled in-panel data backup creation and backup list.
- Updater performs backup then health check.
- Existing alpha data can be migrated from the previous runtime location.

### Security notes
- User PINs may be 4 characters by operator choice.
- Administrator passwords remain stronger.
- Traffic quota is currently a stored policy; usage accounting/enforcement is not fabricated.

## [0.1.0-alpha] - 2026-09-25
- Initial web management foundation.
