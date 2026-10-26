# Makia 1.6.6 integration candidate (not a production release)

This integration combines two independent changes on top of the official
1.6.5 `main` baseline (`5b03c8687c24df40304e57cb5a6e0c8d73ab955c`):

- PR #126: pin the compatible upstream Xray installer to an immutable commit,
  execute with explicit arguments, and preserve historical upgrade fixtures.
- PR #119: opt-in, revocable 30-day Client Portal / Browser VPN sessions and
  verified browser egress with a fail-closed reconnect path. The default
  Client Portal session remains 12 hours.
- Integration hardening: removed the pre-checked 30-day login choice in both
  the web and browser-extension forms. Every new login must explicitly opt in;
  an old stored preference does not re-check the box automatically.

The installer resolution retains PR #126's pinned script and supported
`-u nobody` argument. It must not silently regress to the mutable upstream
installer adopted in the older PR #119 branch.

## Local integration checks (2026-10-26)

- Python unit suite: **519 passed**, with deprecation warnings only.
- Browser verified-egress contract: **16 scenario groups passed**.
- JavaScript `node --check`, Bash `bash -n` and Git whitespace checks: passed.
- Both component branches have independently passed their core GitHub CI.
  **The combined merge commit still needs its own complete GitHub CI.**
- No live VPS, deployed users, certificates, listener ownership, or service
  state was modified by these local tests.

## Release and rollback gates

1. Obtain a full green GitHub CI matrix for the **exact** integration commit,
   including clean installs and upgrades from 1.3.0 and 1.5.1.
2. Perform independent review of remembered-session revocation, short-lived
   proxy credentials, origin/cookie protections and the no-direct-fallback
   browser egress state machine.
3. Confirm authorised SSH access to the target VPS and capture read-only
   baseline versions, service/listener state, active user sessions and a
   current `makia-doctor` report.
4. Create and verify an encrypted off-host full-migration backup, confirm a
   reproducible rollback path, and take a separate database snapshot.
5. Stage the exact commit and test opt-in 30-day versus default 12-hour
   sessions, logout, password change, account/device revocation, Chrome/Edge
   reconnect, failure handling, public egress IP and DNS over representative
   client networks. Never label a VPN connection verified merely because a
   UI switched state.
6. Keep the production Client Portal/Browser VPN switches and existing VPN
   listeners unchanged until those tests pass and a maintenance window is
   approved. Promote explicitly; do not auto-publish Android/Windows/Chrome
   stable artifacts from this integration.
7. After deployment, compare protocol services/listeners and identities with
   the baseline, run `makia-doctor` and `makia-uat-smoke`, test representative
   existing accounts, then retain a time-bounded rollback window.

**Status:** source-level integration only; pending combined CI, real-device
UAT, verified backup and production deployment authorization.
