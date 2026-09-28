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
- OpenVPN UDP و TCP باید به‌صورت دو Runtime مستقل قابل فعال‌سازی هم‌زمان باشند؛ هر کدام Listener، tunnel device و subnet جدا دارد و PKI مشترک را استفاده می‌کند.

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

ابتدا UDP موجود را فعال نگه دارید و سپس از کارت TCP، TCP را نیز فعال کنید. فعال‌سازی TCP **نباید UDP را متوقف یا Config اصلی را بازنویسی کند**.

```bash
sudo systemctl status openvpn-server@server --no-pager
sudo systemctl status openvpn-server@transport-tcp --no-pager
sudo ss -lunp | grep openvpn
sudo ss -ltnp | grep openvpn
```

در Protocol Hub هر دو کارت UDP و TCP باید هم‌زمان READY شوند. برای یک Client موجود، فایل UDP و TCP جدا صادر و هر دو از Client واقعی تست شوند.

### Stealth

Stealth باید در صورت نبود TCP Backend، یک OpenVPN TCP Runtime مستقل را خودکار آماده کند؛ UDP موجود نباید قطع شود. سپس Stunnel روی یک TCP port آزاد مثل 9443 Configure شود.

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
