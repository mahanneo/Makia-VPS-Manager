# Makia VPS Manager v1.2.8 — Updater Syntax Rebuild UAT

Date: 2026-09-29
Target: `1.2.8`

## Root cause

The v1.2.7 updater on `main` became syntactically invalid: the DNS precheck block was truncated and a duplicate tail of the updater remained appended after the normal terminator. Bash therefore failed before any update logic ran with:

`syntax error near unexpected token ';'`

## Fix

- Rebuilt `scripts/update.sh` from the last known-good v1.2.6 updater instead of editing the corrupted file in place.
- Re-applied the v1.2.7 DNS repair transaction cleanly.
- Preserved v1.2.6 MTProxy accepted-state transaction handling.
- Kept FORCE_MAIN recovery, running-backend version verification, shared config permission repair and optional-service scoped soft-fail logic.
- Added structural regression tests that require exactly one updater terminator, one `assert_preserved_file` function, one `on_exit` function and no dangling `; then` tail.
- Existing CI Bash syntax gate continues to run `bash -n` across `scripts/*.sh`.
- Rotated the UI service-worker cache to `makia-shell-v128`.

## Host recovery acceptance

- [ ] Download the latest updater from main.
- [ ] Run `bash -n /tmp/makia-update-128.sh` and require exit code 0 before executing it.
- [ ] Run the updater with `MAKIA_FORCE_MAIN=1`.
- [ ] Confirm installed VERSION and backend health both report 1.2.8.
- [ ] Confirm DNS repair either succeeds or remains an isolated optional-service warning without rolling back the panel release.
- [ ] Confirm Telegram MTProxy remains ACTIVE + Listener when previously repaired.
- [ ] Run direct `sudo makia-uat-smoke`; any remaining optional service failure is then treated as a real host issue, not an updater syntax failure.

## Promotion rule

Do not merge unless the final HEAD passes `test`, `xray-core-smoke`, and `browser-smoke`, including the Bash syntax gate.
