## نسخه ۰.۲۶.۰-rc1 — کاندیدای نهایی انتشار عمومی

این نسخه روی ایرادهای واقعی Host و تکمیل تجربه مدیریتی متمرکز است. خطای ساخت Xray با پیام `runuser: cannot set user id: Operation not permitted` بدون حذف `NoNewPrivileges` رفع شده است؛ Login نیز Focus Surface واحد، تغییر زبان واقعی FA/EN و Dark/Light واقعی دارد.

در Xray، Wizard و Backend از یک **Compatibility Matrix مشترک** استفاده می‌کنند تا ترکیب نامعتبر Protocol/Transport/Security اصلاً به مرحله Commit نرسد. CI روی Xray Core 26.3.27 مجموعه Guided شامل VLESS، VMess، Trojan، Shadowsocks، Hysteria2، HTTP و SOCKS و چند Transport را validate می‌کند و VLESS/REALITY علاوه بر syntax، Handshake و Traffic واقعی CI دارد. قابلیت **Advanced JSON** برای تنظیمات خارج از Guided mode حفظ شده است.

OpenVPN دیگر UDP-only نیست: تنظیم واقعی **TCP/UDP، Port، DNS، Keepalive، Redirect Gateway و Client-to-client** با Backup، Restart verification و Rollback اضافه شده و فایل OVPN دانلودشده از Runtime فعلی بازسازی می‌شود. WireGuard نیز Peer/Handshake/Traffic/QR و تنظیمات DNS، Port، MTU، Keepalive، AllowedIPs و CIDR را یکپارچه نمایش می‌دهد.

Support به Help & Diagnostics ساده‌تر تبدیل شده، Remote Support به بخش Advanced منتقل شده، Admin Security نمای HTTPS/2FA/UFW/Fail2ban/SSH/API Tokens دارد، و راهنمای عمومی برای هر چهار خانواده پروتکل دارای نمودارهای تصویری قدم‌به‌قدم است.

> **نکته برای نصب فعلی:** اگر Footer/Login شما هنوز `v0.24.0-rc1` را نشان می‌دهد، UI قدیمی Users طبیعی است. بعد از Merge این RC، `sudo makia-upgrade` را اجرا کنید و Browser را Hard Refresh کنید.

### وضعیت انتشار

`0.26.0-rc1` برای نصب عمومی به‌عنوان **Release Candidate** آماده می‌شود، اما Stable اعلام نمی‌شود تا UAT واقعی Upgrade/Clean Install و تست Client داخل ایران طبق [UAT 0.26](docs/UAT-0.26.0-RC1.md) و [Iran Field Test](docs/IRAN-CONNECTIVITY-FIELD-TEST.md) تکمیل شود.

## نسخه ۰.۲۵.۰-rc1 — رابط حرفه‌ای و خلوت‌تر

این نسخه منوی Hover/Rail قبلی را کنار می‌گذارد و یک Sidebar ثابت، خوانا و دسته‌بندی‌شده ارائه می‌کند. صفحات روزمره عمداً خلوت‌تر شده‌اند: در صفحه کاربران فقط اطلاعات اصلی دیده می‌شود و QR، فایل Native، Protected ZIP، ویرایش و لغو دسترسی داخل Detail Drawer باز می‌شوند.

ساخت دسترسی جدید نیز دیگر یک Modal بزرگ و شلوغ نیست؛ یک Provisioning Drawer مرحله‌ای باز می‌شود و فقط اطلاعات ضروری را نشان می‌دهد. تنظیمات تخصصی مثل Session/IP limits، MTU، Keepalive، Xray Transport/Security و Quota با Progressive Disclosure نمایش داده می‌شوند.

بخش **Connectivity Lab** وضعیت واقعی Runtime و Endpointهای SSH/Xray/WireGuard/OpenVPN را بررسی می‌کند. این بخش عمداً بین «Server Ready» و «تأیید اتصال از داخل ایران» تفاوت می‌گذارد. برای تست واقعی ایران، `docs/IRAN-CONNECTIVITY-FIELD-TEST.md` و ابزار `scripts/iran-field-preflight.sh` اضافه شده‌اند. هیچ Release نباید بدون Field Test واقعی داخل ایران ادعای سازگاری قطعی داشته باشد.

