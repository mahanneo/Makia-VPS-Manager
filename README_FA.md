## نسخه v0.17.0-rc1 — WireGuard Runtime Repair و تست IP/Domain

در این نسخه تشخیص و تعمیر WireGuard عمیق‌تر شده است. پنل وضعیت Service، Interface، UDP Listener، IP Forwarding، FORWARD Rule، NAT و Handshake Peerها را بررسی می‌کند و گزینه **Repair Runtime** دارد.

همچنین در Protocol Hub گزینه **IP / Domain Readiness** اضافه شده تا یک IP یا دامنه را برای SSH، Xray، WireGuard و OpenVPN از نظر Runtime، DNS و Listener بررسی کنید.

Updater نیز WireGuard موجود را قبل از UAT نهایی بررسی می‌کند و در صورت نیاز با Backup تعمیر می‌کند.

> توجه: تست داخلی و CI جای تست اتصال واقعی از یک موبایل/کامپیوتر خارج از VPS را نمی‌گیرد. برای Stable باید IP و Domain واقعی روی Client خارجی تست شوند.

راهنمای UAT: [UAT v0.17.0-rc1](docs/UAT-0.17.0-RC1.md)

# راهنمای فارسی Makia VPS Manager

**Makia VPS Manager** یک پنل مدیریت VPS برای مدیریت دسترسی‌های SSH، Xray، WireGuard و OpenVPN، تحویل امن کانفیگ، دامنه/HTTPS، بکاپ و مهاجرت سرور است.

> وضعیت فعلی پروژه Release Candidate است. قبل از استفاده Production، UAT واقعی روی VPS مقصد انجام شود.

## نسخه v0.16.0-rc1 — Owner Control Center و Remote Support امن

از این نسخه، مدیریت تجاری Makia از یک **Owner Control Center جدا** انجام می‌شود. این سرویس روی VPS مشتری نصب نمی‌شود و Private Key صدور License فقط روی سرور مالک باقی می‌ماند.

قابلیت‌های Owner Control Center:
- ثبت مشتری و Installation ID
- صدور Full یا Custom License
- تمدید بدون نیاز به Paste مجدد Code توسط مشتری
- Revoke واقعی از طریق Signed Online Lease
- Inbox مرکزی Ticketها
- Audit عملیات مالک
- Password + TOTP برای ورود Owner

برای مشتری، Remote Support نیز فقط با رضایت مدیر محلی فعال می‌شود. مدیر از License & Support یک Code یک‌بارمصرف ۱۵ تا ۱۲۰ دقیقه‌ای می‌سازد و Scope را Read-only یا Operator تعیین می‌کند. هیچ Master Password یا Backdoor دائمی وجود ندارد.

حتی Remote Support Operator اجازه تغییر Password/2FA مدیر، API Token، حذف License، Export Credential یا Portable Backup را ندارد.

راهنماها:
- [Owner Control Center](docs/OWNER-CONTROL-CENTER-FA.md)
- [امنیت Remote Support](docs/REMOTE-SUPPORT-SECURITY-FA.md)

## نسخه v0.14.0-rc1 — Glass Aurora و OpenVPN با دامنه

ظاهر پیش‌فرض پنل به **Glass Aurora** تغییر کرده است: سایدبار و Topbar شیشه‌ای، کارت‌های شفاف آبی/بنفش، Dashboard جدید با وضعیت سرویس‌ها، چهار کارت خلاصه، حلقه‌های CPU/RAM/Disk، نمودار واقعی شبکه و نمایش Responsive. نصب‌های قبلی در اولین اجرای این Release یک‌بار به Glass منتقل می‌شوند و Themeهای قبلی همچنان از Settings قابل انتخاب‌اند.

### OpenVPN با دامنه

HTTPS پنل و TLS داخلی OpenVPN یک چیز نیستند. HTTPS پنل توسط Nginx/Let's Encrypt مدیریت می‌شود، اما OpenVPN از CA و Certificateهای EasyRSA خودش استفاده می‌کند. دامنه در فایل OVPN فقط Endpoint سرور است.

