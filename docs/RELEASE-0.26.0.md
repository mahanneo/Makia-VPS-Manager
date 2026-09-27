# Official 0.26.0

Makia VPS Manager 0.26.0 is the first official release after the 0.26 hardening cycle.

## Included

- Professional fixed sidebar and compact client directory with progressive detail drawer.
- Rebuilt login form with one focus surface, working FA/EN, Dark/Light and password visibility.
- Xray guided provisioning for VLESS, VMess, Trojan, Shadowsocks, Hysteria2, HTTP Proxy and SOCKS5.
- Xray compatibility filtering so invalid Transport/Security combinations are not offered by the guided UI.
- Fix for hardened-systemd Xray creation where runuser could fail with "cannot set user id: Operation not permitted".
- WireGuard peer management, QR/native export, handshake/traffic visibility, endpoint diagnostics and advanced server Port/MTU controls.
- OpenVPN PKI client management with UDP or TCP active transport, server Port, DNS, Keepalive, Redirect Gateway and Client-to-client controls.
- Transport-aware port collision checks.
- Visual connection guides for Xray, WireGuard, OpenVPN and SSH/NPV.
- Modern Admin Security center covering UFW, Fail2ban, 2FA, HTTPS, Self-Test, Audit and scoped API tokens.
- Simplified Support center; temporary Remote Support remains opt-in, audited and read-only by default.
- Backup, portable migration, updater rollback and host smoke gates.

## Verification

The release pipeline must pass:
- Python compile/import
- Unit and contract tests
- JavaScript and Bash syntax
- Browser smoke
- Xray Core guided protocol matrix
- Protected ZIP / QR / native delivery workflows
- UI navigation and security contracts

## Network compatibility boundary

0.26.0 is an official software release. It does not claim that every protocol works on every ISP or censorship regime.

Iran compatibility is tracked separately in `docs/IRAN-CONNECTIVITY-FIELD-TEST.md`. A protocol should only be marked Iran-verified after real client testing from inside Iran, including handshake, DNS, traffic and reconnect.

## Upgrade from older installs

```bash
sudo makia-upgrade
sudo makia-doctor
sudo makia-uat-smoke
```

After upgrade, verify that the Login footer and panel show `v0.26.0`. If an older version remains visible, perform a hard refresh and confirm `/opt/makia-vps-manager/VERSION` contains `0.26.0`.