## نسخه ۰.۲۴.۰-rc1 — ساختار پنل نزدیک به Sanaei / 3x-ui

در این نسخه معماری رابط Makia از نو مرتب شده است. هدف، کپی ظاهری صرف نیست؛ ساختار تعامل و چیدمان پنل به الگوی آشنای 3x-ui/Sanaei نزدیک شده است: Sidebar باریک و قابل Pin، Dashboard فشرده، Inboundها به‌عنوان بخش مستقل، Client Directory واحد، Submenu برای تنظیمات و ابزارهای Xray، و فرم‌ها/جدول‌های فشرده‌تر.

Backend Makia عوض نشده و قابلیت‌های اختصاصی آن مانند SSH/NPV، WireGuard، OpenVPN، Full-stack provisioning، Transport-aware port allocation، Backup، Support و Node management حفظ شده‌اند.

Dashboard جدید فقط داده واقعی API را نمایش می‌دهد و صفحه Inbounds نیز وضعیت واقعی Xray Core را می‌خواند. برای قابلیت‌هایی که Backend مستقل ندارد، کنترل نمایشی جعلی اضافه نشده است.

قبل از Stable، [UAT نسخه ۰.۲۴.۰-rc1](docs/UAT-0.24.0-RC1.md) باید روی VPS واقعی PASS شود.

## نسخه ۰.۲۳.۰-rc1 — بازطراحی کامل پنل

این نسخه رابط کاربری Makia را از Login تا Dashboard و Workspaceهای داخلی از پایه بازطراحی می‌کند. ساختار جدید مطابق طرح تأییدشده از تم سرمه‌ای بسیار تیره، آبی الکتریکی، بنفش، سبز وضعیت و کارت‌های فشرده عملیاتی استفاده می‌کند.

Sidebar جدید، مدیریت کاربران را به SSH، V2Ray/Xray، WireGuard و OpenVPN تفکیک می‌کند و بخش‌های «مدیریت سرویس‌ها»، «مدیریت پورت‌ها»، «گزارش‌ها»، «تنظیمات پنل»، «امنیت»، «بکاپ»، «بروزرسانی» و «پشتیبانی» را به‌صورت مرتب نگه می‌دارد. Dashboard جدید اطلاعات Fake ندارد و KPIها، نمودار Metrics، تعداد کاربران و وضعیت سرویس‌ها را از APIهای واقعی خود Makia می‌خواند.

صفحه‌های SSH/Xray/WireGuard/OpenVPN نیز Table-first شده‌اند تا ساخت کاربر، مشاهده وضعیت، حجم/انقضا در جایی که Accounting واقعی وجود دارد، فعال/غیرفعال، Export و عملیات مدیریتی سریع‌تر باشد.

این نسخه RC است و قبل از Stable باید [UAT رابط کاربری ۰.۲۳.۰-rc1](docs/UAT-0.23.0-RC1.md) روی VPS واقعی بررسی شود.

## نسخه ۰.۲۲.۰-rc1 — نصب کامل و آمادهٔ ساخت کاربر

از این نسخه، نصب تازه Makia دیگر فقط پنل و SSH را بالا نمی‌آورد. Installer به‌صورت خودکار **Xray / V2Ray، WireGuard، OpenVPN، Easy-RSA، iptables و Stunnel** را نصب می‌کند و Runtimeهای WireGuard و OpenVPN را نیز Bootstrap می‌کند. Xray هم با Core اعتبارسنجی‌شده و Config سالم فعال می‌شود.

بعد از پایان نصب، مدیر باید بتواند مستقیماً وارد Workspace مربوط به SSH، Xray، WireGuard یا OpenVPN شود و **فقط User/Client بسازد**؛ مرحلهٔ Install/Bootstrap عادی دیگر بخشی از راه‌اندازی اولیه نیست.

