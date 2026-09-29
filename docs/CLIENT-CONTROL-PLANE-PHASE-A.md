# Makia Client Control Plane — Phase A

Status: development branch only  
Branch: `feat/v1.3-client-control-plane-phase-a`  
Production default: **disabled**

## Objective

Introduce the client-facing control-plane foundation without changing any existing VPN/proxy runtime, credential, peer, inbound, service, firewall rule, backup contract, or currently connected user.

Phase A is intentionally additive. It establishes identity, session, device and access-assignment primitives plus a mobile-first PWA shell. It does **not** start or stop tunnels.

## Safety boundary

The feature is disabled unless the host explicitly sets:

```bash
MAKIA_CLIENT_APP_ENABLED=1
```

The default in `.env.example` is `0`.

No Phase A code imports or invokes:
- `protocol_ops`
- `network_services`
- subprocess/systemctl
- WireGuard/OpenVPN/Xray/SSH runtime mutation

Existing `protocol_clients`, `access_artifacts` and `account_profiles` remain authoritative and are not rewritten by the client portal.

## Data model

Four additive SQLite tables are created with `CREATE TABLE IF NOT EXISTS`:

- `client_accounts`: end-user login identity, separate from Makia admin accounts.
- `client_devices`: browser/device registrations. Phase A uses a secure random HttpOnly device identifier.
- `client_sessions`: opaque server-revocable session tokens; only SHA256 hashes are stored.
- `client_access_bindings`: references an existing `access_artifacts(kind, external_key)` record without copying protocol credentials.

Existing account policy is reused through `account_profiles`:
- `device_limit` → maximum registered devices.
- `connection_limit` → maximum concurrent client sessions.
- `quota_mb` → displayed plan quota; protocol enforcement remains with existing runtime/policy systems.
- `expire_date` and `enabled` → client login eligibility.

## Routes

Client-facing, feature-gated:
- `GET /client-app/login`
- `POST /client-app/login`
- `POST /client-app/logout`
- `GET /client-app/`
- `GET /client-app/api/me`
- `GET /client-app/manifest.webmanifest`
- `GET /client-app/sw.js`

Admin-session protected provisioning API:
- `GET /api/client-app/admin/accounts`
- `POST /api/client-app/admin/accounts`
- `POST /api/client-app/admin/accounts/{id}/password`
- `POST /api/client-app/admin/accounts/{id}/bindings`
- `DELETE /api/client-app/admin/accounts/{id}/bindings/{binding_id}`
- `POST /api/client-app/admin/accounts/{id}/devices/{device_id}/revoke`

The admin provisioning API does not expose decrypted protocol payloads.

## Authentication and device policy

Client credentials are independent from admin credentials and use the existing scrypt password primitive.

Login flow:
1. Apply a client-specific rate-limit key.
2. Validate client account password.
3. Reuse linked `account_profiles` policy.
4. Reject disabled/expired accounts.
5. Register or recognize the browser device.
6. Enforce device limit transactionally with `BEGIN IMMEDIATE`.
7. Revoke previous sessions on the same device.
8. Enforce concurrent session limit.
9. Issue an opaque random session token and store only its SHA256 hash.

A device can be revoked by the administrator, which also revokes its active sessions.

### Phase A device-binding limitation

Browser device IDs are suitable for account/device-count policy, but they are not hardware attestation. Clearing browser storage/cookies makes the browser appear as a new device.

Phase B will replace this soft binding with a client-generated asymmetric device key pair and Makia Agent/native attestation. The schema already reserves `public_key` for this migration.

## PWA

The client UI is isolated from the admin panel:
- `client_app_login.html`
- `client_app.html`
- `client-app.css`
- `client-app.js`
- `client-app-sw.js`
- `client-app-icon.svg`

The service worker is scoped to `/client-app/` and does not intercept admin or protocol API traffic.

## Current UX

The client can see:
- subscription active/inactive state
- plan
- expiry
- device limit
- concurrent-session limit
- quota metadata
- registered devices
- assigned protocol access cards

The Connect buttons are deliberately disabled in Phase A.

## Phase B

Phase B introduces **Makia Agent for Windows first**, while preserving this web UI as the shared presentation layer.

Target flow:

```text
Makia Client PWA
      |
      | authenticated command
      v
Makia Agent (localhost/native)
      |
      +-- WireGuard
      +-- OpenVPN
      +-- Xray
      +-- SSH tunnel
```

Phase B must use short-lived, device-bound command grants. Protocol private keys/secrets must not be persisted in the browser.

## Staging activation only

Do not enable this feature on the production host until Phase A CI and staging UAT pass.

For staging:

```bash
echo 'MAKIA_CLIENT_APP_ENABLED=1' >> /etc/makia-vps-manager/makia.env
systemctl restart makia-vps-manager
```

Then validate `/client-app/login` on a non-production account.

## Promotion gate

Before merging to a release branch:
- all existing CI must remain green
- client control-plane tests must pass
- existing browser smoke must remain unchanged/green
- no protocol runtime diff is allowed
- no existing user credential may rotate
- no existing service may restart solely because Phase A tables/assets exist
- production feature flag stays OFF by default
