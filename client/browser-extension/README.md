# Makia Browser VPN 1.5.0 — Pure Browser

This extension does not require MakiaBrowserHost.exe, Native Messaging, sing-box on Windows, UAC, registry changes, or any desktop installation.

## Flow

Chrome / Edge → HTTPS authenticated proxy → Makia Browser Gateway on the VPS → Internet.

## User install

For pre-publication UAT:
1. Extract the Browser Extension artifact.
2. Open chrome://extensions or edge://extensions.
3. Enable Developer mode.
4. Load the extension directory unpacked.
5. Enter the HTTPS Makia panel URL and Client account credentials.
6. Press Connect.

For production users, publish the exact Web Store ZIP from the Browser Extension Build workflow and distribute the Store link.

## Server prerequisites

- Makia 1.5.0+
- Client Platform enabled
- public HTTPS panel domain
- valid certificate
- TCP/8445 reachable from browsers
- Browser Gateway active

## Security

- no VPN protocol credential is exposed to extension JavaScript;
- proxy credentials are short-lived;
- proxy credentials live in chrome.storage.session;
- local/private target addresses are blocked server-side;
- browser traffic counts toward the Client account quota;
- account/session/device revocation invalidates Browser Gateway access.

Development extension ID:
jgpmmenelldgfmjfnonhjaaaccfeniji

Store IDs can be added server-side with MAKIA_BROWSER_EXTENSION_IDS.
