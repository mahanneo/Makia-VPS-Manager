# Makia 1.4.0 — MahiNet Commerce Host UAT

Status: **mandatory before PR #79 can leave Draft**

This checklist validates the MahiNet commerce integration on the real Makia host without exposing a browser admin session or a generic privileged command endpoint.

## Safety boundary

Before starting:

- keep PR #79 unmerged;
- keep the Client Portal rollout disabled for general users;
- do not rotate existing Xray UUIDs, WireGuard keys, OpenVPN certificates, SSH credentials or Outline keys;
- do not change active listener ports merely for this UAT;
- use disposable MahiNet orders/accounts only;
- never place the Makia API bearer token in browser JavaScript, HTML, logs or screenshots.

## 1. Capture production evidence

Record:

- currently installed Makia version;
- active Xray / WireGuard / OpenVPN / SSH / Outline listeners;
- one known-good existing connection for every protocol currently in use;
- current `makia-doctor` result;
- current `makia-uat-smoke` result.

Create a **Full Migration Backup**, copy it off-host and record its SHA256 before updating.

## 2. Deploy the frozen UAT2 commit

Deploy only the exact SHA recorded on PR #79 / `release/v1.4.0-uat2`.

For pre-merge UAT, do not run an unpinned `makia-upgrade` that resolves to `main`.

After update, verify:

```bash
sudo makia-doctor
sudo makia-uat-smoke
curl -fsS http://127.0.0.1:8787/healthz
```

Confirm the running Makia version is 1.4.0 and existing protocol credentials/listeners are unchanged.

## 3. Commerce API network boundary

When MahiNet and Makia share the same VPS, keep the safe default:

```text
MAKIA_COMMERCE_ALLOWED_CIDRS=127.0.0.1/32,::1/128
```

Prefer server-to-server loopback access from the MahiNet backend. Do not expose the bearer token to the public storefront.

If a reverse proxy is used, confirm the actual source address observed by Makia. Forwarded client IP headers are trusted only when the immediate peer is loopback.

If MahiNet is later moved to another host, replace the allowlist with only the exact trusted source CIDR proven by UAT.

## 4. Dedicated API token

Create a dedicated token for MahiNet with only:

- `commerce:provision`
- `commerce:service`

Do not reuse an administrator browser session and do not grant unrelated read/write scopes.

## 5. Provisioning smoke

Use unique disposable `external_id` values and a unique `Idempotency-Key` for each new mutation.

### Xray

Provision against an **existing validated inbound tag**.

Verify:

- one client is created;
- the returned connection data works;
- quota / expiry / device-limit values match the request;
- Makia records an audit event;
- no duplicate client is created when the exact request is replayed with the same idempotency key.

### Outline

Verify:

- one real Outline key is created;
- the returned `ss://` credential works;
- quota is applied where requested;
- Makia stores the delivery artifact;
- replay returns the same logical response without creating a second key.

## 6. Idempotency security

For both provisioning and service actions:

1. replay the exact same payload + key → expect the stored successful response;
2. reuse the same key with a changed payload → expect HTTP 409;
3. send two concurrent first attempts with the same key → only one claim may execute;
4. inspect the Makia SQLite database and confirm replay credentials/configs are not stored as plaintext JSON;
5. confirm failed requests cannot later replay as successful.

## 7. Lifecycle actions

For managed Xray / Outline clients, verify only supported actions:

- renew;
- suspend;
- resume;
- upgrade;
- Outline credential reissue where supported.

Confirm state changes are visible in Makia and reflected in the returned commerce response.

## 8. WireGuard / OpenVPN enforcement boundary

Provisioning may be tested, but Makia 1.4.0 must not claim native per-client quota/expiry lifecycle enforcement where the underlying engine does not provide it.

A lifecycle request that would imply unsupported enforcement must fail explicitly rather than silently pretending success.

## 9. Existing-user regression

After disposable commerce tests, reconnect the pre-existing real test users captured before update.

Verify that the UAT did not rotate or invalidate:

- Xray credentials;
- WireGuard keys;
- OpenVPN certificates;
- SSH credentials;
- Outline keys.

## 10. Restore proof

Create a new Full Migration Backup after UAT and restore it on a disposable replacement VPS.

Verify:

- panel health;
- protocol state;
- Client Platform data;
- commerce/idempotency database state;
- at least one disposable Xray or Outline commerce-managed access.

## 11. Promotion gate

PR #79 may leave Draft only when all of the following are recorded:

- exact final Git commit;
- GitHub CI / browser / Xray smoke PASS;
- Ubuntu 22.04 + 24.04 Clean Install PASS;
- Windows connector artifact from the exact final SHA;
- Android connector artifact from the exact final SHA;
- real-host update PASS;
- existing-user regression PASS;
- MahiNet Xray + Outline provisioning PASS;
- idempotency security PASS;
- restore proof PASS;
- limited canary PASS.
