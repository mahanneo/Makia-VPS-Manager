# Makia 1.5.0 — Pure Browser Gateway

Makia 1.5.0 removes the Windows Native Messaging dependency from the normal Chrome/Edge Browser VPN path.

## Architecture

Chrome / Edge Extension → authenticated HTTPS proxy on Makia VPS → public Internet.

The extension uses the Chrome proxy API with an HTTPS proxy and Manifest V3 proxy-auth handling. No EXE, UAC, Registry change, Native Messaging host, local SOCKS listener, or sing-box installation is required for browser-only users.

## Security model

- Browser Gateway listens on TCP/9443 by default.
- TLS uses the existing Let's Encrypt certificate for the configured Makia panel domain.
- Extension login uses the existing Client Platform account/device/session controls.
- Connect returns a random short-lived proxy credential bound to the active Client session and device.
- Proxy credentials are stored only in Chrome session storage.
- Browser credentials are revoked when the Client session or device is revoked.
- Gateway rejects loopback, private, link-local, multicast, reserved and other non-global destination addresses.
- Default destination ports are only 80 and 443.
- Browser traffic is included in the Client account quota.
- URLs and destination hostnames are not written to the Makia database or audit log.

## Server requirements

1. Configure a public panel domain such as p.example.com.
2. Issue a valid Let's Encrypt certificate from the Makia panel.
3. TCP/9443 must be reachable from users. If UFW is active, Makia adds an allow rule during install/update. Cloud/provider firewalls must also allow TCP/9443.
4. Client Portal must be enabled.
5. Create Client Platform accounts as usual.

Optional environment overrides:

- MAKIA_BROWSER_GATEWAY_PORT=9443
- MAKIA_BROWSER_GATEWAY_HOST=p.example.com
- MAKIA_BROWSER_GATEWAY_ALLOWED_PORTS=80,443
- MAKIA_BROWSER_GATEWAY_MAX_CONNECTIONS=32

## User flow

1. Install Makia Browser VPN from Chrome Web Store / Edge Add-ons, or load the store-ready ZIP for UAT.
2. Enter the Makia HTTPS panel URL.
3. Login with the Client Platform username/password.
4. Press Connect.
5. Only Chrome/Edge web traffic uses the Makia VPS. Other Windows applications remain direct.

Full-device VPN remains a separate optional client path.
