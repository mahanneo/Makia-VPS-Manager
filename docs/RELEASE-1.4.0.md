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

Artifact integrity rule:

- use only artifacts produced by the green Actions runs for the frozen UAT SHA;
- record the Windows and Android artifact digests in the UAT evidence / PR #73;
- do not treat an older candidate digest as the final release digest.

Expected UAT artifact names:
- Windows: `Makia-Client-Connector-Windows-x64`
- Android: `Makia-Android-Connector-1.4.0-UAT`

## Android signing boundary

The normal PR Android package is suitable for RC/UAT and is debug-signed.

For general distribution, the repository now includes the manual **Android Signed Release** workflow. It builds from the UAT-approved ref and requires one persistent private signing identity stored in the protected `android-release` GitHub environment:

- `MAKIA_ANDROID_KEYSTORE_B64`
- `MAKIA_ANDROID_KEYSTORE_PASSWORD`
- `MAKIA_ANDROID_KEY_ALIAS`
- `MAKIA_ANDROID_KEY_PASSWORD`

The signing key must be backed up securely and must not be rotated between routine releases; Android requires the same signing identity for seamless upgrades. The private keystore must never be committed to the repository or distributed with artifacts.

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
