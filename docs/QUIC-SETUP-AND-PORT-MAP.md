# TUIC + Hysteria2 / QUIC integration and port map

## Release status

This work is part of **Makia 1.6.10-rc3** and is not a production-stable release until CI, local data-plane checks and external client handshakes pass. The new managed TUIC and Hysteria2 services run independently under sing-box. Any existing Xray-based Hysteria2 entries are left untouched; the new service has its own user store and UDP port.

## Runtime design

- Runtime: official sing-box **1.14.4**, pinned by scripts/setup-tuic-backend.sh and installed from the signed SagerNet package repository.
- Service: **makia-tuic.service**, isolated from the default sing-box.service.
- Listener: **UDP/8445** (QUIC/TUIC), independent of TCP/443 and WireGuard UDP/443.
- TLS: existing Let's Encrypt certificate for **p.mahinet.shop** is copied to a dedicated root-owned, sing-box-group directory. A deploy hook refreshes the copied certificate and restarts only makia-tuic.service after certificate renewal.
- Authentication: per-user UUID + strong password. Zero-RTT is disabled. User changes validate the complete candidate config, back up the prior config, apply atomically, restart TUIC, verify the listener, and roll back on failure.
- Exports: TUIC share link, QR SVG, and connection guide are stored through Makia's existing access-artifact delivery path. The sing-box server config and private key are never sent to the browser.
- Runtime isolation: the TUIC unit runs as the dedicated sing-box user with NoNewPrivileges, ProtectSystem=strict and restricted address families.
- Certificate renewal is automated; UDP/8445 must also be permitted by any upstream/cloud firewall. A local listener check does not prove external reachability.
- Hysteria2 uses **makia-hysteria2.service** and its own `/etc/sing-box/makia-hysteria2.json`, with password authentication and **UDP/8446**. It shares the copied TLS certificate but has independent users, config backups, systemd lifecycle and rollback.
- Hysteria2 uses `scripts/setup-hysteria2-backend.sh`; TUIC uses `scripts/setup-tuic-backend.sh`. Both setup scripts leave their listener stopped until the first user is created through Makia.

## Verified port ownership on the host

| Service | Transport / port | Ownership note |
|---|---|---|
| Nginx / panel HTTPS | TCP/443 | Existing public HTTPS owner; do not replace it |
| WireGuard | UDP/443 | Kernel WireGuard socket; can coexist with TCP/443 |
| OpenVPN TCP | TCP/8443 | Existing service |
| WStunnel | TCP/8444 | Existing service |
| TUIC / QUIC | UDP/8445 | New isolated listener; confirm external reachability |
| Hysteria2 / QUIC | UDP/8446 | New isolated listener; confirm external reachability |
| MTProto proxy | TCP/10443 | Existing service |
| SSTP | TCP/14443 | Existing dedicated listener |
| IKEv2 / IPsec | UDP/500 and UDP/4500 | Existing IPsec ports |
| OpenVPN UDP | UDP/1194 | Existing service |
| L2TP | UDP/1701 | Existing service |
| AmneziaWG | UDP/51821 | Existing awg0 interface |
| Outline | Generated TCP/UDP port(s) | Use the generated Outline access key; do not hardcode one port |

The port map is transport-aware: TCP/443 and UDP/443 are different sockets. TUIC and Hysteria2 do not take over Nginx, SSTP or any existing VPN listener.

## Current validation and remaining checks

1. Unit and regression tests cover share-link escaping, QR export, username validation, atomic config updates and rollback for both protocols, endpoint preflight, Cyberpunk UI and API contracts.
2. The protocol endpoint matrix includes both QUIC runtimes and their UDP listeners.
3. Before release, verify TLS key/certificate matching, UDP/8445 and UDP/8446 listeners, and successful local plus external client handshakes that fetch a public HTTPS resource.
4. Verify the provider firewall allows both UDP ports. The host's UFW is inactive at the time of this review, so no UFW rule is needed unless its state changes.
5. Test certificate renewal hooks in a controlled staging run; do not force a production certificate renewal merely to test them.
6. Windows native SSTP error 720 remains a separate release blocker. Successful QUIC handshakes do not clear that SSTP gate.
