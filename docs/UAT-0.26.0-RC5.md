# Makia 0.26.0-rc5 — Xray Inbound Center UAT

RC5 is a Release Candidate, not Stable.

## 1. Upgrade
1. Create a Full Migration Backup.
2. Upgrade the existing VPS to RC5.
3. Confirm VERSION and dashboard show `0.26.0-rc5`.
4. Run `makia-doctor` and `makia-uat-smoke`.

## 2. Single Xray creation workflow
From both `Xray / V2Ray` and the global `Create Access` button, choosing Xray must open the same **XRAY INBOUND CENTER**.
No legacy/simple Xray wizard should be required for normal creation.

## 3. Required real-host inbound matrix
Use unused ports and create these profiles one by one:
- VLESS / TCP RAW / NONE
- VLESS / WebSocket / NONE
- VLESS / WebSocket / TLS (valid certificate required)
- VLESS / gRPC / REALITY
- VLESS / XHTTP / REALITY
- VLESS / mKCP / NONE
- VMess / TCP RAW / NONE
- VMess / WebSocket / NONE
- Trojan / TCP RAW / TLS
- Trojan / TCP RAW / REALITY
- Shadowsocks / TCP RAW / NONE

For each successful creation:
- Xray service remains active.
- The requested TCP/UDP listener exists.
- QR/share link imports into a compatible client.
- A real HTTP/HTTPS request passes through the tunnel.
- Reconnect works after client disconnect.

## 4. Transport controls
Verify the form changes with Transport:
- RAW: header type, HTTP camouflage, PROXY protocol.
- WebSocket: path, host, headers, heartbeat.
- gRPC: serviceName, authority, multi mode.
- HTTPUpgrade: path, host, headers.
- XHTTP: path, host, mode, xPaddingBytes.
- mKCP: MTU, TTI, capacity, CWND/window.

## 5. Security controls
- NONE must not force TLS or REALITY.
- TLS must require a usable Makia certificate/SNI.
- REALITY must generate server private/client public key material and Short ID without exposing the private key to the client.
- Invalid combinations such as REALITY + WebSocket or TLS + mKCP must be rejected before service mutation.
- XTLS Vision must only be offered/applied for VLESS + RAW + TLS/REALITY in this RC.

## 6. Sniffing / Sockopt
Create at least one test inbound with Sniffing enabled and common Sockopt controls such as TCP Fast Open or congestion selection. Confirm Core validation and runtime startup still pass.

## 7. Multiple clients on one inbound
On a VLESS inbound:
1. Click `+ Client` twice.
2. Confirm all clients share the same inbound/port but have independent UUIDs, QR/share links and subscription IDs.
3. Revoke one client.
4. Confirm the inbound and the remaining client continue working.
5. Revoke the final client and confirm the inbound is removed according to the existing lifecycle.

## 8. No-fake-controls gate
Shadowsocks/HTTP/SOCKS must not show a multi-client action that Makia cannot reliably model.
Any Core-level feature not represented by a structured form must remain available through **Advanced JSON** with Xray validation/backup/rollback.

## 9. Existing functions regression
Re-test:
- Xray quota / expiry / IP limit / reset.
- Subscription and client page.
- Native profile download / QR / Protected ZIP.
- OpenVPN OVPN download.
- Full Migration Backup Verify & Preview.

## 10. Iran field gate
From at least one Iranian mobile network and one fixed ISP where possible, test intended Xray profiles for handshake, DNS, routed traffic, reconnect and at least 10 minutes of stability.

Do not promote RC5 to Stable until the real VPS and Iran field gate pass.