برای Domain Endpoint:
- رکورد **A** باید مستقیماً به IPv4 همان VPS اشاره کند.
- رکورد VPN پشت Proxy/CDN معمولی مثل Cloudflare در حالت Proxied نباشد؛ برای OpenVPN خام از **DNS-only** استفاده کنید.
- Profileهای جدید و Exportهای مجدد با `udp4` یا `tcp4-client` ساخته می‌شوند تا AAAA اشتباه باعث رفتن Client به IPv6 نشود.
- Profileهای قدیمی هنگام Export با Domain فعلی پنل دوباره Render می‌شوند؛ Certificate کاربر Reissue نمی‌شود.
- از **Settings → WG / OpenVPN → Domain Diagnostics** می‌توانید DNS، A/AAAA، Listener، systemd و Port را بررسی کنید.
- **Normalize IPv4 runtime** از `server.conf` Backup می‌گیرد، OpenVPN را روی `udp4` یا `tcp4-server` نرمال می‌کند و در Failure Rollback می‌کند.
- OpenVPN روی **TCP/443** با Nginx HTTPS روی همان IP و Port تداخل دارد، مگر Port-sharing/IP جدا داشته باشید. **UDP/443** می‌تواند هم‌زمان با HTTPS/TCP 443 استفاده شود.

## نصب

روی Ubuntu 22.04 یا 24.04 تازه:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/install.sh)
```

پس از نصب، رمز اولیه مدیر در ترمینال نمایش داده می‌شود. بعد از اولین ورود رمز مدیر را تغییر دهید و در صورت امکان 2FA را فعال کنید.

## بروزرسانی

```bash
sudo makia-upgrade
sudo makia-doctor
sudo makia-uat-smoke
```

Updater قبل از تغییر نسخه Backup می‌گیرد و در Failure مسیر Rollback دارد. تنظیم فعال Nginx/Certbot در Update حفظ می‌شود.

## دامنه و HTTPS

از **Settings → Domain / Nginx / HTTPS**:

1. دامنه را روی IP سرور تنظیم کنید.
2. دامنه را در پنل Apply کنید.
3. ایمیل معتبر وارد کنید.
4. گواهی Let's Encrypt را صادر کنید.
5. پنل را از طریق `https://your-domain.example` باز کنید.

برای مهاجرت VPS بهتر است Clientها با **دامنه ثابت** ساخته شوند، نه IP مستقیم. در زمان انتقال سرور فقط DNS دامنه به IP جدید تغییر می‌کند.

## Xray

### ساخت سریع

از **Access Center → Xray** می‌توان برای VLESS، VMess، Trojan، Shadowsocks و Hysteria2 پروفایل ساخت. Transportها و Securityهای قابل پشتیبانی از طریق Wizard کنترل‌شده ارائه می‌شوند.

### Full Xray Core

از **Settings → Xray Defaults → Advanced JSON** می‌توانید Config کامل Xray Core را ویرایش کنید. قبل از Apply:

- JSON بررسی می‌شود؛
- خود Xray Core کانفیگ را Validate می‌کند؛
- از Config قبلی Backup گرفته می‌شود؛
- پس از Apply سرویس Restart می‌شود؛
- در Failure، Rollback انجام می‌شود.

### اگر Xray روی Failed رفت

در **Services** یا **Protocol Hub** روی **Diagnose** بزنید. Makia موارد زیر را بررسی می‌کند:

- نسخه Xray Core؛
- اعتبار کانفیگ با root؛
- اعتبار کانفیگ با همان User واقعی systemd؛
- Permission فایل Config؛
- دسترسی Xray به Certificate/Private Key؛
- خطاهای اخیر `journalctl -u xray`.

دکمه **Repair & Restart** قبل از تغییر از Config Backup می‌گیرد، Permissionها و TLS runtime files را اصلاح می‌کند، با همان User سرویس Validate می‌کند و سپس Xray را Restart می‌کند.

نسخه Xray که این Release در CI با آن اعتبارسنجی می‌شود: **26.3.27**.

