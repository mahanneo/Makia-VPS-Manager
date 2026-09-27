# Makia VPS Manager 0.27.0-rc1 — Protocol Modes UAT

این Release Candidate بخش **Change Protocol** را با Backend واقعی برای IKEv2، WireGuard، OpenVPN UDP/TCP، Stealth/TLS و WStunnel/WSS اضافه می‌کند.

> این نسخه Stable نیست. فعال بودن Server Runtime به معنی تأیید اتصال از همه شبکه‌های ایران نیست.

## 1. Upgrade gate

روی VPS واقعی:

```bash
sudo makia-upgrade
cat /opt/makia-vps-manager/VERSION
sudo makia-doctor
sudo makia-uat-smoke
```

انتظار:
- Version برابر `0.27.0-rc1`.
- کاربران، SQLite، Xray، WireGuard keys، OpenVPN PKI، Nginx و Certificateهای موجود حفظ شوند.
- `swanctl`، `wstunnel` و Stunnel tooling نصب باشند.
- Unitهای `makia-ikev2-firewall`، `makia-stealth` و `makia-wstunnel` نصب باشند.
- هیچ Package Manager از داخل Web Backend اجرا نشود.

## 2. Change Protocol UI

در **Network / Ports → Change Protocol** دقیقاً شش Mode دیده شود:
1. IKEv2
2. WireGuard
3. UDP
4. TCP
5. Stealth
6. WStunnel

هر Mode باید وضعیت واقعی Runtime را نشان دهد. گزینه بدون Backend/Listener واقعی نباید READY نمایش داده شود.

## 3. IKEv2 / StrongSwan

پیش‌نیاز:
- Domain معتبر.
- Certificate معتبر Let's Encrypt.
- UDP/500 و UDP/4500 در Provider firewall/UFW قابل دسترسی.

Checks:
- Configure IKEv2 بدون Certificate باید با پیام واضح Fail شود.
- `swanctl --list-conns` باید Connection مدیریت‌شده Makia را نشان دهد.
- StrongSwan باید روی UDP/500 و UDP/4500 Listen کند.
- NAT/Forwarding برای Pool مدیریت‌شده فعال باشد.
- ساخت User باید EAP-MSCHAPv2 Credential مستقل بسازد.
- Native credential export و Protected ZIP برای User کار کند.
- حذف User باید Credential را از Runtime حذف کند.
- تست واقعی iOS/macOS/Windows یا Android-compatible client: IKE handshake، DNS، Browse، Traffic و Reconnect.

## 4. WireGuard

Engine موجود حفظ می‌شود:
- UDP port واقعی.
- Peer create/delete.
- QR + Native config.
- Handshake و RX/TX.
- DNS / MTU / Keepalive / AllowedIPs / CIDR.
- Client واقعی باید اینترنت و Reconnect را PASS کند.

## 5. OpenVPN UDP

Mode UDP همان OpenVPN Server واقعی است، نه Label جدا:
- تنظیم Transport به UDP.
- Listener واقعی UDP روی Port انتخابی.
- Existing PKI حفظ شود.
- Client export از Runtime فعلی Port/Transport را بگیرد.
- DNS / Browsing / Reconnect روی Client واقعی PASS شود.

## 6. OpenVPN TCP

Mode TCP همان OpenVPN Server واقعی است:
- تغییر UDP → TCP باید Backup/Restart/Verify/Rollback داشته باشد.
- Listener واقعی TCP ظاهر شود.
- PKI و Clientها حفظ شوند.
- سپس Client واقعی Import/Connect/Traffic/Reconnect تست شود.

> معماری فعلی OpenVPN یک Server Profile مدیریت‌شده دارد؛ UDP و TCP دو Label جعلی هم‌زمان نیستند. تغییر Mode، Transport همان Profile را تغییر می‌دهد.

## 7. Stealth / Stunnel

Stealth فقط وقتی قابل فعال‌سازی است که:
- OpenVPN روی TCP فعال باشد.
- Domain Certificate معتبر باشد.
- Port خارجی آزاد باشد.

Checks:
- Stunnel باید Listener واقعی روی Port انتخابی داشته باشد.
- Target فقط `127.0.0.1:<OpenVPN TCP port>` باشد.
- سرویس `makia-stealth` Active باشد.
- در تداخل Port با HTTPS یا سرویس دیگر Configure باید Reject شود.
- Client-side Stunnel + OpenVPN باید به‌صورت واقعی تست شود.

## 8. WStunnel / WSS

Makia از wstunnel pinned release استفاده می‌کند و checksum را قبل از install verify می‌کند.

Checks:
- `wstunnel --version` موجود باشد.
- WSS فقط با Certificate واقعی Domain فعال شود.
- Server forwarding به OpenVPN/TCP روی loopback محدود باشد.
- Path Prefix تصادفی/اختصاصی تنظیم شود.
- Port collision Reject شود.
- Client command تولیدشده با wstunnel Client اجرا شود.
- OpenVPN Client به Local endpoint متصل و DNS/Browse/Traffic/Reconnect تست شود.

## 9. Port safety

TCP و UDP مستقل ارزیابی شوند.
- WireGuard UDP/443 می‌تواند کنار HTTPS TCP/443 باشد.
- OpenVPN UDP/443 می‌تواند کنار HTTPS TCP/443 باشد.
- OpenVPN TCP، Stealth یا WStunnel نباید بدون Multiplexer واقعی روی TCP/443 با Nginx هم‌زمان Bind شوند.
- Makia باید Collision را Reject کند؛ نباید با Stop کردن مخفیانه سرویس دیگر Port آزاد کند.

## 10. Iran field gate

برای هر Mode منتشرشده حداقل:
- یک Mobile ISP داخل ایران
- یک Fixed/Wi-Fi path داخل ایران

ثبت شود:
- Import/setup
- Handshake/Login
- DNS
- Browsing
- Traffic
- Disconnect/Reconnect

**0.27.0 Stable فقط بعد از PASS شدن Host UAT و Client Field Test واقعی مجاز است.**
