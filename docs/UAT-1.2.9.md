# Makia VPS Manager v1.2.9 — Verified Runtime Script Install UAT

Date: 2026-09-29
Target: `1.2.9`

## Root cause

A host reached the new backend successfully but rolled back because the installed `/usr/local/sbin/makia-uat-smoke` differed from the repository source and contained an unmatched backtick near EOF. The source copy on `main` was syntactically valid, so the failure was local runtime-script drift/corruption rather than application logic.

## Fix

- Critical shell scripts are syntax-checked from the downloaded release before runtime mutation.
- Critical runtime shell scripts are installed through a verified atomic staging flow.
- The staged file must pass `bash -n` and match the source SHA256 before it can replace the live command.
- After installation, the live file is syntax-checked again and must match the source SHA256.
- Immediately before Host Smoke, `makia-update`, `makia-doctor`, and `makia-uat-smoke` are re-verified; a drifted/corrupt file is automatically reinstalled from the current release source.
- Host Smoke cannot run until the runtime script integrity gate passes.
- Retains v1.2.8 clean updater rebuild, v1.2.7 DNS repair, v1.2.6 MTProxy update transaction, and shared permission recovery.

## Host recovery acceptance

- [ ] Download latest `scripts/update.sh` from main.
- [ ] Run `bash -n` on the downloaded updater.
- [ ] Execute with `MAKIA_FORCE_MAIN=1`.
- [ ] Observe `Preflighting critical release shell scripts...`.
- [ ] Observe `Verifying installed critical shell artifacts before host smoke...`.
- [ ] Confirm `bash -n /usr/local/sbin/makia-uat-smoke` succeeds after update.
- [ ] Confirm source/live SHA256 for uat-smoke are identical if checked manually.
- [ ] Confirm installed and running versions both report 1.2.9.
- [ ] Confirm Host Smoke executes instead of failing with a shell parser error.
- [ ] Confirm direct `sudo makia-uat-smoke` completes and reports its real service results.

## Promotion rule

Do not merge unless final HEAD passes test, Bash syntax, xray-core-smoke and browser-smoke.
