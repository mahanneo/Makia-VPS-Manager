# Makia Release Status

## Active candidate (2026-10-31)

The France VPS (155.117.5.236, p.mahinet.shop) is being validated on Makia 1.6.10-rc6. This is a release candidate, not an official Stable tag. The source branch is release/1.6.10-rc6-uat-20261031; GitHub publication and promotion to main must use the exact tested commit.

### Automated and host verification

- Python/pytest suite: 578 PASS.
- Python compile, Bash syntax and JavaScript syntax: PASS.
- Browser extension verified-egress contract: 16 scenario groups PASS.
- mtg 2.2.8 release smoke: PASS.
- WStunnel 11.0.0 installer/flag smoke: PASS.
- makia-uat-smoke: 34 PASS / 1 WARN / 0 FAIL.
- makia-doctor: 34 PASS / 1 WARN / 0 FAIL.
- Nginx config and HTTPS domains: valid; Makia health endpoint returns OK.
- Xray active config: valid; 11 inbounds are present.
- TUIC UDP/8445 and Hysteria2 UDP/8446: server readiness, TLS certificate, listener and user checks PASS; temporary external clients from Germany both completed HTTPS egress through France (155.117.5.236). Temporary users were removed.
- WireGuard, OpenVPN, IKEv2, L2TP, SSTP backend, WStunnel, MTProxy and DNS runtime checks are healthy.
- MTProxy mtg doctor passed Telegram DC/front-domain checks. tg.mahinet.shop resolves to France; TCP/10443 is reachable from Germany. The Telegram app itself still needs a real-device handshake.
- MahiNet storefront/worker and Outline Shadowbox containers are running.

### Warnings and remaining Stable gates

1. Telegram real-client UAT: import the current MTProxy link into Telegram on a real phone/desktop and confirm connection.
2. Windows SSTP: the server-side SSTP service is ready on TCP/14443, but Windows RasClient error 720 has not been cleared by a real Windows connection test.
3. Field-network UAT: verify Android and intended protocols from the actual Iranian/mobile/ISP networks; the Germany-to-France QUIC test does not prove every ISP path.
4. Disaster recovery: create an encrypted off-host backup and demonstrate restore/rollback on a disposable target. The pre-update France backup is local to the France VPS and is not a substitute for off-host backup.
5. Stealth ownership: legacy global stunnel4 owns the active Stealth listener; it was deliberately not stopped or migrated because old client dependencies have not been audited.
6. Client Portal: the host smoke warns that Client Portal is enabled; confirm that exposure is intentional.

Do not call 1.6.10 Stable, create the stable tag, or delete the Germany rollback VPS until the field tests and off-host backup/rollback gates above are complete. Keep the Germany server available for rollback until then.

## Current server release: 1.6.5 (2026-10-09)

