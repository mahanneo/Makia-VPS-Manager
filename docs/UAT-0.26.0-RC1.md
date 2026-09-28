# Makia VPS Manager 0.26.0-rc1 — Finalization UAT

این Release Candidate برای جمع‌بندی ایرادهای گزارش‌شده روی Host واقعی و آماده‌سازی انتشار عمومی ساخته شده است. نسخه‌ای که در اسکرین‌شات Host دیده شد `0.24.0-rc1` بود؛ بنابراین UAT باید **Upgrade مستقیم 0.24.0-rc1 → 0.26.0-rc1** را هم پوشش دهد.

> این سند Stable gate است. CI یا تست داخل VPS به‌تنهایی اثبات نمی‌کند که یک پروتکل در همه شبکه‌های ایران قابل اتصال است.

## 1. Upgrade from 0.24.0-rc1

روی Host فعلی:

```bash
sudo makia-upgrade
sudo makia-doctor
sudo makia-uat-smoke
```

انتظار:
- `VERSION` برابر `0.26.0-rc1`.
- کاربران، PKI، WireGuard keys، Xray config و تنظیمات قبلی حفظ شوند.
- Backend، Nginx، Xray، WireGuard، OpenVPN، Fail2ban و سرویس‌های Makia فعال بمانند.
- Service Worker cache باید به `makia-shell-v0260rc1` تغییر کند.
- بعد از Upgrade یک Hard Refresh انجام شود.
- در صورت شکست Upgrade یا runtime، rollback موجود باید قابل استفاده باشد.

## 2. Login regression

Desktop و Mobile:

- با کلیک روی Username یا Password فقط **یک Focus Surface** دیده شود؛ Input نباید کادر دوم داخل کادر اصلی بسازد.
- Password Show/Hide کار کند.
- کلید FA/EN واقعاً متن، `lang` و `dir` را تغییر دهد.
- Theme toggle واقعاً Dark/Light را تغییر دهد و بعد از Reload حفظ شود.
- Autofill مرورگر نباید Border/Background دوم بسازد.
- Login با رمز درست موفق و با رمز غلط ناموفق باشد.
- در صورت تنظیم Domain عمومی، HTTPS باید فعال شود؛ استفاده عمومی روی HTTP/IP هشدار امنیتی دارد.
- `makia-uat-smoke` برای Domain تنظیم‌شده باید Certificate، Listener واقعی TCP/443 و درخواست `https://DOMAIN/healthz` را PASS کند.
- Certbot و `python3-certbot-nginx` باید توسط Installer/Updater روت نصب شوند؛ Backend وب نباید `apt-get` اجرا کند. خطاهای `seteuid 42` / `setresuid: Operation not permitted` در مسیر HTTPS Regression محسوب می‌شوند.

## 3. Users / Access Center

پس از Upgrade نباید UI قدیمی v0.24 دیده شود.

انتظار:
- صفحه Users از `.pro-user-row` استفاده کند.
- Row فقط Identity، Protocol، Status، Usage/Expiry و More را نشان دهد.
- QR / Native / Protected ZIP / Manage / Revoke داخل Detail Drawer باشند.
- Filterهای Xray / SSH / WireGuard / OpenVPN کار کنند.
- Search کار کند.
- Drawer روی Sidebar قرار گیرد و Sidebar کلیک‌های Drawer را Block نکند.

## 4. Create Access

- Provisioning به‌صورت Right Drawer باز شود.
- 4 Protocol Card با Icon مستقل: SSH، Xray، WireGuard، OpenVPN.
- Advanced fields فقط وقتی لازم است نمایش داده شوند.
- Review قبل از Commit نمایش داده شود.
- Protected package PIN قابل Generate باشد.

## 5. Xray root-cause regression

ایراد گزارش‌شده:
`runuser: cannot set user id: Operation not permitted`

این خطا نباید از Web Service برگردد.

الزام‌ها:
- systemd hardening مانند `NoNewPrivileges=true` نباید برای رفع خطا حذف شود.
- Root Xray syntax validation باید انجام شود.
- وقتی Makia تحت NoNewPrivileges اجرا می‌شود، Service-user readability باید بدون setuid/runuser ممنوعه Validate شود.
- اگر runuser فقط به دلیل EPERM/setuid محدود شد، static permission validation اجرا شود.
- سایر خطاهای واقعی Xray نباید swallow شوند.

## 6. Xray guided matrix

نسخه Core مورد انتظار: Xray `26.3.27`.

UI فقط ترکیب‌های Guided معتبر را ارائه کند و Backend هم همان Matrix را enforce کند:

| Protocol | Guided transports | Security |
|---|---|---|
| VLESS | TCP/RAW, WS, gRPC, HTTPUpgrade, XHTTP, mKCP | REALITY / TLS / None |
| VMess | TCP/RAW, WS, gRPC, HTTPUpgrade, XHTTP, mKCP | None / TLS |
| Trojan | TCP/RAW, WS, gRPC, HTTPUpgrade, XHTTP | TLS |
| Shadowsocks | TCP | None |
| Hysteria2 | Hysteria/UDP | TLS |
| HTTP | TCP | None |
| SOCKS5 | TCP | None |

