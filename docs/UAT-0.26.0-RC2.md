# Makia VPS Manager 0.26.0-rc2 — Release Gate

RC2 extends the 0.26 hardening line with real connection modes. It is **not Stable** until all gates below pass on the real VPS and real clients.

## Automated gate

Required before merge:
- Python compile/import
- Unit and contract tests
- Bash syntax
- JavaScript syntax
- Browser smoke
- Xray Core 26.3.27 exhaustive guided matrix
- VLESS RAW/REALITY handshake + routed traffic

## Upgrade gate

Existing host upgrade must preserve:
- Makia SQLite data and administrator state
- SSH accounts and policy metadata
- Xray configuration and client credentials
- WireGuard private/public keys and peers
- OpenVPN PKI, clients and server configuration
- Nginx / Let's Encrypt state

Run:

```bash
sudo makia-upgrade
cat /opt/makia-vps-manager/VERSION
sudo makia-doctor
sudo makia-uat-smoke
```

Expected version: `0.26.0-rc2`.

## Connection Modes gate

Follow `docs/UAT-PROTOCOL-MODES.md`.

The six cards must be backed by real runtime state:
- IKEv2
- WireGuard
- UDP
- TCP
- Stealth
- WStunnel

No card may claim READY without its actual service/listener/runtime being ready.

## HTTPS prerequisite

IKEv2, Stealth and WStunnel TLS/WSS paths require a valid direct-domain Let's Encrypt certificate. Certbot installation belongs to the root installer/updater and must never run through the hardened web service.

## Stable gate

Do not promote to `0.26.0` Stable until:
1. upgrade UAT passes on the production-like VPS;
2. clean-install UAT passes on supported Ubuntu;
3. published modes pass real client import/authentication/handshake/DNS/traffic/reconnect checks;
4. Iran field testing is recorded for at least one mobile and one fixed/Wi-Fi path for each mode claimed as supported in Iran.


## TCP / Stealth root-cause gate

On the real VPS, open **Network / Ports → Connection Modes** and record the **TCP Port Ownership** section before changing anything.

Required:
- HTTPS/Nginx owns TCP/443 when panel HTTPS is active.
- OpenVPN UDP may use UDP/443 at the same time; that is not a collision with TCP/443.
- OpenVPN TCP fallback must use a distinct free TCP port and must become active as `openvpn-server@makia-tcp`.
- The TCP fallback must use its own `10.9.0.0/24` tunnel network and must not mutate the primary UDP server or PKI.
- If the requested TCP port is occupied, Makia must identify the real owner where possible and suggest a free alternative.
- Stealth public Stunnel port must differ from the OpenVPN TCP backend port.
- Stealth must reuse the TCP fallback backend and must not disconnect/reconfigure existing UDP users.
- WStunnel, Stealth, HTTPS and OpenVPN TCP may not claim the same TCP listener simultaneously.
- Any missing OpenVPN PKI file must be shown as a setup blocker, not hidden behind a generic SETUP state.

Host evidence:
```bash
sudo ss -lntup
sudo systemctl status openvpn-server@server openvpn-server@makia-tcp stunnel4 makia-wstunnel --no-pager
sudo journalctl -u openvpn-server@makia-tcp -u stunnel4 -n 120 --no-pager
```

## Full VPS migration / disaster-recovery gate

Use a disposable replacement Ubuntu 22.04/24.04 VPS. Do not test destructive Restore on the only production VPS.

1. In **Backup**, run **Preflight Migration Check**.
2. Create **Quick Backup** and confirm it remains host-local.
3. Create **Full Migration Backup** with a strong password.
4. Confirm History shows Date, Size, Version, SHA256, AES-256 Encryption and Restore readiness.
5. Install the **same RC2 version** on the replacement VPS.
6. Open **Upload & Restore**, upload the encrypted bundle, enter the password, and confirm:
   - manifest format/version passes;
   - payload SHA256 integrity passes;
   - app-version compatibility passes;
   - component preview is correct;
   - no runtime mutation happens before Restore Now.
7. Start Restore and confirm the detached `makia-migration-restore@<job>.service` continues while `makia-vps-manager` restarts.
8. Confirm runtime validation passes for every component present in the bundle.
9. Force one disposable failure and verify automatic rollback returns the pre-restore Makia runtime/data instead of leaving a half-restored host.
10. Verify old identity material is unchanged:
    - Xray UUIDs / REALITY key pair / Short IDs;
    - WireGuard server key and peer keys/configs;
    - OpenVPN CA, server/client certificates, CRL and tls-crypt key;
    - IKEv2 users/certificate state;
    - Stunnel/WStunnel settings;
    - SSH Makia-managed account identity.
11. Verify NAT/forwarding was rebound to the **new VPS default interface**.
12. Confirm the panel displays:
    `Cloudflare A record: <same-domain> → NEW_VPS_IP`
13. Change the A/AAAA record only after restore validation passes. For raw VPN/SSH endpoints, Cloudflare must be **DNS only**.
14. Refresh Restore status and confirm DNS diagnostics report that the domain resolves to the replacement VPS.
15. Test old **domain-based** client configs without regenerating credentials.
16. Any config containing the old literal VPS IP must be marked for endpoint change/re-export; DNS cannot preserve a literal IP.

### Security evidence

- Full migration export is AES-256 encrypted.
- Password is not written into status/audit output.
- Staged password file is root-only and is removed by the restore runner.
- Payload SHA256 is checked before mutation.
- Pre-restore rollback data is root-only and deleted after success/rollback.
- No `NoNewPrivileges` relaxation is permitted for the Makia web service.
- Quick Backup is not offered as a portable/plaintext download.

## Final field UAT after DNS cutover

After DNS propagation, test the old domain-based profiles from inside Iran on:
- at least one mobile ISP;
- at least one fixed/Wi-Fi path.

For every mode intended for publication record: import, handshake/auth, DNS, browsing, meaningful traffic and reconnect. **RC2 remains a Release Candidate until this gate passes.**
