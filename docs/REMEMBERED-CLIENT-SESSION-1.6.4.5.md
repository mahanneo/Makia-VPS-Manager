# Makia Client — Remember this device and one-click browser reconnect (UAT candidate)

**Status:** Browser VPN 1.6.4.5 remains a UAT candidate on PR #119 (based on official main 1.6.5). An authorized **limited live Client Web pilot** installed only `app/client_portal.py`, `app/templates/client_login.html` and `app/static/client.css` after a verified rollback backup (details in PR #119); the original app reports 1.6.5. This is NOT a tagged 1.6.6 release, and extension live Chrome Reload / remembered-login restart / authenticated-egress UAT remain outstanding. It does not change administrator authentication, VPN protocol listeners, MahiNet or Outline.

## User behavior

- The web Client login and extension login now expose an initially checked option **«ورودم روی این دستگاه تا ۳۰ روز حفظ شود»**. Users on shared devices can uncheck it for the previous 12-hour session. There is **no saved username/password login** or localStorage of the password.
- The web Client stores an opaque, server-revocable, HttpOnly, SameSite=Strict, Secure-on-HTTPS cookie under `/client`. It persists after browser closure for up to 30 days when opted in. The separate device-identification cookie is NOT an authentication credential.
- The extension stores the opaque account session in `chrome.storage.local` only if opted in; for unchecked sessions it uses `chrome.storage.session`, which is cleared on browser restart. The normal username may be remembered for convenience; passwords are never persisted.
- Server stores a **hash only** of the account token, bounded by the existing `create_session` maximum of 30 days. Every request still validates the account state, subscription expiry/quota, active device, nonrevoked session and fixed expiry. Password change, account disable, explicit logout and device revoke invalidate it.
- Browser Gateway credentials remain independent, server-generated and short-lived (12 hours max), in Chrome `storage.session`. They are never copied into persistent local storage.
- Upon browser restart/update the effective HTTPS proxy is held and marked **unverified**; the user can use **«اتصال مجدد امن»** to fetch fresh Gateway credentials using the remembered Client session and rotate the proxy credential in place, without removing the proxy and without retyping their account password. Only the verified, configured Makia control-plane host bypasses the proxy so reauthentication remains reachable. Browser traffic to other websites stays proxied/blocked.
- If a session expires/revokes, login with the actual account credentials is still mandatory; remembering a device is not permanent or permissionless. Other proxy extensions, policy takeover, failed exit-IP verification and expired account do not falsely show Connected.
- Incognito and browser profile changes are separate devices/sessions. Clearing site data/extension data or uninstalling loses saved login.

## Regression and UAT

- `pytest tests/test_remembered_client_sessions.py`: 30-day opt-in duration, 12-hour unchanged default, password/device/account revocation, short proxy token, login form/extension contract.
- `node client/browser-extension/test_verified_egress.cjs`: 16 groups, including browser restart with deleted session-only proxy secrets, one-click renewal, expired/mismatched credential rejection, no direct fallback if exit check fails.
- Full repo CI, browser extension build and signed-source checks must pass on the final SHA.
- Mandatory real Host/staging UAT before merge or deployment: password login with checked/unchecked option, PWA close/reopen, Chrome/Edge restart, session expiry and forced revoke, 12-hour Gateway credential expiry or safe time-controlled simulation, fresh egress IP after one-click reconnect, explicit Disconnect to direct, proxy conflict, account expiry/quota, logout, same device vs another device.
- Confirm a live existing 1.6.4.4 unpacked extension can upgrade without changing extension identity or wiping local account session, and that its control-plane domain is reachable to fetch new credentials after upgrade.
- Do not store extension, web Client, proxy or admin credentials in logs, reports or GitHub artifacts; do not enable autosignin on shared computers.

No claims of real-browser, real-VPS or deployment verification until those steps actually pass.
