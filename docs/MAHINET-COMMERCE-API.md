# MahiNet Commerce API

This draft API gives MahiNet a narrow, audited mutation surface without reusing the browser admin session or exposing a generic privileged command endpoint.

## Token scopes

- `commerce:provision`
- `commerce:service`

Create a dedicated API token with only the scopes MahiNet needs.

## Network allowlist

Set `MAKIA_COMMERCE_ALLOWED_CIDRS` in `/etc/makia-vps-manager/makia.env`.

Example for a same-host deployment after confirming the real reverse-proxy source address:

```text
MAKIA_COMMERCE_ALLOWED_CIDRS=127.0.0.1/32,172.16.0.0/12,212.100.171.183/32
```

Use the narrowest CIDR(s) proven by host UAT.

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
- mandatory idempotency key for mutations
- Makia audit events
- existing protocol validation and artifact storage
- no root shell or generic command execution API
- cleanup on partial create failure

Keep this API disabled from MahiNet until real-host UAT has passed.
