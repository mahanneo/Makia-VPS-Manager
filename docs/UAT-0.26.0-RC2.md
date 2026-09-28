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
- OpenVPN PKI, clients and all UDP/TCP server configurations
- IKEv2/strongSwan users and key material
- Stealth/Stunnel and WStunnel runtime configuration
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

## Disaster Recovery gate

From the panel, build **Disaster Recovery Backup** with a strong password. Validate the encrypted bundle on a second VPS before considering failover ready:

```bash
sudo makia-restore-portable /path/to/makia-portable-*.zip
sudo makia-restore-portable /path/to/makia-portable-*.zip --apply
sudo makia-doctor
sudo makia-uat-smoke
```

Required:
- migration manifest format v2 and SHA256 payload validation PASS;
- DB/.secret, SSH hashes, Xray/REALITY, WireGuard, OpenVPN PKI/configs, IKEv2, Stunnel/Stealth, WStunnel and TLS/Nginx state restore successfully when present;
- WireGuard/OpenVPN NAT/FORWARD rules are rebuilt for the **destination** VPS uplink interface;
- when client profiles use the preserved domain, changing that domain's DNS A/AAAA record to the new VPS is sufficient for cutover without changing keys/UUID/PKI;
- direct-IP profiles are identified as requiring reissue;
- raw WireGuard/OpenVPN/IKEv2 DNS records in Cloudflare are DNS-only.

## HTTPS prerequisite

IKEv2, Stealth and WStunnel TLS/WSS paths require a valid direct-domain Let's Encrypt certificate. Certbot installation belongs to the root installer/updater and must never run through the hardened web service.

## Stable gate

Do not promote to `0.26.0` Stable until:
1. upgrade UAT passes on the production-like VPS;
2. clean-install UAT passes on supported Ubuntu;
3. published modes pass real client import/authentication/handshake/DNS/traffic/reconnect checks;
4. Iran field testing is recorded for at least one mobile and one fixed/Wi-Fi path for each mode claimed as supported in Iran.
