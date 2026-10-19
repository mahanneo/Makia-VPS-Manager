"""Makia Windows Desktop — a browser-free front end for the existing connector.

The server owns accounts and one-time tickets. Only an opaque cookie is remembered
using Windows DPAPI; this application never persists account passwords or
delivered VPN profiles. Full-device connections may require Windows elevation.
"""
import ctypes
from ctypes import wintypes
import http.cookiejar
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
import urllib.error
import urllib.parse
import urllib.request

PRODUCT = "Makia Desktop"
VERSION = "1.6.5-desktop-rc1"
CONTROLLER = "https://p.mahinet.shop"
ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Makia" / "Desktop"
SESSION_FILE = ROOT / "session.dat"
CONNECTOR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Makia" / "Connector" / "bin" / "MakiaClientConnector.exe"
CONNECTOR_STATE = CONNECTOR.parent.parent / "state.json"
ENGINES = {"xray", "outline", "wireguard", "openvpn", "openvpn_wstunnel", "openvpn-wstunnel", "ssh"}
USER_AGENT = "MakiaDesktop/" + VERSION


def _blob(raw):
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(raw)
    return Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer, Blob


def protect(raw, decrypt=False):
    """DPAPI CurrentUser: encrypted session is unusable on a different user/PC."""
    if os.name != "nt":
        raise OSError("Windows DPAPI is required")
    source, keep, Blob = _blob(raw)
    target = Blob()
    dll = ctypes.windll.crypt32
    fn = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN: no dialogs, only current Windows account.
    if not fn(ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))


def _cookie(name, value, expires=None):
    return http.cookiejar.Cookie(
        0, name, value, None, False, urllib.parse.urlparse(CONTROLLER).hostname,
        False, False, "/client", True, True, expires, expires is None, None,
        None, {}, False,
    )


class ClientAPI:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.remember = True

    def _request(self, route, values=None, form=False):
        url = CONTROLLER + route
        if values is None:
            data = None
        elif form:
            data = urllib.parse.urlencode(values).encode("utf-8")
        else:
            data = json.dumps(values).encode("utf-8")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json",
                   "Cache-Control": "no-store"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
            headers["X-Makia-Client"] = "1"
            headers["Origin"] = CONTROLLER
        request = urllib.request.Request(url, data=data, headers=headers,
                                         method="POST" if data is not None else "GET")
        try:
            with self.opener.open(request, timeout=16) as response:
                body = response.read(2_000_000)
                content_type = response.headers.get("Content-Type", "")
                return json.loads(body) if "json" in content_type else {"ok": True}
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise PermissionError("نشست منقضی شده؛ دوباره وارد حساب شوید.") from None
            if exc.code == 403:
                raise PermissionError("حساب، دستگاه یا سرویس اجازه اتصال ندارد.") from None
            if exc.code == 429:
                raise RuntimeError("تلاش‌های ورود زیاد است؛ کمی بعد دوباره امتحان کنید.") from None
            raise RuntimeError("پاسخ ناموفق سرور: HTTP " + str(exc.code)) from None
        except urllib.error.URLError:
            raise RuntimeError("ارتباط امن با سرور برقرار نشد؛ اینترنت و آدرس پنل را بررسی کنید.") from None

    def login(self, username, password, remember=True):
        if not username.strip() or not password:
            raise ValueError("نام کاربری و رمز اشتراک لازم است.")
        self.remember = bool(remember)
        self._request("/client/login", {
            "username": username.strip(), "password": password,
            "device_label": "Windows / Makia Desktop",
            "remember_device": "1" if remember else "",
        }, form=True)
        account = self.me()  # A redirect or HTML response does not prove authentication.
        if remember:
            self.save()
        else:
            self.clear_saved()
        return account

    def me(self):
        return self._request("/client/api/me")

    def profiles(self):
        data = self._request("/client/api/protocols")
        return [x for x in data.get("items", []) if str(x.get("engine") or "").lower() in ENGINES]

    def ticket(self, item):
        kind = str(item.get("delivery_kind") or "")
        item_id = int(item.get("delivery_id") or 0)
        if kind not in ("protocol", "artifact") or item_id < 1:
            raise ValueError("پروفایل انتخاب‌شده معتبر نیست.")
        return self._request("/client/api/connect/{}/{}/ticket".format(kind, item_id), {})

    def logout(self):
        try:
            self._request("/client/logout", {}, form=True)
        except Exception:
            pass
        self.jar.clear()
        self.clear_saved()

    def save(self):
        payload = []
        for c in self.jar:
            if c.name in ("makia_client_session", "makia_client_device"):
                payload.append({"name": c.name, "value": c.value, "expires": c.expires})
        if not any(x["name"] == "makia_client_session" for x in payload):
            raise RuntimeError("سرور کوکی معتبر ورود برنگرداند.")
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_bytes(protect(json.dumps(payload).encode("utf-8")))
        tmp.replace(SESSION_FILE)

    def load(self):
        if not SESSION_FILE.exists():
            return False
        try:
            saved = json.loads(protect(SESSION_FILE.read_bytes(), decrypt=True))
            now = int(time.time())
            for item in saved:
                if item.get("name") not in ("makia_client_session", "makia_client_device"):
                    continue
                exp = item.get("expires")
                if exp is not None and int(exp) <= now:
                    continue
                self.jar.set_cookie(_cookie(item["name"], item["value"], exp))
            return any(c.name == "makia_client_session" for c in self.jar)
        except (OSError, ValueError, KeyError, TypeError):
            self.clear_saved()
            return False

    def clear_saved(self):
        try:
            SESSION_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def public_ip():
    # No application-level proxy: full-device TUN routes remain observable.
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with direct.open(urllib.request.Request(
            "https://api.ipify.org?format=json", headers={"User-Agent": USER_AGENT}
        ), timeout=9) as r:
            value = json.loads(r.read(200))["ip"]
            return value if isinstance(value, str) and 3 <= len(value) <= 45 else ""
    except (OSError, ValueError, KeyError):
        return ""


