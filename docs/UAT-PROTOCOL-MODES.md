# Makia Protocol Modes — Host UAT

این سند برای قابلیت‌های جدید Connection Modes است. تا زمانی که Host و Client واقعی PASS نشوند، این قابلیت‌ها Stable/verified محسوب نمی‌شوند.

## Modes

- IKEv2: strongSwan + EAP-MSCHAPv2، UDP/500 و UDP/4500.
- WireGuard: موتور موجود Makia.
- UDP: OpenVPN Server روی UDP.
- TCP: OpenVPN Server روی TCP.
- Stealth: OpenVPN TCP پشت TLS واقعی Stunnel.
- WStunnel: WireGuard UDP از داخل WSS/WStunnel.

## Important port rule

روی یک IPv4، چند سرویس نمی‌توانند هم‌زمان مالک TCP/443 باشند. Makia نباید این وضعیت را Fake کند.

- HTTPS/Nginx معمولاً TCP/443 را نگه می‌دارد.
- WireGuard می‌تواند UDP/443 را هم‌زمان استفاده کند.
- Stealth و WStunnel باید TCP port آزاد داشته باشند مگر در آینده ingress/multiplexing واقعی اضافه شود.
- UDP و TCP در کارت‌های OpenVPN دو حالت یک Server Profile فعال هستند، نه دو instance جعلی هم‌زمان.

## Host gate

بعد از upgrade:

```bash
sudo makia-upgrade
sudo makia-doctor
sudo makia-uat-smoke
```

Toolingهای مورد انتظار:

```bash
command -v ipsec
command -v wstunnel
command -v wg
command -v openvpn
command -v stunnel4
```

### IKEv2

ابتدا HTTPS دامنه باید معتبر باشد. سپس Configure از Protocol Hub و یک User تست ساخته شود.

```bash
sudo ipsec statusall
sudo ss -lunp | grep -E ':(500|4500)\b'
sudo systemctl status makia-ikev2-network --no-pager
```

از Client واقعی: import/configure، authentication، DNS، browsing، reconnect.

### UDP / TCP OpenVPN

هر دو حالت جداگانه تست شوند. تغییر transport باید backup/restart/listener verification/rollback داشته باشد.

### Stealth

OpenVPN باید ابتدا TCP باشد. سپس Stealth روی TCP port آزاد Configure شود.

```bash
sudo systemctl status stunnel4 --no-pager
sudo cat /etc/stunnel/makia-openvpn.conf
```

Client باید ابتدا stunnel local listener را اجرا کند و OpenVPN را به localhost متصل کند.

### WStunnel

WireGuard باید سالم باشد. WStunnel روی WSS port آزاد Configure شود.

```bash
wstunnel --version
sudo systemctl status makia-wstunnel --no-pager
sudo cat /etc/makia-vps-manager/wstunnel.env
```

Client باید WStunnel local UDP forward را اجرا کند و WireGuard Endpoint را روی local endpoint قرار دهد.

## Iran field gate

برای هر Mode که قرار است منتشر/تبلیغ شود، حداقل یک Mobile ISP و یک Fixed/Wi-Fi داخل ایران باید این موارد را ثبت کند:

- handshake/login
- DNS
- browsing/meaningful traffic
- reconnect
- حداقل چند دقیقه اتصال پایدار

PASS شدن CI یا VPS فقط سلامت سمت Server را ثابت می‌کند و جای Client field test را نمی‌گیرد.
