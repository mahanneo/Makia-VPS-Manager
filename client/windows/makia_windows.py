#!/usr/bin/env python3
"""Makia Windows launcher. Secure sign-in remains in the official HTTPS Client Portal.

This UI is intentionally not a parallel VPN engine and never stores passwords,
bearer tokens, protocol shares, device secrets or proxy credentials.
"""
import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

APP_VERSION="1.6.5.1"
APP_TITLE="Makia Windows"
PORTAL_URL="https://p.mahinet.shop/client/"
IP_CHECK_URL="https://api.ipify.org?format=json"
ROOT=Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())/"Makia"/"Connector"
STATE=ROOT/"state.json"


def local_state():
    """Untrusted local metadata; never present it as verified VPN connectivity."""
    try:
        if STATE.is_file():
            obj=json.loads(STATE.read_text(encoding="utf-8"))
            if isinstance(obj,dict) and obj.get("mode") in {
                "process","multi-process","wireguard"
            }:
                return "آخرین فرمان اتصال ثبت شده؛ وضعیت IP خروجی را بررسی کنید."
    except (OSError,ValueError,UnicodeError):
        pass
    return "اتصال فعالی در وضعیت محلی ثبت نشده است."


def connector_path():
    # GUI and connector ship side by side; never execute arbitrary path from
    # a URL, network share, environment override or user-owned config file.
    return Path(sys.executable).resolve().parent/"MakiaClientConnector.exe"


def open_official_portal():
    return webbrowser.open(PORTAL_URL,new=2)


def main():
    if "--healthcheck" in sys.argv:
        print(json.dumps({"ok":True,"app":APP_TITLE,"version":APP_VERSION,
                          "portal":PORTAL_URL,"password_stored":False},ensure_ascii=False))
        return 0
    if "--open-portal" in sys.argv:
        return 0 if open_official_portal() else 2

    window=tk.Tk()
    window.title(APP_TITLE+" · "+APP_VERSION)
    window.geometry("490x440")
    window.minsize(440,405)
    window.configure(bg="#0b1221")

    def label(text,**kw):
        return tk.Label(window,text=text,bg="#0b1221",fg=kw.pop("fg","#e9eefb"),
                        font=kw.pop("font",("Segoe UI",11)),justify="center",
                        wraplength=435,**kw)

    label("MAKIA",font=("Segoe UI Semibold",26),fg="#b9c8ff").pack(pady=(26,1))
    label("WINDOWS · FULL DEVICE CONNECTOR",font=("Segoe UI",9),
          fg="#95a8ce").pack(pady=(0,18))
    label("ورود و انتخاب سرویس در پنل امن Makia انجام می‌شود.",
          font=("Segoe UI",11)).pack(pady=5)
    label("رمز حساب در این برنامه ذخیره نمی‌شود.",font=("Segoe UI",9),
          fg="#91a8cd").pack(pady=(0,14))

    status=tk.StringVar(value=local_state())
    tk.Label(window,textvariable=status,bg="#182439",fg="#d9e7ff",
             font=("Segoe UI",10),wraplength=400,justify="center",
             padx=13,pady=12).pack(fill="x",padx=28,pady=(2,12))

    def button(text,command,primary=False):
        return tk.Button(window,text=text,command=command,cursor="hand2",
                         bg="#6579ed" if primary else "#223451",
                         fg="white",activebackground="#5264ca" if primary else "#304365",
                         activeforeground="white",relief="flat",bd=0,
                         font=("Segoe UI Semibold",11),pady=9)

    button("ورود / انتخاب سرویس و اتصال",lambda:(
        open_official_portal() or messagebox.showwarning(
            APP_TITLE,"مرورگر باز نشد؛ این آدرس را دستی باز کنید:\n"+PORTAL_URL)
    ),True).pack(fill="x",padx=28,pady=5)

    def disconnect():
        if not messagebox.askyesno(APP_TITLE,"اتصال VPN این ویندوز قطع شود؟"):
            return
        exe=connector_path()
        if not exe.is_file():
            messagebox.showerror(APP_TITLE,"Connector نصب نیست؛ برنامه را دوباره نصب کنید.")
            return
        try:
            # Connector itself has a UAC manifest; explicit user consent
            # is needed for a full-device VPN/tunnel disconnection.
            proc=subprocess.run([str(exe),"--disconnect"],capture_output=True,
                                text=True,timeout=45,check=False)
            if proc.returncode:
                messagebox.showerror(APP_TITLE,
                                     "قطع اتصال تأیید نشد. لاگ Connector را بررسی کنید.")
            else:
                status.set(local_state())
                messagebox.showinfo(APP_TITLE,"فرمان قطع اتصال اجرا شد.")
        except (OSError,subprocess.TimeoutExpired):
            messagebox.showerror(APP_TITLE,"اجرای Connector ناموفق بود؛ اتصال را بررسی کنید.")

    button("قطع اتصال",disconnect).pack(fill="x",padx=28,pady=5)
    button("بررسی IP خروجی",lambda:webbrowser.open(IP_CHECK_URL,new=2)).pack(
        fill="x",padx=28,pady=5)
    button("تازه‌سازی وضعیت",lambda:status.set(local_state())).pack(
        fill="x",padx=28,pady=5)
    label("برای اتصال، داخل پنل روی «اتصال مستقیم» پروفایل خود بزنید.\n"
          "این پنجره وضعیت محلی را نشان می‌دهد، نه تضمین عبور اینترنت.",
          fg="#99a8c5",font=("Segoe UI",9)).pack(pady=(12,5))
    window.mainloop()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