def connector(command):
    if not CONNECTOR.is_file():
        raise RuntimeError("موتور اتصال نصب نیست. Install-Makia.cmd را اجرا کنید.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run([str(CONNECTOR), command], capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=65, creationflags=flags, check=False)
    except OSError as exc:
        raise RuntimeError("مجوز Windows UAC برای اتصال رد شد یا موتور اجرا نشد.") from exc
    if result.returncode:
        # No raw ticket/configuration/process command lines in user-facing errors.
        raise RuntimeError("موتور اتصال موفق نشد. فایل connector.log را بررسی کنید.")
    return True


def active_state():
    try:
        raw = json.loads(CONNECTOR_STATE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


class Desktop:
    def __init__(self):
        self.api = ClientAPI()
        self.account = None
        self.items = []
        self.events = queue.Queue()
        self.busy = False
        self.root = tk.Tk()
        self.root.title("Makia Desktop · Windows")
        self.root.geometry("560x590")
        self.root.minsize(510, 540)
        self.root.configure(bg="#0e1424")
        self.root.option_add("*Font", "Segoe UI 10")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", padding=8, fieldbackground="#f8fafc")
        self.panel = tk.Frame(self.root, bg="#0e1424", padx=30, pady=22)
        self.panel.pack(fill="both", expand=True)
        self.heading = self.label("MAKIA", 28, "#ecf2ff", True)
        self.label("WINDOWS · FULL DEVICE VPN", 10, "#91a1c2")
        self.label("p.mahinet.shop  |  HTTPS", 10, "#7695cf")
        tk.Frame(self.panel, bg="#283650", height=1).pack(fill="x", pady=18)
        self.auth_frame = tk.Frame(self.panel, bg="#0e1424")
        self.auth_frame.pack(fill="x")
        self.label("ورود به حساب اشتراک", 14, "#ecf2ff", True, self.auth_frame)
        self.username = self.entry(self.auth_frame, "نام کاربری")
        self.password = self.entry(self.auth_frame, "رمز عبور", show="*")
        self.remember = tk.BooleanVar(value=True)
        tk.Checkbutton(self.auth_frame, text="حفظ ورود روی این ویندوز (بدون ذخیره رمز)",
                       variable=self.remember, bg="#0e1424", fg="#d7e1f7",
                       activebackground="#0e1424", activeforeground="#ffffff",
                       selectcolor="#253457").pack(anchor="e", pady=8)
        self.login_btn = self.button(self.auth_frame, "ورود امن", self.login, "#517cf6")
        self.main_frame = tk.Frame(self.panel, bg="#0e1424")
        self.status = tk.StringVar(value="در حال آماده‌سازی…")
        self.account_text = tk.StringVar(value="")
        self.label_var(self.account_text, "#d8e5fd", 11, self.main_frame)
        self.label("سرویس‌های این حساب", 11, "#eaf0ff", True, self.main_frame)
        self.choice = ttk.Combobox(self.main_frame, state="readonly", font=("Segoe UI", 10))
        self.choice.pack(fill="x", pady=12)
        self.connect_btn = self.button(self.main_frame, "●  اتصال VPN", self.connect, "#3cbd9b")
        self.disconnect_btn = self.button(self.main_frame, "■  قطع اتصال", self.disconnect, "#bf5264")
        self.button(self.main_frame, "↻  تازه‌سازی حساب و سرویس‌ها", self.refresh, "#283d62")
        self.button(self.main_frame, "خروج از حساب", self.logout, "#28304a")
        self.label_var(self.status, "#a3d6e8", 10, self.panel)
        self.label("فقط وضعیت IP خروجیِ آزمایش‌شده تأیید اتصال است.", 9, "#7e91b4")
        self.label("WireGuard/OpenVPN ممکن است نصب جداگانه نیاز داشته باشند.", 9, "#7e91b4")
        self.root.after(120, self.drain)
        if self.api.load():
            self.job(self.auto_login)
        else:
            self.status.set("برای شروع یک‌بار وارد حساب شوید.")

    def label(self, text, size, color, bold=False, parent=None):
        w = tk.Label(parent or self.panel, text=text, fg=color, bg="#0e1424",
                     font=("Segoe UI", size, "bold" if bold else "normal"),
                     anchor="e", justify="right")
        w.pack(fill="x", pady=3)
        return w

    def label_var(self, variable, color, size, parent):
        w = tk.Label(parent, textvariable=variable, fg=color, bg="#0e1424",
                     font=("Segoe UI", size), anchor="e", justify="right", wraplength=480)
        w.pack(fill="x", pady=9)

    def entry(self, parent, placeholder, show=None):
        self.label(placeholder, 10, "#adbedc", parent=parent)
        e = tk.Entry(parent, font=("Segoe UI", 12), relief="flat",
                     bg="#eff4fc", fg="#142238", show=show)
        e.pack(fill="x", ipady=7, pady=(0, 8))
        return e

    def button(self, parent, caption, fn, color):
        w = tk.Button(parent, text=caption, command=fn, bg=color, fg="white",
                      activebackground=color, activeforeground="white",
                      relief="flat", borderwidth=0, cursor="hand2",
                      font=("Segoe UI", 11, "bold"), pady=8)
        w.pack(fill="x", pady=5)
        return w

    def job(self, fn):
        if self.busy:
            return
        self.busy = True
        self.status.set("در حال بررسی امن…")
        def work():
            try:
                answer = fn()
                self.events.put(("ok", answer))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.busy = False
                if kind == "error":
                    self.status.set("خطا: " + value)
                    continue
                if callable(value):
                    value()
        except queue.Empty:
            pass
        self.root.after(120, self.drain)

    def show_account(self, account, items):
        self.account = account
        self.items = [x for x in items if x.get("available")]
        self.auth_frame.pack_forget()
        self.main_frame.pack(fill="x", pady=(5, 0))
        self.account_text.set("{} | {}".format(
            account.get("display_name") or account.get("username") or "Makia",
            account.get("plan_name") or "اشتراک"))
        self.choice["values"] = [
            "{}  ·  {}".format(x.get("label") or x.get("name") or x.get("protocol") or "سرویس",
                              x.get("engine") or "VPN") for x in self.items
        ]
        if self.items:
            self.choice.current(0)
        self.status.set("حساب آماده است؛ برای شروع «اتصال VPN» را بزنید.")

    def auto_login(self):
        a = self.api.me()
        items = self.api.profiles()
        return lambda: self.show_account(a, items)

    def login(self):
        u, p = self.username.get(), self.password.get()
        remember = self.remember.get()
        def work():
            account = self.api.login(u, p, remember)
            items = self.api.profiles()
            return lambda: (self.password.delete(0, tk.END),
                            self.show_account(account, items))
        self.job(work)

    def refresh(self):
        self.job(self.auto_login)

    def connect(self):
        i = self.choice.current()
        if i < 0 or i >= len(self.items):
            self.status.set("ابتدا یک سرویس فعال انتخاب کنید.")
            return
        item = self.items[i]
        def work():
            before = public_ip()
            ticket = self.api.ticket(item)
            launch = ticket.get("launch_url") or ""
            if not launch.startswith("makia://connect?"):
                raise RuntimeError("سرور بلیت یک‌بارمصرف معتبر برنگرداند.")
            connector(launch)
            time.sleep(3)
            after = public_ip()
            # Do NOT claim connected from a process being launched alone.
            if before and after and before != after:
                message = "اتصال واقعی تأیید شد. IP خروجی: " + after
            elif after:
                message = "موتور اجرا شد؛ تغییر IP هنوز تأیید نشده. وضعیت: " + after
            else:
                message = "موتور اجرا شد، اما تست HTTPS خروجی ناموفق است؛ سلامت تونل تأیید نشده."
            return lambda: self.status.set(message)
        self.job(work)

    def disconnect(self):
        def work():
            connector("--disconnect")
            return lambda: self.status.set("دستور قطع اتصال اجرا شد. دسترسی مستقیم پس از قطع مجاز است.")
        self.job(work)

    def logout(self):
        if self.busy:
            return
        # Logging out must not silently disconnect an active OS tunnel.
        def work():
            self.api.logout()
            return lambda: (self.main_frame.pack_forget(), self.auth_frame.pack(fill="x"),
                            self.status.set("نشست این دستگاه باطل شد. VPN را جداگانه قطع کنید."))
        self.job(work)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Desktop().run()
