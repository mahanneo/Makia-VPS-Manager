# Makia VPS Manager 0.26.0-rc9 — UAT / Release Gate

Date: 2026-09-29
Branch: `feat/rc7-ops-suite-outline`
Target: `0.26.0-rc9`
Status: **Release Candidate — not Stable**

## Automated gates
- Python compile/import/startup
- Full pytest and DB/migration compatibility
- JavaScript syntax and Playwright browser smoke
- Xray Core 26.3.27 smoke
- RC8 Operations Suite mocked Outline/Cloudflare/Telegram coverage
- RC9 Outline DR Docker preflight
- RC9 Remote SCP retry semantics
- RC9 integration-secret error redaction
- Bash/systemd/packaging/security contracts
- Directional Full Migration compatibility through RC9

## RC9 acceptance
1. Outline-bearing bundles fail before mutation when Docker is absent.
2. `sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade` prepares Docker outside the web service.
3. Remote SCP failure does not advance `backup_schedule_last_run`.
4. Local retention runs before remote transfer.
5. Credential-bearing network errors do not expose Telegram/Outline URL secrets.
6. Verified RC2-RC8 Full Migration bundles are accepted on RC9; newer-to-older claims remain rejected.

## Real Host UAT required before Stable
- Existing-host upgrade and clean install on Ubuntu 22.04/24.04.
- Real Outline Shadowbox/API fingerprint/key/quota/expiry/traffic.
- Encrypted scheduled backup to a real SCP target and retry after a controlled SCP failure.
- Replacement-VPS restore with Outline state and one controlled rollback failure.
- Live Cloudflare DNS-only cutover and propagation.
- Live Telegram send/webhook/secret checks.
- Real Client Portal plus SSH/NPV, Xray, WireGuard, OpenVPN and Outline clients on target networks.
- Confirm hostname-based configs survive DNS cutover; literal-IP profiles require endpoint replacement.

## Promotion rule
Do not tag or call RC9 Stable until all executable CI gates are green on the RC9 head commit and the real-host UAT above is recorded without unresolved blockers.
