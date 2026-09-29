# Makia VPS Manager 0.26.0-rc10 — UAT / Release Gate

Date: 2026-09-29
Branch: `feat/rc7-ops-suite-outline`
Target: `0.26.0-rc10`
Status: **Release Candidate — not Stable**

## RC10 scope

RC10 keeps the RC8/RC9 Operations Suite and focuses on the real issues found during post-release UI/Outline audit:

- Outline Setup no longer collapses a missing Docker host dependency into a raw browser alert. The panel shows a structured root-shell workflow with the host-preparation command and the pinned Outline install command.
- The Outline install API explicitly reports `requires_dependency`, `dependency_command`, Docker readiness and the install command without running APT/Docker inside the hardened web service.
- SSH, Xray, WireGuard, OpenVPN and managed Outline users use one consistent `•••` access-detail workflow for management and delivery.
- The unified Clients page includes an Outline filter.
- The access drawer exposes protocol-specific management plus common Native/QR/Client Portal/Protected ZIP/Guide delivery controls.
- Outline usage/expiry are rendered as managed policy data instead of falling back to PKI/Certificate labels.
- Outline now has a first-class public connection-guide section and correct guide routing.
- Protocol sidebar stays expanded while Outline is active.

## Automated gates

- Python compile and application import/startup
- Full pytest / DB / migration compatibility
- JS syntax
- HTML/UI action-to-handler mapping through existing contracts
- Playwright browser smoke
- Xray Core 26.3.27 smoke
- RC8 mocked Outline/Cloudflare/Telegram coverage
- RC9 DR/remote backup/secret-redaction regressions
- RC10 unified access-menu static + browser contracts
- Five-protocol public visual guide contract
- Full Migration compatibility RC2 through RC10
- Bash, systemd, packaging and security guards

## Real Host UAT required before Stable

1. Upgrade the actual VPS to RC10 and verify Footer/API version is `0.26.0-rc10`.
2. Run `sudo makia-doctor` and `sudo makia-uat-smoke`.
3. Open Outline Setup on a host without Docker and verify the panel displays:
   - `sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade`
   - the pinned `makia-install-outline` command
4. Execute the host-preparation command, then the Outline installer; verify Docker, Shadowbox and Management API status.
5. Create a real Outline key and validate quota, expiry, traffic, QR, copy, Protected ZIP, Client Portal, renew, reissue, delete and diagnostics.
6. In SSH, Xray, WireGuard, OpenVPN and Outline workspaces verify each managed user has the same `•••` management entry point.
7. Verify Client Portal and downloads on Android/iOS/Windows/macOS.
8. Repeat replacement-VPS Full Migration restore and Cloudflare DNS-only cutover.
9. Validate real external connectivity for SSH/NPV, Xray, WireGuard, OpenVPN and Outline.

## Promotion rule

Do not call RC10 Stable until all executable CI jobs are green on the final RC10 head and the real-host checks above complete without unresolved blockers.