## WireGuard

Default سازگاری فعلی:

- UDP Port: `443`
- MTU: `1280`
- PersistentKeepalive: `15`
- AllowedIPs: `0.0.0.0/0`

این تنظیمات مشکلات رایج NAT و MTU را کاهش می‌دهند، ولی در شبکه‌ای که خود WireGuard در سطح پروتکل مسدود شده باشد تضمین عبور وجود ندارد. در آن شرایط Xray/REALITY را نیز تست کنید.

## راهنمای کاربران

یک صفحه عمومی بدون نیاز به Login وجود دارد:

```text
https://YOUR-PANEL-DOMAIN/help/connect
```

لینک مستقیم بخش‌ها:

- Xray: `/help/connect#xray`
- WireGuard: `/help/connect#wireguard`
- OpenVPN: `/help/connect#openvpn`
- SSH / NPV: `/help/connect#ssh`

از داخل پنل نیز بخش **راهنمای اتصال** وجود دارد و می‌توانید لینک مناسب را Copy و برای کاربر ارسال کنید.

Protected ZIPهای تحویل نیز فایل `connection-guide-fa.txt` دارند.

راهنمای کامل کاربران: [docs/CLIENT-GUIDE-FA.md](docs/CLIENT-GUIDE-FA.md)

## SSH / NPV Tunnel

Makia برای SSH می‌تواند:

- OpenSSH config
- Credentials
- لینک `npvt-ssh://`
- QR سازگار
- Protected ZIP

تولید کند.

فرمت proprietary و رمزگذاری‌شده `.npv4` بدون مشخصات رسمی جعل یا تولید نمی‌شود.

## Backup و مهاجرت VPS

دو مدل Backup وجود دارد:

### Local Backup

برای Rollback و بازیابی روی همان Host.

### Portable Migration

از **Backups → Portable Migration** یک ZIP رمزگذاری‌شده AES-256 ساخته می‌شود که در صورت وجود شامل این موارد است:

- SQLite و `.secret`
- Xray config و REALITY keys
- WireGuard keys/peers
- OpenVPN PKI
- Nginx
- Let's Encrypt
- SSH password hashes کاربران مدیریت‌شده

روی VPS مقصد ابتدا همان نسخه Makia را نصب کنید و سپس:

```bash
sudo makia-restore-portable /path/to/bundle.zip
sudo makia-restore-portable /path/to/bundle.zip --apply
sudo makia-doctor
sudo makia-uat-smoke
```

بعد از PASS شدن مقصد، DNS دامنه را به IP جدید تغییر دهید.

هدف Migration، **حفظ Credential کاربران** است؛ DNS propagation ممکن است یک بازه کوتاه Cutover ایجاد کند.

## عیب‌یابی

دستورات اصلی:

```bash
sudo makia-doctor
sudo makia-uat-smoke
sudo systemctl status xray --no-pager
sudo journalctl -u xray -n 80 --no-pager
sudo nginx -t
```

در حالت معمول ابتدا از Diagnostics داخل پنل استفاده کنید، چون تست Xray را هم با root و هم با User واقعی systemd اجرا می‌کند.

## امنیت

- پنل عمومی را فقط با HTTPS استفاده کنید.
- 2FA مدیر را فعال کنید.
- Protected ZIP و رمز آن را در دو پیام جدا ارسال کنید.
- QR و Share Link حاوی Credential هستند.
- فایل OVPN، WireGuard config و SSH Credentials را عمومی نکنید.
- Portable Migration Bundle شامل Secretهای حساس است؛ پس از انتقال امن، نسخه‌های اضافی را حذف کنید.

## تست و Release Gate

هر Release Candidate باید حداقل این Gateها را پاس کند:

- Python compile/import
- Unit tests
- JavaScript/Bash syntax
- Browser Smoke با Playwright
- Xray Core 26.3.27 validation
- Protected ZIP
- QR/Share
- تمام Sidebar views
- Settings contracts
- UAT واقعی روی VPS برای نسخه Stable
