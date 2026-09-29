# Makia VPS Manager v1.0.0 — Release/UAT Report

Date: 2026-09-29  
Branch: `feat/rc7-ops-suite-outline`  
Target: `1.0.0`

## Release scope

v1.0.0 consolidates the RC line into the first public installation baseline.

### Protocols
- SSH / NPV
- Xray / V2Ray
- WireGuard
- OpenVPN
- Outline

### Operations
- unified client management
- Plans / Templates
- Expiry Center
- Bulk actions where enforceable
- Notifications
- encrypted local backup
- scheduled backup
- remote SCP backup
- Full Migration / Disaster Recovery
- Cloudflare DNS cutover
- Telegram integration
- per-access diagnostics
- Multi-VPS telemetry
- tokenized Client Portal
- QR / native config / protected ZIP delivery

## v1 fixes included

- Fixed Outline create ReferenceError caused by DOM-id globals.
- Isolated Outline managed clients from Xray/V2Ray workspaces.
- Hardened Outline key creation with create → rename → quota and rollback deletion.
- Added valid `ss://` credential validation before storing/delivering Outline keys.
- Fixed managed Outline revoke from the unified `•••` detail drawer.
- Managed Outline delete now:
  1. verifies Management API reachability,
  2. removes the runtime key when present,
  3. cleans encrypted delivery artifact,
  4. removes the Makia managed-client record.
- If the runtime key is already absent, local cleanup remains valid.
- If the Outline API is unreachable, local state is preserved for retry instead of silently forgetting a possibly-live credential.
- Removed fragile DOM-id-global assumptions from management forms.
- Added the official Makia logo to the panel and GitHub README.

## Automated release gates

The final v1 head must pass all of the following:

- Python `compileall`
- application import/startup
- DB initialization and migration tests
- full pytest suite
- JavaScript syntax
- Bash syntax
- systemd/static packaging checks
- UI action → JavaScript handler contract
- UI static API → FastAPI route contract
- duplicate FastAPI route detection
- browser/Playwright smoke
- official logo asset/render references
- Xray Core smoke
- Outline mocked Management API
- Outline create / quota / renew / reissue
- Outline managed revoke/delete lifecycle
- Outline partial-create rollback
- Xray/Outline engine isolation
- Cloudflare mocked API
- Telegram mocked API
- Backup create/verify contracts
- Disaster Recovery static/cryptographic safety
- secret leakage guards
- node telemetry tests
- directional Full Migration compatibility through 1.0.0

## Real-host acceptance checklist

These checks are environment-dependent and must be performed on the target VPS after install/update.

### Base host
- [ ] Ubuntu 22.04/24.04 clean or supported upgrade source
- [ ] `cat /opt/makia-vps-manager/VERSION` returns `1.0.0`
- [ ] `sudo makia-doctor` passes
- [ ] `sudo makia-uat-smoke` passes
- [ ] panel loads over intended HTTPS hostname
- [ ] login/theme/language controls work
- [ ] no browser console errors during normal management actions

### SSH / NPV
- [ ] create user
- [ ] edit expiry/session/device policy
- [ ] NPV/QR delivery
- [ ] disconnect/lock/unlock
- [ ] revoke/delete
- [ ] real client connection

### Xray / V2Ray
- [ ] create guided inbound/client
- [ ] generated Share Link/QR works in a compatible client
- [ ] policy edit works
- [ ] renew works
- [ ] diagnostics works
- [ ] revoke/delete works
- [ ] Outline rows do not appear in Xray workspace

### WireGuard
- [ ] create peer
- [ ] download native config
- [ ] QR import
- [ ] disable/enable
- [ ] reissue
- [ ] revoke/delete
- [ ] real handshake/traffic

### OpenVPN
- [ ] create client
- [ ] download .ovpn
- [ ] real client import/connect
- [ ] diagnostics
- [ ] revoke/delete

### Outline
- [ ] Docker installed/ready
- [ ] Shadowbox container RUNNING
- [ ] Management API READY
- [ ] create managed key without browser ReferenceError
- [ ] returned key begins with `ss://`
- [ ] copy Access Key into official Outline Client
- [ ] QR import works
- [ ] real VPN traffic works
- [ ] quota applies on real server
- [ ] expiry/renew works
- [ ] reissue invalidates the old runtime key
- [ ] diagnostics works
- [ ] unified drawer revoke/delete removes runtime + Makia state
- [ ] external Outline key delete works
- [ ] Cloudflare hostname, if used, is DNS Only

### Backup / DR
- [ ] create encrypted Full Migration backup
- [ ] verify backup
- [ ] scheduled backup runs
- [ ] remote SCP succeeds with pinned/trusted host key
- [ ] restore on replacement VPS
- [ ] restored users/keys/configs match expected state
- [ ] service diagnostics pass after restore
- [ ] DNS/Cloudflare cutover points to new public IP
- [ ] external clients reconnect after cutover

## Release interpretation

GitHub CI can validate source behavior, mocked integrations, browser workflows, packaging contracts and migration safety. It cannot prove provider firewall/NAT behavior, DNS propagation, real mobile/desktop client connectivity, Docker networking or an external SCP destination.

For that reason, v1.0.0 is the public software version while each deployment still requires the real-host acceptance checklist above.
