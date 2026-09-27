# UAT — Makia VPS Manager 0.21.0-rc1

این چک‌لیست برای ارتقا از 0.20.0 و نصب تازه روی Ubuntu 22.04/24.04 است. Stable فقط بعد از PASS شدن این ماتریس روی VPS واقعی قابل اعلام است.

## 1. Update / rollback

- قبل از Update یک Backup سالم بسازید.
- از 0.20.0 به 0.21.0-rc1 ارتقا دهید و صحت VERSION، backend health و login را بررسی کنید.
- `makia-doctor` و `makia-uat-smoke` باید PASS شوند.
- یک Rollback آزمایشی انجام دهید و سپس دوباره RC را نصب کنید؛ کاربران، artifacts، Xray config، WireGuard peers و OpenVPN PKI نباید از بین بروند.

## 2. Navigation / responsive UI

- Desktop: منوی جداگانه SSH / NPV، Xray / V2Ray، WireGuard، OpenVPN و Protocol Hub باید بدون صفحه خالی باز شوند.
- Mobile: Sidebar باز/بسته شود و هیچ Workspace اسکرول افقی ناخواسته ایجاد نکند.
- Ctrl/Cmd+K باید هر چهار Workspace پروتکل را پیدا کند.
- Dashboard باید لینک مستقیم هر Workspace را نشان دهد.

## 3. SSH / NPV

- ساخت حساب با PIN/Password، Expiry، Session Limit و Device/IP Limit.
- Edit، Lock/Unlock، Disconnect و Bulk expiry.
- Native/NPV/Protected delivery.
- تأیید کنید UI برای SSH ادعای Traffic Quota واقعی نمی‌کند.

## 4. Xray / V2Ray

برای VLESS، VMess، Trojan، Shadowsocks، Hysteria2 و در صورت استفاده HTTP/SOCKS:

- ساخت Client از Xray Workspace.
- Quota و Expiry و Reset cycle فقط جایی که Accounting supported است.
- Manual traffic reset.
- Enable/Disable و بازگشت صحیح Engine config.
- IP/device visibility و رفتار Coreهای فاقد Online-IP API.
- QR، share، subscription و protected package.
- Advanced JSON: validate، backup، apply و rollback.
- Xray diagnostics و restart/repair.

## 5. WireGuard

- Bootstrap wg0، ساخت Peer با Domain و IP.
- Enable/Disable ماندگار Peer.
- RX/TX و Last Handshake.
- QR، native .conf و protected delivery.
- Runtime diagnostics: listener، forwarding، NAT و endpoint.

## 6. OpenVPN

- Bootstrap با UDP و یک بار جداگانه با TCP روی VPS آزمایشی.
- ساخت Client و import فایل OVPN روی دستگاه واقعی.
- Revoke client و تأیید CRL.
- Domain diagnostics و repair/rollback.
- تأیید کنید UI Quota/Reset per-client جعلی نشان نمی‌دهد.

## 7. Port collision matrix

این سناریوها الزامی‌اند:

| سناریو | نتیجه مورد انتظار |
|---|---|
| Nginx TCP/443 + WireGuard UDP/443 | PASS؛ هم‌زیستی مجاز |
| WireGuard UDP/443 + OpenVPN UDP/443 | BLOCK قبل از bootstrap دوم |
| Nginx TCP/443 + OpenVPN TCP/443 | BLOCK |
| Listener UDP/8443 + Xray TCP/8443 | PASS |
| Listener TCP/8443 + Xray TCP/8443 | BLOCK |
| Xray mKCP/UDP روی Port اشغال UDP | BLOCK |
| Xray tunnel TCP+UDP روی Portی که یکی از Transportها اشغال است | BLOCK |

بعد از هر BLOCK، سرویس قبلی باید بدون Restart ناخواسته و بدون قطعی باقی بماند.

## 8. External connectivity

از یک موبایل یا کامپیوتر خارج از VPS، حداقل یک Client واقعی برای SSH، Xray، WireGuard و OpenVPN تست شود. CI یا Listener داخلی جای اتصال واقعی اینترنت را نمی‌گیرد.

## 9. Stable gate

Stable زمانی مجاز است که:
- CI کامل PASS باشد؛
- Update و Rollback واقعی PASS باشند؛
- ماتریس Port بدون Regression PASS باشد؛
- External client tests برای چهار Workspace PASS باشند؛
- هیچ داده یا Credential موجود در ارتقا از 0.20.0 از بین نرود.
