# Makia VPS Manager v1.2.6 — Updater MTProxy Repair Transaction UAT

Date: 2026-09-29
Target: `1.2.6`

## Root cause

v1.2.5 correctly repaired the shared config-directory permission conflict, but the updater still compared the MTProxy files against their *pre-repair* SHA256 values after an intentional repair. A successful repair that moved a broken legacy proxy from port 443 to an automatic free high port therefore looked like an unauthorized mutation and triggered rollback.

## Fix

- Optional installers are verified against the original MTProxy/DNS hashes before any repair is attempted.
- A healthy pre-update MTProxy is never rewritten by the repair phase.
- Only a previously inactive configured MTProxy enters the repair transaction.
- When repair succeeds, the repaired MTProxy state/config hashes become the accepted transaction baseline.
- Final acceptance checks compare against the accepted repaired hashes, not the obsolete pre-repair hashes.
- If repair fails, the original MTProxy hashes must be restored exactly or the update fails.
- DNS state/config remain byte-preserved throughout the update.
- v1.2.5 shared permission repair, force-main recovery, running-version verification, AUTO port selection and update soft-fail behavior remain active.

## Recovery acceptance

- [ ] From an installed 1.2.0/1.2.5 host with broken/inactive MTProxy state, run:
      `curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/upgrade.sh | sudo env MAKIA_FORCE_MAIN=1 bash`
- [ ] Confirm updater prints an accepted repaired MTProxy state if it changes the legacy port/config.
- [ ] Confirm update completes instead of rolling back.
- [ ] Confirm `cat /opt/makia-vps-manager/VERSION` prints `1.2.6`.
- [ ] Confirm `curl -fsS http://127.0.0.1:8787/healthz` reports `1.2.6`.
- [ ] Confirm `stat -c '%a %U %G' /etc/makia-vps-manager` prints `710 root makia-mtproxy`.
- [ ] Open Telegram Proxy and verify AUTO/read-only port behavior.
- [ ] Verify configured MTProxy reaches ACTIVE + Listener.
- [ ] Run direct `sudo makia-uat-smoke` after repair and require PASS.

## Promotion rule

CI must pass test, browser-smoke and xray-core-smoke. Real host update from a broken legacy MTProxy state remains the final production UAT.
