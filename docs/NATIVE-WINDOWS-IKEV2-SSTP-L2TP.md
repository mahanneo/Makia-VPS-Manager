# Native Windows VPN (release-gated)

**Candidate only, NOT three live working protocols.** Uses Windows built-in whole-device VPN rather than Chrome proxy extension.

## Live audit, 2026-10-20
Production Makia reports 1.6.5. strongSwan starter is active, UDP 500/4500 listening, existing IPsec configuration and Makia IKEv2 env present, with 0 security associations at time of audit. xl2tpd and accel-ppp are absent/inactive. TCP 443 belongs to existing Nginx HTTPS; UDP 443 is separate. Do not interrupt MahiNet storefront, Makia browser panel, Outline, Xray, WireGuard or existing user sessions.

## Actual candidate capabilities
- Preserve existing protocol_ops as the single IKEv2/strongSwan owner and existing API for IKEv2 user creation, listing and revocation.
- Authenticated /api/protocols/native-windows reports honest statuses. IKEv2 ready requires managed config, active daemon, UDP 500 and 4500, and a configured DNS hostname.
- Only when ready, authenticated /api/protocols/native-windows/ikev2/profile.ps1 provides a credential-free Windows native client setup file. Admin may share this file with subscriber; each subscriber receives separate IKEv2 credentials via the existing account workflow.
- SSTP and L2TP/IPsec appear BLOCKED, without fake account provisioning or false Connected UI. Their servers are NOT installed by this change.

## Windows installation
Download Makia-IKEv2-Windows.ps1 from the IKEv2 card only after server readiness. Inspect and verify file provenance on Windows 10/11. Run it in Windows PowerShell under the intended Windows account, then open Settings > Network & Internet > VPN > Makia IKEv2 > Connect. Enter the user-specific IKEv2 credentials at first connect; the script contains no password or private key, and refuses overwriting a different existing profile. Ensure the server DNS name matches the trusted certificate SubjectAltName. Windows RememberCredential is separate from browser-login persistence. Test actual changed public IP, DNS, route, browsing and server traffic counters.

## Hard blockers and separate rollout
SSTP requires an actual audited Windows-compatible server and external TCP 443 with trusted TLS. Current shared public IPv4 TCP 443 is occupied by Nginx, so it requires a separate public IP or an independently reviewed non-disruptive Layer-4 SNI multiplexing architecture. A subdomain alone does not free port 443. Do not replace Nginx.

L2TP/IPsec requires actual L2TP/PPP daemon plus IPsec-only tunnel, Windows-compatible credentials and safe coexistence of IKEv1 transport with currently configured strongSwan IKEv2. Do not expose UDP 1701 unencrypted or create universal weak pre-shared keys. Avoid claiming account quota, expiry or billing enforcement without actual backend measurement.

Before live enablement: source and install/upgrade/rollback gates from official 1.6.5, certificates and port-owner audit, test user creation/revocation, Windows 10/11 credential and egress UAT, DNS and firewall, reboot, accounting validation and verified preservation of existing VPN services. All mutating host installation must follow a backup and explicit rollback plan; normal GET/status and Windows export have zero host side effects.
