# Makia Native Client Connector v1.4.0 — Release Handoff

Release line: `1.4.0`

Development branch: `feature/native-client-connector-v1.4.0`

## Goal

Turn the Makia PWA into a one-click client experience on Windows while keeping browser credentials and VPN secrets out of custom-protocol URLs.

## Security model

1. The authenticated PWA requests a one-time connector ticket.
2. The ticket is bound to the current Client account and device.
3. Ticket lifetime is 60 seconds and it can be redeemed once.
4. The browser launches `makia://connect?controller=...&ticket=...`.
5. Makia Client Connector redeems the ticket over HTTPS.
6. The server returns the selected profile only after successful redemption.
7. The connector starts the local tunnel runtime.
8. `makia://disconnect` stops the active tunnel and removes temporary active profile/state files.

No UUID, password, private key or complete profile is placed in the `makia://` launch URL.

## Windows direct-connect matrix

| Makia access | Runtime | Result |
| --- | --- | --- |
| VLESS | sing-box TUN | full-tunnel |
| VMess | sing-box TUN | full-tunnel |
| Trojan | sing-box TUN | full-tunnel |
| Hysteria2 | sing-box TUN | full-tunnel |
| Outline / Shadowsocks | sing-box TUN | full-tunnel |
| SSH / NPV profile | sing-box SSH outbound + TUN | full-tunnel |
| WireGuard | official WireGuard for Windows | native tunnel |
| OpenVPN | OpenVPN binary/client runtime | native tunnel |

The connector validates sing-box configuration before starting it.

## Windows package

GitHub Actions builds:

`Makia-Client-Connector-Windows-x64.zip`

Contents:

- `MakiaClientConnector.exe`
- pinned `sing-box.exe` 1.14.2
- `install.ps1`
- `uninstall.ps1`

The sing-box archive is SHA256-pinned in CI.

Installer registers the per-user `makia://` URL protocol.

## Production safety

- Client Portal remains disabled by default until live UAT.
- Existing production credentials are not rotated.
- Existing VPN services on the VPS are not restarted by this client work.
- Direct-connect tickets are additive metadata in the Client plane.
- Repository promotion to `main` does not enable the Client Portal. Production activation remains blocked until real-host UAT and canary pass.

## Required live Windows UAT

1. Download the CI-built Windows connector artifact.
2. Verify artifact SHA256 and unpack.
3. Run `install.ps1`.
4. Enable Client Portal only in the controlled UAT window.
5. Create disposable Client: 1 GB / 1 day / device=1 / concurrent=1.
6. Login to PWA on a Windows test machine.
7. Validate one-click Connect + Disconnect for each disposable protocol.
8. Confirm public IP/DNS route through the tunnel where expected.
9. Confirm quota/expiry policy disconnect behavior.
10. Confirm second device and concurrent login enforcement.
11. Confirm ticket replay is rejected.
12. Confirm existing real users remain connected throughout.
13. Backup -> restore -> repeat one direct-connect smoke.
14. Limited canary only after all checks pass.

## Chrome / Edge Browser Extension

Makia 1.4.0 also builds a Manifest V3 Chromium extension and a non-elevated MakiaBrowserHost.exe.

- Browser Only starts a loopback-only SOCKS5 endpoint through sing-box and applies it only to the current Chrome/Edge browser with the proxy permission.
- Device VPN delegates to the existing elevated MakiaClientConnector.exe and keeps the full-tunnel behavior.
- Pairing uses a five-minute, one-time code generated inside the authenticated Client Portal.
- The extension never receives VPN delivery secrets or the long-lived Client session token.
- The Native Host protects its Client session token with Windows DPAPI.
- Native Messaging allows only exact extension IDs; there is no wildcard origin and no generic command bridge.

GitHub Actions artifacts:

- Makia-Client-Connector-Windows-x64
- Makia-Browser-Extension-Chromium-1.4.0

See docs/BROWSER-EXTENSION-V1.4.0.md for the full handoff and client/browser-extension/INSTALL.md for UAT installation.

## Android

The Android connector is built from pinned official SagerNet sources and uses Android `VpnService`.

Direct Connect support in 1.4.0:

- VLESS
- VMess
- Trojan
- Hysteria2
- Shadowsocks / Outline
- SSH
- WireGuard

OpenVPN remains Import-based in 1.4.0.

The Android package is validated in GitHub Actions and must still pass real-device UAT before general rollout.

## iPhone / iPad

The authenticated Makia PWA supports iOS login, Add to Home Screen and platform-aware profile Open/Import.

Makia 1.4.0 does **not** claim native in-app iOS VPN. A native iOS tunnel requires an Apple-signed application with Network Extension / Packet Tunnel entitlements and real-device UAT.

See `docs/UAT-1.4.0.md` for the production gate.


## Final CI artifacts

The authoritative connector artifacts must be taken from the green GitHub Actions runs for the **frozen UAT SHA** referenced by PR #73 / `release/v1.4.0-uat1`.

- Windows artifact: `Makia-Client-Connector-Windows-x64`
- Android UAT artifact: `Makia-Android-Connector-1.4.0-UAT`

Record the GitHub Actions artifact digests from those exact runs in the UAT evidence. Do not copy a digest from an earlier candidate because build artifacts can differ even when product source changes are documentation/test-only.

The Android PR/UAT artifact is debug-signed. Do not treat it as the permanent public signing identity. Before general Android distribution, configure and preserve a single private release signing key so later APK upgrades remain signature-compatible.
