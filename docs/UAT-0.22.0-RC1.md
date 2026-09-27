# Full Stack Ready UAT — Makia VPS Manager 0.22.0-rc1

هدف این UAT این است که نصب تازه یا Upgrade بدون ورود به صفحه Setup، یک سرور آمادهٔ ساخت User/Client تحویل دهد.

## A. Clean install gate

روی Ubuntu 22.04 یا 24.04 تازه نصب را اجرا کنید. پایان موفق Installer فقط زمانی PASS است که:

- Makia backend، Nginx، Policy Enforcer، Metrics، Traffic Collector و Fail2ban فعال باشند.
- Xray Core نصب باشد، Config معتبر داشته باشد و سرویس xray Active باشد.
- WireGuard نصب باشد، wg0.conf ساخته شده باشد، wg-quick@wg0 Active باشد و Listener/NAT/FORWARD سالم باشند.
- OpenVPN + Easy-RSA نصب باشند، server.conf و PKI ساخته شده باشند، openvpn-server@server Active و Listener فعال باشد.
- Stunnel tooling نصب باشد.
- `sudo makia-doctor` بدون FAIL تمام شود.
- `sudo makia-uat-smoke` با `HOST SMOKE: PASS` تمام شود.

## B. Upgrade from SSH-only installation

از یک نصب 0.21 که Xray/WireGuard/OpenVPN در آن نصب یا Bootstrap نشده‌اند:

1. `sudo makia-upgrade`
2. تأیید کنید Xray به‌صورت خودکار نصب و Active شده است.
3. تأیید کنید wg0 به‌صورت خودکار ساخته و Active شده است.
4. تأیید کنید OpenVPN server + PKI به‌صورت خودکار ساخته و Active شده‌اند.
5. Stunnel باید نصب شده باشد.
6. هیچ SSH User، DB record یا تنظیم موجود نباید حذف شود.

## C. Existing configuration preservation

روی سروری که از قبل Xray inbound، WireGuard peer و OpenVPN client دارد Upgrade کنید:

- Xray config نباید جایگزین Empty config شود.
- wg0.conf و PrivateKey/Peerها باید حفظ شوند.
- OpenVPN CA، server certificate، client certificateها و CRL باید حفظ شوند.
- Runtime repair فقط در صورت نیاز انجام شود.
- Native/Protected exports موجود باید همچنان قابل دسترسی باشند.

## D. Automatic port allocation

سناریوهای زیر را تست کنید:

| وضعیت قبل از Provision | نتیجه |
|---|---|
| TCP/443 توسط Nginx | WireGuard روی UDP/443 مجاز |
| UDP/443 اشغال | WireGuard باید Port fallback آزاد انتخاب کند |
| UDP/1194 آزاد | OpenVPN روی UDP/1194 |
| UDP/1194 اشغال | OpenVPN باید Port fallback آزاد انتخاب کند |
| Port fallback انتخاب شد | همان Port باید در Settings defaults ذخیره شود |

هیچ سرویس موجود نباید برای آزاد کردن Port متوقف شود.

## E. User-only workflow

بعد از Clean Install، بدون استفاده از هیچ دکمه Install/Bootstrap:

- SSH: یک User بسازید و Login واقعی تست کنید.
- Xray: یک VLESS/REALITY Client بسازید و اتصال واقعی بیرون VPS تست کنید.
- WireGuard: یک Peer بسازید، Config را Import و Handshake/Internet routing را تست کنید.
- OpenVPN: یک Client بسازید، OVPN را Import و اتصال/Internet routing را تست کنید.

سپس VMess، Trojan و در صورت داشتن Domain/TLS معتبر Hysteria2 را نیز بررسی کنید.

## F. Important boundary

Xray Engine از ابتدا آماده است، اما هر Inbound/Client هنگام ساخت User ایجاد می‌شود. Hysteria2/TLS به Domain و Certificate معتبر نیاز دارد؛ Installer نباید Certificate جعلی یا ناامن تولید کند.

Stable فقط بعد از PASS شدن Clean Install، SSH-only Upgrade، preservation و external-client connectivity مجاز است.
