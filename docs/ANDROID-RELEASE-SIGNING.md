# Android Release Signing — Makia v1.6.4

## Current, verified release status (2026-10-08)

- Android Connector UAT Build: **SUCCESS** on `main` v1.6.4. Its APK is a debug/UAT-signed artifact only.
- Android Signed Release: **FAILURE** at the `Install persistent release signing identity` step. GitHub Actions emitted `MAKIA_ANDROID_KEYSTORE_B64 is required`; the required keystore secret was empty.
- Native Android build dependency / AAR phase completed; the failing step is release signing configuration, not a proven native protocol defect.
- **No signed production APK should be claimed or downloaded from the v1.6.4 release until the signed workflow succeeds and the asset is verified.**

## Mandatory signing identity / upgrade compatibility

Before enabling production distribution, first determine whether any previously installed release-signed Makia Android app already exists. If it does, reuse that **exact** existing signing identity and key alias. Changing Android signing certificates without an authorized signing-key rotation path can block in-place upgrades.

Keep keystore files and passwords entirely outside the public repository and ChatGPT messages. Store an independently protected recovery copy of the original keystore.

The Android application ID is `com.makia.client`.

## Required GitHub Actions secrets (exact names from current workflow)

The workflow `.github/workflows/android-release.yml` executes in GitHub Actions environment `android-release` and reads these four secrets:

| Exact GitHub secret | Content |
| --- | --- |
| `MAKIA_ANDROID_KEYSTORE_B64` | Base64 of the **existing** Android release keystore binary |
| `MAKIA_ANDROID_KEYSTORE_PASSWORD` | Keystore/store password |
| `MAKIA_ANDROID_KEY_ALIAS` | Key alias inside the keystore |
| `MAKIA_ANDROID_KEY_PASSWORD` | Key/alias password |

**Important:** `MAKIA_ANDROID_STORE_PASSWORD` (without `KEY`) is an old documentation typo; the current workflow reads **`MAKIA_ANDROID_KEYSTORE_PASSWORD`**. Do not configure only the obsolete name.

The repository owner can set these via GitHub → Repository **Settings** → **Environments** → **android-release** → **Environment secrets** → **Add secret**, or repository-level Actions secrets if permitted by policy. The deployment environment name must match `android-release`.

Prefer protected environment secrets, restrictive environment deployment permissions, and a trusted signing identity. Never echo key data in logs or commit base64 content.

## Publish gate

1. Verify availability of the original keystore and check signing certificate fingerprint against any prior installed release-signed package. If no prior signed release exists, explicitly approve creating and securely backing up the first permanent production key.
2. Configure all four exact Secrets in the `android-release` environment.
3. From GitHub **Actions** → **Android Signed Release** → **Run workflow**, select the approved release source `main` or the exact v1.6.4 release commit.
4. Confirm successful Gradle build, `apksigner verify`, expected ARM64 native libraries, uploaded APK and checksum, and APK presence in `v1.6.4` GitHub Release.
5. Perform Android ARM64 real-device install/update and connect/disconnect tests, including WStunnel443, quota/revoke, app lifecycle, and restricted-network field tests. Do not claim that every Iranian ISP is supported.

## UAT-only APK

The separately named `Makia-Android-Connector-1.6.4-UAT` GitHub Actions artifact is appropriate for controlled tests only. Debug signatures should not be used for permanent, publicly distributed production clients. A VPN client's native connection, permission prompts, account binding, quota and revocation are only proven by actual device testing.