[Release v1.6.5](https://github.com/mahanneo/Makia-VPS-Manager/releases/tag/v1.6.5) · [Live-tested source commit](https://github.com/mahanneo/Makia-VPS-Manager/commit/9fb4a51a738aa6641c272855115f3f75e65a89e3)

Makia 1.6.5 is a **server/control-plane hotfix**, installed on p.mahinet.shop from the exact immutable GitHub commit above using `MAKIA_LIVE_SAFE=1`. Both the internal health endpoint and public HTTPS domain returned `1.6.5`. Host smoke **PASS** and Doctor **35 PASS / 1 WARN / 0 FAIL** were observed after deployment; code and installed updater matched the pinned source. Backup archives (database, runtime and extended network settings) passed SHA-256 verification after the update.

**Session-preservation evidence:** The main PIDs for Xray, primary OpenVPN, Makia Stealth, both WStunnel services and Browser Gateway were unchanged before and after the upgrade. Nginx, WireGuard, MahiNet 2.1.0 and Outline remained active. PID preservation does not prove that every end-user VPN connection passed a full data-path test.

**Known warning:** Legacy `stunnel4.service` is still in a failed systemd state from duplicate TCP/39443 ownership. The separately running old TCP/9443 listener was preserved, as was Makia's active Stealth listener on TCP/39443. No forced migration or restart was attempted; retire legacy Stunnel only after confirming client dependencies.

**Client release boundary:** 1.6.5 does not publish a new Android/Windows/Chrome client, and it does not claim actual Android/iOS/client-network UAT. v1.6.4 client packages remain a separate artifact line. Chrome Browser VPN 1.6.4.3 remains an isolated candidate pending real Chrome/Edge testing. Auto-release uploads of unreviewed client builds were disabled.

**Remaining acceptance:** Verify real client issuance, connection, egress, quota/expiry/revocation, IPv6 and representative ISP networks. The Client Portal is enabled; confirm its exposure is intentional. UFW remains inactive and should be hardened only under a separately verified firewall rollback plan.

## Previous release: 1.6.4 (historical)

Previous server/control-plane stable release: **1.6.4** (2026-10-08). [Release v1.6.4](https://github.com/mahanneo/Makia-VPS-Manager/releases/tag/v1.6.4). PR #99 is merged to `main` as `4ac973e0b21cbd73179dcc349e5cbc2e7a4645b8`; the live VPS was upgraded using the exact tested candidate `a3d2eaeee9678be613de0fa22d565d46c4ed5ea1`. Both commits have the **identical Git tree SHA**, so the published source and installed source are equivalent. PR #98 remains a separate draft and is **not** included in v1.6.4.

| Surface | Repository / host evidence | Release readiness |
| --- | --- | --- |
| VPS panel, installer and updater | CI, Ubuntu 22.04/24.04 clean install, upgrades from 1.3.0/1.5.1, production host update and HTTPS health PASS | **v1.6.4 server release approved** |
| WStunnel443 (OpenVPN bridge and Android WG backend) | Backend `ready=True`, policy socket ready, HTTPS TCP/443 gateway, loopback TCP/10445 and TCP/11950; transactional provisioning test suite PASS | Server-side readiness confirmed; real-account/field-connection UAT still pending |
| Stealth / legacy Stunnel | Dedicated TCP/39443 active; legacy TCP/9443 listener preserved during upgrade | Listener preserved; legacy global `stunnel4.service` still has a failed systemd status and requires separate cleanup |
| WireGuard / Xray / OpenVPN primary | Existing configs preserved, diagnostics PASS, services active | Server runtime healthy; cross-provider client connectivity unverified |
| Browser VPN | Browser extension workflow and browser CI PASS | Build available; real browser/store review remains separate |
| Windows full device | Windows connector build PASS | Build-ready, real-device connection/revocation UAT required |
| Android full device | Android UAT/debug build workflow separate from signed release | **Not signed/verified production stable**; needs existing signing keystore and ARM64 real-device field UAT |
| Client Portal / PWA | Live backend HEALTH OK; SQLite integrity check OK, account/artifact counts retained | Server-side account delivery operational; real-user end-to-end test pending |
| iOS/iPadOS | PWA/Open/Import | Native iOS VPN functionality is **not** claimed |

## October 8 production acceptance evidence

- Server `p.mahinet.shop` returns `{"ok":true,"version":"1.6.4"}` from both public HTTPS and local TLS Nginx route.
- Nginx, Makia, WStunnel, OpenVPN backend, Stealth, WireGuard, Xray, policy enforcer and browser gateway are active; TCP 80/443/9443/39443/10445/11950 listeners remain.
- Server-side SQLite `PRAGMA integrity_check=ok`; the pre/post aggregate state still has 2 client accounts, 14 access artifacts, 2 artifact bindings.
- Fresh data and runtime archives were transferred to the operator workstation and authenticated/encrypted AES-256-GCM off-host with SHA-256 and decrypt-roundtrip checks. Isolated restore and SQLite integrity check PASS. **No live destructive disaster-recovery cutover has been tested.**
- The updater preserves the existing TCP/9443 Stunnel process during normal update and rollback and honors an explicitly pinned immutable GitHub SHA even when a custom archive URL is configured.
- Existing MahiNet storefront and Outline containers are running; pre-existing MahiNet Worker health and Watchtower restart issues remain separately tracked and are not Makia v1.6.4 regressions.

## Remaining release boundaries

- Do not state that WStunnel, WireGuard or Stealth is guaranteed to work across all Iranian ISPs; field tests on multiple real mobile/desktop networks are needed.
- Android signing must use the *existing* operator-owned release keystore; do not replace signing identity or publish UAT/debug APK as release-signed.
- Confirm real profile issuance and native connect/disconnect, quota, expiry, revoke and rollback on test accounts before marking client applications fully production verified.
- The distinct experimental WireGuard constrained-network PR #98 is not part of this release.
- Historical 1.6.3 documents remain accessible for audit only. For new installs and updates, use the current official release/main documentation.
