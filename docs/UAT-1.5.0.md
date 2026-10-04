# Makia 1.5.0 Pure Browser VPN UAT

## Release invariants

Do not rotate or recreate existing:
- Xray UUIDs/credentials;
- WireGuard keys;
- OpenVPN certificates;
- SSH credentials;
- Outline access keys.

The Browser Gateway is an additive runtime.

## Repository gates

Required on one exact candidate SHA:
- CI PASS;
- Clean Install Ubuntu 22.04 PASS;
- Clean Install Ubuntu 24.04 PASS;
- Upgrade 1.3.0 -> 1.5.0 PASS;
- Upgrade production 1.4.2 -> 1.5.0 PASS;
- Browser Extension Build PASS;
- optional Windows Full Device Connector PASS if triggered.

## Host UAT

Before update:
1. Create Full Migration Backup.
2. Copy backup off-host and record SHA256.
3. Record existing Xray/WireGuard/OpenVPN/SSH/Outline user identity/credential samples without exposing secrets.
4. Verify existing users can connect.

After exact-SHA update:
1. `cat /opt/makia-vps-manager/VERSION` returns 1.5.0.
2. `/healthz` returns version 1.5.0.
3. `makia-doctor` has zero core FAIL.
4. `makia-uat-smoke` passes.
5. Browser Gateway is active when HTTPS domain/certificate are ready.
6. TCP/8445 is reachable externally.
7. Existing protocol credentials and users are unchanged.

## Extension UAT

Use the exact Browser Extension artifact from the same SHA:
1. Load the Web Store ZIP unpacked for pre-publication UAT.
2. Confirm Manifest V3 version 1.5.0.
3. Confirm `nativeMessaging` permission is absent.
4. Login with a disposable Client account.
5. Connect.
6. Confirm browser public IP is the Makia VPS egress IP.
7. Confirm non-browser applications are not proxied.
8. Confirm Disconnect restores normal Chrome/Edge routing.
9. Confirm Client logout invalidates proxy access.
10. Confirm device revoke invalidates proxy access.
11. Confirm account disable/expiry/quota exhaustion stops new proxy traffic.
12. Confirm private destinations such as localhost/RFC1918 are not reachable through the gateway.
13. Confirm no VPN protocol secret exists in extension local/session storage.

## Store promotion

Publish first as Unlisted/private-link distribution. Add the Store extension ID to `MAKIA_BROWSER_EXTENSION_IDS` if it differs from the development ID, restart Makia, and repeat login/connect UAT before wider rollout.
