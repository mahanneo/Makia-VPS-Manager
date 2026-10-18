# Makia Browser VPN 1.6.4.4 — verified egress candidate

**Status: UAT candidate, NOT official or deployed stable.** Server remains Makia 1.6.5; this Chrome/Edge extension is browser-only (not a device VPN). The previous 1.6.4.3 candidate is preserved as historical documentation.

## Why this candidate exists

The live screenshot submitted on October 17 shows a green Connected indicator but no `IP خروجی تأییدشده` card. The public IP shown by Check-Host was 109.230.72.229, identical to the direct baseline measured on both authorized office devices. This suggests a stale/unverified older extension or a proxy-controller conflict, but **does not establish the cause for a different browser profile**. The official extension ID was not found in the active Chrome/Edge profile inspected on Edari-Sec; Bunny VPN was present in Chrome, so do not attribute that profile's behavior to Makia or claim live reproduction.

## Changes compared to 1.6.4.3 candidate

- A proxy installation is not deemed a successful VPN until Chrome reports effective proxy control and a real HTTPS IP check returns a changed exit IP.
- A failed egress probe is fail-closed: retain the effective proxy, show **unverified**, clear previous exit IP, offer explicit Disconnect. Never silently switch to direct because a probe failed.
- A successful old probe becomes stale after two minutes; the next status request revalidates it, rather than continuing to show Connected from prior state.
- The popup hands the server-provided proxy credential expiry to the worker; expired credentials result in **unverified**, even when Chrome still has the proxy setting.
- Browser restart/update retain installed proxy as unverified with session-only credentials; explicit Disconnect/Reconnect after restart is necessary.
- Add the Node mock egress test to the mandatory CI test job: 14 scenario groups including stale probe, expiring credentials, failed CONNECT and no direct fallback.
- Unique manifest and build artifact version **1.6.4.4**, to distinguish this candidate from historical versions.

## Gates required before stable approval

- Confirm manifest 1.6.4.4 and exact source SHA in ZIP and extension management UI.
- On an authorized test Chrome/Edge profile, disable **other proxy-owning extensions temporarily**, keeping user data intact; ensure Makia is the only controller.
- Take a **direct baseline** from the same browser and network after explicit Disconnect.
- Connect a dedicated test account and verify a successful HTTPS GET through Makia and **actual changed public IPv4**. Check correct exit-IP card and fresh timestamp, compare against local baseline; capture an authenticated 407->auth->200 tunnel sequence without recording password.
- Check normal Chrome site browsing, HTTP and HTTPS, IPv6, DNS/WebRTC limitations, restrictions to browser traffic (not Windows system VPN).
- Check token expiry, browser startup/update, disabled/expired/quota-exhausted account, other-extension/policy conflict, network drop, fail-closed, recovery and explicit Disconnect.
- Host journals, DB token status and RX/TX require authorized server SSH access. An outside unauthenticated 407 on port 9444 proves the Gateway responds, **not** user traffic egress.
- Do not install an unpacked package over an existing identical-ID extension or expose customer credentials; first identify installed extension version and install mode. Do not ship publicly before real UAT.

No changes to live user VPN listeners, Makia server, MahiNet, Outline or Telegram Shop are part of this branch.
