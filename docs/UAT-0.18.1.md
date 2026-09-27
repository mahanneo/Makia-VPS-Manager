# Makia 0.18.1 — Protocol connectivity UAT

Update the existing installation with `sudo makia-upgrade`. Verify `cat /opt/makia-vps-manager/VERSION` is `0.18.1`. Keep the updater backup until client tests pass. Run `sudo makia-doctor` and `sudo makia-uat-smoke`, and save their output and the time of each failed client attempt. Do not re-bootstrap an existing OpenVPN server: its PKI and imported client profiles must be preserved.

## Validate from an external client

Create one **new** profile per tested protocol. Choose the known working public IPv4 first, then a direct DNS-only hostname that resolves to that IPv4. Do not reuse an imported profile that still contains an old endpoint. Test on mobile data and Wi-Fi separately.

| Service | Client observation | Server observation |
|---|---|---|
| SSH / NPV | Login plus useful traffic | `systemctl status ssh`, active SSH port and account policy |
| Xray VLESS simple | RAW/REALITY import and request through tunnel | `systemctl status xray`, configured TCP port and service-user config validation |
| Xray other protocols | Matching transport/security in client; TLS requires the selected SNI certificate | Xray listener, `journalctl -u xray`, actual client request |
| WireGuard | New handshake within 180 seconds, RX/TX grows, DNS and internet work | Protocols → WireGuard Diagnostics: UDP listener, forwarding, NAT and peer counters |
| OpenVPN | Tunnel established, DNS and internet through tunnel | Protocols → OpenVPN Diagnostics: listener, `tun` interface, FORWARD and NAT |

If OpenVPN connects but traffic does not pass, inspect the managed `makia-up.sh` and `iptables -S FORWARD` / `iptables -t nat -S POSTROUTING`. The updater repairs older Makia scripts when forwarding was absent, with rollback on service failure. For WireGuard with no handshake, confirm that the public UDP port is permitted by the provider and that the selected hostname has no unusable AAAA record. A green server diagnostic cannot prove provider or mobile-network reachability.

CI exercises repository tests, browser wizard behavior, Xray Core config and a loopback VLESS/REALITY handshake with real HTTP traffic. It does not connect to this particular VPS. For any remaining failure, collect the protocol name, selected endpoint type, port, exact client error, relevant server journal (without private keys), `makia-doctor` and the two diagnostics screens. Avoid sharing `.ovpn` client keys or WireGuard private keys.
