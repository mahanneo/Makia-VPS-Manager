<p align="center">
  <img src="docs/assets/makia-brand.png" width="128" alt="Makia VPS Manager logo">
</p>

<h1 align="center">Makia VPS Manager</h1>

<p align="center">
  Web-first VPS access management for Ubuntu · SSH/NPV · Xray/V2Ray · WireGuard · OpenVPN · Outline
</p>

<p align="center">
  <strong>Version 1.1.0</strong> · Persian/English · Responsive · Backup/DR · Multi-VPS · Client Portal
</p>

**[راهنمای فارسی](README_FA.md)** · **[راهنمای اتصال کاربران](docs/CLIENT-GUIDE-FA.md)** · **[v1 UAT](docs/UAT-1.1.0.md)**

---

## What Makia is

Makia VPS Manager is a self-hosted control panel for managing access services and operational recovery on Ubuntu VPS hosts. It keeps protocol-specific runtime operations separate while presenting users, delivery artifacts, expiry, diagnostics, backup and disaster-recovery workflows through one UI.

Makia does **not** expose a generic root shell in the browser. Operations that require package installation or host-level privilege remain explicit root-shell steps.

## Iran Network Inbound Presets

The Xray Inbound Center includes selectable, Core-validated starting profiles for networks where censorship or path quality changes frequently:

- **Recommended:** VLESS + REALITY + RAW/Vision
- **Alternative:** VLESS + gRPC + REALITY
- **Alternative:** VLESS + WebSocket + TLS
- **Alternative:** VLESS + HTTPUpgrade + TLS
- **Alternative:** Trojan + gRPC + TLS
- **Alternative / UDP:** Hysteria2 + TLS
- **Compatibility:** VMess + WebSocket + TLS
- **Experimental:** VLESS + XHTTP + REALITY

These are **starting presets, not a connectivity guarantee**. ISP filtering, mobile networks, datacenter policy, client implementation and protocol fingerprints change over time. Makia therefore keeps XHTTP experimental on the pinned 26.3.27 Core and validates every selectable preset with the actual Xray binary in CI.

## Protocol support

| Protocol | Provisioning | Delivery | Policy / operations |
|---|---|---|---|
| SSH / NPV | ✅ | NPV link, QR, client page | expiry, sessions/devices, lock, disconnect |
| Xray / V2Ray | ✅ | share link, QR, subscription, client page | quota, expiry, IP policy, renew, diagnostics |
| WireGuard | ✅ | native config, QR, client page | enable/disable, reissue, diagnostics |
| OpenVPN | ✅ | .ovpn download, client page | revoke, transport/runtime diagnostics |
| Outline | ✅ | real `ss://` key, QR, client page, protected ZIP | quota, expiry, renew/reissue, traffic, diagnostics, revoke |

Xray guided workflows include VLESS, VMess, Trojan, Shadowsocks and Hysteria2 where supported by the bundled Xray Core/runtime contract. Advanced Xray configuration is validated before apply and uses rollback on failure.

WireGuard/OpenVPN do not claim per-client quota/expiry where the underlying engine does not enforce it. Makia prefers an explicit unavailable state over a fake control.

## Operations Suite

- Plans / Templates
- Bulk renew / enable / disable where enforceable
- Expiry Center
- Notifications Center
- Scheduled encrypted backup
- Remote SCP backup with strict host-key checking
- Full Migration / Disaster Recovery
- Cloudflare DNS cutover (**DNS Only** for raw VPN/SSH services)
- Telegram status / expiry / backup integration
- Per-access Diagnostics Center
- Multi-VPS node telemetry
- Public, tokenized Client Portal
- QR / native config / protected ZIP delivery
- Audit log and host diagnostics

## Quick install

Use a **fresh Ubuntu 22.04 or 24.04 VPS** and run as root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/install.sh)
```

The installer prints a unique administrator bootstrap password. Change it after first login.

### Update an existing installation

```bash
sudo makia-upgrade
```

For very old installations that do not yet have the bootstrap updater:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/upgrade.sh)
```

## Outline

Outline is installed outside the hardened web service. If Docker is not prepared yet, run:

```bash
sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade
```

Then open **Outline → Setup** and run the pinned installer command shown by Makia.

For an Outline hostname behind Cloudflare DNS, the record must be **DNS Only**. Do not place raw Outline/Shadowsocks traffic behind the normal orange-cloud HTTP proxy.

A managed Outline client follows this lifecycle:

```text
Create real server key
        ↓
Validate ss:// credential
        ↓
Apply name + quota
        ↓
Store encrypted Makia artifact
        ↓
QR / Client Portal / Protected ZIP
        ↓
Renew / Reissue / Revoke
```

If a partial create fails, Makia removes the newly created runtime key instead of leaving an orphan credential.

## Backup & Disaster Recovery

Full Migration backups are encrypted and designed for replacement-VPS recovery. The intended flow is:

1. create/verify Full Migration backup;
2. copy locally or through configured SCP;
3. install Makia on the replacement VPS;
4. restore the migration bundle;
5. run runtime/host verification;
6. update the DNS A record / Cloudflare cutover to the new public IP.

Restore preflight validates the bundle before mutation and keeps rollback behavior for supported state. Outline runtime state is included when present.

## Diagnostics

After install/update:

```bash
sudo makia-doctor
sudo makia-uat-smoke
```

Useful commands:

```bash
sudo makia-backup
sudo makia-uninstall
```

If the panel returns 502:

```bash
sudo systemctl status makia-vps-manager --no-pager -l
sudo journalctl -u makia-vps-manager -n 120 --no-pager
curl -v http://127.0.0.1:8787/healthz
```

## Security model

- authenticated admin sessions with mutation request checks;
- optional admin-network CIDR restriction;
- login-rate limiting and Fail2ban integration;
- encrypted access artifacts and protected ZIP exports;
- no browser-accessible generic root command endpoint;
- secret/token redaction in integration errors;
- Cloudflare raw access records forced to DNS-only workflows;
- strict SSH host-key verification for remote backup;
- owner-only local data/secret permissions;
- explicit audit events for management operations.

Treat Client Portal links and VPN credentials as secrets.

## v1 quality gate

The repository CI for v1 covers:

- Python compilation and application import/startup;
- full pytest suite and DB/migration compatibility;
- JavaScript syntax;
- browser/Playwright smoke;
- UI action → JavaScript handler contract;
- UI API → FastAPI route contract;
- duplicate-route detection;
- Outline create/delete/reissue/quota/renew regression tests;
- Xray/Outline engine isolation;
- backup/restore static and cryptographic safety;
- mocked Cloudflare / Telegram / Outline API flows;
- Xray Core smoke;
- Bash/systemd/packaging/security guards;
- official Makia brand asset presence.

Environment-dependent behavior still requires real-host verification: firewall/NAT, DNS propagation, external VPN clients, Docker/Shadowbox, SCP host trust and provider networking cannot be fully proven by GitHub Actions.

See **[docs/UAT-1.1.0.md](docs/UAT-1.1.0.md)**.

## Runtime layout

```text
/opt/makia-vps-manager/
├── app/
├── data/
├── .venv/
└── VERSION

/etc/systemd/system/
├── makia-vps-manager.service
├── makia-policy-enforcer.service
├── makia-metrics-sampler.service
├── makia-protocol-traffic.service
├── makia-scheduled-backup.service
├── makia-scheduled-backup.timer
├── makia-ops-monitor.service
└── makia-ops-monitor.timer
```

## License

GPL-3.0-or-later. Third-party software remains subject to its own license and attribution requirements.
