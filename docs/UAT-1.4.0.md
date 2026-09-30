# Makia VPS Manager 1.4.0 — Production UAT

Release: `1.4.0`

This UAT is mandatory before enabling the Client Portal or rolling Direct Connect out to real users.

## Repository gates

Required before host work:

- Main CI: PASS
- Xray Core smoke: PASS
- Browser smoke: PASS
- Native Connector Build (Windows): PASS
- Android Connector Build: PASS
- `VERSION` and `app/config.py`: `1.4.0`

Reference final candidate artifacts:

- Windows Actions artifact: `Makia-Client-Connector-Windows-x64`
- Windows artifact digest: `sha256:76aa2b5aa2963e612e04e87d91b7ed70354d0f98d1cf1f10b1159a0ce213cdaa`
- Android Actions artifact: `Makia-Android-Connector-RC`
- Android artifact digest: `sha256:618dba8f8ff41c69c53dae7876c33e41015a2e485403b24cf15e84232af0c9c9`

## Safety invariants

The 1.4.0 rollout must not:

- rotate/delete/recreate existing Xray UUIDs;
- rotate WireGuard private/public keys;
- replace OpenVPN certificates;
- change SSH credentials;
- revoke/reissue Outline keys;
- change active protocol ports without an explicit maintenance decision;
- enable the Client Portal globally before controlled UAT;
- restart protocol services merely to test the Client Portal.

## Before update

1. Verify the repository/source commit that will be deployed.
2. Record current installed version and health.
3. Capture a Full Migration Backup.
4. Copy the backup off-host.
5. Record SHA256 for the backup.
6. Run `makia-doctor` and `makia-uat-smoke`.
7. Record active listeners/services for Xray, WireGuard, OpenVPN, SSH and Outline.
8. Verify at least one existing real user can connect before the update.
9. Keep `MAKIA_CLIENT_PORTAL_ENABLED=auto` with the Admin rollout setting OFF.

## Update

Use the normal immutable updater path only after the backup is verified:

```bash
sudo makia-upgrade
```

Do not use a floating/unverified archive override.

## Immediate post-update checks

1. `/healthz` returns healthy.
2. Installed/running Makia reports version `1.4.0`.
3. `makia-doctor` passes.
4. `makia-uat-smoke` passes.
5. Existing Xray users still connect.
6. Existing WireGuard users still connect.
7. Existing OpenVPN users still connect.
8. Existing SSH users still connect.
9. Existing Outline keys still work.
10. No unexpected credential/port/runtime changes are present.

## Disposable Client UAT

Create a disposable account only:

- quota: 1 GB;
- expiry: 1 day;
- device limit: 1;
- concurrent device limit: 1.

Bind only disposable/test accesses.

Verify:

- correct login/rejection behavior;
- quota/expiry status;
- device registration and revoke;
- same-account access isolation;
- second-device/concurrent-limit rejection;
- logout/session revoke;
- delivered secrets are not retained in PWA cache;
- connector ticket expiry;
- connector ticket replay rejection;
- revoked device cannot redeem a ticket.

## Windows Direct Connect

Install the CI-built Windows package and verify:

- installer completes;
- `makia://` is registered;
- VLESS Direct Connect;
- VMess Direct Connect;
- Trojan Direct Connect;
- Hysteria2 Direct Connect;
- Shadowsocks / Outline Direct Connect;
- SSH / NPV Direct Connect;
- WireGuard native path;
- OpenVPN native path;
- Disconnect stops only the disposable client tunnel;
- connector error dialog/log works;
- DNS and public IP follow the selected tunnel where expected.

## Android Direct Connect

On a disposable Android device:

1. Open `https://<public-host>/client/`.
2. Login using the disposable Makia Client account.
3. Optionally install the PWA with Install app/Add to Home Screen.
4. Install the approved Makia Android Connector APK.
5. Grant Android VPN permission.
6. Test VLESS, VMess, Trojan, Hysteria2, Shadowsocks/Outline, SSH and WireGuard where provisioned.
7. Confirm Direct Connect starts/stops cleanly.
8. Confirm OpenVPN is shown as Import-based, not falsely claimed as Direct.
9. Confirm revoked/expired/quota-exhausted accounts cannot establish a new connector session.

## iPhone / iPad

On Safari:

1. Open the same `/client/` URL.
2. Login with the disposable account.
3. Share → Add to Home Screen.
4. Reopen Makia from Home Screen.
5. Confirm account/quota/device data is correct.
6. Test `اتصال / Import` for assigned profiles with a compatible iOS client.

Makia 1.4.0 does **not** claim native in-app iOS tunnelling. A future native iOS client requires Apple signing and Network Extension / Packet Tunnel entitlements plus real-device UAT.

## Reverse proxy / public origin

For native Direct Connect, the public origin must be HTTPS.

When reverse-proxy headers are reliable, Makia can derive the public origin. Otherwise set:

```bash
sudo makia-owner-config --public-base-url https://panel.example.com
```

The approved Android APK download URL can be configured with:

```bash
sudo makia-owner-config --android-connector-url https://downloads.example.com/Makia-Android-Connector.apk
```

Restart only the Makia web service after changing these runtime URL settings; do not restart VPN runtimes.

## Backup / restore proof

After Client UAT:

1. Create another Full Migration Backup.
2. Restore it on a disposable replacement VPS/staging host.
3. Confirm Client accounts, devices, access bindings, policy state and connector metadata survive.
4. Repeat one Windows and one Android disposable Direct Connect smoke.

## Canary gate

Only after all previous checks pass:

1. enable Client Portal for a very small canary group;
2. do not migrate all users at once;
3. verify existing non-Client-Portal users remain unaffected;
4. observe accounting, expiry and device-limit behavior;
5. keep rollback backup immediately available.

General rollout is allowed only after the canary passes.

## Current production status

Repository CI can prove build/unit/browser/package contracts, but it cannot prove the real VPS network path, provider firewall/NAT, installed protocol daemons, DNS routing, Android OEM behavior or Apple client behavior. Those remain host/device UAT requirements.
