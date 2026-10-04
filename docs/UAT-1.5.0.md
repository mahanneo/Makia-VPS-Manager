# Makia 1.5.0 Production UAT

## Release invariants

- Existing Xray UUIDs, WireGuard keys, OpenVPN certificates, SSH credentials and Outline access keys must not rotate.
- Existing users must remain connected after update.
- Browser Gateway is additive and must not claim TCP/9443 (Stealth) or TCP/8444 (WStunnel).
- Browser Gateway default is TCP/9444.
- Browser-only users require no Windows executable, UAC, Registry entry or Native Messaging host.

## Server update

```bash
sudo makia-backup
sudo makia-upgrade
cat /opt/makia-vps-manager/VERSION
sudo makia-doctor
sudo makia-uat-smoke
```

Expected version: `1.5.0`.

For a configured panel domain and certificate:

```bash
systemctl is-active makia-browser-gateway
ss -ltnp | grep ':9444'
```

If UFW is already active, the updater adds TCP/9444. If a provider/cloud firewall is used, allow inbound TCP/9444 there as well.

## Browser UAT

1. Install/load `Makia-Browser-VPN-1.5.0.zip`.
2. Confirm extension version 1.5.0 and the pinned extension ID.
3. Confirm there is no Native Messaging permission.
4. Login to the HTTPS Makia panel with a disposable Client Platform account.
5. Press Connect.
6. Verify Chrome/Edge public IP becomes the VPS egress IP.
7. Verify a non-browser Windows application remains on the normal system route.
8. Browse HTTP and HTTPS sites; test WebSocket/WSS where practical.
9. Confirm Client account used bytes increase.
10. Disconnect and confirm the browser returns to its normal route.
11. Reconnect, revoke the device/session from Makia, then verify new proxy requests are rejected.
12. Confirm expired/quota-exhausted/disabled Client accounts cannot obtain a new Browser Gateway credential.

## Security UAT

- Attempt 127.0.0.1, RFC1918, link-local and metadata destinations through the proxy; they must be rejected.
- Attempt destination ports other than 80/443; they must be rejected by default.
- Confirm proxy auth credentials are not stored in `chrome.storage.local`; they live only in session storage.
- Confirm no URLs/destination hostnames are stored in Makia audit logs.
- Confirm TLS certificate presented on TCP/9444 matches the configured Makia panel domain.

## Promotion

Promote only after repository gates, real-host update, browser routing, accounting, revocation and existing-user regression all pass.
