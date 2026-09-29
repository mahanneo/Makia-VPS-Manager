# Makia Client Platform v0.1 — Architecture & Safety Contract

Status: development branch only
Branch: `feat/client-platform-v0.1`
Production default: **disabled**

## Goal

Add an end-user client plane beside the existing Makia admin/control plane without changing active protocol runtimes or existing connected users.

The first delivery is a mobile/desktop PWA foundation. Native tunnel execution remains a later agent/mobile phase.

## Safety boundary

The client platform is additive and disabled by default:

```env
MAKIA_CLIENT_PORTAL_ENABLED=0
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

### Phase B — native enforcement adapters

Add per-protocol enforcement/telemetry adapters for SSH, WireGuard and OpenVPN without changing existing credential identities. PWA v0.1 can securely deliver their existing profiles, but strong device-lock and connection enforcement for those tunnel credentials arrives with native/host enforcement adapters.

### Phase C — Windows Agent

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

