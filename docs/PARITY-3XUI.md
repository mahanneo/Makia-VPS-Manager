# Makia ↔ 3x-ui capability parity matrix

Baseline reviewed: current MHSanaei/3x-ui feature set as of 2026-09-26.

Legend:
- **Native**: dedicated Makia UI + validated backend path.
- **Advanced**: supported through validated engine configuration, without a dedicated form yet.
- **Foundation**: data/control plane exists but full parity is not complete.
- **Pending sidecar**: requires a separately managed runtime; Makia does not show it as working yet.

| Capability | Makia v0.21.0-rc1 |
|---|---|
| VLESS | Native |
| VMess | Native |
| Trojan | Native |
| Shadowsocks | Native (no reliable per-client quota in quick profile) |
| Hysteria2 | Native through current Xray core when supported |
| HTTP Proxy | Native |
| SOCKS5 | Native |
| Dokodemo / Tunnel | Native |
| TUN | Advanced Xray JSON |
| WireGuard | Native |
| OpenVPN | Native |
| Stunnel | Native service integration |
| REALITY | Native VLESS wizard |
| TLS | Native via panel-managed certificate |
| RAW/TCP | Native |
| WebSocket | Native |
| gRPC | Native |
| HTTPUpgrade | Native |
| XHTTP | Native |
| mKCP | Native |
| Xray routing | Advanced validated JSON |
| Xray outbounds | Advanced validated JSON |
| Fallbacks | Advanced validated JSON |
| Per-Xray-client traffic | Native for VLESS/VMess/Trojan/Hysteria2 |
| Client quota | Native where engine exposes reliable per-client counters |
| Expiry | Native |
| IP/device limit | Native when online-IP API is exposed; otherwise clearly unavailable |
| Traffic reset cycle | Native |
| Subscription raw/base64 | Native |
| QR/share link | Native |
| SSH expiry/session/device policy | Native |
| Multi-node heartbeat | Foundation |
| Admin 2FA | Native |
| Scoped API tokens | Native |
| Audit log | Native |
| Backups | Native |
| Domain + Let's Encrypt | Native |
| PWA shell | Native |
| Persian / English | Native |
| Theme/density | Native |
| TUIC v5 | Pending sidecar |
| AmneziaWG | Pending sidecar |
| MTProto | Pending sidecar |
| HWID-aware client fingerprinting | Pending client/subscription protocol design |
| Clash/JSON subscription auto-negotiation | Pending |
| Telegram/Discord bot | Pending |
| PostgreSQL storage | Pending |

## UI / operations note for v0.21.0-rc1

Daily operation is no longer concentrated in one provisioning page. SSH / NPV, Xray / V2Ray, WireGuard and OpenVPN have dedicated workspaces, while All Clients remains the cross-protocol directory. The Protocol Hub owns engine setup, diagnostics, advanced configuration and port allocation visibility.

Port preflight is transport-aware: TCP and UDP may reuse the same numeric port when their listeners are compatible, while same-transport collisions are blocked before service bootstrap or Xray mutation.

## Release rule

A Pending item must not be represented by a working-looking control. It becomes Native only when Makia has:
1. deterministic installation or explicit external-runtime detection;
2. validated configuration;
3. start/restart and health checks;
4. safe update/recovery behavior;
5. host UAT documentation.
