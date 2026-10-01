<p align="center">
  <img src="docs/assets/makia-brand.png" width="128" alt="لوگوی Makia VPS Manager">
</p>

<h1 align="center">Makia VPS Manager</h1>

<p align="center">
  پنل تحت وب مدیریت VPS و دسترسی برای Ubuntu
</p>

<p align="center">
  <strong>نسخه ۱.۴.۰</strong> · SSH/NPV · Xray/V2Ray · WireGuard · OpenVPN · Outline
</p>

**[راهنمای اتصال کاربران](docs/CLIENT-GUIDE-FA.md)** · **[گزارش UAT نسخه ۱.۴](docs/UAT-1.4.0.md)**

---

## Makia چیست؟

Makia یک پنل Self-hosted برای مدیریت دسترسی‌ها و عملیات VPS است. هر پروتکل Runtime مستقل خودش را دارد، اما ساخت کاربر، تحویل کانفیگ، تمدید، عیب‌یابی، بکاپ، بازیابی و Multi-VPS در یک رابط یکپارچه مدیریت می‌شوند.

Makia داخل مرورگر **Shell روت عمومی** ارائه نمی‌کند. نصب Packageها و عملیات حساس Host فقط از مسیرهای صریح و محدود Root انجام می‌شوند.

## Presetهای شبکه ایران

در **Xray Inbound Center** یک کتابخانه Preset آماده اضافه شده تا به‌جای تنظیم دستی ده‌ها فیلد، ساختار معتبر را انتخاب کنید:

- **Recommended:** VLESS + REALITY + RAW/Vision
- **Alternative:** VLESS + gRPC + REALITY
- **Alternative:** VLESS + WebSocket + TLS
- **Alternative:** VLESS + HTTPUpgrade + TLS
- **Alternative:** Trojan + gRPC + TLS
- **Alternative / UDP:** Hysteria2 + TLS
- **Compatibility:** VMess + WebSocket + TLS
- **Experimental:** VLESS + XHTTP + REALITY

این Presetها **تضمین اتصال روی همه اپراتورها نیستند**. وضعیت فیلترینگ، ISP، دیتاسنتر و Client تغییر می‌کند. هر Preset فقط ترکیبی را اعمال می‌کند که Core فعلی Makia واقعاً پشتیبانی می‌کند و قبل از Commit توسط خود Xray Validate می‌شود. XHTTP روی Core فعلی به‌دلیل گزارش‌های جدید Compatibility/Resource در حالت Experimental باقی مانده است.

## پروتکل‌ها

| پروتکل | ساخت | تحویل به کاربر | مدیریت |
|---|---|---|---|
| SSH / NPV | ✅ | NPV، QR، صفحه اختصاصی | انقضا، Session/Device، Lock، Disconnect |
| Xray / V2Ray | ✅ | Share Link، QR، Subscription، Portal | حجم، انقضا، IP Policy، تمدید، Diagnostics |
| WireGuard | ✅ | Config، QR، Portal | فعال/غیرفعال، Reissue، Diagnostics |
| OpenVPN | ✅ | فایل OVPN، Portal | Revoke، Transport/Runtime Diagnostics |
| Outline | ✅ | Access Key واقعی `ss://`، QR، Portal، ZIP رمزدار | حجم، انقضا، تمدید، Reissue، Traffic، Diagnostics، حذف |

در Xray مسیرهای Guided برای پروتکل‌های پشتیبانی‌شده مانند VLESS، VMess، Trojan، Shadowsocks و Hysteria2 وجود دارند و تنظیمات Advanced قبل از Apply توسط Core اعتبارسنجی می‌شوند.

در WireGuard/OpenVPN، Makia قابلیتی را که Engine واقعاً enforce نمی‌کند به‌صورت Fake نمایش نمی‌دهد.

## Makia Client نسخه ۱.۴

کاربر نهایی یک آدرس HTTPS واحد از Makia می‌گیرد و با نام کاربری و رمز خودش وارد می‌شود. داخل Client Portal فقط حجم، تاریخ انقضا، وضعیت دستگاه‌ها و دسترسی‌های همان حساب نمایش داده می‌شود.

- **Windows:** اتصال مستقیم با Makia Client Connector.
- **Android:** Makia Android Connector برای پروتکل‌های پشتیبانی‌شده از Android VpnService استفاده می‌کند؛ OpenVPN در نسخه ۱.۴ همچنان Import-based است.
- **iPhone / iPad:** کاربر در Safari وارد می‌شود، Makia را با Add to Home Screen نصب می‌کند و از جریان Open/Import متناسب با iOS استفاده می‌کند. VPN Native داخل خود Makia در iOS تا زمان ساخت Apple-signed با Network Extension و UAT روی دستگاه واقعی ادعا نمی‌شود.
- Ticket اتصال Native یک‌بارمصرف، وابسته به Device و کوتاه‌عمر است و Secret اصلی داخل لینک `makia://` قرار نمی‌گیرد.
- Client Portal تا پایان UAT/Canary واقعی روی Host به‌صورت پیش‌فرض غیرفعال می‌ماند.

