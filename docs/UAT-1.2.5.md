# Makia VPS Manager v1.2.5 — Shared Config Permission / Update Recovery UAT

Date: 2026-09-29
Target: `1.2.5`

## Root cause

The Telegram MTProxy and DNS installers share `/etc/makia-vps-manager`.

- MTProxy correctly prepared that directory as `0710 root:makia-mtproxy` so the unprivileged service could traverse the directory and read only its `0640 root:makia-mtproxy` TOML.
- The DNS installer later reset the same directory to `0700`, silently revoking the MTProxy service group's traverse permission.
- A configured but already-broken MTProxy could then make the strict post-update UAT fail, causing the release containing the fix to roll back.

## Fix

- DNS installer now preserves the shared-directory contract.
- Install and update re-assert final ownership/modes after all optional network installers.
- Root-only files such as `makia.env`, `dns.json`, and `mtproxy.env` remain `0600 root:root`.
- `mtproxy.toml` remains `0640 root:makia-mtproxy`.
- Portable restore repairs the same contract before starting MTProxy.
- Updater attempts MTProxy auto-repair with the new runtime code before final acceptance.
- A pre-existing inactive optional MTProxy may soft-fail only inside the updater smoke gate so the repaired release can land; direct `makia-uat-smoke` remains strict.
- `MAKIA_FORCE_MAIN=1` bypasses any pinned archive override for emergency recovery.
- Updater verifies the running backend version matches the installed VERSION before accepting the release.
- Service worker cache advances to `makia-shell-v125` so the AUTO-port UI is not hidden behind stale assets.

## Host acceptance

- [ ] Force latest main once: `sudo env MAKIA_FORCE_MAIN=1 makia-upgrade`.
- [ ] Confirm `cat /opt/makia-vps-manager/VERSION` prints `1.2.5`.
- [ ] Confirm `curl -fsS http://127.0.0.1:8787/healthz` reports version `1.2.5`.
- [ ] Confirm `stat -c '%a %U %G' /etc/makia-vps-manager` prints `710 root makia-mtproxy`.
- [ ] Confirm `stat -c '%a %U %G' /etc/makia-vps-manager/mtproxy.toml` prints `640 root makia-mtproxy` when configured.
- [ ] Open Telegram Proxy and confirm port is AUTO/read-only rather than a manual 443 default.
- [ ] Save `tg.mahinet.shop`; verify an automatic high TCP port is selected.
- [ ] Verify Configured=YES, Service=ACTIVE and Listener=TCP/<port>.
- [ ] Refresh repeatedly; state remains stable.
- [ ] Run `sudo makia-uat-smoke` directly and require full PASS for the configured MTProxy.
- [ ] Verify the generated t.me/tg:// link on an external Telegram client.

## Promotion rule

CI validates source contracts, unit regressions, browser behavior and Xray compatibility. External Telegram reachability remains a real VPS/client UAT item.
