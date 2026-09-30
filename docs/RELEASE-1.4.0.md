# Makia VPS Manager 1.4.0 — Release Readiness

Status: **Code-complete / repository-verified / production-UAT pending**

Target branch after UAT: `main`

Release branch: `feature/native-client-connector-v1.4.0`

## Included

- authenticated Client Portal / PWA
- isolated end-user accounts, quota, expiry and device controls
- Windows Direct Connect
- Android Direct Connect
- mobile-first Android/iPhone login flow
- one-time device-bound connector tickets
- HTTPS reverse-proxy origin hardening
- Windows installer verification in CI
- Android APK build and package validation
- Client UAT and rollout documentation

## Final repository verification

On the final 1.4.0 candidate line:

- CI: PASS
- Xray smoke: PASS
- Browser smoke: PASS
- Windows Native Connector Build: PASS
- Android Connector Build: PASS

Final verified artifact digests from the green candidate run:

- Windows `Makia-Client-Connector-Windows-x64`:
  `sha256:6c0ce22b2c82e645df8c5c521ebe9e7bf83fa1b6476f3c046853653fc13ffb8c`
- Android `Makia-Android-Connector-RC`:
  `sha256:e6677669268bda57e85a1595fe874795a0ea1926793a7cb844e9e3aed68ba4ad`

## Android signing boundary

The CI Android package is suitable for RC/UAT but is debug-signed. General distribution requires one persistent private release signing identity. Do not rotate that key between releases, otherwise Android will reject seamless upgrades.

## iOS boundary

Makia 1.4.0 provides the authenticated iPhone/iPad PWA, Add to Home Screen, device-aware UI and profile Open/Import flow. Native in-app iOS tunnelling is intentionally not claimed in 1.4.0 because it requires Apple signing, Network Extension / Packet Tunnel entitlements and real-device validation.

## Production promotion gate

Do not enable general rollout until all of the following are complete:

1. verify repository state and target commit;
2. take a Full Migration Backup from the real VPS;
3. calculate and store backup SHA256;
4. run update/UAT on the live host without rotating or recreating existing credentials;
5. verify existing Xray / WireGuard / OpenVPN / SSH / Outline users remain connected;
6. run disposable Windows and Android Direct Connect tests;
7. test iPhone/iPad PWA + Import flow on a real device;
8. validate quota / expiry / device limits and ticket replay rejection;
9. restore the backup on a disposable replacement VPS and repeat a connector smoke;
10. enable a very small canary;
11. only then merge/promote and enable general Client Portal rollout.

The Client Portal remains disabled by default, so repository promotion alone does not expose the new client surface.
