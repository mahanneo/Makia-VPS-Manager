# Makia VPS Manager 0.26.0-rc11 — UAT / Release Gate

Date: 2026-09-29
Branch: `feat/rc7-ops-suite-outline`
Target: `0.26.0-rc11`
Status: **Release Candidate — not Stable**

## RC11 scope

RC11 fixes the real browser/runtime defects observed after RC10:

- Outline create no longer relies on browser-created global variables such as `olName`, `olQuota` or `olDays`.
- Xray/V2Ray workspaces explicitly request `engine=xray`, so Outline-managed clients cannot leak into Xray client lists or open invalid Xray detail drawers.
- The protocol-client API now supports an explicit engine filter while preserving internal unfiltered access aggregation.
- Outline key creation now uses a stable Manager API flow: create credential first, then rename and apply data limit. If policy application fails, the newly created key is deleted to avoid orphan credentials.
- The returned Outline credential must be a valid `ss://` key before Makia stores/delivers it.
- Outline delivery is verified as Access Key + QR + Client Portal + one-tap/share contract.
- Management forms no longer rely on fragile DOM-id globals for SSH, Plans, Quick Provision, Backup Scheduler, Cloudflare, Telegram, Settings, 2FA, Xray Tunnel/Inbound/Advanced and protocol policy forms.

## Automated gates

- Python compile/import/startup
- Full pytest and DB/migration compatibility
- JavaScript syntax
- Playwright browser smoke
- Browser regression for Outline create: open modal → fill fields → mocked real API response → Client Portal
- Xray workspace isolation from Outline clients
- Stable mocked Outline Manager API create/name/data-limit flow
- Partial Outline key rollback test
- Outline delivery contract: `ss://` key, QR artifact and one-tap URL
- DOM-global regression guard across management forms
- Existing RC8/RC9/RC10 Outline, Cloudflare, Telegram, backup/restore, security and migration gates
- Xray Core 26.3.27 smoke
- Bash/systemd/packaging/security contracts
- Directional Full Migration compatibility through RC11

## Real Host UAT required before Stable

1. Upgrade the actual VPS and confirm version `0.26.0-rc11`.
2. Run `sudo makia-doctor` and `sudo makia-uat-smoke`.
3. Verify Outline status shows Docker, Shadowbox container and Management API READY.
4. Create a real Outline user from the panel and confirm no browser ReferenceError occurs.
5. Confirm the user appears only in Outline / unified Clients, not Xray/V2Ray.
6. Copy the generated `ss://` Access Key into the official Outline Client on Android/iOS/Windows/macOS and verify a real VPN connection.
7. Scan the Outline QR from the Client Portal and verify import/connect.
8. Validate quota, expiry, traffic, renew, reissue, delete and diagnostics against the real Outline server.
9. If using a Cloudflare-hosted hostname for Outline, the DNS record must remain **DNS Only**; do not proxy Shadowsocks/Outline traffic through Cloudflare orange-cloud HTTP proxying.
10. Re-run replacement-VPS Full Migration restore and verify the same Outline state/credentials survive when the server state is restored.
11. Verify SSH/NPV, Xray, WireGuard and OpenVPN management drawers still work after the DOM-global hardening.

## Promotion rule

Do not call RC11 Stable until all final-head CI jobs are green and the real-host/client UAT above completes without unresolved blockers.
