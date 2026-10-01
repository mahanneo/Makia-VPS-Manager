# MahiNet scoped write API contract

This contract is for MahiNet storefront automation only. It deliberately does **not** expose shell execution, package installation, Nginx mutation, arbitrary Xray inbound creation, or arbitrary port selection.

## Token model

Create a dedicated Makia API token with only the scopes needed by MahiNet:

- `status:read`
- `protocols:read`
- `provision:xray`
- `provision:wireguard`
- `provision:openvpn`
- `provision:outline`
- `provision:lifecycle`

Any token containing a `provision:*` scope must have at least one IP/CIDR allowlist entry. The token is stored hashed. The CIDR policy is stored separately.

The external API trusts `X-Forwarded-For` only when the direct peer is within `MAKIA_TRUSTED_PROXY_CIDRS` (loopback by default). This is intended for the local Nginx reverse proxy.

## Idempotency

Every mutating endpoint requires:

`X-Idempotency-Key: <stable-order/service-operation-key>`

A key cannot be reused for a different route or payload. Completed responses are encrypted at rest before they are cached for safe replay.

## Provisioning endpoints

- `POST /api/v1/provision/xray` — adds a client to an **existing** Xray inbound only.
- `POST /api/v1/provision/wireguard` — creates a managed WireGuard peer.
- `POST /api/v1/provision/openvpn` — creates a managed OpenVPN client; quota/expiry managed services require the OpenVPN hard-policy runtime.
- `POST /api/v1/provision/outline` — creates a managed Outline access key.
- `POST /api/v1/provision/lifecycle` — updates suspend/resume, expiry, quota, and supported reissue operations.
- `GET /api/v1/provision/service/{client_account_id}` — returns the Makia policy-account snapshot without exposing raw API token material.

Each provisioned MahiNet service receives an internal Makia Client Platform policy account. Xray/Outline clients are protocol-bound; WireGuard/OpenVPN credentials are artifact-bound. This gives the existing Makia policy engine a real owner for expiry/quota enforcement rather than keeping those fields as storefront-only metadata.

## Host UAT requirements

Before enabling MahiNet auto-provisioning:

1. Confirm the real source IP/CIDR that Nginx forwards for traffic originating from the MahiNet container and use only that CIDR on the write token.
2. Confirm `MAKIA_TRUSTED_PROXY_CIDRS` contains only the local reverse proxy.
3. Create the dedicated write token from Makia Settings.
4. Verify a duplicate request with the same idempotency key returns the same credential instead of creating a second client.
5. Provision one disposable service for each enabled protocol and verify suspend, resume/renew, quota and expiry.
6. For OpenVPN, verify `openvpn_policy_status().ready == true` before selling quota/expiry-managed plans.
