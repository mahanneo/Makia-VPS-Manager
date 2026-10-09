# راهنمای ساده راه‌اندازی Makia با IP یا دامنه (نسخه ۱.۶.۴ – مسیر توسعه)

این راهنما برای مدیرانی است که تازه یک Ubuntu VPS خریده‌اند. **IP و دامنه جایگزین هم در همه پروتکل‌ها نیستند**؛ مخصوصاً جایی که TLS و گواهی دیجیتال الزامی است. خطای نامعتبر باید *قبل از ساخت و تحویل پروفایل* دیده شود، نه پس از ارائه QR به کاربر.

## راه انتخاب سریع

| نیاز | فقط IP عمومی | دامنه | شرط مهم |
|---|---|---|---|
| SSH / NPV | بله | بله | TCP/SSH، پورت باز و رمز/کلید معتبر |
| WireGuard معمولی | بله | بله | UDP، Forward/NAT، handshake واقعی |
| OpenVPN معمولی | بله | بله | IP و دامنه در remote مجازند؛ تنظیم verify-x509-name و CA را بی‌دلیل حذف نکنید |
| Outline / Shadowsocks | بله | بله | کلید و پورت واقعی سرویس؛ معمولاً DNS Only |
| Xray / VLESS/VMess/Trojan | بسته به transport، TLS و SNI | بسته به transport | REALITY و TLS نام/کلید و Client compatibility خاص دارند؛ استفاده از IP را به‌صورت سراسری فعال فرض نکنید |
| Browser VPN Chrome/Edge | **نه در نسخه TLS فعلی** | بله | دامنه + گواهی معتبر + پورت HTTPS Proxy + احراز هویت + تست IP خروجی |
| WStunnel WSS / OpenVPN WStunnel 443 | **نه در نسخه TLS فعلی** | بله | دامنه + SNI/TLS + سرویس Backend و Client سازگار |
| Stealth Stunnel TLS | **نه در نسخه TLS فعلی** | بله | گواهی مطابق دامنه و پورت TCP آزاد |
| IKEv2 با گواهی Makia | **نه در پیاده‌سازی فعلی** | بله | هویت و گواهی دامنه، UDP 500/4500 |
| PPTP | خیر | خیر | در Makia پشتیبانی نمی‌شود؛ قدیمی و ناامن است |

**نکته:** یک TLS certificate معتبر می‌تواند از نظر استاندارد شامل IP SAN باشد، اما مسیر صدور/تأیید گواهی برای IP در Makia فعلی تعبیه نشده است؛ واردکردن IP به کادر دامنه یا کنارگذاشتن validation راه‌حل امنی نیست.

## از صفر؛ بدون دامنه

۱. از ارائه‌دهنده VPS، IP عمومی IPv4 را بگیرید؛ مانند `203.0.113.10` (این فقط آدرس نمونه و غیرقابل استفاده است).

۲. پس از نصب Makia، در مرورگر `http://SERVER_IP/` را باز کنید. این فقط دسترسی **HTTP مدیریتی اولیه** است. برای ورود حساس در اینترنت عمومی از شبکه امن، VPN مدیریتی یا HTTPS معتبر استفاده کنید؛ HTTP روی IP به‌خودی‌خود رمزگذاری نیست. در صورت نبود گواهی، آن را HTTPS جا نزنید.

۳. فعلاً SSH، WireGuard معمولی یا OpenVPN معمولی را انتخاب کنید. IP را **بدون** `http://`، `https://` یا `:port` وارد کنید؛ پورت فیلد جداگانه است. هر کانفیگ باید با Runtime واقعی، فایروال، Client و handshake آزمایش شود.

۴. برای انتخاب بدون تغییر سیستم، داخل سورس Makia اجرا کنید:

```bash
sudo makia-endpoint-wizard
# یا (از داخل سورس Makia)
python3 scripts/endpoint-wizard.py
# یا
python3 -m app.endpoint_preflight --protocol wireguard --endpoint 203.0.113.10 --port 51820 --json
```

در مثال بالا IP رزروشده مستندات عمداً در preflight رد می‌شود؛ IP واقعی و عمومی خودتان را جایگزین کنید.

## وقتی دامنه دارید

۱. رکورد DNS `A` را مثلاً `vpn.example.com → SERVER_PUBLIC_IP` قرار دهید؛ تا زمان propagation صبر کنید.

۲. برای SSH/WireGuard/OpenVPN/Outline معمولی، رکورد باید برای TCP/UDP مستقیم قابل استفاده باشد. Cloudflare orange-cloud HTTP proxy به شکل معمول برای این پروتکل‌های خام قابل استفاده نیست؛ **DNS Only** انتخاب کنید. تنظیمات AAAA را هم با IPv6 واقعی سرور هماهنگ کنید.

۳. برای Browser Gateway، WSS/Stealth و IKEv2 در پیکربندی فعلی Makia، ابتدا دامنه و گواهی معتبر همان نام را تهیه کنید و سپس کانفیگ بسازید. **سرور نباید گواهی نامطابق را به‌طور خودکار نادیده بگیرد**.

۴. نتیجه بررسی IP یا دامنه باید *قبل از Apply* نشان دهد: حالت، IPهای DNS، هم‌خوانی با IP سرور، گواهی/تاریخ اعتبار، پورت اشغال‌شده، سرویس موجود و راه اصلاح.

