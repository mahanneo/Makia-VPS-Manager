# Makia VPS Manager v1.2.10 — Immutable Release Archive UAT

Date: 2026-09-29
Target: `1.2.10`

## Root cause

The bootstrap updater fetched the latest `scripts/update.sh` from `raw.githubusercontent.com/main`, but then downloaded a floating branch archive from `archive/refs/heads/main.tar.gz`. The host showed the new updater logic while the extracted archive still contained an older/corrupt `uat-smoke.sh`, causing source preflight to fail before runtime mutation.

## Fix

- Force-main no longer downloads a floating branch tarball.
- The updater resolves `main` (or the selected GitHub ref) to an exact 40-character commit SHA using the GitHub commits API.
- It downloads an immutable codeload archive for that exact commit SHA.
- The archive is validated with `tar -tzf` before extraction.
- The extracted root directory must match `Makia-VPS-Manager-<resolved-commit>`.
- The downloaded release must contain a valid semantic VERSION before shell preflight begins.
- Explicit administrator-provided `MAKIA_RELEASE_ARCHIVE_URL` remains supported when FORCE_MAIN is not enabled.
- Retains v1.2.9 atomic shell install + SHA256 verification, v1.2.8 clean updater rebuild, and DNS/MTProxy repair transactions.

## Host recovery acceptance

- [ ] Download the latest updater from raw main.
- [ ] Run `bash -n` on that bootstrap updater.
- [ ] Execute with `MAKIA_FORCE_MAIN=1`.
- [ ] Observe `pinned immutable source commit: <40-char SHA>`.
- [ ] Observe `Downloaded immutable Makia release: version=1.2.10 commit=<same SHA>`.
- [ ] Source shell preflight must pass.
- [ ] Host update must no longer see a stale/corrupt uat-smoke from a floating branch archive.
- [ ] Installed VERSION and backend health must both report 1.2.10.
- [ ] Direct `sudo makia-uat-smoke` must execute normally.

## Promotion rule

Do not merge unless final HEAD passes test, Bash syntax, xray-core-smoke and browser-smoke.
