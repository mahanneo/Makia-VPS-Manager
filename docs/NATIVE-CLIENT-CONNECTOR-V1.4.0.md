# Makia Native Client Connector v1.4.0 — RC Handoff

Branch: `feature/native-client-connector-v1.4.0`

Base PWA RC: `feature/client-platform-pwa-v1.3.1`

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
- No merge to main until VPS UAT + Windows canary passes.

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

## Apple / Android

The ticket API is platform-neutral, but true system VPN on Android/iOS requires a signed native app using the OS VPN APIs. The Windows RC does not claim those native apps are production-ready.