## قابلیت‌های مدیریتی

- Plans / Templates
- Bulk Renew / Enable / Disable در موارد قابل enforce
- Expiry Center
- Notifications Center
- بکاپ زمان‌بندی‌شده و رمزدار
- Remote Backup با SCP و Host-key verification
- Full Migration / Disaster Recovery
- Cloudflare DNS Cutover
- Telegram Bot / Notifications
- Diagnostics برای هر Access
- Multi-VPS Dashboard
- Client Portal / PWA احراز هویت‌شده برای کاربران نهایی
- QR / Config / Protected ZIP
- Audit Log
- Host Diagnostics

## نصب سریع

روی **Ubuntu 22.04 یا Ubuntu 24.04 تمیز** و با دسترسی Root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/install.sh)
```

Installer یک رمز اولیه تصادفی برای مدیر نمایش می‌دهد. بعد از اولین ورود آن را عوض کنید.

### بروزرسانی

```bash
sudo makia-upgrade
```

برای نصب‌های بسیار قدیمی که هنوز Bootstrap Updater ندارند:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/upgrade.sh)
```

## Outline

Outline عمداً از داخل Web Service Hardened نصب نمی‌شود.

اگر Docker هنوز آماده نیست:

```bash
sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade
```

بعد وارد **Outline → Setup** شوید و دستور Pin‌شده‌ای که پنل نمایش می‌دهد را روی SSH سرور اجرا کنید.

اگر Hostname مربوط به Outline در Cloudflare است، رکورد باید **DNS Only** باشد؛ Orange Cloud برای ترافیک خام Outline/Shadowsocks مناسب نیست.

چرخه کاربر Managed Outline:

```text
ساخت Key واقعی روی Outline Server
        ↓
اعتبارسنجی ss://
        ↓
Name + Quota
        ↓
ذخیره Artifact رمزدار
        ↓
QR / Client Portal / Protected ZIP
        ↓
Renew / Reissue / Revoke
```

اگر ساخت Key در میانه کار Fail شود، Makia Key نیمه‌کاره را حذف می‌کند.

## بکاپ و Disaster Recovery

هدف Full Migration این است که در صورت فیلترشدن، از دسترس خارج‌شدن یا تعویض VPS:

1. Backup رمزدار و Verified داشته باشید؛
2. آن را روی VPS جدید Restore کنید؛
3. سرویس‌ها و Runtimeها را Verify کنید؛
4. A Record/Cloudflare را به IP جدید Cutover کنید.

Restore قبل از Mutation محتویات Backup را بررسی می‌کند. State مربوط به Outline نیز در صورت وجود داخل Migration قرار می‌گیرد.

## تست سلامت

بعد از نصب یا Update:

```bash
sudo makia-doctor
sudo makia-uat-smoke
```

دستورات مفید:

```bash
sudo makia-backup
sudo makia-uninstall
```

برای خطای 502:

```bash
sudo systemctl status makia-vps-manager --no-pager -l
sudo journalctl -u makia-vps-manager -n 120 --no-pager
curl -v http://127.0.0.1:8787/healthz
```

## امنیت

- Session احراز هویت‌شده برای مدیر؛
- کنترل Mutation و Same-origin؛
- امکان محدودسازی IP/CIDR مدیریت؛
- Login rate limiting و Fail2ban؛
- Artifactهای رمزدار؛
- عدم وجود Generic Root Shell در Browser؛
- Redaction توکن‌ها از Errorها؛
- DNS Only برای Cutover سرویس‌های Raw؛
- Strict host-key checking برای SCP Backup؛
- Permission محدود برای فایل Secret و دیتابیس؛
- Audit برای عملیات مدیریتی.

لینک Client Portal، Access Key و Configها را مانند رمز عبور نگهداری کنید.

## Gate نسخه v1

CI نسخه ۱ شامل Python compile/import، Pytest، DB/Migration، JavaScript syntax، Playwright، بررسی Action→Handler، بررسی API→Route، Duplicate Route، تست‌های ساخت/حذف/تمدید Outline، جداسازی Xray/Outline، Backup/Restore، Cloudflare/Telegram/Outline Mock، Xray Core و Bash/systemd/security contracts است.

موارد وابسته به محیط مانند Firewall/NAT، DNS propagation، Docker/Shadowbox واقعی، اتصال Client واقعی و SCP واقعی باید روی Host مقصد تست شوند.

جزئیات در **[docs/UAT-1.4.0.md](docs/UAT-1.4.0.md)** ثبت شده است.

## مجوز

GPL-3.0-or-later. اجزای Third-party تابع مجوز و Attribution خودشان هستند.
