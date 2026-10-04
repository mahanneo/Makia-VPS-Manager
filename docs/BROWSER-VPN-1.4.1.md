# Makia Browser VPN 1.4.1

Makia 1.4.1 adds a Chrome/Edge browser-only VPN mode without changing existing server credentials or protocol runtimes.

## Architecture

Chrome/Edge Extension → Native Messaging → MakiaBrowserHost.exe → local 127.0.0.1 SOCKS5 → sing-box → assigned Makia access.

Full Device Direct Connect remains separate and continues to use MakiaClientConnector.exe and the existing makia:// flow.

## Supported Browser VPN profiles

Supported through the existing share-link parser:
- VLESS
- VMess
- Trojan
- Hysteria2
- Shadowsocks / Outline
- SSH / NPV

WireGuard and OpenVPN remain Full Device / Import only.

## Security contract

- Extension ID is pinned by manifest public key: jgpmmenelldgfmjfnonhjaaaccfeniji
- Native host allowlist permits only that extension origin.
- The extension requests access only to the operator-supplied HTTPS Makia origin.
- Client passwords are sent only to the Makia HTTPS origin.
- VPN profile secrets are never returned to extension JavaScript.
- Every connect uses a short-lived, one-time, device-bound connector ticket.
- Browser proxy is loopback-only.
- Browser and Full Device process/state files are separate.
- Browser startup clears stale proxy state.

## User install

1. Install the Windows connector package with Install-Makia.cmd.
2. Chrome: chrome://extensions → Developer mode → Load unpacked → select browser-extension.
3. Edge: edge://extensions → Developer mode → Load unpacked → select browser-extension.
4. Pin Makia Browser VPN.
5. Enter the HTTPS Makia panel URL and Client account credentials.
6. Approve permission for that exact panel origin.
7. Select an available profile and press Connect.

## Operator note

The Client Portal must remain gated until the 1.4.1 UAT is complete.
