# Makia VPS Manager v1.2.11 — Immutable Main Update UAT

Date: 2026-09-29
Target: `1.2.11`

## Root cause

The bootstrap updater fetched the latest `scripts/update.sh` from raw `main`, but then downloaded a floating `main.tar.gz`. On the affected VPS this produced a mixed release: the bootstrap updater was current while the extracted archive still contained an older/corrupt host-smoke script.

## Fix

- Resolve `main` or the selected GitHub ref to an exact 40-character commit SHA through the GitHub commits API.
- Download only the immutable codeload tarball for that SHA.
- Validate tar integrity before extraction.
- Require the extracted root folder to match the resolved commit SHA.
- Validate semantic VERSION before shell preflight.
- Keep administrator-supplied `MAKIA_RELEASE_ARCHIVE_URL` support only when FORCE_MAIN is not enabled.
- Preserve the current main hotfix that rebuilt the host-smoke script, plus runtime script SHA/syntax checks, DNS repair, MTProxy repair and rollback protections.

## Host recovery

1. Download the latest updater from raw main.
2. Run `bash -n` on it.
3. Execute it with `MAKIA_FORCE_MAIN=1`.
4. Confirm output includes:
   - `pinned immutable source commit: <sha>`
   - `Downloaded immutable Makia release: version=1.2.11 commit=<same sha>`
5. Confirm source shell preflight passes.
6. Confirm installed VERSION and backend health both report 1.2.11.
7. Confirm direct `sudo makia-uat-smoke` executes without parser errors.

## Promotion rule

Do not merge unless test, Bash syntax, xray-core-smoke and browser-smoke all pass on the final HEAD.
