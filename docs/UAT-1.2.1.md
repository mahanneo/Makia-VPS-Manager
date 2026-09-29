# Makia VPS Manager v1.2.1 — Network State Preservation UAT

Date: 2026-09-29
Branch: `fix/v1.2.1-network-state-preservation`
Target: `1.2.1`

## Scope

This patch prevents configured Telegram MTProxy and Makia DNS state from being silently lost or left inactive during upgrades.

## Update invariants

Before mutation the updater records SHA256 for any existing:
- `/etc/makia-vps-manager/mtproxy.env`
- `/etc/makia-vps-manager/mtproxy.toml`
- `/etc/makia-vps-manager/dns.json`
- `/etc/unbound/unbound.conf.d/makia.conf`

After optional tooling refresh and again before final acceptance, every pre-existing file must still exist with the same SHA256. Any mismatch aborts the update and triggers rollback.

The updater also records whether `makia-mtproxy` and `unbound` were active before the update. A previously active service becoming inactive during tooling refresh is treated as an update failure.

## Rollback

The runtime rollback snapshot already includes MTProxy/DNS state and binaries. v1.2.1 additionally restarts configured `makia-mtproxy` and `unbound` after rollback restoration so a failed update does not leave restored network services stopped.

## Acceptance

- [ ] Configure Telegram Proxy and verify Configured=YES, Service=ACTIVE and Listener=TCP/<port>.
- [ ] Record the t.me link and MTProxy secret suffix.
- [ ] Run `sudo makia-upgrade`.
- [ ] Verify the same hostname, port and secret remain after update.
- [ ] Verify the old t.me link still connects.
- [ ] Configure DNS policy and record mode/upstream/allowlist.
- [ ] Run another update and verify DNS policy and resolver state remain unchanged.
- [ ] Force an update failure in staging and verify rollback restores and restarts configured MTProxy/Unbound.

## Promotion rule

CI proves the preservation contract and regression checks. Real VPS acceptance is still required for external Telegram connectivity and DNS reachability.
