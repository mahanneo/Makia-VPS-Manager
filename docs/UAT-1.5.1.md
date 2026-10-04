# Makia 1.5.1 — Stable Production UAT

## Server

1. Create and verify a Full Migration Backup.
2. Run `sudo makia-upgrade`.
3. Verify `cat /opt/makia-vps-manager/VERSION` returns `1.5.1`.
4. Run `sudo makia-doctor`.
5. Run `sudo makia-uat-smoke`.
6. Verify existing Xray/WireGuard/OpenVPN/SSH/Outline identities were not rotated.
7. Verify at least one existing user still connects.

## Browser

1. Install/load Makia Browser VPN 1.5.1.
2. Verify no Native Messaging permission exists.
3. Login with a disposable Client Platform account.
4. Connect and verify browser public IP changes to VPS egress.
5. Verify a non-browser application remains on the normal route.
6. Verify WebRTC does not expose non-proxied UDP while connected.
7. Verify Client used-bytes increases.
8. Revoke session/device and confirm new Browser Gateway requests fail.
9. Verify quota-exhausted, expired and disabled accounts cannot obtain fresh gateway credentials.

## Windows Full Device

1. Use the exact green `Makia-Client-Connector-Windows-x64-1.5.1` artifact.
2. Install with `Install-Makia.cmd`.
3. Confirm Browser VPN is not bundled or required.
4. Validate Direct Connect + Disconnect on disposable VLESS/Trojan/Outline or another supported sing-box profile.
5. Validate WireGuard/OpenVPN only when the corresponding official runtime is installed.
6. Confirm ticket replay is rejected.
7. Confirm disconnect removes the temporary active state/profile.

## Android

1. Use the exact green `Makia-Android-Connector-1.5.1-UAT` artifact for device UAT.
2. Confirm application id `com.makia.client`.
3. Validate Direct Connect on a real Android device for at least one Xray-family profile and one supported alternate profile.
4. Confirm Android VpnService permission/UI behaves correctly.
5. Confirm disconnect/reconnect, device revocation and expiry/quota behavior.
6. The CI artifact is **debug/UAT signed**. Do not publish it as a permanent public Android release.

## iPhone / iPad

Validate Client Portal/PWA login, Add to Home Screen, profile delivery and Open/Import. Makia does not claim a native in-app iOS tunnel.

## Promotion rule

Repository CI is necessary but not sufficient for provider networking, firewall/NAT, DNS propagation and real-device behavior. Public rollout requires real-host/browser/device UAT for the path being offered.