Portها نیز خودکار و Transport-aware تخصیص داده می‌شوند: WireGuard ابتدا UDP/443 و OpenVPN ابتدا UDP/1194 را امتحان می‌کنند. اگر همان Transport روی آن Port اشغال باشد، Makia Port جایگزین آزاد انتخاب می‌کند و مقدار واقعی را در تنظیمات پیش‌فرض ذخیره می‌کند. TCP/443 پنل با UDP/443 WireGuard تداخل محسوب نمی‌شود.

نصب‌های فعلی که فقط SSH روی آن‌ها کار می‌کند نیز با اجرای `sudo makia-upgrade` Full Stack را دریافت می‌کنند. Updater کانفیگ‌های موجود را overwrite نمی‌کند و فقط بخش‌های مفقود را می‌سازد یا Runtime مدیریت‌شده را Repair می‌کند.

قبل از Stable، [UAT نسخه ۰.۲۲.۰-rc1](docs/UAT-0.22.0-RC1.md) باید روی VPS واقعی PASS شود.

## نسخه ۰.۲۱.۰-rc1 — Control Center ماژولار

ساختار پنل در این RC از حالت «همه‌چیز در یک صفحه» خارج شده است. **SSH / NPV، Xray / V2Ray، WireGuard و OpenVPN هرکدام فضای مستقل** دارند و «همه کاربران» فقط نمای سراسری بین پروتکل‌هاست. Dashboard همچنان وضعیت کل سرور، سرویس‌ها، منابع و تعداد دسترسی‌ها را خلاصه می‌کند.

در Xray، قابلیت‌های واقعی Client شامل حجم، تاریخ انقضا، Reset دوره‌ای، IP/Device Limit، فعال/غیرفعال، Subscription و Diagnostics در همان Workspace دیده می‌شوند. SSH سیاست‌های Expiry/Session/Device را جدا نگه می‌دارد؛ WireGuard ترافیک RX/TX و Handshake و فعال/غیرفعال‌سازی همتا را دارد؛ OpenVPN مدیریت PKI و OVPN و Diagnostics را دارد و تا زمانی که Accounting قابل اتکای per-client اضافه نشود، Quota نمایشی نشان نمی‌دهد.

### ایمنی Port

ساخت سرویس‌ها از بررسی **Transport-aware** استفاده می‌کند. شماره Port به‌تنهایی تعارض محسوب نمی‌شود؛ Protocol و Transport هم مهم‌اند. برای نمونه **Nginx روی TCP/443 می‌تواند هم‌زمان با WireGuard روی UDP/443** کار کند، اما دو سرویس که هر دو بخواهند UDP/443 را Bind کنند اجازه ساخت نمی‌گیرند. Xray و Tunnel نیز فقط Transport واقعی خودشان را برای Collision بررسی می‌کنند.

این نسخه Release Candidate است. قبل از Stable باید [UAT نسخه ۰.۲۱.۰-rc1](docs/UAT-0.21.0-RC1.md) روی VPS واقعی اجرا شود.

## نسخه ۰.۱۹.۰ — فضای مدیریت WireGuard

منوی مستقل WireGuard وضعیت سرویس، فهرست همتاها، آخرین handshake، مصرف RX/TX، آدرس Endpoint و دکمه‌های QR، فایل کانفیگ و فعال/غیرفعال‌سازی ماندگار را نشان می‌دهد. هنگام ساخت همتا دامنه یا IP را انتخاب کنید. ظاهر پنل و ناوبری موبایل خواناتر شده‌اند. اگر ذخیرهٔ تنظیمات سرور یا بستهٔ رمزنگاری‌شده شکست بخورد، همتای تازه ساخته‌شده پاک می‌شود. برای بررسی اتصال واقعی بیرون سرور، [چک‌لیست ۰.۱۹.۰](docs/UAT-0.19.0.md) را اجرا کنید.

## اصلاح اتصال نسخه v0.18.1

