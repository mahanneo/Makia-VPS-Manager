# Android Release Signing

The automatic Android connector workflow intentionally produces an installable **UAT/debug-signed** APK. A debug signing identity is not suitable for permanent public distribution because future builds may not be upgrade-compatible and the key is not an operator-controlled production identity.

## Production requirement

Before publishing Makia Android publicly, create one long-lived private Android release keystore and keep it outside the repository. Store the keystore and passwords only in a protected release system / GitHub Actions secrets.

Never commit the private keystore, passwords or base64 keystore contents to Git.

Recommended secret names for a future signed-release workflow:

- `MAKIA_ANDROID_KEYSTORE_B64`
- `MAKIA_ANDROID_KEY_ALIAS`
- `MAKIA_ANDROID_KEY_PASSWORD`
- `MAKIA_ANDROID_STORE_PASSWORD`

The first public production APK/AAB must establish the permanent application signing identity for `com.makia.client`. Preserve that key for all future upgrades.

Until those secrets are configured and a signed release workflow is verified on a real device, GitHub artifacts must remain clearly labelled `UAT`.
