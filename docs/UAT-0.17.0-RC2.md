# Makia v0.17.0-rc2 — WireGuard Repair Hardening UAT

## هدف
این RC روی دو Regression مهم v0.17.0-rc1 تمرکز دارد: Repair کانفیگ‌های قدیمی WireGuard بدون PostUp/PostDown و تشخیص صریح نبود Handshake واقعی از اینترنت.

## Upgrade
- مبنا: v0.17.0-rc1.
- Update باید Data، License، Owner Control Center، Remote Support و Client artifacts را حفظ کند.
- Stable اعلام نشود تا UAT واقعی روی VPS و Client خارج سرور انجام شود.

## Legacy WireGuard Config Regression
یک wg0.conf معتبر بسازید که [Interface] و حداقل یک [Peer] داشته باشد ولی PostUp/PostDown نداشته باشد.
سپس از Protocol Hub → WireGuard Diagnostics → Repair Runtime استفاده کنید.

PASS:
- PostUp و PostDown داخل [Interface] و قبل از اولین [Peer] قرار بگیرند.
- wg-quick@wg0 بعد از Repair active باشد.
- wg show interfaces شامل wg0 باشد.
- UDP listener روی ListenPort دیده شود.
- net.ipv4.ip_forward=1 باشد.
- FORWARD و MASQUERADE سالم باشند.
- اگر Repair fail شد، wg0.conf و sysctl قبلی rollback شوند.

## External UDP / Handshake
- یک Peer واقعی بسازید.
- ابتدا Endpoint=Public IPv4 و سپس Endpoint=DNS-only Domain تست شود.
- Client باید از شبکه خارج VPS تلاش کند.
- PASS واقعی فقط زمانی است که Latest Handshake و RX/TX تغییر کند.
- اگر Runtime سمت سرور سالم است ولی Handshake نداریم، Diagnostics نباید نتیجه اتصال را موفق اعلام کند و باید احتمال UDP filtering، upstream firewall/NAT، ISP/network blocking یا endpoint/key mismatch را نمایش دهد.
- هیچ ادعای تضمینی درباره کارکرد WireGuard در ایران یا هر شبکه محدودشده‌ای مجاز نیست.

## Protocol Matrix
SSH / NPV، Xray، WireGuard و OpenVPN را برای Public IPv4 و Domain مستقیم بررسی کنید.
Domain مربوط به WireGuard/OpenVPN باید DNS-only و مستقیم به VPS باشد.

## CI
- Unit tests
- Browser Smoke Playwright
- Bash syntax
- JavaScript syntax
- Xray Core 26.3.27
- WireGuard legacy repair placement regression
- WireGuard no-handshake / external UDP diagnostic regression
- OpenVPN domain regression
- Licensing / Owner Control Center / Remote Support regressions

## Release Status
Release Candidate only. Stable requires real VPS external-client UAT.
