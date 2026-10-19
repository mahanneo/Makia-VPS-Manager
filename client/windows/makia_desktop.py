#!/usr/bin/env python3
"""MAKIA Desktop — native Windows client shell around the existing connector.

This UI never receives a delivered VPN private key. Instead, the existing
privileged connector redeems an account/device-bound one-use ticket over HTTPS.
No password and no raw bearer token are written to disk.
"""
import base64
import ctypes
from ctypes import wintypes
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from tkinter import messagebox, ttk

VERSION="0.1.0-rc1"
DEFAULT_CONTROLLER="https://p.mahinet.shop"
ROOT=Path(os.environ.get("LOCALAPPDATA") or Path.home())/"Makia"/"Desktop"
STORE=ROOT/"device.json"
CONNECTOR_STATE=Path(os.environ.get("LOCALAPPDATA") or Path.home())/"Makia"/"Connector"/"state.json"
IP_ENDPOINTS=("https://api.ipify.org?format=json","https://api4.ipify.org?format=json")
HEADERS={"X-Makia-Desktop":"1","User-Agent":"MakiaDesktop/"+VERSION}
COLOR_BG="#0a1020"
COLOR_CARD="#121d31"
COLOR_EDGE="#27364e"
COLOR_ACCENT="#6ca8fc"
COLOR_TEXT="#eaf2ff"
COLOR_MUTED="#9bacbf"
COLOR_GOOD="#4ddab5"


def origin(value):
    p=urllib.parse.urlsplit(str(value or "").strip())
    if p.scheme!="https" or not p.netloc or not p.hostname or p.username or p.password or p.path not in {"","/"} or p.query or p.fragment:
        raise ValueError("آدرس پنل باید HTTPS و بدون مسیر یا رمز باشد.")
    if not re.fullmatch(r"[A-Za-z0-9.:-]{1,253}",p.netloc):
        raise ValueError("آدرس پنل معتبر نیست.")
    return "https://"+p.netloc.lower()


def dpapi(value,unprotect=False):
    """Windows CurrentUser DPAPI; no plaintext or cross-user fallback."""
    if os.name!="nt":
        raise RuntimeError("Secure credential storage requires Windows DPAPI")
    class Blob(ctypes.Structure):
        _fields_=[("cbData",wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_byte))]
    data=bytes(value)
    source=ctypes.create_string_buffer(data)
    inp=Blob(len(data),ctypes.cast(source,ctypes.POINTER(ctypes.c_byte)))
    out=Blob()
    crypt=ctypes.windll.crypt32
    func=crypt.CryptUnprotectData if unprotect else crypt.CryptProtectData
    func.argtypes=([ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,
                   ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)])
    func.restype=wintypes.BOOL
    if not func(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.pbData,out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))


def seal(s):
    return base64.b64encode(dpapi(s.encode("utf-8"))).decode("ascii")


def unseal(s):
    return dpapi(base64.b64decode(s.encode("ascii"),validate=True),True).decode("utf-8")


def read_saved():
    try:
        obj=json.loads(STORE.read_text("utf-8"))
        if not isinstance(obj,dict):
            raise ValueError("invalid device record")
        return obj
    except (OSError,ValueError,UnicodeError):
        return {}


def save_record(controller,device_key,token="",expires=0,remember=False):
    ROOT.mkdir(parents=True,exist_ok=True)
    values={"version":1,"controller":origin(controller),
            "device_key_sealed":seal(device_key) if device_key else "",
            "token_sealed":seal(token) if token and remember else "",
            "expires_at":int(expires) if token and remember else 0}
    temporary=STORE.with_suffix(".tmp")
    temporary.write_text(json.dumps(values),encoding="utf-8")
    os.replace(temporary,STORE)


