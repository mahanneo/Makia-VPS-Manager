# Chrome / Edge Store Package — Makia Browser VPN 1.5.0

The GitHub workflow **Browser Extension Build** creates:

`Makia-Browser-VPN-Chrome-Edge-1.5.0.zip`

The ZIP has `manifest.json` at its root and contains only extension runtime files.

## Recommended first publication

Use an Unlisted/direct-link Chrome Web Store listing during rollout. The same source can be submitted to Microsoft Edge Add-ons.

The Store upload itself requires the owner's Chrome Web Store / Edge developer account and cannot be completed by the VPS updater.

## Before uploading

- verify artifact SHA256;
- verify version is 1.5.0;
- verify `nativeMessaging` is absent;
- verify permissions are limited to the documented pure-browser functions;
- complete privacy/store disclosures for proxy traffic and authentication;
- provide store artwork/screenshots separately.

If the Store assigns an ID different from the development ID, add it to:

`MAKIA_BROWSER_EXTENSION_IDS`

in `/etc/makia-vps-manager/makia.env`, then restart the backend:

```
sudo systemctl restart makia-vps-manager
```

No Windows executable is required by the 1.5 browser extension.
