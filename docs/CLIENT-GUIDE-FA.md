# راهنمای اتصال کاربران Makia

این فایل برای ارسال به کاربران نهایی طراحی شده است. برای راهنمای عمومی روی خود پنل نیز می‌توان از آدرس زیر استفاده کرد:

```text
https://YOUR-PANEL-DOMAIN/help/connect
```

## Xray — VLESS / VMess / Trojan / Shadowsocks / Hysteria2

### روش QR

1. برنامه سازگار مانند v2rayNG، Hiddify یا NekoBox را باز کنید.
2. گزینه Scan QR / Add from QR را انتخاب کنید.
3. QR اتصال مستقیم را اسکن کنید.
4. Profile ساخته‌شده را انتخاب و Connect کنید.

### روش Copy Link

1. Share Link دریافتی را Copy کنید.
2. در Client گزینه Import from Clipboard را بزنید.
3. Profile Import شده را ذخیره و فعال کنید.

### روش Subscription

1. Subscription URL یا QR اشتراک را دریافت کنید.
2. در قسمت Subscription برنامه، Add را بزنید.
3. URL را Paste یا QR را Scan کنید.
4. Update / Refresh subscription را اجرا کنید.

**نکته:** در REALITY مقادیر SNI، Public Key، Short ID و Fingerprint را دستکاری نکنید.

## WireGuard

### Android / iPhone

1. برنامه رسمی WireGuard را باز کنید.
2. روی + بزنید.
3. Create from QR code یا Import from file را انتخاب کنید.
4. QR را اسکن یا فایل `.conf` را انتخاب کنید.
5. Tunnel را روشن کنید.

### Windows / macOS

1. WireGuard را اجرا کنید.
2. Import tunnel(s) from file را انتخاب کنید.
3. فایل `.conf` را Import کنید.
4. Activate را بزنید.

اگر روی یک شبکه وصل نشد، Wi-Fi و Mobile Data را جداگانه امتحان کنید. Endpoint، Port، MTU و DNS را بدون هماهنگی تغییر ندهید.

## OpenVPN

1. OpenVPN Connect را نصب و اجرا کنید.
2. Upload File / Import Profile را انتخاب کنید.
3. فایل `.ovpn` را Import کنید.
4. Add و سپس Connect را بزنید.

فایل OVPN اختصاصی است و نباید برای کاربر دیگری ارسال شود.

اگر Profile با دامنه ساخته شده است:
- رکورد A دامنه باید مستقیم به IP همان VPS اشاره کند.
- برای OpenVPN خام از رکورد Proxy/CDN معمولی مانند Cloudflare Proxied استفاده نکنید؛ رکورد VPN باید DNS-only باشد.
- Makia Profile را روی `udp4` یا `tcp4-client` می‌سازد تا رکورد AAAA اشتباه باعث انتخاب IPv6 نشود.
- SSL/HTTPS پنل با Certificate داخلی OpenVPN یکی نیست؛ OpenVPN از CA/PKI خودش استفاده می‌کند.

## WStunnel 443 — OpenVPN over WebSocket/TLS

این Mode برای شبکه‌هایی است که HTTPS/TCP443 بهتر از VPN خام عبور می‌کند. ترافیک OpenVPN داخل WebSocket/TLS روی همان پورت عمومی 443 پنل Makia حمل می‌شود.

### Windows — اتصال مستقیم Makia

1. آخرین **Makia Windows Full Device Connector** را نصب کنید.
2. OpenVPN runtime/client را روی Windows نصب داشته باشید.
3. وارد Client Portal Makia شوید.
4. پروفایل **WStunnel 443** را انتخاب کنید.
5. روی **اتصال مستقیم** بزنید.
6. Makia ابتدا WStunnel محلی را اجرا می‌کند و بعد OpenVPN را روی همان تونل بالا می‌آورد.
7. برای قطع، از Disconnect خود Makia استفاده کنید تا هر دو Process بسته شوند.

### اتصال دستی

بسته WStunnel شامل فایل `.ovpn` و فایل `wstunnel-client-command.txt` است.

1. فرمان WStunnel را اجرا کنید.
2. صبر کنید Local endpoint آماده شود.
3. فایل `.ovpn` را با OpenVPN اجرا/Import کنید.
4. تا پایان VPN، WStunnel باید باز بماند.

### Android — اتصال مستقیم داخل Makia

در Makia 1.6.0، **WStunnel 443 روی Android به‌صورت Full Device Direct Connect** پشتیبانی می‌شود.

1. آخرین **Makia Android Connector 1.6.0** را از همان Client Portal نصب کنید.
2. با یوزر و رمز خود وارد Client Portal شوید.
3. پروفایل **WStunnel 443** را انتخاب کنید.
4. روی **اتصال مستقیم** بزنید.
5. بار اول مجوز Android VPN را تأیید کنید.
6. Connector، WStunnel را داخل خود برنامه روی WSS/TCP443 اجرا می‌کند و ترافیک کامل دستگاه را از تونل عبور می‌دهد.
7. برای قطع اتصال از گزینه **قطع اتصال** در Makia استفاده کنید.

Runtime رسمی WStunnel داخل APK قرار دارد؛ کاربر نیاز به نصب WStunnel، OpenVPN یا اجرای فرمان جداگانه روی Android ندارد.

### iPhone / iPad

در 1.6.0 هنوز Native WStunnel Full Device داخل iOS ادعا نمی‌شود و iOS همچنان از Profile/Import یا کلاینت سازگار استفاده می‌کند.

**نکته امنیتی:** مسیر WebSocket و فایل OVPN اختصاصی‌اند. آن‌ها را برای شخص دیگری ارسال نکنید.

## SSH / NPV Tunnel / NapsternetV

### NPV

1. لینک `npvt-ssh://` را Copy کنید یا QR مربوط به NPV را باز کنید.
2. در نسخه سازگار NPV Tunnel / NapsternetV گزینه Import from Clipboard یا Scan QR را انتخاب کنید.
3. Profile را ذخیره و Connect کنید.

### SSH معمولی

از اطلاعات زیر استفاده کنید:

- Server
- Port
- Username
- Password

نمونه:

```bash
ssh USER@SERVER -p PORT
```

OpenSSH رمز عبور را داخل فایل config ذخیره نمی‌کند.

## اگر اتصال برقرار نشد

- اینترنت دستگاه را بررسی کنید.
- تاریخ و ساعت دستگاه صحیح باشد.
- VPN دیگری هم‌زمان فعال نباشد.
- Wi-Fi و Mobile Data را جداگانه تست کنید.
- QR یا Link را دوباره از منبع اصلی Import کنید.
- Credentialها را دستی تغییر ندهید.
- برای پشتیبانی، نام Profile، نام برنامه، سیستم‌عامل و متن خطا را ارسال کنید.
- Credential کامل یا QR را در گروه عمومی نفرستید.
