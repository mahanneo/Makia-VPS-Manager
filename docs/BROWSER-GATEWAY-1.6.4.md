# Makia 1.6.4 — Pure Browser Gateway

Makia Browser VPN is a browser-only path that does not require a Windows executable, Registry registration, Native Messaging host, local SOCKS listener, or local sing-box.

## Architecture

Chrome / Edge Extension → authenticated TLS Browser Gateway on the Makia VPS → public Internet.

The extension uses Manifest V3, Chrome proxy APIs, short-lived Gateway credentials, WebRTC non-proxied UDP blocking, and network-prediction suppression while connected.

## Security contract

- Default gateway listener: TCP/9444.
- TLS certificate must match the configured Makia panel/gateway hostname.
- Login uses the Client Platform account/device/session controls.
- Gateway credentials are random, short-lived, session-bound, and stored only as hashes server-side.
- Extension proxy credentials live in session storage, not local storage.
- Proxy authentication is supplied only to the exact configured Makia gateway challenger.
- Revoking the Client session or device invalidates browser credentials.
- Loopback, private, link-local, multicast, reserved and other non-global destinations are rejected.
- Destination ports default to 80/443.
- Browser traffic contributes to Client account usage/quota.
- URLs and destination hostnames are not persisted in Makia audit/database records.

## Server requirements

1. Valid public HTTPS panel domain.
2. Valid TLS certificate for the Browser Gateway hostname.
3. TCP/9444 reachable from users.
4. Client Portal enabled.
5. Valid Client Platform account.

Optional overrides:

- `MAKIA_BROWSER_GATEWAY_PORT=9444`
- `MAKIA_BROWSER_GATEWAY_HOST=p.example.com`
- `MAKIA_BROWSER_GATEWAY_ALLOWED_PORTS=80,443`
- `MAKIA_BROWSER_GATEWAY_MAX_CONNECTIONS=32`
- `MAKIA_BROWSER_EXTENSION_IDS=<comma-separated-extension-ids>`

## User flow

1. Install Makia Browser VPN from Chrome Web Store / Edge Add-ons, or load the signed/store-ready ZIP for controlled UAT.
2. Enter the HTTPS Makia panel URL.
3. Login with Client Platform credentials.
4. Press Connect.
5. Only browser traffic uses the Makia VPS; other applications remain on the normal system route.

Full-device Windows/Android clients are separate optional products.
