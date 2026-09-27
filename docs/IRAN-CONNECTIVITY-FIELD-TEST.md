# Iran Connectivity Field Test

این سند برای تست از یک Client واقعی داخل ایران است. اجرای تست روی خود VPS یا CI جایگزین این مرحله نیست.

## اصل مهم

شرایط شبکه ایران می‌تواند بین اپراتور، شهر، ساعت، IPv4/IPv6 و مسیر بین‌الملل متفاوت باشد. بنابراین هیچ Build نباید صرفاً بر اساس Server-side diagnostics با برچسب «در ایران کار می‌کند» منتشر شود.

## حداقل ماتریس

| Protocol | Profile | Mobile | Fixed | Reconnect | DNS | Traffic | Result |
|---|---|---|---|---|---|---|---|
| SSH/NPV | Native | ☐ | ☐ | ☐ | N/A | ☐ | Pending |
| Xray | VLESS/REALITY | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| Xray | VMess | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| Xray | Trojan | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| Xray | Shadowsocks | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| Xray | Hysteria2 | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| WireGuard | Native | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
| OpenVPN | Published transport | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |

## ثبت نتیجه

برای هر مورد ثبت شود:
- تاریخ و ساعت
- نام ISP/اپراتور
- Mobile/Fixed
- Client OS
- Client app/version
- Endpoint و Port بدون درج Credential
- نتیجه Handshake
- زمان اتصال
- Download test
- Reconnect
- توضیح خطا در صورت Fail

## ابزار کمکی

`scripts/iran-field-preflight.sh` فقط Reachability پایه را بررسی می‌کند. PASS شدن آن به معنی PASS شدن VPN/Proxy نیست؛ Handshake واقعی هر Client همچنان لازم است.
