# Chrome Web Store publishing — Makia Browser VPN 1.5.0

The GitHub workflow **Browser Extension Build** produces `Makia-Browser-VPN-1.5.0.zip`, ready for Chrome Web Store upload.

Recommended visibility: **Unlisted** until production UAT is complete.

## Store permissions rationale

- `proxy`: routes Chrome HTTP/HTTPS traffic through the selected Makia Browser Gateway.
- `storage`: stores panel URL, Client session state and local connection state.
- `webRequest` + `webRequestAuthProvider`: supplies short-lived authentication only when Chrome receives a proxy authentication challenge.
- `<all_urls>`: required because Browser VPN applies to browser web requests. Makia does not inspect or store visited URLs in the extension.

The extension no longer requests `nativeMessaging`.

## Privacy notes for listing

Makia Browser VPN authenticates against the operator's Makia server. The extension does not sell data, does not embed analytics, and does not store VPN protocol credentials. Browser traffic traverses the operator-controlled Makia Browser Gateway as expected for a browser VPN/proxy service.

Publishing to Chrome Web Store requires the repository owner/operator's Chrome Web Store developer account. GitHub CI can prepare and verify the package, but store submission must be authorized by that publisher account.


## Store-assigned extension ID

The unpacked/UAT package keeps the pinned development ID. If Chrome Web Store or Edge Add-ons assigns another 32-character extension ID, add it on the Makia server without changing application code:

```bash
sudo sh -c 'printf "\nMAKIA_BROWSER_EXTENSION_IDS=<store-extension-id>\n" >> /etc/makia-vps-manager/makia.env'
sudo systemctl restart makia-vps-manager
```

Multiple IDs may be comma-separated. The built-in UAT ID remains accepted so staged rollout can continue.
