#!/usr/bin/env python3
"""Read-only Persian endpoint chooser for new Makia VPS installations."""
from pathlib import Path
import sys

SOURCE_ROOT=Path(__file__).resolve().parents[1]
if not (SOURCE_ROOT/"app"/"endpoint_preflight.py").exists():
    SOURCE_ROOT=Path("/opt/makia-vps-manager")
sys.path.insert(0,str(SOURCE_ROOT))
from app.endpoint_preflight import ALL, evaluate

OPTIONS=[
    ("ssh","SSH / NPV — اتصال مستقیم با IP یا دامنه"),
    ("wireguard","WireGuard — UDP، با IP یا دامنه"),
    ("openvpn","OpenVPN معمولی — با IP یا دامنه"),
    ("outline","Outline — خروجی مستقیم با IP یا دامنه"),
    ("xray-direct","Xray مستقیم — بسته به transport انتخاب‌شده"),
    ("browser-gateway","VPN مرورگر — دامنه و گواهی TLS ضروری"),
    ("openvpn-wstunnel","OpenVPN + WStunnel 443 — دامنه و TLS ضروری"),
    ("wstunnel-wss","WireGuard over WStunnel WSS — دامنه و TLS ضروری"),
    ("stealth-tls","Stealth TLS — دامنه و TLS ضروری"),
    ("ikev2-cert","IKEv2 با گواهی — دامنه و TLS ضروری"),
]

def main():
    print("\nMakia | راهنمای انتخاب IP یا دامنه (بدون تغییر تنظیمات)\n")
    for n,(_,desc) in enumerate(OPTIONS,1):
        print(f" {n:2}. {desc}")
    try:
        picked=int(input("\nشماره پروتکل: ").strip())
        if not (1<=picked<=len(OPTIONS)):
            raise ValueError()
    except (ValueError,EOFError):
        print("شماره معتبر وارد کنید.",file=sys.stderr)
        return 2
    protocol=OPTIONS[picked-1][0]
    try:
        address=input("IP عمومی یا نام دامنه (بدون https:// و پورت): ").strip()
        raw_port=input("پورت [Enter = پیش‌فرض]: ").strip()
        raw_server=input("IP عمومی VPS برای بررسی DNS [اختیاری]: ").strip()
        kwargs={"server_ipv4":raw_server}
        if raw_port:
            kwargs["port"]=int(raw_port)
        result=evaluate(protocol,address,**kwargs)
    except (EOFError,ValueError) as exc:
        print("خطا:",exc,file=sys.stderr)
        return 2
    print("\nنتیجه:", "مناسب برای ادامه تنظیمات" if result.ok else "نیازمند اصلاح قبل از ساخت کانفیگ")
    print(f"آدرس: {result.endpoint} | پورت: {result.port}/{result.transport}")
    print("گواهی TLS لازم است:", "بله" if result.needs_tls_certificate else "خیر")
    print("IP مستقیم پشتیبانی می‌شود:", "بله" if result.direct_ip_supported else "در حالت فعلی خیر")
    print("راهنما:", result.user_message_fa)
    for label,items in (("اشکال",result.errors),("هشدار",result.warnings),("قدم بعد",result.next_steps)):
        for item in items:
            print(f"- {label}: {item}")
    print("این ابزار فقط بررسی می‌کند؛ پروتکل، فایروال، گواهی یا پورت را تغییر نداده است.")
    return 0 if result.ok else 2

if __name__=="__main__":
    raise SystemExit(main())
