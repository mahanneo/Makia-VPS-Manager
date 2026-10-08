# Makia Release Status

Current server/control-plane stable release: **1.6.4** (2026-10-08). [Release v1.6.4](https://github.com/mahanneo/Makia-VPS-Manager/releases/tag/v1.6.4). PR #99 is merged to `main` as `4ac973e0b21cbd73179dcc349e5cbc2e7a4645b8`; the live VPS was upgraded using the exact tested candidate `a3d2eaeee9678be613de0fa22d565d46c4ed5ea1`. Both commits have the **identical Git tree SHA**, so the published source and installed source are equivalent. PR #98 remains a separate draft and is **not** included in v1.6.4.

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
