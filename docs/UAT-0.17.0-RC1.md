# Makia v0.17.0-rc1 — WireGuard / Endpoint Compatibility UAT

## هدف
این Release Candidate روی پایداری WireGuard، تشخیص واقعی Runtime و بررسی آمادگی IP/Domain برای SSH، Xray، WireGuard و OpenVPN تمرکز دارد.

## Upgrade
- از v0.16.0-rc1 با `sudo makia-upgrade` آپدیت شود.
- Data/License/Client artifacts حفظ شوند.
- اگر WireGuard قبلی وجود دارد، Updater قبل از UAT وضعیت forwarding/NAT/listener را بررسی کند.
- اگر Runtime ناسالم است، Repair امن با Backup انجام شود.
- اگر WireGuard قبل از Update سالم بوده و بعد از Repair سالم نشود، Update rollback شود.

## WireGuard Runtime
- `wg-quick@wg0` active باشد.
- `wg show interfaces` شامل wg0 باشد.
- UDP listener روی ListenPort دیده شود.
- `net.ipv4.ip_forward=1`.
- FORWARD rule ورودی و خروجی برای wg0 وجود داشته باشد.
- MASQUERADE برای subnet WireGuard روی uplink فعال باشد.
- PostUp ruleها idempotent و با `iptables -C ... || iptables -I` ساخته شوند.
- NAT به subnet WireGuard محدود باشد.
- Repair Runtime قبل از تغییر از wg0.conf Backup بگیرد.
- در Failure کانفیگ قبلی restore شود.

## IP / Domain
برای هر دو مقدار واقعی زیر جداگانه تست شود:
1. IPv4 عمومی VPS
2. دامنه مستقیم/DNS-only همان VPS

از Protocol Hub → IP / Domain Readiness استفاده شود.

برای هر Endpoint:
- SSH runtime + endpoint readiness
- Xray runtime + حداقل یک inbound
- WireGuard runtime + endpoint DNS/IP
- OpenVPN runtime + listener + endpoint DNS/IP

Domain باید A record مستقیم به IPv4 VPS داشته باشد.
برای WireGuard و OpenVPN، HTTP/CDN Proxy قابل قبول نیست.

## WireGuard Client Real-world UAT
- یک Peer جدید با Endpoint=Public IPv4 ساخته شود.
- Config روی موبایل/دسکتاپ خارج از VPS Import شود.
- Handshake برقرار شود.
- Internet routing و DNS کار کند.
- همان Peer با Endpoint=Domain مجدداً صادر/ساخته شود.
- Handshake و Internet routing تکرار شود.
- در Diagnostics، Latest Handshake و RX/TX قابل مشاهده باشند.

## OpenVPN Real-world UAT
- Client با Endpoint=IP ساخته و روی شبکه خارجی متصل شود.
- Client با Endpoint=Domain ساخته و متصل شود.
- udp4/tcp4-client حفظ شود.
- Domain در حالت DNS-only باشد.

## Xray Real-world UAT
- برای Endpoint=IP و Domain، حداقل VLESS/REALITY تست شود.
- برای TLS/Hysteria2 فقط Domain با Certificate معتبر استفاده شود.
- Xray Core config validation PASS باشد.
- سرویس پس از ساخت Client active بماند.

## SSH Real-world UAT
- Login با Public IP.
- Login با Domain.
- Policy/expiry/session controls حفظ شوند.

## UI
- Scrollbar سایدبار باریک، تیره/گرادیانی و هماهنگ با Glass UI باشد.
- Scrollbar سفید Native در Sidebar دیده نشود.
- WireGuard Diagnostics و Repair Runtime در Protocol Hub قابل دسترسی باشند.
- IP / Domain Readiness Matrix روی Desktop و Mobile قابل خواندن باشد.

## Regression Gates
- Python compile PASS
- Unit tests PASS
- JavaScript syntax PASS
- Bash syntax PASS
- UAT contracts v0.11 تا v0.17 PASS
- Browser Smoke PASS
- Xray 26.3.27 matrix PASS
- OpenVPN domain tests PASS
- WireGuard IP/domain tests PASS
- Online License / Remote Support tests PASS

## نکته
CI می‌تواند config generation، runtime rules، DNS logic و listener contracts را اعتبارسنجی کند، اما «اتصال واقعی از اینترنت» باید در UAT روی VPS واقعی و یک Client خارج از آن انجام شود.
