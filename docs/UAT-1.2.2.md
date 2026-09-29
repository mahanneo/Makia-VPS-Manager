# Makia VPS Manager v1.2.2 — MTProxy Transaction / Refresh Persistence UAT

Date: 2026-09-29
Target: `1.2.2`

## Scope

This patch fixes a transactional edge case where a UFW rule failure after a successful MTProxy start could roll back the entire proxy configuration. That could make a successfully entered hostname/secret/port disappear when the Telegram Proxy page was refreshed.

## Behavior

- MTProxy identity/configuration is rolled back only when the service itself cannot reach an active listener.
- UFW rule application remains fail-closed but is non-destructive: a firewall error does not delete `mtproxy.env` or `mtproxy.toml`.
- The API reports `firewall_warning`, `firewall_active`, and `firewall_allowed`.
- The UI clearly warns when the proxy is configured/running but UFW does not expose its port.
- v1.2.1 update-state SHA256 preservation and rollback service recovery remain in force.

## Host acceptance

- [ ] Configure a FakeTLS hostname and preferred port.
- [ ] Confirm Configured=YES, Service=ACTIVE, Listener=TCP/<port>.
- [ ] Click the Telegram Proxy page Refresh button several times; hostname, port, secret-derived links and QR must remain unchanged.
- [ ] Run `sudo makia-upgrade`; the same proxy identity must remain.
- [ ] With UFW active, verify the current proxy port is allowed.
- [ ] In staging, force the UFW helper to fail and verify configuration remains present while the UI reports a firewall warning.
- [ ] Verify the existing t.me link still connects after a normal update.

## Promotion rule

CI validates the transaction and browser contracts; external Telegram connectivity still requires real VPS/client UAT.
