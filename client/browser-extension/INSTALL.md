# Makia VPN Browser Extension — Chrome / Edge

This package is the Chromium companion for Makia 1.4.0.

## Modes

- **Browser Only** routes only Chrome/Edge through a loopback SOCKS5 proxy started by Makia Browser Host. It does not change the Windows system proxy.
- **Device VPN** delegates to Makia Client Connector and starts the full Windows tunnel. Windows UAC can appear because TUN/WireGuard operations require elevation.

Browser Only is available for the sing-box delivery family used by Makia: VLESS, VMess, Trojan, Hysteria2, Shadowsocks/Outline and SSH. WireGuard and OpenVPN use Device VPN mode.

## UAT installation

1. Extract the GitHub Actions artifact named Makia-Client-Connector-Windows-x64.
2. Run Install-Makia.cmd once.
3. In Chrome open chrome://extensions or in Edge open edge://extensions.
4. Enable Developer mode.
5. Choose Load unpacked and select the BrowserExtension folder from the extracted Windows package.
6. Sign in to your Makia Client Portal.
7. Select اتصال افزونه Chrome / Edge and create a one-time Pair Code.
8. Open the Makia VPN toolbar popup.
9. Enter the HTTPS panel origin and the Pair Code, then select Pair Extension.
10. Select Browser Only or Device VPN and connect an assigned profile.

The development manifest key fixes the unpacked UAT extension ID to:

kifidlpkeejegkcolpjfipmjllldakik

The Windows installer allowlists this ID for Native Messaging. When the extension is later published in Chrome Web Store or Microsoft Edge Add-ons, the final catalog extension IDs must also be passed to install.ps1 so the Native Messaging allowlist contains the exact published origins.

## Security

- Pair codes are one-time and short-lived.
- VPN delivery secrets never enter extension storage.
- The native Client session token is stored by Makia Browser Host encrypted with Windows DPAPI.
- The extension requests only nativeMessaging, proxy and privacy permissions. The privacy permission is used only to disable non-proxied WebRTC UDP while Browser Only is active, then released on disconnect.
- There are no content scripts, host permissions, cookies permission, remote JavaScript, wildcard Native Messaging origins or generic shell commands.