## معنی ساده فیلدها

- **IP سرور:** آدرس عمومی اختصاص‌یافته به VPS، نه IP داخلی `192.168.x.x`.
- **دامنه:** نامی مانند `vpn.example.com`؛ ابتدا باید DNS آن تنظیم شود.
- **پورت:** شماره درگاه سرویس، در بازه ۱ تا ۶۵۵۳۵؛ TCP با UDP متفاوت است. دو سرویس با یک IP و پروتکل انتقال یکسان نمی‌توانند بدون Multiplexer روی یک پورت یکسان Listen کنند.
- **TCP/UDP:** نوع انتقال. WireGuard معمولی UDP است و OpenVPN می‌تواند بسته به Server، UDP یا TCP باشد.
- **TLS/SNI/Certificate:** گواهی باید نام مقصد استفاده‌شده توسط Client را پوشش دهد؛ از غیرفعال‌سازی احراز هویت TLS برای حل خطا استفاده نکنید.
- **Handshake:** پاسخ واقعی دو سمت ارتباط؛ فایل QR یا سبز بودن سرویس، به‌تنهایی اتصال موفق نیست.

## ترتیب صحیح ساخت کاربر و کانفیگ

۱. بررسی نصب بودن موتور واقعی، وضعیت سرویس، پورت و Firewall. ۲. انتخاب نوع آدرس و اجرای preflight. ۳. ارزیابی تضاد پورت/اشغال‌بودن و TLS/DNS. ۴. **Validate** کانفیگ توسط موتور (مثلاً `xray run -test` برای Xray). ۵. اعمال با backup، rollback و ثبت audit. ۶. تولید Profile/QR فقط پس از Apply موفق. ۷. تست سمت کاربر شامل IP خروجی، DNS leak و handshake. در صورت شکست مرحله‌ای، نتیجه باید خطای انسانی قابل فهم بدهد و کانفیگ خراب را «موفق» اعلام نکند.

## استفاده روی Android / iPhone / Windows / Chrome

- **Android:** از Release رسمی APK امضاشده با گواهی دائمی استفاده کنید؛ قبل از نصب، SHA256 و امضا را بررسی کنید. UAT/debug APK جایگزین نسخه نهایی نیست. در Import Mode فایل WireGuard/OpenVPN یا لینک Xray را در اپ سازگار وارد کنید. VPN system-wide به اجازه Android VPNService نیاز دارد.
- **iPhone/iPad:** در Safari صفحه `https://PANEL_DOMAIN/client/` را باز کنید و «Add to Home Screen» را برای PWA بزنید. **PWA به‌تنهایی VPN سراسری iOS ایجاد نمی‌کند**. برای تونل واقعی، Client بومی معتبر مانند WireGuard یا OpenVPN را با Import/QR استفاده کنید؛ iOS native Makia بدون Network Extension امضاشده ادعا نشده است.
- **Windows:** بسته Full Device Connector با برچسب UAT را از Release بگیرید؛ بعد از تست و تأیید مناسب استفاده کنید. یک مرورگر مستقل، کل Windows را تونل نمی‌کند.
- **Chrome/Edge:** افزونه Browser VPN فقط HTTP/HTTPS همین مرورگر را از HTTPS Proxy عبور می‌دهد. بعد از اتصال، IP خروجی تأییدشده و خطاهای Auth/Proxy را بررسی کنید؛ مرورگر باید تنظیم Proxy را واقعاً پذیرفته باشد. افزونه جایگزین WireGuard سراسری نیست.

مراجع: [راهنمای کاربران](CLIENT-GUIDE-FA.md)، [گیت‌های Release](RELEASE-STATUS.md)، [امضای Android](ANDROID-RELEASE-SIGNING.md)، [تست اینترنت ایران](IRAN-CONNECTIVITY-FIELD-TEST.md).

## اگر خطا دیدید

| علامت | علت‌های محتمل | بررسی درست |
|---|---|---|
| دامنه ذخیره نمی‌شود | رکورد A اشتباه، SSL نامعتبر، CDN proxy | `dig +short A HOST`، مقایسه IP و نام گواهی |
| «Port already in use» | Listener فعلی TCP یا UDP همان درگاه | `ss -lntup`؛ پورت آزاد انتخاب کنید؛ سرویس فعال دیگر را متوقف نکنید |
| WireGuard QR صادر شد اما وصل نیست | UDP فیلتر، NAT/Forward ناقص، IP اشتباه | `wg show` و handshake، NAT و route |
| OpenVPN connected اما اینترنت ندارد | DNS/route/forward/NAT | Route table، DNS، client/server logs |
| مرورگر Connected و IP عوض نشد | Proxy تحت کنترل افزونه نیست، auth/egress fail | IP verified، proxy error و 407 در Gateway |
| IKEv2/Stealth/Browser بدون دامنه کار نمی‌کند | گواهی TLS فعلی برای نام دامنه است | دامنه معتبر و صدور گواهی، نه bypass امنیت |
| PPTP انتخاب نشده | عمداً پشتیبانی نشده | WireGuard یا OpenVPN |

**محدودیت نسخه:** preflight جدید *read-only* است و هنوز جایگزین Validation در تمام فرم‌های UI نشده است. هر پروتکل برای ادعای Production-ready به UAT واقعی همان پروتکل نیاز دارد.
