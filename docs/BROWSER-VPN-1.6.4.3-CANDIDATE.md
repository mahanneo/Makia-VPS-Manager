# Makia Browser VPN 1.6.4.3 — Candidate safety fix

**Status: candidate only; not a Stable release and not verified on a real Chrome/Edge client.**
The server release remains **v1.6.4**. This change does not modify the live VPS, Browser Gateway backend, TLS certificates, OpenVPN/WireGuard, Outline or MahiNet.

## Fixed behavior

Previously, a failed initial proxy exit-IP verification or manual recheck could call `clearBrowserProxy()`, silently removing the installed HTTPS proxy and permitting browser traffic to go out directly. The proxy-error event handler already kept the proxy installed on an unsuccessful follow-up check, but other paths did not.

This candidate retains a proxy that Chrome confirms is controlled by Makia, reports the connection as **not verified**, clears any previous verified exit IP, and shows a visible **Disconnect** action. Users can manually retry verification without changing network mode. A second Connect request is rejected while the held proxy remains installed. This is intentional **fail-closed** behavior: browser networking may be unavailable until the user explicitly disconnects or the Gateway recovers.

If Chrome never granted effective control of proxy settings (for instance, policy or another extension owns it), Makia cannot enforce a browser-wide kill switch and reports the failure instead of claiming protection. The UI distinguishes an active-but-unverified proxy from an established verified connection.

A portal authorization failure alone no longer triggers automatic proxy removal while an effective Makia proxy remains installed.

## Validation gates

- JavaScript syntax and mocked MV3 egress tests in GitHub Actions
- Python static manifest/UX contract regressions
- Chrome browser-extension artifact creation
- A **separate manual-release gate**: pushing to `main` no longer automatically overwrites an existing public stable asset. Upload is triggered only by a deliberately published matching server GitHub Release.

## Required before release

1. Install the unpacked candidate in Chrome and Edge, using a dedicated test account.
2. Check `chrome.proxy.settings` effective control, HTTP CONNECT auth/407, TLS identity, verified IPv4 exit IP, IPv6 behavior and DNS/WebRTC leakage on real desktop clients.
3. Simulate gateway connection refusal and DNS failures **during initial connect**, **while connected**, and **during manual reverify**. Ensure traffic does not silently fall back to direct while the proxy is held.
4. Confirm that **Disconnect** explicitly clears the proxy and privacy settings; check policy or other-extension conflicts.
5. Test browser restart, extension update and session expiry separately. **Automatic browser startup handling is not yet claimed fail-closed across process restart**, because the existing onStartup routine resets proxy state; this remains an explicit release blocker.
6. Confirm real-world behavior on unstable networks without exposing test credentials or genuine end-user traffic.

Do not treat a green mock test as a real Browser VPN UAT or publish this candidate before the remaining failure modes are addressed.
