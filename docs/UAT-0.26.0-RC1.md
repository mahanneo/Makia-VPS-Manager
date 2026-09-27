# Makia VPS Manager 0.26.0-rc1 — Final Hardening UAT

این نسخه برای رفع خطاهای واقعی Host و تکمیل UX قبل از Release رسمی آماده شده است.

## 1. Login

- Username و Password فقط یک Focus Surface داشته باشند و Chrome autofill کادر دوم نسازد.
- FA/EN واقعاً زبان را عوض کند و جهت RTL/LTR درست شود.
- Dark/Light واقعاً Theme ورود را عوض کند و پس از Reload حفظ شود.
- Password visibility کار کند.
- روی Raw IP و Domain صفحه بدون Horizontal overflow نمایش داده شود.

## 2. Installed-version verification

- پس از Upgrade، Footer/Login و API باید 0.26.0-rc1 نشان دهند.
- Browser hard reload انجام شود.
- Service worker cache باید makia-shell-v0260rc1 باشد.

## 3. Xray root-cause regression

Host دارای systemd hardening با NoNewPrivileges=true و RestrictSUIDSGID=true باید بتواند Xray Profile بسازد.
خطای runuser: cannot set user id: Operation not permitted نباید تکرار شود.

Profileهای منتشرشده: VLESS/REALITY، VMess، Trojan/TLS، Shadowsocks، Hysteria2/TLS، HTTP Proxy و SOCKS5.
برای هر Profile: Create، Core validation، Xray restart، QR/Share، Native export، Protected ZIP و Revoke بررسی شود.
Wizard فقط ترکیب‌های سازگار Transport/Security را نمایش دهد.

## 4. OpenVPN

- Server Advanced Settings باز شود.
- UDP و TCP هر دو قابل انتخاب باشند.
- تغییر Port/Transport با backup و rollback-safe restart انجام شود.
- DNS اول/دوم، Keepalive، Redirect Gateway و Client-to-client قابل تنظیم باشند.
- PKI و Certificateهای Client هنگام تغییر Server Transport حفظ شوند.
- Profile جدید با Transport فعال Server ساخته شود.
- معماری این Release یک OpenVPN Server Profile فعال دارد؛ UDP و TCP قابل انتخاب‌اند اما دو instance همزمان ادعا نمی‌شود.

## 5. WireGuard

- Advanced Settings شامل Server UDP Port و MTU باشد.
- Peer keys هنگام تغییر Server settings حفظ شوند.
- Port collision بر اساس UDP بررسی شود.
- Restart failure باید rollback کند.
- Peer create همچنان DNS / MTU / Keepalive / AllowedIPs / QR / Native export را پوشش دهد.

## 6. Users

- Users باید UI جدید v0.25+ را نشان دهد، نه layout قدیمی.
- Row فقط Identity / Protocol / Status / Usage / More داشته باشد.
- عملیات Delivery و Revoke داخل Detail Drawer باشند.

## 7. Guides

- Public guide باید برای Xray، WireGuard، OpenVPN و SSH/NPV تصویر داشته باشد.
- Admin Guide Center نیز 4 کارت تصویری داشته باشد.
- تصاویر نباید Credential داشته باشند.

## 8. Support

- صفحه Support باید Health / Guides / Logs / Connectivity را در Quick Actions نشان دهد.
- Ticket form ساده باشد.
- Remote Support به‌صورت Advanced disclosure باشد.
- Default scope روی Read-only باشد.
- One-time code و Audit behavior قبلی حفظ شود.

## 9. Admin Security

- UFW، Fail2ban، 2FA، HTTPS، Self-Test، Audit و API Tokens از یک Security Center قابل مشاهده/دسترسی باشند.

## 10. Release gate

برای تبدیل این RC به Stable/Official همه موارد زیر الزامی‌اند:
- Unit/contract CI PASS
- Xray Core smoke PASS
- Browser smoke PASS
- Upgrade روی VPS واقعی PASS
- sudo makia-doctor PASS
- sudo makia-uat-smoke PASS
- ساخت Xray روی Host واقعی بدون runuser error
- OpenVPN UDP و TCP روی Host واقعی تست شوند
- WireGuard handshake واقعی تست شود
- Iran Field Test از حداقل یک Mobile و یک Fixed network انجام شود

تا قبل از این Gateها نسخه Stable نام‌گذاری نمی‌شود.
