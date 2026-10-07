# Makia Browser VPN 1.6.3 — Chrome Web Store Handoff

Upload the ZIP produced by the green **Browser Extension Build** workflow. The ZIP root contains `manifest.json`.

## Recommended distribution

Start as **Unlisted** for controlled customer rollout. Store visibility is not an access-control boundary: Browser Gateway access still requires a valid Makia Client account and short-lived authenticated gateway credential.

## Listing

Name: **Makia Browser VPN**

Purpose: browser-only VPN access through an authenticated Makia Browser Gateway. No Windows application is required.

## Permissions

- `proxy`: routes browser traffic to the selected Makia Gateway.
- `storage`: stores non-secret local state and account/session metadata.
- `webRequest` + `webRequestAuthProvider`: supplies short-lived proxy authentication only to the exact Makia Gateway challenge.
- `privacy`: blocks non-proxied WebRTC UDP and disables network prediction while connected; settings are cleared on disconnect.
- `<all_urls>`: Browser VPN must apply to web destinations opened in the browser.
- optional `https://*/*`: requested for the operator-selected Makia panel origin.

## Privacy disclosure

Publish a real Privacy Policy describing authentication, IP/session/security logging, quota accounting, gateway processing, retention, and that user data is not sold to advertisers.

## Store ID

The repository manifest key pins the development extension ID. If Chrome Web Store assigns or confirms another production ID, add that ID to `MAKIA_BROWSER_EXTENSION_IDS` on the VPS and restart the Makia service.

## Review checklist

- no Native Messaging permission;
- no Windows EXE dependency;
- no remotely hosted executable code;
- no VPN credential in extension local storage;
- clear browser-only scope;
- screenshots contain no real credentials;
- Privacy Policy URL is reachable;
- production Browser Gateway TLS certificate is valid.
