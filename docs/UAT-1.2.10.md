# Makia VPS Manager v1.2.10 — Host Smoke Script Rebuild UAT

Date: 2026-09-29
Target: `1.2.10`

## Root cause

The release source itself contained a corrupted DNS query block in `scripts/uat-smoke.sh`. The single-quoted grep expression was truncated, leaving an unmatched quote. The file also had duplicated tail content from an earlier in-place edit. As a result, the v1.2.9 updater correctly stopped during:

`Preflighting critical release shell scripts...`

with an EOF/quote parser error before any runtime mutation.

A second latent issue was present: the script referenced `warn` for updater-scoped optional-service soft-fail handling without defining a `warn()` helper.

## Fix

- Rebuilt `scripts/uat-smoke.sh` from the last known-good v1.2.6 copy instead of patching the corrupted blob.
- Added a real non-failing `warn()` helper.
- Replaced the fragile DNS grep regex with a simple captured `dig` result and non-empty check.
- Preserved updater-scoped `MAKIA_UAT_DNS_SOFTFAIL` behavior while direct `makia-uat-smoke` remains strict.
- Added regression tests requiring one clean file terminator, one DNS section, one OpenVPN TCP fallback section, no duplicate tail, no dangling `; then`, and no backticks.
- v1.2.9 verified/atomic runtime-shell installation remains active, so the live `makia-uat-smoke` must match the release source before Host Smoke.
- Service worker cache advances to `makia-shell-v1210`.

## Host recovery acceptance

- [ ] Download latest `scripts/update.sh` from main.
- [ ] Run `bash -n` on the downloaded updater and require success.
- [ ] Execute with `MAKIA_FORCE_MAIN=1`.
- [ ] Confirm the release preflight passes `scripts/uat-smoke.sh` without EOF/quote errors.
- [ ] Confirm installed/runtime version report `1.2.10`.
- [ ] Run `bash -n /usr/local/sbin/makia-uat-smoke` and require success.
- [ ] Run direct `sudo makia-uat-smoke`; any remaining failure must be a real service/host issue, not a parser error.
- [ ] Confirm MTProxy remains ACTIVE + Listener and DNS query behavior is reported normally.

## Promotion rule

Do not merge unless final HEAD passes `test` (including Bash syntax), `xray-core-smoke`, and `browser-smoke`.