Checks:
- invalid REALITY combinations cannot be selected/committed.
- Trojan/Hysteria2 without required Domain/TLS material fail early with clear prerequisite instead of a low-level error.
- Xray Core smoke validates generated configs.
- At least VLESS RAW/REALITY must execute a real CI client handshake + routed traffic.
- Advanced JSON remains available for features outside Guided mode and must validate before Apply.

## 7. OpenVPN

OpenVPN must not be presented as UDP-only.

Checks:
- Workspace shows real live transport and port.
- Server Settings exposes both UDP and TCP.
- Change UDP → TCP on a free port:
  - backup existing config
  - rewrite proto/port
  - restart service
  - listener appears on requested transport
  - UFW rule is updated when UFW is active
  - on failure old config is restored
- Change TCP → UDP similarly.
- DNS push values editable.
- Keepalive ping/timeout editable.
- Redirect Gateway toggle works.
- Client-to-client toggle works and defaults conservatively.
- Existing PKI/clients are preserved.
- Re-downloaded `.ovpn` profile uses **current** live transport/port.
- TCP/443 collision with HTTPS on same IP is rejected/warned; UDP/443 is transport-distinct.

## 8. WireGuard

Checks:
- Peer create/delete.
- Enable/disable persists.
- Native `.conf` and QR export.
- Last handshake visible.
- RX/TX traffic visible.
- Server UDP port, DNS, MTU, Persistent Keepalive, AllowedIPs and Tunnel CIDR visible/configurable through VPN settings.
- Diagnostics verifies listener, ip_forward, FORWARD and NAT.
- No fake per-peer expiry/firewall feature is shown unless real enforcement exists.

## 9. Support

Expected primary Support page:
- system health
- Xray/WireGuard/OpenVPN runtime cards
- Connectivity Lab
- Visual Guides
- Update Center
- GitHub Issues
- configured Telegram channel only when configured

The following should be progressively disclosed, not dominate the page:
- Send support report
- Temporary Remote Support
- Recent reports

Remote Support must remain one-time, time-limited and scoped.

## 10. Visual guides

`/help/connect` must include visual step diagrams for:
- Xray
- WireGuard
- OpenVPN
- SSH/NPV

Each section should explain Import/QR/File and Connect steps. User-provided credentials must never be embedded in public documentation.

## 11. Admin Security

The Security tab should report:
- HTTPS readiness
- Admin 2FA
- UFW
- Fail2ban
- OpenSSH
- active API token exposure

Checks:
- HTTP/IP mode produces a visible security warning.
- Domain/HTTPS path is one click away.
- Session lifetime setting works.
- Password change enforces server-side policy.
- TOTP setup/disable works.
- API tokens remain scoped and revocable.
- Audit log remains accessible.

## 12. Clean-install public release gate

On fresh Ubuntu 22.04 and/or 24.04:
- install command completes.
- full protocol stack is provisioned.
- first login works.
- all automated host smoke gates pass.
- no license/activation dependency exists.
- README install/update/recovery instructions are sufficient for a third party.

## 13. Iran connectivity field gate

Use `docs/IRAN-CONNECTIVITY-FIELD-TEST.md`.

A real Client inside Iran must record results on at least:
- one Mobile ISP
- one Fixed/Wi-Fi path

For each published protocol/profile test:
- import
- handshake
- DNS
- browsing
- meaningful traffic
- reconnect

**Do not promote 0.26.0-rc1 to 0.26.0 Stable until this Host + Iran field gate is complete.**


## Disaster Recovery / Replacement VPS Gate

Before any Stable promotion, verify the **Full VPS Backup** workflow from the panel on a disposable replacement VPS:

1. Create and download the AES-encrypted Full VPS Migration bundle.
2. Install the same Makia version on a clean Ubuntu 22.04/24.04 VPS.
3. Copy the bundle and run:
   `sudo makia-restore-portable /root/makia-full-migration.zip --apply`
4. Confirm the restore validates DB, Xray, WireGuard, all OpenVPN server units, IKEv2, Stealth, WStunnel and local HTTPS where configured.
5. Confirm WireGuard and OpenVPN NAT rules were rebound to the **new VPS default interface**, while server keys, peers, CA and client certificates stayed unchanged.
6. Change the existing VPN hostname A/AAAA record to the replacement VPS and test old **domain-based** client profiles without reissuing credentials.
7. Raw WireGuard/OpenVPN/SSH records on Cloudflare must be **DNS only**. Do not use the orange-cloud HTTP proxy for these transports.
8. Any client profile that embeds the old server IP is **not** eligible for DNS-only cutover and must be re-exported with a domain endpoint before a real incident.

### Parallel OpenVPN / Stealth Gate

- Primary OpenVPN UDP users must remain connected when the parallel TCP fallback is enabled.
- `openvpn-server@makia-tcp` must use its own tunnel subnet and listener.
- Stealth must reuse the parallel TCP backend rather than changing the primary OpenVPN transport.
- Enabling Stealth must not mutate/revoke existing OpenVPN PKI or UDP client certificates.
- Port collisions with Nginx/HTTPS, WStunnel or other TCP listeners must be rejected.
