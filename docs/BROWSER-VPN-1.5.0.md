# Makia Browser VPN 1.5.0

Makia 1.5 introduces a pure browser VPN path for Chrome and Edge. The end user does not install a Windows executable, Native Messaging host, registry entry, local sing-box runtime, or administrator helper.

## Architecture

```
Chrome / Edge Extension
  -> HTTPS forward proxy + short-lived proxy authentication
  -> Makia Browser Gateway on the VPS
  -> Public Internet
```

The Browser Gateway is additive. Existing Xray, WireGuard, OpenVPN, SSH, Outline, MTProxy and DNS users/configuration are not converted, rotated or removed.

## Server endpoint

Default browser gateway listener:

```
TCP/8445
```

The gateway hostname defaults to the configured Makia panel domain. TLS defaults to the same Let's Encrypt certificate lineage.

Requirements:
- the Makia panel has a valid public HTTPS domain;
- the certificate exists under the expected Let's Encrypt lineage;
- TCP/8445 is reachable from client browsers;
- the Client Platform is enabled for accounts that use the extension.

If HTTPS prerequisites are not ready, Makia installation/update succeeds and the Browser Gateway remains deferred instead of breaking the core VPN runtime.

## Security model

- proxy credentials are random and short-lived;
- only their hash is stored server-side;
- extension proxy credentials use `chrome.storage.session`, not persistent local storage;
- Client logout, session revoke, device revoke, account disable and password reset revoke browser proxy access;
- account quota includes Browser Gateway traffic;
- only HTTP/80 and CONNECT/443 are accepted;
- loopback, private, link-local and non-global proxy targets are rejected to prevent using the gateway as a pivot into the VPS/LAN;
- proxy credentials are sent to the gateway only inside TLS;
- protocol credentials such as VLESS UUIDs, WireGuard keys, SSH passwords and Outline access keys are never returned to pure-browser extension JavaScript.

## Browser extension

The extension uses Manifest V3:
- `chrome.proxy` for browser-only proxy settings;
- `webRequestAuthProvider` for authenticated proxy challenges;
- no `nativeMessaging` permission;
- no Windows service or local executable dependency.

The development extension ID is:

`jgpmmenelldgfmjfnonhjaaaccfeniji`

Production Store IDs are allowlisted through:

`MAKIA_BROWSER_EXTENSION_IDS=id1,id2`

## Operations

After setting/changing the panel domain or issuing its certificate, Makia automatically runs:

`makia-browser-gateway-sync`

Manual verification:

```
sudo systemctl status makia-browser-gateway --no-pager
sudo makia-browser-gateway-sync
sudo makia-doctor
sudo makia-uat-smoke
```

If a cloud/provider firewall is used, allow TCP/8445 to the VPS. Makia only opens this port automatically when UFW is already active on the host.
