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