def api_request(controller,path,token="",body=None,timeout=15):
    headers=dict(HEADERS)
    if token:
        headers["Authorization"]="Bearer "+token
    raw=None
    if body is not None:
        raw=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        headers["Content-Type"]="application/json"
    request=urllib.request.Request(origin(controller)+path,data=raw,headers=headers,
                                   method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            if response.status!=200:
                raise RuntimeError("Makia API HTTP "+str(response.status))
            return json.loads(response.read(512*1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail=json.loads(exc.read(4096).decode("utf-8")).get("detail","")
        except (ValueError,UnicodeError):
            detail=""
        # Neither request headers, raw URLs with tickets nor passwords are logged.
        raise RuntimeError(str(detail or ("Makia HTTP "+str(exc.code)))) from None
    except urllib.error.URLError:
        raise RuntimeError("ارتباط HTTPS با پنل Makia برقرار نشد.") from None


def check_ip():
    for url in IP_ENDPOINTS:
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"MakiaDesktop/0.1"})
            with urllib.request.urlopen(req,timeout=6) as response:
                ip=str(json.loads(response.read(1000).decode("utf-8")).get("ip") or "")
                if re.fullmatch(r"[0-9a-fA-F:.]{3,45}",ip):
                    return ip
        except (OSError,ValueError,UnicodeError):
            pass
    return ""


def launch_ticket(launch_url):
    u=urllib.parse.urlsplit(str(launch_url))
    q=urllib.parse.parse_qs(u.query)
    if u.scheme!="makia" or u.netloc!="connect" or set(q)!={"controller","ticket"}:
        raise ValueError("پاسخ بلیت اتصال معتبر نیست.")
    origin(q["controller"][0])
    ticket=q["ticket"][0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,128}",ticket):
        raise ValueError("بلیت اتصال نامعتبر است.")
    if os.name!="nt":
        raise RuntimeError("Windows connector is required")
    # Registry-based launcher is installed with MakiaClientConnector.exe.
    # Windows UAC appears only when its TUN process needs elevation.
    os.startfile(launch_url)


def disconnect_connector():
    if os.name!="nt":
        raise RuntimeError("Windows connector is required")
    os.startfile("makia://disconnect")


def fmt_bytes(n):
    try: value=float(n or 0)
    except (TypeError,ValueError): value=0
    for unit in ("B","KB","MB","GB","TB"):
        if value<1024 or unit=="TB": return f"{value:.1f} {unit}"
        value/=1024


class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title("MAKIA Desktop")
        self.root.geometry("510x660")
        self.root.minsize(460,580)
        self.root.configure(bg=COLOR_BG)
        self.events=queue.Queue()
        self.controller=DEFAULT_CONTROLLER
        self.device_key=""
        self.token=""
        self.expires=0
        self.remember=True
        self.account={}
        self.items=[]
        self.baseline=""
        self.busy=False
        self.build()
        saved=read_saved()
        self.controller=str(saved.get("controller") or DEFAULT_CONTROLLER)
        self.url.set(self.controller)
        try:
            self.device_key=unseal(saved.get("device_key_sealed")) if saved.get("device_key_sealed") else ""
            if saved.get("expires_at",0)>int(time.time()) and saved.get("token_sealed"):
                self.token=unseal(saved["token_sealed"])
                self.expires=int(saved["expires_at"])
        except (ValueError,RuntimeError,OSError):
            self.token=""
            self.device_key=""
        self.root.after(100,self.drain)
        if self.token:
            self.run_job("resume",self.load_account)
        else:
            self.show_login()

    def build(self):
        tk.Label(self.root,text="MAKIA",font=("Segoe UI",26,"bold"),fg=COLOR_ACCENT,
                 bg=COLOR_BG).pack(pady=(22,0))
        tk.Label(self.root,text="DESKTOP  •  WINDOWS FULL DEVICE",font=("Segoe UI",9),
                 fg=COLOR_MUTED,bg=COLOR_BG).pack(pady=(0,15))
        self.panel=tk.Frame(self.root,bg=COLOR_CARD,highlightbackground=COLOR_EDGE,highlightthickness=1)
        self.panel.pack(fill="both",expand=True,padx=22,pady=(0,12))
        self.message=tk.StringVar(value="در حال آماده‌سازی…")
        tk.Label(self.root,textvariable=self.message,font=("Segoe UI",9),fg=COLOR_MUTED,
                 bg=COLOR_BG,wraplength=455).pack(pady=(0,15))
        self.url=tk.StringVar(value=DEFAULT_CONTROLLER)
        self.username=tk.StringVar()
        self.password=tk.StringVar()
        self.keep=tk.BooleanVar(value=True)

    def clear_panel(self):
        for child in self.panel.winfo_children(): child.destroy()

    def label(self,text,size=11,fg=COLOR_TEXT,pady=6):
        return tk.Label(self.panel,text=text,font=("Segoe UI",size),
                        fg=fg,bg=COLOR_CARD,anchor="e",justify="right",wraplength=420)

    def entry(self,var,show=None):
        e=tk.Entry(self.panel,textvariable=var,show=show,justify="left",font=("Segoe UI",11),
                   bg="#0b1425",fg=COLOR_TEXT,insertbackground=COLOR_TEXT,
                   relief="flat",highlightthickness=1,highlightbackground=COLOR_EDGE)
        e.pack(fill="x",padx=24,ipady=9,pady=(0,9))
        return e

    def button(self,title,callback,accent=False):
        return tk.Button(self.panel,text=title,command=callback,
                  font=("Segoe UI",11,"bold"),bg=COLOR_ACCENT if accent else "#243955",
                  fg="#081323" if accent else COLOR_TEXT,activebackground="#85baff",
                  relief="flat",bd=0,cursor="hand2",padx=12,pady=10)

    def show_login(self):
        self.clear_panel()
        self.label("ورود به حساب اشتراک Makia",15).pack(fill="x",padx=24,pady=(25,13))
        self.label("آدرس پنل",10,fg=COLOR_MUTED).pack(fill="x",padx=24)
        self.entry(self.url)
        self.label("نام کاربری",10,fg=COLOR_MUTED).pack(fill="x",padx=24)
        self.entry(self.username)
        self.label("رمز عبور",10,fg=COLOR_MUTED).pack(fill="x",padx=24)
        pw=self.entry(self.password,"•")
        row=tk.Frame(self.panel,bg=COLOR_CARD)
        row.pack(fill="x",padx=24,pady=9)
        tk.Checkbutton(row,text="حفظ ورود روی این ویندوز تا ۳۰ روز (بدون ذخیره رمز)",
             variable=self.keep,fg=COLOR_TEXT,bg=COLOR_CARD,selectcolor="#253550",
             activebackground=COLOR_CARD,activeforeground=COLOR_TEXT,
             font=("Segoe UI",9)).pack(anchor="e")
        self.button("ورود امن",self.submit_login,True).pack(fill="x",padx=24,pady=13)
        self.label("روی کامپیوتر مشترک، حفظ ورود را غیرفعال کنید.",9,fg=COLOR_MUTED).pack(fill="x",padx=24)
        pw.bind("<Return>",lambda _:self.submit_login())
        self.message.set("برای تونل کامل ویندوز، Connector و موتور سازگار لازم است.")

    def run_job(self,label,task,*args):
        if self.busy: return
        self.busy=True
        self.message.set("در حال "+label+"…")
        def runner():
            try: self.events.put((label,True,task(*args)))
            except Exception as exc: self.events.put((label,False,str(exc)))
        threading.Thread(target=runner,daemon=True).start()

    def drain(self):
        while True:
            try: label,ok,value=self.events.get_nowait()
            except queue.Empty: break
            self.busy=False
            if not ok:
                if label=="resume" or ("session" in str(value).lower() and label!="connect"):
                    self.token=""
                    try: save_record(self.controller,self.device_key)
                    except Exception: pass
                    self.show_login()
                self.message.set("خطا: "+str(value)[:220])
            elif label in ("login","resume","refresh"):
                self.account=value.get("account") or {}
                self.items=value.get("items") or []
                self.show_home()
                self.message.set("حساب آماده است. سرویس را انتخاب کنید؛ اتصال فقط بعد از تست IP تأیید می‌شود.")
            elif label=="connect":
                self.message.set(value)
            elif label=="disconnect":
                self.message.set("دستور قطع ارسال شد؛ خروج از VPN را بررسی کنید.")
        self.root.after(170,self.drain)

    def submit_login(self):
        try: self.controller=origin(self.url.get())
        except ValueError as exc:
            self.message.set(str(exc));return
        username=self.username.get().strip()
        password=self.password.get()
        remember=self.keep.get()
        self.password.set("")
        if not username or not password:
            self.message.set("نام کاربری و رمز را وارد کنید.");return
        self.run_job("login",self.login,username,password,remember)

    def login(self,username,password,remember):
        result=api_request(self.controller,"/client/desktop/login",body={
            "username":username,"password":password,"device_key":self.device_key,
            "device_label":"Windows · Makia Desktop","remember_device":remember
        })
        self.token=result["token"]
        self.device_key=result["device_key"]
        self.expires=int(result["expires_at"])
        self.remember=remember
        save_record(self.controller,self.device_key,self.token,self.expires,remember)
        self.username.set(username)
        return self.load_account()

    def load_account(self):
        account=api_request(self.controller,"/client/desktop/me",self.token)
        items=api_request(self.controller,"/client/desktop/access",self.token)["items"]
        return {"account":account,"items":items}

    def show_home(self):
        self.clear_panel()
        a=self.account
        self.label(a.get("display_name") or a.get("username") or "Makia",15).pack(fill="x",padx=24,pady=(22,0))
        left=int(a.get("quota_bytes") or 0)
        used=int(a.get("used_bytes") or 0)
        self.label(f"حجم مصرفی: {fmt_bytes(used)}  /  {fmt_bytes(left) if left else 'نامحدود'}",10,fg=COLOR_MUTED).pack(fill="x",padx=24,pady=5)
        self.label("سرویس‌های قابل اتصال",11).pack(fill="x",padx=24,pady=(12,5))
        self.listbox=tk.Listbox(self.panel,font=("Segoe UI",10),height=10,bg="#0b1425",
                        fg=COLOR_TEXT,selectbackground="#305a9a",selectforeground="#ffffff",
                        relief="flat",highlightthickness=1,highlightbackground=COLOR_EDGE)
        self.listbox.pack(fill="both",expand=True,padx=24,pady=(0,12))
        for item in self.items:
            title=item.get("label") or item.get("name") or item.get("protocol") or "Makia"
            state=" ✓" if item.get("available") else " (غیرفعال)"
            self.listbox.insert("end",f" {title}  ·  {item.get('engine') or item.get('protocol') or ''}{state}")
        if self.items:self.listbox.selection_set(0)
        self.button("اتصال VPN",self.submit_connect,True).pack(fill="x",padx=24,pady=4)
        self.button("قطع اتصال",lambda:self.run_job("disconnect",disconnect_connector)).pack(fill="x",padx=24,pady=4)
        tools=tk.Frame(self.panel,bg=COLOR_CARD);tools.pack(fill="x",padx=24,pady=11)
        tk.Button(tools,text="↻ تازه‌سازی",command=lambda:self.run_job("refresh",self.load_account),
                  bg=COLOR_CARD,fg=COLOR_ACCENT,relief="flat").pack(side="right")
        tk.Button(tools,text="خروج از حساب",command=self.logout,
                  bg=COLOR_CARD,fg=COLOR_MUTED,relief="flat").pack(side="left")
        self.label("اتصال کامل دستگاه ممکن است درخواست مجوز Windows UAC داشته باشد.",9,fg=COLOR_MUTED).pack(fill="x",padx=24,pady=2)

    def submit_connect(self):
        selected=self.listbox.curselection()
        if not selected:
            self.message.set("ابتدا یک سرویس را انتخاب کنید.");return
        item=self.items[selected[0]]
        if not item.get("available"):
            self.message.set("این اشتراک برای اتصال فعال نیست.");return
        if str(item.get("engine") or "").lower() not in {"xray","outline","ssh","wireguard","openvpn","openvpn_wstunnel","openvpn-wstunnel"}:
            self.message.set("این نوع پروفایل هنوز در Connector ویندوز پشتیبانی نشده است.");return
        self.run_job("connect",self.connect,item)

    def connect(self,item):
        # Never expose a delivered VPN secret in the UI or persistent state.
        baseline=check_ip()
        kind=str(item["delivery_kind"])
        identifier=int(item["delivery_id"])
        response=api_request(self.controller,f"/client/desktop/ticket/{kind}/{identifier}",
                             self.token,body={})
        launch_ticket(response["launch_url"])
        # UAC + tunnel startup can take time. Poll actual HTTPS egress rather
        # than declaring Connected when the protocol URL is merely opened.
        if not baseline:
            return "دستور اتصال ارسال شد. IP مستقیم در دسترس نبود؛ اتصال هنوز تأیید نشده است."
        for _ in range(12):
            time.sleep(3)
            ip=check_ip()
            if ip and ip!=baseline:
                return f"✓ اتصال HTTPS تأیید شد: {baseline} → {ip}"
        return "اتصال اجرا شد، اما تغییر IP خروجی تأیید نشد؛ لاگ Connector را بررسی کنید."

    def logout(self):
        if not messagebox.askyesno("خروج امن","از حساب این دستگاه خارج شوید؟"):
            return
        token=self.token
        self.token=""
        try: save_record(self.controller,self.device_key)
        except Exception: pass
        self.account={};self.items=[]
        self.show_login()
        if token:
            def remote_logout():
                try: api_request(self.controller,"/client/desktop/logout",token,body={})
                except Exception: pass
            threading.Thread(target=remote_logout,daemon=True).start()
        self.message.set("اطلاعات ورود این دستگاه پاک شد. تونل فعال را جداگانه قطع کنید.")

    def run(self):
        self.root.mainloop()


if __name__=="__main__":
    if sys.platform!="win32":
        raise SystemExit("Makia Desktop requires Windows")
    App().run()
