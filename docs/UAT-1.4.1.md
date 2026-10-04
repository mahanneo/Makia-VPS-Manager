# Makia VPS Manager 1.4.1 — Browser VPN UAT

Release: 1.4.1

This patch builds on the frozen 1.4.0 UAT2 candidate. It must not rotate or recreate existing Xray, WireGuard, OpenVPN, SSH or Outline credentials.

## Repository gates

Required:
- Main CI: PASS
- Clean Install Smoke: PASS
- Native Connector Build: PASS
- Android Connector Build: PASS where triggered
- VERSION and app/config.py: 1.4.1
- Browser extension JavaScript syntax: PASS
- Windows connector regression tests: PASS
- Chrome/Edge native-host installer smoke: PASS

## Pre-update

1. Record installed version and health.
2. Run makia-doctor and makia-uat-smoke.
3. Create a Full Migration Backup and copy it off-host.
4. Record SHA256.
5. Verify at least one existing real user still connects before update.
6. Keep Client Portal rollout controlled.

## Pre-merge update

Deploy only the exact frozen 1.4.1 candidate SHA:

sudo env MAKIA_REF=<FROZEN_1_4_1_SHA> MAKIA_FORCE_MAIN=0 makia-upgrade

Do not use floating main for pre-merge UAT.

## Windows package

1. Download the exact-SHA Native Connector Build artifact.
2. Verify BUILD-INFO.txt and SHA256SUMS.txt.
3. Run Install-Makia.cmd.
4. Confirm makia:// registration.
5. Confirm Chrome and Edge NativeMessagingHosts registry entries point to com.makia.browser_host.json.
6. Confirm allowed_origins contains only chrome-extension://jgpmmenelldgfmjfnonhjaaaccfeniji/.

## Chrome / Edge

For each browser:
1. Load the bundled browser-extension folder unpacked.
2. Confirm extension ID is jgpmmenelldgfmjfnonhjaaaccfeniji.
3. Login using a disposable Makia Client account.
4. Verify permission is requested only for the selected Makia HTTPS origin.
5. Connect VLESS or Trojan.
6. Verify public IP changes only in that browser.
7. Verify another application on Windows does not inherit the browser proxy.
8. Disconnect and verify normal browser routing returns.
9. Repeat with Outline/Shadowsocks.
10. Verify WireGuard/OpenVPN are marked Full Device / Import and cannot start Browser VPN.

## Security checks

- Inspect chrome.storage.local: no VLESS UUID, Shadowsocks password, SSH password, WireGuard key or OpenVPN profile.
- Reuse a connector ticket: must fail.
- Expired/revoked/quota-exhausted account: new connection must fail.
- Revoke device: existing extension session must stop obtaining tickets.
- Change extension ID: Native Messaging must fail.
- Kill MakiaBrowserHost/sing-box and restart browser: stale proxy must be cleared.
- Browser disconnect must not stop an active Full Device Makia tunnel.

## Existing-user regression

After install/update verify existing Xray, WireGuard, OpenVPN, SSH and Outline users remain unchanged and can still connect.

## Promotion gate

Merge/promote only after exact-SHA CI, exact-SHA Windows artifact, real Chrome and Edge UAT, existing-user regression, and restore proof pass.
