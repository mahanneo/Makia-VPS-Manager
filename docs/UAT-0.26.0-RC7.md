# Makia 0.26.0-rc7 — Operations Suite + Outline Real VPS UAT

RC7 is **not Stable** until this checklist passes on the real Ubuntu VPS and intended clients.

## 1. Non-destructive upgrade
1. Create and verify a Full Migration Backup before upgrade.
2. Upgrade RC6 → RC7.
3. Confirm existing SSH, Xray, WireGuard, OpenVPN credentials and client portal links remain valid.
4. Run `makia-doctor` and `makia-uat-smoke`.
5. Confirm dashboard/version show `0.26.0-rc7`.

## 2. Plans / Templates
Create one plan for SSH, Xray, WireGuard, OpenVPN and Outline (after Outline setup).
Use each plan from the Plans page and confirm duration/quota/device/session defaults are applied to the real creation form rather than UI-only labels.

## 3. Quick Renew / Bulk / Expiry
- Renew an SSH account and verify Linux account expiry changes.
- Renew an Xray managed client and verify DB/runtime policy remains active.
- Run bulk renew/quota operations on several supported managed users.
- Disable and re-enable a test Outline key: disable must make the old ss:// key unusable; re-enable must issue a fresh real Outline key.
- Verify Expiry Center ordering and expired/soon counts.

## 4. Scheduled / Remote Backup
- Create a local Quick schedule and run it manually.
- Verify remote + Quick is rejected.
- Create an encrypted Full Migration schedule with a 10+ character password.
- Test one configured S3-compatible target (S3/R2/B2 as applicable) and/or SFTP target.
- Verify uploaded object/file exists remotely and local Backup Run shows success.
- Verify retention deletes only older backups belonging to that schedule.
- Download and Verify/Preview the scheduled Full Migration archive.

## 5. Disaster Recovery + Cloudflare
On a disposable replacement VPS:
1. Install RC7.
2. Restore the RC7 Full Migration archive.
3. Verify runtime/services before DNS cutover.
4. Configure a least-privilege Cloudflare API token and test record resolution.
5. Run cutover to the replacement IPv4.
6. Confirm Makia writes the A record as **DNS only** (not proxied).
7. Verify domain-based old client configs reconnect unchanged after DNS propagation.
8. Confirm literal-IP clients are explicitly reported as requiring re-export.

## 6. Telegram alerts / bot
- Configure Bot Token + exact Chat ID and send test.
- Verify only the configured Chat ID gets responses.
- Test read-only commands: `/status`, `/expiry`, `/backups`, `/help`.
- Stop/recover one non-critical monitored service in a controlled test and verify alert de-duplication (no alert storm).
- Confirm no Telegram mutation command can create/delete/renew access.

## 7. Device-aware Client Portal
Open one Xray/WireGuard/OpenVPN/SSH/Outline portal from Android/iOS and desktop where possible.
- Mobile guidance should prefer QR/one-tap only when the protocol has a supported URI.
- Desktop should prefer downloadable file/copy link.
- OpenVPN must not expose a fake custom one-tap URI.
- Outline ss:// one-tap/import and QR must represent the exact current access key.

## 8. Diagnostics Center
Verify DNS, HTTPS, services, portable backup, Outline and Fleet checks reflect actual runtime state.
Break one safe test dependency and confirm Diagnostics reports ATTENTION instead of a false PASS.

## 9. Multi-VPS Fleet
Connect at least one second VPS/node.
Confirm fresh heartbeat reports:
- hostname/version/region/public URL
- CPU/RAM/disk
- managed user and online counts
- RX/TX
- latency
- Makia/Xray/WireGuard/Nginx service states
Revoke the node and verify future heartbeats are rejected.

## 10. Outline
Outline is optional. If used:
1. Install host dependency with `sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade`.
2. Run Outline setup from Makia.
3. Confirm Shadowbox container is running.
4. Confirm management API certificate fingerprint matches `/opt/outline/access.txt`.
5. Create an Outline access key, set quota and optional expiry.
6. Import the ss:// key in official Outline Client and pass real traffic.
7. Reduce quota/change quota and verify management API applies it.
8. Disable the managed key and verify the **old key stops working**.
9. Re-enable/renew it and verify Makia reissues a new key and updates its Client Portal.
10. Create a Full Migration Backup; confirm Outline state is included.
11. Restore on replacement VPS and confirm Shadowbox + managed keys become available again before DNS cutover.

## 11. Existing protocol regression
Re-test at least:
- VLESS TCP/NONE
- VLESS TCP/REALITY
- one VLESS WS/gRPC/XHTTP profile used in production
- WireGuard .conf + QR
- OpenVPN UDP/TCP .ovpn download
- SSH/NPV
- Backup Verify/Preview and client portal link rotation

## 12. Inside-Iran field gate
From at least one Iranian mobile network and one fixed ISP where possible, test intended protocols for:
- portal reachability over HTTPS
- import/download
- handshake/connect
- DNS and HTTP/HTTPS traffic
- reconnect
- at least 10 minutes stability

Only after these real-host and real-client checks pass may RC7 be considered for Stable promotion.
