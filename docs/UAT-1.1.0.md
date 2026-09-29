# Makia VPS Manager v1.1.0 — Xray Iran Network Presets UAT

Date: 2026-09-29  
Branch: `feat/v1-iran-inbound-presets`  
Target: `1.1.0`

## Scope

v1.1.0 adds a selectable preset library to the structured Xray Inbound Center. Presets are starting configurations for changing/censored network paths; they are not connectivity guarantees.

### Presets

| Tier | Preset | Core combination |
|---|---|---|
| Recommended | VLESS · REALITY · RAW/Vision | VLESS + RAW + REALITY + xtls-rprx-vision |
| Alternative | VLESS · gRPC · REALITY | VLESS + gRPC + REALITY |
| Alternative | VLESS · WebSocket · TLS | VLESS + WebSocket + TLS |
| Alternative | VLESS · HTTPUpgrade · TLS | VLESS + HTTPUpgrade + TLS |
| Alternative | Trojan · gRPC · TLS | Trojan + gRPC + TLS |
| Alternative / UDP | Hysteria2 · TLS · UDP | Hysteria2 + TLS |
| Compatibility | VMess · WebSocket · TLS | VMess + WebSocket + TLS |
| Experimental | VLESS · XHTTP · REALITY | VLESS + XHTTP + REALITY, packet-up |

## Safety / honesty rules

- Presets never bypass the normal Xray config validation and rollback path.
- TLS presets explicitly require a valid domain/certificate.
- Hysteria2 explicitly declares UDP dependency.
- XHTTP is not marked Recommended on the pinned Xray 26.3.27 Core.
- The UI states that a preset is not a guarantee of connectivity.
- Operators can edit the applied preset before creation.

## Automated gates

- preset IDs unique
- every preset combination accepted by the Makia builder compatibility validator
- recommended tier excludes XHTTP
- TLS presets declare domain dependency
- UDP dependency only appears on Hysteria2
- UI preset cards and delegated action handler exist
- browser selects Recommended, Hysteria2 and Experimental presets and verifies populated fields
- every preset is converted to a real Xray config and validated by the pinned Xray 26.3.27 binary in the Xray Core CI smoke
- full existing v1 Python/DB/JS/browser/systemd/security/backup/restore gates remain enabled

## Host field UAT

Because Iran filtering conditions differ by ISP, mobile operator, datacenter and time, perform real field testing on the intended network:

- [ ] VLESS RAW REALITY imports in the target client and carries traffic
- [ ] VLESS gRPC REALITY imports and carries traffic
- [ ] TLS domain/certificate is valid before WS/HTTPUpgrade/Trojan TLS testing
- [ ] WS TLS carries traffic on the intended ISP
- [ ] HTTPUpgrade TLS carries traffic on the intended ISP/client
- [ ] Trojan gRPC TLS carries traffic
- [ ] Hysteria2 UDP works on the target ISP; if UDP is degraded/blocked, do not use it as the primary profile
- [ ] XHTTP Lab is tested only on compatible clients and server memory/socket usage is observed before fleet rollout
- [ ] at least two independent fallback presets are kept for users rather than relying on one network path

## Promotion rule

Automated CI proves schema/config validity and browser behavior. It cannot prove that a specific Iranian ISP or filtering regime will pass a protocol at a particular time. Field results should therefore inform which preset is shown to customers as the operational primary/fallback.
