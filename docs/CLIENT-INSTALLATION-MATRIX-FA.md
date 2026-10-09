# راهنمای نصب کلاینت Makia — Android، iPhone، Windows و مرورگر

این راهنما درباره تفاوت **پروفایل VPN کامل سیستم** و **Proxy مخصوص مرورگر** است. هیچ اتصال یا مسیریابی صرفاً با علامت «متصل» اثبات نمی‌شود.

## Android

- **WireGuard:** برنامه رسمی WireGuard → Add → Scan QR / Import file → فایل `.conf` اختصاصی → Activate → مشاهده دریافت و ارسال واقعی دیتا. اگر Endpoint با IP باشد، نیازی به دامنه نیست.
- **OpenVPN:** برنامه OpenVPN Connect → Upload File → `.ovpn` → Connect. فایل certificate/key متعلق به همان کاربر را فقط از پنل تحویل بگیرید.
- **Xray:** کلاینت سازگار با VLESS/VMess/Trojan/Reality انتخاب کنید (پشتیبانی هر قابلیت بستگی به نسخه کلاینت دارد) → QR یا Share Link → Import → Connect. SNI، Reality Public Key، Short ID را تغییر ندهید.
- **Makia Android Connector:** APK فقط از صفحه رسمی Release دانلود شود؛ **نسخه آزمایشی/debug جای APK رسمی امضاشده نیست**. برای اولین نصب اجازه VPN سیستم را تأیید کنید. برای بروزرسانی‌های بعدی امضای یکسان باید حفظ شود.
- **WStunnel + OpenVPN:** فقط وقتی Build و پروفایل مشخص در Android واقعی تست شده از Direct Connect استفاده کنید. مسیر وب‌سوکت و گواهی میزبان باید معتبر باشد.

## iPhone / iPad

- **WireGuard:** اپ رسمی WireGuard → `+` → Create from QR Code / Import file.
- **OpenVPN:** OpenVPN Connect → Import `.ovpn`.
- **IKEv2:** Settings → VPN / VPN & Device Management → Add VPN Configuration → IKEv2؛ شناسه گواهی و Server/Remote ID باید مطابق کانفیگ صادرشده باشند.
- **Xray:** از کلاینت iOS سازگار با پروتکل صادرشده استفاده کنید. سازگاری VLESS/REALITY/Hysteria2 بین اپ‌ها یکسان نیست.
- **Makia PWA:** در Safari گزینه Share → Add to Home Screen؛ این **پنل مدیریت اکانت و دریافت پروفایل است، نه VPN بومی iOS**. اتصال سراسری iOS نیاز به اپ VPN و مجوز Network Extension مستقل دارد.
- **PPTP:** iOS جدید پشتیبانی داخلی ندارد؛ از IKEv2، WireGuard یا OpenVPN استفاده کنید.

## Windows

- برای VPN کل سیستم از WireGuard، OpenVPN یا Connector امضاشده/آزمایش‌شده مناسب با پروفایل استفاده کنید.
- پیش از نصب هر Connector، SHA-256 بسته و هویت سازنده را بررسی کنید.
- تست صحیح: DNS Resolve → Connect → Handshake → تغییر IP خروجی (در صورت Full Tunnel) → ترافیک دانلود و آپلود → Disconnect/Reconnect → Revocation.

## Chrome / Edge

- **Makia Browser VPN 1.6.4.2** یک HTTP(S) Proxy برای **مرورگر** است، نه یک VPN سراسری ویندوز.
- افزونه را از فایل رسمی GitHub Release، در `chrome://extensions` / `edge://extensions` با Load unpacked نصب کنید.
- پس از Login و Connect، بخش **IP خروجی تأییدشده** را بررسی کنید. صرف «آماده اتصال» یا «متصل» کافی نیست.
- خطای `ERR_TUNNEL_CONNECTION_FAILED` ممکن است از TLS، HTTP CONNECT، Proxy Authentication یا سیاست پورت مقصد باشد؛ عیب‌یاب داخل افزونه رمزها را نمایش نمی‌دهد.
- برای WebRTC leak protection و conflict با افزونه‌های Proxy دیگر، آنها را غیرفعال و تست IP/WebRTC را مجدد اجرا کنید.
- Web/PWA معمولی بدون افزونه یا کلاینت بومی **نمی‌تواند خودسرانه همه ترافیک دستگاه** را از VPN عبور دهد.

## بررسی مستقل

1. در حالت عادی IP عمومی را از `https://api.ipify.org` ثبت کنید.
2. پروفایل را متصل کنید؛ از همان مرورگر/دستگاه درخواست HTTPS جدید بفرستید.
3. IP خروجی، DNS و WebRTC را بررسی کنید. ترافیک مقصد باید در Counter سرور و کلاینت دیده شود.
4. اگر IP عوض نشد، قبل از ساخت اکانت جدید، Firewall/Port/Handshake و تنظیمات Client را بررسی کنید.
5. پس از اتمام کار، Disconnect و قطع واقعی تونل را بررسی کنید.

هرگز رمز، Access Token، کلید خصوصی WireGuard، فایل `.ovpn` یا QR کاربر را در گروه عمومی قرار ندهید.

برای تنظیم سرور، [SETUP-IP-OR-DOMAIN-FA.md](SETUP-IP-OR-DOMAIN-FA.md) را بخوانید.
