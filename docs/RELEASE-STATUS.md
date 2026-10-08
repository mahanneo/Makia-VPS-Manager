# Makia Release Status

Current stable line: **1.6.3** (as of 2026-10-08). PR #98 and PR #99 are draft / unmerged; neither is a production release.

| Surface | Repository gate | Distribution state | Production claim |
| --- | --- | --- | --- |
| VPS panel / installer | CI + Ubuntu 22.04/24.04 clean-install + upgrade smoke | `main` installer/updater | Ready, subject to host/provider UAT |
| Browser VPN | Browser Extension Build + real TLS gateway smoke | GitHub Release / Chrome Web Store package | Ready after store review + real browser UAT |
| Windows Full Device | Windows build + installer smoke | GitHub Actions artifact | Build-ready; real Windows protocol UAT required |
| OpenVPN WStunnel 443 | CI + clean-install + upgrade + Windows/Android package gates | opt-in mode, disabled until configured | Code gates passed, but actual WStunnel setup, user policy and Iran-network UAT remain pending on production VPS |
| Android Full Device | Android UAT build; signed build currently fails at release signing secrets | UAT/debug-signed artifact only, no verified release-signed APK for 1.6.3 | ARM64 direct-connect implementation is not yet production verified on real devices/restricted networks |
| Client Portal / PWA | CI/browser smoke | served by Makia panel | Ready for account/profile delivery |
| iOS/iPadOS | PWA/Open/Import | served by Makia panel | No native in-app VPN claim |

## Product boundaries

- Browser VPN and Windows Full Device are separate products.
- Browser VPN does not require the Windows package.
- Windows Full Device does not install/register a browser Native Messaging host.
- Android CI artifacts are explicitly UAT/debug-signed until an operator-controlled release key is configured.
- Native iOS VPN is not claimed.

## Production acceptance still required

- Verify the exact installed host version and existing-user baseline before any upgrade.
- Confirm DNS, certificate chain, Nginx TCP/443 ownership, loopback OpenVPN backend and policy management socket.
- Prove authenticated Client Platform delivery, OpenVPN/Android transport, quota, expiry, disable/re-enable and revocation on real clients.
- Observe WireGuard UDP and TCP/TLS/WSS separately across different Iranian operators; a single profile cannot be universally certified as fast or reachable.
- Run off-host encrypted backup verification and reversible upgrade / existing-user regression.
- Persistent Android release signing requires operator-controlled environment secrets; never generate an unannounced new signing identity.

## Release hygiene

Only the latest stable `main` and current release documentation should be used for installation. Historical UAT documents remain for audit/history and are not current install instructions.
