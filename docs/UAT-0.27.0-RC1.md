# Makia VPS Manager 0.27.0-rc1 — Connection Modes UAT

This release candidate adds six runtime-backed connection modes: IKEv2, WireGuard, OpenVPN UDP, OpenVPN TCP, Stealth (Xray VLESS/REALITY) and WStunnel (WireGuard over WSS).

> This is not a Stable release. Server-side CI does not prove connectivity from every ISP or from inside Iran.

## 1. Upgrade gate

Run on the real VPS:

```bash
sudo makia-upgrade
cat /opt/makia-vps-manager/VERSION
sudo makia-doctor
sudo makia-uat-smoke
```

Expected version: `0.27.0-rc1`. Existing users, SQLite data, OpenVPN PKI, WireGuard keys and Xray configuration must remain intact.

## 2. Connection Modes workspace

Settings/navigation must expose a dedicated Connection Modes page with exactly these managed modes:
- IKEv2
- WireGuard
- OpenVPN UDP
- OpenVPN TCP
- Stealth / VLESS REALITY
- WStunnel / WireGuard over WSS

Every ACTIVE badge must be derived from live runtime status. No mode may be marked active just because its package is installed.

## 3. Port collision contract

- WireGuard UDP/443 and OpenVPN UDP/443 cannot bind simultaneously on the same IP.
- Nginx HTTPS TCP/443 and OpenVPN TCP/443 cannot bind simultaneously on the same IP.
- WStunnel must reuse Nginx HTTPS/WSS and an internal loopback listener rather than taking a second public TCP/443 socket.
- Xray Stealth must reject any selected TCP port already occupied by another service.

## 4. IKEv2

Prerequisites:
- direct DNS A record to this VPS
- valid Let's Encrypt certificate for the configured VPN domain
- strongSwan tooling installed by root installer/updater

Checks:
- `ipsec statusall` succeeds
- `strongswan-starter` is active
- UDP/500 listener exists
- UDP/4500 listener exists
- `makia-ikev2-firewall` is active after configuration
- EAP-MSCHAPv2 user can be created and revoked
- iOS/macOS/Windows native IKEv2 or Android strongSwan can authenticate
- DNS and routed Internet traffic work through the tunnel

## 5. WireGuard

Existing WireGuard regression gates remain required: peer creation, QR/native config, handshake, RX/TX, NAT, forwarding, DNS, MTU, Keepalive and AllowedIPs.

## 6. OpenVPN UDP/TCP

Switch each transport using the Connection Modes UI. Backup/restart verification/rollback must remain intact. Use a free port when 443 conflicts with another listener. Existing PKI must survive transport changes.

## 7. Stealth

`Stealth` is a UI mode backed by the real Xray VLESS/REALITY implementation. Verify:
- client creation produces a VLESS/REALITY share link
- Xray Core validates the generated config
- selected TCP port is free
- handshake and meaningful routed traffic work from an external client

## 8. WStunnel

Prerequisites:
- Makia HTTPS is valid on the chosen domain
- WireGuard server and retained client profile already exist
- validated WStunnel 11.0.0 binary is installed

Checks:
- `makia-wstunnel` is active
- only the internal loopback TCP listener is created by WStunnel
- Nginx WSS path is present and `nginx -t` passes
- generated client bundle contains the WStunnel command and rewritten WireGuard config
- start WStunnel client first, then WireGuard
- WireGuard handshake, DNS, browsing, traffic and reconnect succeed through WSS

## 9. Client field gate

Test published modes from at least one mobile ISP and one fixed/Wi-Fi path inside Iran. Record import/setup, handshake/login, DNS, browsing, meaningful traffic and reconnect. Do not promote to Stable until the real-host and field gates pass.
