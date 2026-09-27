# Makia VPS Manager 0.25.0-rc1 — Professional UX / Iran Connectivity UAT

این UAT برای Release Candidate نسخه 0.25 است. هدف اصلی آن دو چیز است:

1. رابط کاربری روزمره خلوت، خوانا و حرفه‌ای باشد.
2. وضعیت Server-side همه پروتکل‌ها دقیق بررسی شود و تأیید اتصال ایران فقط پس از Field Test واقعی ثبت شود.

## A. UI shell

Desktop: 1280×800، 1440×900، 1920×1080.

- Sidebar ثابت و خوانا با عرض استاندارد.
- Dashboard و Users باید بدون Hover-based rail قابل استفاده باشند.
- فقط گروه‌های اصلی روی منو دیده شوند: اصلی، پروتکل‌ها، زیرساخت، سیستم.
- موارد ثانویه داخل Submenu باشند.
- Font اصلی صفحات حداقل در محدوده 12–14px خوانا باشد.
- عنوان صفحه حداقل 22px.
- هیچ صفحه‌ای نباید به‌خاطر تعداد کنترل‌ها حس «همه چیز روی یک صفحه» داشته باشد.

## B. Users

- Summary فشرده در بالا.
- Search و Protocol filter.
- هر Row فقط Identity، Protocol، Status، Usage/Expiry و دکمه More داشته باشد.
- Delivery / QR / Native / Protected ZIP / Revoke فقط داخل Detail Drawer نمایش داده شوند.
- Detail Drawer باید برای SSH، Xray، WireGuard و OpenVPN کار کند.

## C. New Access

- Create Access باید Drawer مستقل باشد، نه Modal بزرگ وسط صفحه.
- مرحله 1: انتخاب Protocol.
- مرحله 2: فقط Identity/Endpoint اصلی.
- Advanced settings به‌صورت Progressive Disclosure.
- مرحله 3: Policy / Network.
- مرحله 4: Review و Protected Delivery PIN.
- Mobile باید Full-width شود.
- ساخت واقعی SSH / Xray / WireGuard / OpenVPN باید با APIهای فعلی انجام شود.

## D. Connectivity Lab

Connectivity Lab باید:

- Xray diagnostics را بخواند.
- WireGuard diagnostics را بخواند.
- OpenVPN diagnostics را بخواند.
- Endpoint Matrix را نمایش دهد.
- Self-Test را نمایش دهد.
- عبارت «Server ready» را از «تأیید اتصال از داخل ایران» جدا نگه دارد.
- هیچ پروتکلی بدون Field Test واقعی نباید Iran PASS تلقی شود.

## E. Iran field test gate

حداقل از دو مسیر اینترنت مستقل داخل ایران تست شود؛ ترجیحاً یک Mobile network و یک Fixed network.

برای هر پروتکل:

### SSH / NPV
- TCP reachability
- Login واقعی
- انتقال حداقل 1 MB
- Disconnect / reconnect
- تست Session/Device limit

### Xray / V2Ray
Profileهایی که واقعاً ارائه می‌شوند باید جداگانه تست شوند:
- VLESS + REALITY
- VMess
- Trojan
- Shadowsocks
- Hysteria2
- HTTP/SOCKS فقط در صورت ارائه به کاربر

برای هر Profile:
- Import
- Handshake / connect
- DNS resolution
- HTTPS browsing
- حداقل 10 MB download
- Reconnect
- Mobile data و Wi-Fi/fixed

### WireGuard
- Handshake
- Internet route
- DNS
- MTU-sensitive page
- reconnect پس از تغییر شبکه

### OpenVPN
- TLS/PKI handshake
- Internet route
- DNS
- reconnect
- UDP و TCP فقط در صورتی که هر دو در محصول ارائه شوند

## F. Stable rule

Stable ممنوع است مگر:
- CI PASS
- Browser Smoke PASS
- Clean Install PASS
- Upgrade PASS
- Server-side Connectivity Lab بدون Critical failure
- Iran Field Test واقعی برای پروتکل‌های منتشرشده ثبت شده باشد

نتیجه تست ایران باید تاریخ، ISP/اپراتور، نوع اتصال، Client app، Protocol/Profile و PASS/FAIL داشته باشد.
