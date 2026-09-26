# Makia 0.17.0-rc3 — WireGuard domain and protocol UAT

## Installation and rollback

Back up the VPS and update the existing rc2 installation with `sudo makia-upgrade`. Confirm `cat /opt/makia-vps-manager/VERSION` reports `0.17.0-rc3`. Keep the existing rollback point until the external-client checks pass. Do not reinstall or replace the WireGuard server keys.

## WireGuard IP → domain diagnosis

1. In Access Center, note the Endpoint in the **actual client `.conf`**, its UDP port, and the working public IPv4. The panel domain is not necessarily the profile endpoint.
2. Open Protocols → WireGuard Diagnostics. Enter the domain and the known working IPv4. Record `A`, `AAAA`, local VPS IP, service, interface, UDP listener, forwarding, NAT and each peer's handshake/RX/TX.
3. The VPN hostname must have an A record for the working VPS IPv4 and DNS-only/direct routing. If it has AAAA, that address must also belong to the VPS and its IPv6 UDP route/firewall must be tested; otherwise use a dedicated A-only hostname. An IPv4 tunnel can use an IPv6 transport endpoint when IPv6 is actually working. A web proxy/CDN hostname cannot transport raw WireGuard UDP. With upstream NAT, confirm the A record against the public IP in the VPS provider console.
4. For a saved peer, choose **Endpoint** in Access Center. This preserves keys and port and rebuilds encrypted `.conf`/QR/ZIP. Import the new profile on the phone; an existing imported profile does not automatically change. Legacy peers without a retained client key must be reissued after the domain passes diagnostics.
5. Connect from a device outside the VPS, first with the working IPv4 and then with the A-only domain. Require a fresh `wg show wg0 latest-handshakes`, increasing RX/TX, reachable internet and working DNS. A green server-side check alone is not a connection pass.

## Protocol matrix (real clients)

| Protocol | Public IPv4 | Direct domain | Runtime and client pass condition |
|---|---|---|---|
| SSH / NPV | Import/connect | A record → VPS, import/connect | SSH session and NPV application traffic |
| Xray | Supported IP mode | TLS/SNI/certificate as configured | Core validation, listener, client traffic |
| WireGuard | Fresh handshake and RX/TX | DNS-only direct; AAAA requires working VPS IPv6, same handshake and traffic | UDP listener, forwarding, NAT, client DNS and internet |
| OpenVPN | Import/connect | DNS-only direct, IPv4 client profile | Service/listener, tunnel traffic and DNS |

Test both Wi-Fi and mobile networks. If WireGuard has no handshake despite a correct domain, inspect provider firewall/security groups, port/UDP reachability, client keys and network filtering. No software-only gate can guarantee operation on every network.

## Release gate

Run unit, browser smoke, Bash/JS syntax and Xray 26.3.27 CI on the exact PR commit and main after merge. Keep the version as RC until this real VPS matrix passes.
