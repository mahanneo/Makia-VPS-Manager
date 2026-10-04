# MahiNet Commerce API

This draft API gives MahiNet a narrow, audited mutation surface without reusing the browser admin session or exposing a generic privileged command endpoint.

## Token scopes

- `commerce:provision`
- `commerce:service`

Create a dedicated API token with only the scopes MahiNet needs.

## Network allowlist

Set `MAKIA_COMMERCE_ALLOWED_CIDRS` in `/etc/makia-vps-manager/makia.env`.

The safe default is loopback-only:

```text
MAKIA_COMMERCE_ALLOWED_CIDRS=127.0.0.1/32,::1/128
```

Keep that default when MahiNet and Makia run on the same VPS. If MahiNet is moved to another trusted host, replace it with only the exact source CIDR proven by host UAT. Do not allow whole private-address ranges by default.

## Provision

`POST /api/v1/commerce/provision`

Required headers:

```text
Authorization: Bearer <token>
Idempotency-Key: <unique-key>
Content-Type: application/json
```

Supported profiles:

- `xray:<existing-inbound-tag>`
- `outline`
- `wireguard`
- `openvpn`

Xray provisioning intentionally adds a client to an existing configured inbound instead of creating arbitrary new listeners.

## Service action

`POST /api/v1/commerce/service-action`

Supported managed lifecycle operations are limited to what Makia can actually enforce. Xray/Outline support the commerce lifecycle implemented in the route. WireGuard/OpenVPN do not claim per-client quota/expiry enforcement when the underlying engine does not provide it.

## Safety properties

- scoped bearer token
- explicit CIDR allowlist
- mandatory, token-scoped idempotency key for mutations
- atomic pending/complete/failed idempotency state
- encrypted idempotent response storage (credentials/configs are not stored as plaintext replay JSON)
- Makia audit events
- existing protocol validation and artifact storage
- no root shell or generic command execution API
- cleanup on partial create failure

Keep this API disabled from MahiNet until real-host UAT has passed. For same-host production, prefer a direct loopback backend call where practical; if a local reverse proxy is used, forwarded client addresses are trusted only from a loopback peer.