ساخت ساده Xray اکنون برای VLESS از RAW/REALITY استفاده می‌کند و محدودیت حجم و زمان را به‌صورت پیش‌فرض فعال نمی‌کند. انتخاب پروتکل دیگر ترکیب سازگار اولیه را تنظیم می‌کند و «تنظیمات پیشرفته» همچنان اختیاری است. OpenVPN قانون عبور ترافیک تونل و بررسی NAT/FORWARD دارد؛ در ارتقا، اسکریپت قدیمی مدیریت‌شده با نسخه پشتیبان اصلاح می‌شود. دستور `makia-doctor` نیز هنگام بررسی WireGuard دیگر به متغیر تعریف‌نشده برخورد نمی‌کند. برای آزمون واقعی دستگاه و شبکه، [چک‌لیست v0.18.1](docs/UAT-0.18.1.md) را اجرا کنید.

## نسخه مرجع کد v0.18.0 — انتخاب دامنه یا IP برای همهٔ پروتکل‌ها

در فرم ساخت دسترسی SSH/NPV، Xray، WireGuard و OpenVPN می‌توانید «دامنه» یا «IPv4 عمومی» را صریح انتخاب کنید. همان آدرس در خروجی کلاینت حفظ می‌شود. برای OpenVPN، Port و Transport از تنظیمات واقعی سرور خوانده می‌شود؛ خروجی‌های ذخیره‌شده نیز هنگام دانلود دوباره به دامنهٔ پنل تغییر نمی‌کنند.

این شماره نسخه مبنای رسمی ادامهٔ توسعهٔ کد است. وضعیت اتصال هر پروتکل از بیرون VPS، DNS واقعی و Handshake وایرگارد باید طبق [UAT نسخه 0.18.0](docs/UAT-0.18.0.md) روی سرور شما بررسی شود؛ سبز شدن CI به‌تنهایی اتصال در همهٔ شبکه‌ها را ثابت نمی‌کند.

## نسخه v0.17.0-rc1 — WireGuard Runtime Repair و تست IP/Domain

در این نسخه تشخیص و تعمیر WireGuard عمیق‌تر شده است. پنل وضعیت Service، Interface، UDP Listener، IP Forwarding، FORWARD Rule، NAT و Handshake Peerها را بررسی می‌کند و گزینه **Repair Runtime** دارد.

همچنین در Protocol Hub گزینه **IP / Domain Readiness** اضافه شده تا یک IP یا دامنه را برای SSH، Xray، WireGuard و OpenVPN از نظر Runtime، DNS و Listener بررسی کنید.

Updater نیز WireGuard موجود را قبل از UAT نهایی بررسی می‌کند و در صورت نیاز با Backup تعمیر می‌کند.

> توجه: تست داخلی و CI جای تست اتصال واقعی از یک موبایل/کامپیوتر خارج از VPS را نمی‌گیرد. برای Stable باید IP و Domain واقعی روی Client خارجی تست شوند.

راهنمای UAT: [UAT v0.17.0-rc1](docs/UAT-0.17.0-RC1.md)

# راهنمای فارسی Makia VPS Manager

**Makia VPS Manager** یک پنل مدیریت VPS برای مدیریت دسترسی‌های SSH، Xray، WireGuard و OpenVPN، تحویل امن کانفیگ، دامنه/HTTPS، بکاپ و مهاجرت سرور است.

## نسخه ۰.۲۰.۰ — استفاده بدون لایسنس

پس از نصب و ورود مدیر، SSH، Xray، WireGuard، OpenVPN، خروجی رمزدار، بکاپ و نودها در دسترس‌اند. کد فعال‌سازی، سرور Owner و مرحلهٔ صدور کلید حذف شده‌اند. نصب‌های قبلی با `sudo makia-upgrade` به‌روز می‌شوند؛ لایسنس قدیمی نادیده گرفته می‌شود و کاربران و کانفیگ‌ها باقی می‌مانند.

منوی «پشتیبانی» برای ثبت درخواست و ایجاد کد موقت دسترسی پشتیبانی است؛ استفادهٔ عادی به این کد نیاز ندارد. ورود مدیر، 2FA و محدودیت‌های دسترسی موقت حفظ شده‌اند. آزمون واقعی اتصال از بیرون VPS طبق [چک‌لیست ۰.۲۰.۰](docs/UAT-0.20.0.md) انجام شود.

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
