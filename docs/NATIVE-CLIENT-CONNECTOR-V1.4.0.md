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
