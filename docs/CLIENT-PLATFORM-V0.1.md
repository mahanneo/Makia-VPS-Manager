# Makia Client Platform v0.1 — Architecture & Safety Contract

Status: Release 1.3.0 candidate
Release branch: `feat/client-platform-v0.1`
Production default: **disabled**

## Goal

Add an end-user client plane beside the existing Makia admin/control plane without changing active protocol runtimes or existing connected users.

The first delivery is a mobile/desktop PWA foundation. Native tunnel execution remains a later agent/mobile phase.

## Safety boundary

The client platform is additive and disabled by default:

```env
MAKIA_CLIENT_PORTAL_ENABLED=auto
```

Until explicitly enabled:

- existing admin login/routes are unchanged;
- existing SSH/Xray/WireGuard/OpenVPN/Outline runtime state is unchanged;
- no active user or protocol credential is rotated;
- no firewall, systemd, Xray, WireGuard or OpenVPN configuration is mutated;
- the new database tables are additive only.

Admin control-plane operations in `app/client_admin.py` only manage client accounts, web devices, sessions, and bindings to existing protocol records. They do not call protocol runtime mutators.

## Separate authentication domains

Admin:
- cookie: `makia_session`
- current existing admin authentication/2FA policy.

End user:
- cookie: `makia_client_session`
- device cookie: `makia_client_device`
- independent `client_accounts` credentials;
- independent revocable server-side sessions.

A client account cannot authenticate to admin routes.

## New additive tables

- `client_accounts`
- `client_devices`
- `client_sessions`
- `client_protocol_bindings`
- `client_artifact_bindings`

Existing protocol data remains authoritative. Xray/Outline bindings can reference an existing `protocol_clients.id`; SSH/WireGuard/OpenVPN (and other exportable access types) can reference an existing encrypted `access_artifacts.id`. Creating a client account or binding never creates, rotates, restarts or changes a protocol runtime. A concrete credential/artifact may belong to only one Client account.

## Enforced controls

v0.1 enforces:

- account enabled/disabled state;
- account expiry;
- account aggregate quota based on bound protocol traffic;
- registered device limit;
- concurrently active device limit;
- revocation of sessions on password rotation;
- per-device revocation;
- protocol delivery only for explicitly bound protocol identities/artifacts;
- exclusive credential ownership across Client accounts;
- no protocol secret in ordinary protocol-list responses;
- same-origin mutation header for delivery/revoke actions;
- rate limiting on end-user login.

Web/PWA device binding uses an opaque random device secret stored in an HttpOnly cookie. This is intentionally classified as **soft device binding**. Hardware-backed asymmetric device identity is reserved for the native Makia Agent/mobile phase.

## PWA routes

- `/client/`
- `/client/login`
- `/client/app`
- `/client/manifest.webmanifest`
- `/client/sw.js`
- `/client/api/me`
- `/client/api/protocols`
- `/client/api/protocols/{id}/delivery`
- `/client/api/artifacts/{id}/delivery`
- `/client/api/devices`

Private API and app responses are no-store.

## Admin control-plane API

- `GET /api/client-platform/status`
- `GET/POST /api/client-platform/accounts`
- `GET/PUT /api/client-platform/accounts/{id}`
- `POST /api/client-platform/accounts/{id}/password`
- `GET /api/client-platform/protocols`
- `GET /api/client-platform/artifacts`
- `POST /api/client-platform/accounts/{id}/bindings`
- `POST /api/client-platform/accounts/{id}/artifact-bindings`
- `DELETE /api/client-platform/accounts/{id}/bindings/{protocol_client_id}`
- `POST /api/client-platform/accounts/{id}/devices/{device_id}/revoke`

All mutations use the existing Makia admin authentication + CSRF/same-origin guard and audit trail.

## Delivery phases

### Phase A — v0.1 (this branch)

- isolated client account/session/device model;
- PWA login and dashboard;
- subscription/usage/device display;
- explicit binding to existing protocol client identities;
- non-mutating delivery adapters for existing SSH, WireGuard and OpenVPN artifacts;
- controlled secret delivery only after authenticated POST;
- admin API foundation;
- disabled-by-default rollout.

### Phase B — host enforcement adapters

Implemented on this branch without rotating existing credentials:
- Xray/Outline account expiry/quota enforcement through existing Makia protocol accounting;
- WireGuard expiry/quota enforcement with persistent post-binding transfer deltas;
- SSH expiry plus concurrent-session/source-IP limits (byte quota is not claimed for SSH);
- OpenVPN expiry/quota enforcement when the Makia local CCD + Unix management policy runtime is configured.

Existing OpenVPN servers are never restarted from the recurring policy loop. Policy runtime activation is an explicit local-admin action and performs a controlled OpenVPN restart with rollback on failure. New OpenVPN bootstraps include the local policy controls automatically.

### Phase C — Windows Agent (next product phase)

Native local agent:
- device key pair;
- local authenticated bridge;
- WireGuard/OpenVPN/Xray engine control;
- connect/disconnect;
- DNS and route handling;
- kill switch;
- auto-start;
- remote profile refresh.

The PWA remains the shared UI/control experience.

### Phase D — Android/iOS

- Android VpnService shell;
- iOS NetworkExtension/NEPacketTunnelProvider shell;
- hardware-backed device keys where available;
- shared Control Plane and account/device policy.

## Promotion gates

This branch must not be merged to production until:

1. existing full CI is green;
2. client-platform unit tests are green;
3. browser smoke includes disabled-mode regression;
4. staging startup creates only additive tables;
5. with flag disabled, current admin/protocol UAT is byte/behavior equivalent;
6. with flag enabled on staging, login/device/concurrent/quota/expiry/binding tests pass;
7. no active protocol identity is rotated during enable/disable cycles.



## Production-ready web/PWA operating model

The web/PWA client is usable without the native agent:

1. Administrator creates a Client account from **اپ کاربران / Client Platform**.
2. Administrator sets expiry, quota, device count and concurrent device count.
3. Existing Xray/Outline protocol identities or SSH/WireGuard/OpenVPN encrypted access artifacts are bound to that Client account.
4. The Client Portal is enabled explicitly from the Admin UI.
5. The user opens `/client/`, logs in and may install the PWA on mobile/desktop.
6. The user receives only their bound profiles, with QR/file/deep-link delivery where supported.
7. Account expiry/quota enforcement runs server-side where the enforcement matrix reports **Hard policy**.

The PWA device registration is a soft browser-device control. It does not claim hardware identity. For WireGuard/OpenVPN/Xray native one-click tunnel control and hardware-backed device binding, use the later native-agent/mobile phase.
