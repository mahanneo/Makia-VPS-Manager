# Makia 0.26.0-rc6 — Self-Service Access Portal UAT

RC6 is a Release Candidate, not Stable.

## 1. Upgrade
1. Create a Full Migration Backup from the currently installed release.
2. Upgrade the VPS to RC6.
3. Confirm dashboard and `VERSION` report `0.26.0-rc6`.
4. Run `makia-doctor` and `makia-uat-smoke`.
5. Hard-refresh the browser once after upgrade.

## 2. Client portal link — all protocols
For a newly created access in each protocol family:
- SSH / NPV
- Xray / V2Ray
- WireGuard
- OpenVPN

After creation, confirm a **Client portal link / لینک اختصاصی کاربر** button is visible.
Open the link in a private/incognito browser where the Makia admin is not logged in.

Expected:
- The page opens without an admin login.
- Only that client's data is visible.
- The page is noindex/noarchive and returns no-store cache headers.
- The page contains a clear warning that the link itself is private.

## 3. Protocol-specific delivery
### Xray
- QR is shown.
- Share link is visible and copyable.
- Profile/subscription-related files are downloadable when present.
- Expired, disabled or quota-exhausted managed Xray access does not expose an active connection payload.

### WireGuard
- QR is shown and imports into the official WireGuard client.
- The .conf file downloads and imports successfully.
- Private/public keys and Endpoint match the original generated peer.

### OpenVPN
- The .ovpn file downloads from the browser page.
- The downloaded file imports into OpenVPN Connect.
- No misleading OpenVPN QR is shown.

### SSH / NPV
- SSH connection details are visible to the link holder.
- The NPV QR/link is shown when NPV delivery is enabled.
- credentials.txt and other intended user files are downloadable.
- Standard OpenSSH config does not falsely embed the password.

## 4. Link rotation
For one test user:
1. Copy the current client portal URL.
2. Click **Rotate link / ساخت لینک جدید**.
3. Verify the old URL returns 404.
4. Verify the new URL opens correctly and exposes the same client configuration.

## 5. Revocation
For one test access:
1. Open its client portal and verify it works.
2. Revoke/delete the access from Makia.
3. Confirm the old client portal URL no longer resolves to the access.

## 6. File boundary
From a client portal:
- Download each listed file.
- Confirm filenames and content belong only to that client.
- Manually request a filename that is not in the artifact; it must return 404.
- Try a path traversal-style filename; it must not return another server file.

## 7. Language consistency
Set panel language to Persian and reload:
- Main navigation, dashboard, access center, dialogs, login, 2FA, support login and client portal should render Persian labels.
- Protocol/product names such as Xray, WireGuard and OpenVPN may remain as product names.

Set panel language to English and reload:
- The same surfaces should render English labels.
- Persian UI labels must not remain on the main workflows.
- Client portal and connection guide must open in English by default.

Also verify `?lang=fa` and `?lang=en` on a client portal only change presentation language and do not change the credential/config itself.

## 8. Legacy artifacts
For at least one pre-RC6 access artifact that still has an exportable credential:
- Open Access Center.
- Request its Client Portal link.
- Confirm Makia creates the public token lazily without changing the underlying client credential.
- Re-download the native file and compare its connection identity with the previous export.

## 9. Regression
Re-test:
- Xray QR/share/subscription.
- WireGuard native config export.
- OpenVPN OVPN export.
- SSH/NPV Protected ZIP.
- Full Migration Backup creation and Verify/Preview.
- Full Migration restore from RC5 into RC6 on a disposable VPS.

## 10. Field gate
From at least one Iranian mobile network and one fixed ISP where possible:
- Open the public client portal over HTTPS.
- Download/import the intended protocol file or QR.
- Establish a real tunnel.
- Test DNS, web traffic, reconnect and at least 10 minutes of stability.

Do not promote RC6 to Stable until real VPS portal-link UAT and field testing pass.
