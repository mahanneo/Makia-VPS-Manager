# Makia VPS Manager 1.3.0 — Client Platform Production UAT

Date: 2026-09-29
Target: `1.3.0`

## Release objective

Ship the end-user Makia Client Platform without disrupting existing connected protocol users.

The Client Portal is installed with the release but remains disabled until the administrator enables it from **Client Platform / اپ کاربران**. Existing SSH, Xray, WireGuard, OpenVPN and Outline credentials are not rotated by the release.

## Pre-update safety

- [ ] Current host is healthy on the existing stable release.
- [ ] A full Makia backup exists.
- [ ] Existing Xray/WireGuard/OpenVPN/SSH users are connected normally.
- [ ] DNS and Telegram Proxy state are recorded if used.

## Update acceptance

Run the normal immutable Makia updater.

After update:

- [ ] `cat /opt/makia-vps-manager/VERSION` reports `1.3.0`.
- [ ] `curl -fsS http://127.0.0.1:8787/healthz` reports version `1.3.0`.
- [ ] `sudo makia-uat-smoke` passes the existing host gates.
- [ ] Existing connected protocol users remain usable.
- [ ] Admin panel opens and the new **اپ کاربران / Client Platform** navigation item is visible.
- [ ] Client Portal is still disabled unless explicitly enabled by the administrator.

## Client Platform staging acceptance

Before giving credentials to real customers:

1. Open **اپ کاربران / Client Platform**.
2. Create one test Client account:
   - expiry: 1 day;
   - quota: 1 GB;
   - device limit: 1;
   - concurrent devices: 1.
3. Bind a disposable/test protocol identity or access artifact.
4. Enable Client Portal from the rollout switch.
5. Open `https://<panel-domain>/client/` in a private browser/device.
6. Verify:
   - login works;
   - PWA page loads on mobile and desktop;
   - plan/expiry/quota/device state is displayed;
   - only explicitly bound access is visible;
   - QR/file/deep-link delivery works for the bound protocol;
   - another fresh browser/device is rejected when device limit is 1;
   - password rotation invalidates existing Client sessions;
   - device revoke invalidates that device session;
   - disabling Client Portal returns the public Client routes to disabled state without restarting VPN services.

## Protocol enforcement acceptance

### Xray / Outline

- [ ] Bound test credential is suspended when Client account expires or aggregate quota is exhausted.
- [ ] Credential returns only when the suspension reason belongs to Client Platform and the account is valid again.
- [ ] Pre-existing manually disabled credentials are never auto-enabled.

### WireGuard

- [ ] Existing peer key is not rotated.
- [ ] First runtime counter sample creates a post-binding baseline.
- [ ] Subsequent traffic contributes to Client aggregate usage.
- [ ] Expiry/quota disables only the bound peer.
- [ ] Restoring account policy re-enables only peers suspended by Client Platform.

### SSH

- [ ] Expiry/disabled account locks only the bound SSH user and disconnects active sessions.
- [ ] Concurrent/source-IP ceilings are enforced.
- [ ] Byte quota is not presented as enforceable for SSH.

### OpenVPN

New Makia OpenVPN bootstraps include local Client policy controls. Existing OpenVPN servers require an explicit local-admin setup action.

For an existing server:

- [ ] Client Platform reports **Setup required**, not Hard policy.
- [ ] Administrator clicks **فعال‌سازی کنترل OpenVPN** only in a maintenance window.
- [ ] Warning explicitly states that OpenVPN will restart briefly.
- [ ] Server config is backed up automatically before modification.
- [ ] OpenVPN listener returns after restart.
- [ ] Local Unix management socket is ready.
- [ ] Existing OpenVPN client profiles/certificates are not rotated.
- [ ] A bound OpenVPN test profile records post-binding traffic.
- [ ] Expiry/quota writes only a Makia-owned CCD disable file and disconnects the matching common-name session.
- [ ] Restoring the account removes only the Makia-owned disable file.

## Rollout recommendation

After the test account passes:

- enable the Client Portal;
- onboard a small number of real users first;
- use Device limit = 1 and Concurrent = 1 for single-device plans;
- bind one credential/profile to only one Client account;
- keep the Admin panel URL and credentials private.

## Known boundary

The PWA device registration is a browser/device-control layer, not hardware attestation. Users can securely receive/import their VPN profile from the PWA today. Hardware-backed device binding and one-click native tunnel control require the later Makia native agent/mobile client phase.

## Repository-side privacy and persistence gates

Before canary rollout, CI must also prove these invariants:

- Client logout revokes the server-side Client session and removes the Client session cookie.
- Client PWA CacheStorage is limited to the static shell; private `/client/` pages, API responses and delivered credentials are always network-only with `no-store`.
- A consistent SQLite backup preserves Client accounts, registered devices, sessions, protocol bindings, artifact bindings, usage baselines and Client-owned policy state.
- The updater creates a consistent pre-change data backup and never replaces or removes the persistent application `data` tree.
- These repository gates complement, but do not replace, the live VPS Backup → Update → Restore test and real-device PWA UAT.

## Live VPS evidence to capture

For the production UAT record, retain evidence for:

- the Full Migration Backup created before the host update, including its SHA256;
- the immutable source commit used for the update;
- installed `VERSION` and local `/healthz` result after update;
- the complete `makia-uat-smoke` result;
- before/after status of existing Xray, WireGuard, OpenVPN, SSH and Outline users/services;
- the disposable Client account parameters and bound disposable credential;
- mobile and Windows PWA login/install/device-limit results;
- protocol delivery results for QR, native file and compatible deep link;
- Backup → Restore verification that Client account/device/binding/policy state survives.

Do not promote the Client Portal to general availability from CI alone. The real VPS and canary gates below remain mandatory.

## Stable promotion gate

Release 1.3.0 is code-promotable only when:

- GitHub `test` PASS;
- GitHub `xray-core-smoke` PASS;
- GitHub `browser-smoke` PASS;
- host update/health smoke PASS;
- one real Client account PWA UAT PASS;
- existing connected users show no regression.
