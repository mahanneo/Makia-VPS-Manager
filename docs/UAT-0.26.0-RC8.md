# Makia VPS Manager 0.26.0-rc8 — UAT / Release Gate

Date: 2026-09-29  
Branch: `feat/rc7-ops-suite-outline`  
Target: `0.26.0-rc8`  
Status: **Release Candidate — not Stable**

## Scope

RC8 closes the Operations Suite / Outline workstream without replacing the existing architecture. It covers Plans/Templates, bulk renew, Expiry Center, scheduled + remote Full Migration backup, Disaster Recovery, Cloudflare DNS cutover, Telegram alerts/status, notifications, per-access diagnostics, Multi-VPS telemetry, Client Portal and first-class Outline operations.

## Automated gates required in GitHub Actions

The release commit must pass all existing CI jobs plus the dedicated RC8 operations gate.

| Gate | What is exercised | Expected |
|---|---|---|
| Python compile | `app`, tests and restore/configure scripts | PASS |
| Import/startup smoke | Import `app.main`, resolve version/application | PASS |
| DB/unit/migration | Full `pytest -q`, DB initialization/migration compatibility tests | PASS |
| API/contract smoke | Route/unit tests and release static contracts | PASS |
| JS syntax | `node --check app/static/app.js` | PASS |
| HTML/UI actions | UI contract + real Playwright browser smoke | PASS |
| Protected backup | AES ZIP create + decrypt/verify | PASS |
| Restore static safety | format/checksum/rollback contracts and restore script compile | PASS |
| Outline mocked API | transfer metrics, key rotation, renewal/policy paths | PASS |
| Cloudflare mocked API | A-record cutover and mandatory `proxied=false` | PASS |
| Telegram mocked API | exact Chat ID send + webhook removal | PASS |
| Bulk Renew | managed Outline renewal reaches server-side data-limit path | PASS |
| Expiry | SSH + managed protocol aggregation and renewal eligibility | PASS |
| Node telemetry | CPU/RAM/Disk/IP/Region/User/Traffic/Service heartbeat mapping | PASS |
| Secret leakage | Cloudflare/Telegram read APIs never return stored token secret | PASS |
| Remote SCP security | strict host-key verification + identity permission checks | PASS |
| Xray Core | pinned Xray 26.3.27 guided matrix/data-plane smoke | PASS |
| Browser flow | login, protected/native export, Create Access with Outline, core workspaces | PASS |

## Backup / Disaster Recovery safety contract

1. Full Migration backup is password protected and verified before persistence/use.
2. Bundle manifest contains payload checksums and format compatibility data.
3. Makia data and protocol identity/runtime state are preserved, including `/opt/outline`.
4. Restore verifies the bundle before mutation.
5. Writers are stopped before the rollback snapshot is taken.
6. Restore failure triggers automatic rollback/restart of managed state.
7. Destination runtime is validated before DNS cutover.
8. Cloudflare cutover for raw VPN/SSH endpoints is DNS Only.
9. Remote SCP requires a pre-trusted SSH host key; unknown hosts are rejected.

## Outline safety contract

- Installer: official Outline Server `server-v1.12.0`, exact installer Git-blob integrity check.
- Installer is returned as a root-shell command; the hardened web service does not run APT/Docker installation.
- Management API: localhost transport plus SHA-256 certificate fingerprint validation from `/opt/outline/access.txt`.
- Managed keys: Create, Delete, Reissue, Renew, Quota, Expiry, transfer usage, QR/share, Protected ZIP, private Client Portal and Diagnostics.
- Expired keys are revoked from Outline, not merely hidden in Makia UI.
- Reissue rotates runtime identity while preserving the Makia managed-client record.
- Outline has no fake IP/device-limit control.

## Real Host UAT still mandatory

The following cannot be claimed from GitHub-hosted CI and must be run on a real Ubuntu 22.04/24.04 VPS before Stable:

1. **Upgrade path:** upgrade an existing RC6/RC7-era installation to RC8; run `sudo makia-doctor` and `sudo makia-uat-smoke`.
2. **Clean install:** install RC8 on a clean VPS and repeat host smoke.
3. **Systemd timers:** verify `makia-scheduled-backup.timer` and `makia-ops-monitor.timer` remain enabled/active and actually execute over time.
4. **Outline live:** run `sudo makia-install-outline`, verify Shadowbox container, Management API fingerprint, create/reissue/revoke, quota, expiry and traffic with a real Outline client.
5. **Remote backup:** pre-seed the destination SSH host key, use a 0600/0400 identity file, execute an encrypted scheduled Full Migration backup and verify the remote file/hash.
6. **Replacement VPS restore:** provision a second VPS, install required runtimes, restore the encrypted Full Migration bundle, verify users/keys/configs and automatic rollback by performing one controlled failure test.
7. **Cloudflare live:** test API Token/Zone/A-record, confirm record is DNS Only, cut over to replacement VPS and verify DNS propagation.
8. **Telegram live:** test send, webhook secret, exact Chat ID restriction and read-only `/backup` status command.
9. **External clients:** connect real SSH/NPV, Xray, WireGuard, OpenVPN and Outline clients from the networks/regions intended for production.
10. **Credential continuity:** verify domain-based client configs continue after VPS replacement/DNS cutover; literal-IP profiles are expected to require endpoint replacement.
11. **Client Portal:** test Android/iOS/Windows/macOS detection, QR/import/download, token rotation and revocation/expiry behavior.

## Promotion rule

Do **not** tag or describe RC8 as Stable until:
- every executable GitHub Action gate is green on the release commit, and
- the mandatory real-host UAT above is completed and recorded without unresolved blockers.
