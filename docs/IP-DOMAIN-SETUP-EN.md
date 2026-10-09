# Makia — IP or Domain Setup, Client Installation and Troubleshooting

**Current stable server release: 1.6.4.** This guide describes the staged endpoint preflight candidate. It does not promise that every transport supports an IP-only TLS certificate, and it does not replace live VPS/client acceptance testing. [Persian complete guide](IP-DOMAIN-SETUP-FA.md).

## Address and protocol decision matrix

| Mode | Direct public IPv4 | DNS hostname | Important gate |
| --- | --- | --- | --- |
| SSH / NPV | Supported | Supported | TCP port, working credentials and network route |
| WireGuard (native) | Supported | Supported | UDP/forwarding/NAT/handshake |
| Classic OpenVPN | Supported | Supported | Client remote transport must match server; retain CA verification |
| Outline / Shadowsocks | Supported | Supported | Use the actual port/access key assigned by Outline, not a made-up default |
| Xray/V2Ray | Depends on security/transport | Depends on security/transport | TLS/SNI/REALITY/transport compatibility must be checked per inbound |
| Browser HTTPS Proxy | Not in current TLS implementation | Required | Valid hostname certificate, gateway port/auth and verified browser egress |
| WStunnel WSS / OpenVPN WStunnel | Not in current TLS implementation | Required | Valid TLS hostname + backend readiness |
| Stealth TLS | Not in current TLS implementation | Required | Valid matching certificate and available TCP listener |
| Certificate-backed IKEv2 | Not in current implementation | Required | Trust/name validation + UDP 500/4500 |
| PPTP | Not supported | Not supported | Insecure legacy technology; choose WireGuard/OpenVPN |

A technically possible TLS IP SAN is **not** equivalent to IP certificate issuance and trust being supported by this Makia release. Do not disable certificate validation to make an unsupported setup appear connected.

## First installation without a domain

1. Use a clean Ubuntu 22.04/24.04 VPS with systemd and a publicly routable IPv4. Consult the [README](../README.md) for the pinned install instructions. Do not use a production host for tests that alter protocol listeners.
2. Open `http://SERVER_IP/` only for initial access from a trusted network. HTTP over IP is **not** a secure replacement for HTTPS. Arrange a valid HTTPS control-plane origin before using credentials over an untrusted network.
3. Select native SSH, WireGuard or OpenVPN first. Use the IP alone in the endpoint field, no `https://`, `/path` or inline port. Set the listener port separately.
4. In an installed candidate run `sudo makia-endpoint-wizard`, or run `python3 scripts/endpoint-wizard.py` from a source checkout. Alternatively open **Settings → Domain / Nginx / HTTPS → IP/Domain preflight**. The preview **does not apply settings**.
5. Confirm firewall, listener, DNS/route, actual client handshake and an external egress-IP test before handing out a configuration.

## When using a domain

- Configure an A record to the actual public VPS IPv4 and allow time for propagation. For direct UDP/TCP protocols, do **not** rely on an ordinary HTTP CDN proxy; use DNS Only.
- Confirm that any AAAA record corresponds to reachable IPv6 if clients can select IPv6.
- For certificate-bound modes, issue a trusted certificate that covers the exact hostname used by the client. Check expiry and renewal.
- Do not put an IP address into the **Panel Domain** field; that field is for DNS names. Use the direct IP only for modes that support it.

## Client instructions

- **Chrome / Edge:** install the latest `Makia-Browser-VPN` browser-only extension from the official Release. Confirm the proxy is actually controlled by Makia and read **Verified exit IP**. This is not a full-device VPN; troubleshoot 407/CONNECT/TLS explicitly.
- **Android:** obtain a *release-signed* APK from the official release only after the signing workflow succeeds, certificate fingerprint and checksum match the owner identity, and field UAT is complete. For import mode use a supported WireGuard/OpenVPN/Xray client and the exported profile. A debug/UAT APK is not a stable release.
- **iPhone/iPad:** in Safari install the `/client/` PWA via Add to Home Screen for account/config management. PWA cannot create an iOS system-wide VPN tunnel. Use a supported native VPN app via profile import. An Apple-signed Makia Network Extension build is not currently claimed.
- **Windows:** use the signed-off Windows Full Device Connector build only after end-to-end test; browser-only mode affects only Chrome/Edge.

## Troubleshooting and release validation

Use `sudo makia-doctor`, Nginx diagnostics, protocol-specific validation, service state, listening TCP/UDP sockets and client-side logs. A service can be active while the actual VPN route is broken. **Do not label an unverified configuration 'Connected' just because it was saved or a TCP port responded.** Check NAT/forwarding/handshake, DNS, IPv4/IPv6, TLS identity, proxy authentication and quota/expiry, with non-production test accounts.

See [Client Guide](CLIENT-GUIDE-FA.md), [Android signing](ANDROID-RELEASE-SIGNING.md), [Release status](RELEASE-STATUS.md), and [Iran connectivity field tests](IRAN-CONNECTIVITY-FIELD-TEST.md).
