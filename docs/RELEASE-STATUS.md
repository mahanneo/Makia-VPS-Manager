# Makia Release Status

Current stable line: **1.6.1**

| Surface | Repository gate | Distribution state | Production claim |
| --- | --- | --- | --- |
| VPS panel / installer | CI + Ubuntu 22.04/24.04 clean-install + upgrade smoke | `main` installer/updater | Ready, subject to host/provider UAT |
| Browser VPN | Browser Extension Build + real TLS gateway smoke | GitHub Release / Chrome Web Store package | Ready after store review + real browser UAT |
| Windows Full Device | Windows build + installer smoke | GitHub Actions artifact | Build-ready; real Windows protocol UAT required |
| OpenVPN WStunnel 443 | CI + clean-install + upgrade + Windows/Android package gates | opt-in mode, disabled until configured | Stable server integration; restrictive-network field UAT remains operator-specific |
| Android Full Device | Android build + APK structure/signature smoke | signed GitHub Release artifact + UAT artifact | WStunnel 443 Direct Connect supported on ARM64; real-device/network UAT still recommended |
| Client Portal / PWA | CI/browser smoke | served by Makia panel | Ready for account/profile delivery |
| iOS/iPadOS | PWA/Open/Import | served by Makia panel | No native in-app VPN claim |

## Product boundaries

- Browser VPN and Windows Full Device are separate products.
- Browser VPN does not require the Windows package.
- Windows Full Device does not install/register a browser Native Messaging host.
- Android CI artifacts are explicitly UAT/debug-signed until an operator-controlled release key is configured.
- Native iOS VPN is not claimed.

## Release hygiene

Only the latest stable `main` and current release documentation should be used for installation. Historical UAT documents remain for audit/history and are not current install instructions.
