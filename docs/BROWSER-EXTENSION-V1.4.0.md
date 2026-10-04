# Makia VPN Browser Extension v1.4.0 — Release Handoff

## Architecture

Chrome/Edge toolbar popup communicates with MakiaBrowserHost.exe through Chromium Native Messaging.

Browser Only:
Chrome/Edge -> chrome.proxy -> SOCKS5 127.0.0.1:<dynamic-port> -> sing-box -> Makia access

Device VPN:
Chrome/Edge -> Native Messaging -> elevated MakiaClientConnector.exe -> TUN/WireGuard/OpenVPN

The local proxy binds only to 127.0.0.1. The extension never receives the VPN delivery payload.

## Pairing model

1. The user signs in to the existing Makia Client Portal.
2. The portal creates a one-time Pair Code valid for five minutes.
3. Makia Browser Host redeems that code once over HTTPS.
4. The backend issues a normal device-bound Makia Client session, with a maximum 30-day lifetime.
5. The Native Host encrypts the token with Windows DPAPI in the current Windows user profile.
6. Password rotation, device revocation, account disable, expiry and quota rules continue to use the existing Client session/account controls.

Pair codes are stored only as SHA-256 hashes and cannot be replayed.

## Browser Only support

Supported through sing-box:
- VLESS
- VMess
- Trojan
- Hysteria2
- Shadowsocks / Outline
- SSH

WireGuard and OpenVPN are intentionally Device VPN only in 1.4.0.

## Permissions and attack surface

Manifest V3 permissions:
- nativeMessaging
- proxy
- privacy (only to prevent non-proxied WebRTC UDP while Browser Only is active)

Not requested:
- cookies
- tabs
- webRequest
- host permissions
- content scripts
- all_urls

The Native Host has a fixed action allowlist and does not expose arbitrary shell execution or an arbitrary URL fetch primitive.

## Windows package

The Windows Actions artifact contains:
- MakiaClientConnector.exe
- MakiaBrowserHost.exe
- pinned sing-box.exe
- BrowserExtension directory
- install/uninstall scripts
- checksums and build provenance

The installer registers the Native Messaging host for Chrome and Edge under the current Windows user.

## Publication gate

The unpacked extension ID used for UAT is:
kifidlpkeejegkcolpjfipmjllldakik

Before public Store rollout:
1. Complete real Chrome and Edge UAT on a disposable Makia account.
2. Publish to Chrome Web Store and Microsoft Edge Add-ons.
3. Record the final Store extension IDs.
4. Add those exact IDs to the Native Messaging allowed_origins using the installer parameters.
5. Repeat Store-install UAT.
6. Publish accurate privacy and permission disclosures.
