# Makia Client Platform PWA — Release Candidate Handoff

Branch: `feature/client-platform-pwa-v1.3.1`

Base hardening head: `6ee7f9099cf4edc0d4ebf95707836300f55f5e0f`

## Scope

This candidate completes the browser/PWA client experience without enabling the Client Portal in production and without starting the Windows Agent.

Implemented client surfaces:

- installable PWA shell for Android, iOS/iPadOS, Windows, macOS and standard browsers;
- platform-aware installation guidance and install prompt support;
- account status, quota, expiry, device usage and current-session countdown;
- online/offline state with automatic refresh after network recovery;
- protocol/access delivery with QR, copy, native file download and supported deep links;
- device inventory and non-current-device revocation;
- sensitive delivery cleanup on logout, page hide, visibility loss and BFCache restoration;
- isolated service-worker shell cache with no private Client route caching;
- Client-specific browser hardening headers (CSP, frame denial, referrer and permissions policy).

## Safety boundaries

The following remain intentionally unchanged until real production UAT:

- `MAKIA_CLIENT_PORTAL_ENABLED` remains disabled by default;
- no existing UUID/key/certificate/password is rotated;
- no existing Client, protocol identity or access artifact is recreated;
- no Xray/WireGuard/OpenVPN/SSH/Outline runtime is restarted by the PWA work;
- Windows Agent is not included;
- no merge to `main` is authorized by this candidate alone.

## Required live UAT

After VPS access is restored:

1. Verify production VERSION, services and listeners read-only.
2. Capture a Full Migration Backup and SHA256 before mutation.
3. Apply the immutable approved ref/SHA.
4. Run `makia-uat-smoke`.
5. Verify existing connected users remain connected.
6. Create one disposable Client: 1 GB, 1 day, device limit 1, concurrent 1.
7. Test Android/iOS/Windows PWA login, install, logout, BFCache, offline/online recovery and device revocation.
8. Validate Xray, Outline, WireGuard and SSH delivery with disposable credentials.
9. Test OpenVPN only in an explicit maintenance window if required.
10. Validate Backup -> Restore and Client-state persistence.
11. Run a limited canary.
12. Only after all gates pass, decide merge and rollout.

## Promotion rule

Repository CI is necessary but not sufficient. Production UAT + canary evidence is required before promotion.
