# Makia v0.16.1-rc1 — Protocol Runtime / IP+Domain / WireGuard Recovery UAT

این Release Candidate برای رفع مشکل «systemd Running ولی Protocol عملاً unusable» و مخصوصاً WireGuard ساخته شده است.

## 1. Upgrade / Rollback
- قبل از جایگزینی Runtime، SQLite data backup ساخته شود.
- Rollback archive علاوه بر app/systemd/nginx، تنظیمات فعال WireGuard/OpenVPN/Xray را نیز نگه دارد.
- اگر Update بعد از تغییر Runtime شکست خورد، Protocol serviceهای قبلی نیز Restore/Restart شوند.
- `MAKIA_SUPPORT_WEBHOOK_TOKEN` در Update از env حفظ شود.
- VERSION پس از Update برابر `0.16.1-rc1` باشد.
- `makia-doctor` و `makia-uat-smoke` PASS شوند.

## 2. WireGuard Runtime
- wg0.conf موجود باشد.
- wg-quick@wg0 Active باشد.
- Kernel interface با `wg show wg0` قابل خواندن باشد.
- UDP ListenPort واقعاً با `ss` دیده شود.
- `net.ipv4.ip_forward=1` باشد.
- FORWARD rule برای ingress و egress wg0 وجود داشته باشد.
- NAT/MASQUERADE فقط برای subnet خود WireGuard و uplink واقعی موجود باشد.
- PostUp/PostDown جدید idempotent باشد و Rule تکراری نسازد.
- Repair قبل از تغییر config یک Backup بسازد.
- Repair هیچ PrivateKey یا Peer block را حذف یا تعویض نکند.
- Failure حین Repair باید config قبلی را Restore کند.
- ساخت Peer روی Runtime ناسالم ابتدا Repair را اجرا کند و فقط بعد از runtime PASS ادامه دهد.

## 3. WireGuard Domain + IP
- Endpoint مستقیم IPv4 profile معتبر بسازد.
- Domain فقط وقتی پذیرفته شود که A record مستقیم به IPv4 همین VPS اشاره کند.
- Domain پشت HTTP/CDN Proxy به‌عنوان WireGuard endpoint معتبر تلقی نشود.
- در Profile مبتنی بر Domain، Protected ZIP یک `-ip.conf` و `-ip-qr.svg` با همان Peer/PrivateKey و IPv4 مستقیم داشته باشد.
- CI network-namespace smoke باید Handshake واقعی WireGuard را یک بار با IPv4 و یک بار با hostname انجام دهد.

## 4. OpenVPN Domain + IP
- Server روی udp4 یا tcp4-server Normalize باشد.
- Listener واقعی Port بررسی شود.
- Domain A record با IPv4 VPS تطابق داشته باشد.
- Domain profile ابتدا Domain و سپس matching direct IPv4 fallback را داشته باشد.
- IP profile مستقیم بدون fallback اضافی ساخته شود.
- AAAA/IPv6 و TCP/443 collision warningهای موجود Regression نداشته باشند.

## 5. Xray Domain + IP
- Active config با Xray Core validation موجود PASS شود.
- هر Inbound از نظر TCP/UDP listener مطابق Transport واقعی بررسی شود.
- VLESS/VMess/Trojan/Shadowsocks/Hysteria2 و Transport matrix موجود Regression نداشته باشند.
- Hysteria2 و mKCP به اشتباه TCP تشخیص داده نشوند.
- Domain A record مستقیم برای RAW/REALITY/Hysteria2 قابل بررسی باشد.
- Direct IPv4 endpoint نیز در Runtime diagnostics PASS شود.

## 6. SSH Domain + IP
- SSH/sshd Active باشد.
- TCP/22 listener وجود داشته باشد.
- Domain A record با VPS IPv4 تطابق داشته باشد.
- SSH/NPV delivery هم hostname و هم IPv4 را بدون تغییر Credential حفظ کند.

## 7. Connectivity Lab
- Protocol Hub دکمه `IP / Domain Lab` داشته باشد.
- Endpoint دلخواه Domain یا IPv4 قبول شود.
- SSH / WireGuard / OpenVPN / Xray فقط اگر configured باشند بررسی شوند.
- نتیجه Server-side readiness برای هر Engine جدا نشان داده شود.
- UI صریحاً اعلام کند که این تست DNS/Listener/NAT/Runtime سمت سرور است و Last-mile ISP/Client فقط با اتصال واقعی بیرونی قطعی می‌شود.

## 8. Runtime State UX
- Protocol Hub برای Xray/WireGuard/OpenVPN فقط از systemd Active برای برچسب سلامت استفاده نکند.
- اگر process Running ولی listener/NAT/runtime خراب است، `Runtime attention` نمایش داده شود.
- Services view دکمه Diagnose/Repair را در Runtime attention نشان دهد.
- WireGuard Diagnostics شامل Service, Interface, UDP Listener, ip_forward, NAT, FORWARD, Peers, Handshake و DNS resolution باشد.

## 9. Sidebar / Scrollbar
- Sidebar nav scrollbar سفید پیش‌فرض نمایش داده نشود.
- WebKit/Chromium scrollbar مدرن باریک و هماهنگ Glass UI باشد.
- Firefox از scrollbar-color/scrollbar-width استفاده کند.
- Scrollbar buttonهای بالا/پایین قدیمی در Chromium مخفی باشند.
- Modal/Table/Command list نیز style یکسان و بدون Regression در Scroll داشته باشند.

## 10. Security / Regression
- WireGuard Repair برای Remote Support Operator مجاز باشد، اما ساخت User/Peer/License/Backup/Export همچنان مسدود بماند.
- Private signing key leak guard PASS باشد.
- Unit tests PASS.
- Browser Smoke PASS.
- Xray Core 26.3.27 matrix PASS.
- OpenVPN domain tests PASS.
- WireGuard Runtime tests PASS.
- WireGuard netns IP/domain handshake PASS.
- v0.11 تا v0.16 contractها PASS بمانند.

## محدودیت تأیید
PASS شدن CI و Connectivity Lab به معنی سلامت config/runtime سمت VPS است. تأیید قطعی اینکه یک ISP، اپراتور موبایل، NAT سازمانی یا فایروال خارج از VPS هر Protocol را عبور می‌دهد، فقط با Client واقعی خارج از سرور قابل اثبات است.
