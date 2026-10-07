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
| WireGuard | Native · restricted profile | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |\n| WStunnel 443 | Full Device | ☐ | ☐ | ☐ | ☐ | ☐ | Pending |
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
\n## WireGuard 1.6.4 restricted-network checks\n\n- Server: UDP listener present, forwarding/NAT healthy, MTU 1280, bidirectional TCP MSS clamp READY.\n- Client: MTU 1280, PersistentKeepalive 15, AllowedIPs `0.0.0.0/0`, DNS fallback `1.1.1.1, 8.8.8.8`.\n- Test HTTPS-heavy sites and large downloads, not only ping.\n- If there is no recent handshake while the server is healthy, treat protocol-level UDP/WireGuard blocking as a field-network failure and switch to WStunnel 443 rather than repeatedly changing MTU.\n