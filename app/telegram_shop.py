"""Makia Telegram storefront. Off by default; separate from operator alert bot.

Digital sales are paid with Telegram Stars (XTR) ONLY. No order is
provisioned based on a button click, customer assertion, or pre-checkout.
"""
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import access_ops, integration_ops
from .db import connect, get_service_plan

router = APIRouter()
BASE = Path(__file__).resolve().parent
API_BASE = "https://api.telegram.org"
SUPPORTED_AUTO = {"outline", "wireguard", "openvpn"}


def enabled():
    return os.getenv("MAKIA_SHOP_ENABLED", "0").lower() in {"1", "true", "yes"}


def _token():
    return os.getenv("MAKIA_SHOP_BOT_TOKEN", "").strip()


def _secret():
    return os.getenv("MAKIA_SHOP_WEBHOOK_SECRET", "").strip()


def _configured():
    return enabled() and bool(re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}", _token()))


def _require_enabled():
    if not _configured():
        raise HTTPException(503, "Telegram storefront is not configured")


def _admins():
    return {int(x) for x in os.getenv("MAKIA_SHOP_ADMIN_IDS", "").split(",")
            if x.strip().isdigit() and int(x) > 0}


def _timestamp():
    return int(time.time())


def init_shop_db():
    """Additive migration: no changes to existing commerce, ledger or VPN tables."""
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tg_shop_offers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          plan_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          summary TEXT NOT NULL DEFAULT '',
          icon TEXT NOT NULL DEFAULT '🔐',
          profile TEXT NOT NULL,
          endpoint TEXT NOT NULL DEFAULT '',
          price_stars INTEGER NOT NULL CHECK(price_stars BETWEEN 1 AND 1000000),
          active INTEGER NOT NULL DEFAULT 0,
          sort_order INTEGER NOT NULL DEFAULT 100,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tg_shop_offers_active
          ON tg_shop_offers(active,sort_order,id);
        CREATE TABLE IF NOT EXISTS tg_shop_orders (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          buyer_id INTEGER NOT NULL,
          offer_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          profile TEXT NOT NULL,
          endpoint TEXT NOT NULL DEFAULT '',
          price_stars INTEGER NOT NULL,
          plan_json TEXT NOT NULL,
          invoice_nonce TEXT UNIQUE NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending_invoice',
          telegram_charge_id TEXT UNIQUE,
          paid_at INTEGER,
          fulfilled_at INTEGER,
          delivery_enc TEXT NOT NULL DEFAULT '',
          provision_ref TEXT NOT NULL DEFAULT '',
          error_code TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tg_shop_orders_buyer
          ON tg_shop_orders(buyer_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_tg_shop_orders_status
          ON tg_shop_orders(status,created_at);
        CREATE TABLE IF NOT EXISTS tg_shop_updates (
          update_id INTEGER PRIMARY KEY,
          received_at INTEGER NOT NULL
        );
        """)


def _telegram(method, payload):
    _require_enabled()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,50}", method):
        raise ValueError("invalid Telegram API method")
    result = integration_ops._json_request(
        f"{API_BASE}/bot{_token()}/{method}", method="POST", body=payload, timeout=12
    )
    if not result.get("ok"):
        raise integration_ops.IntegrationError("Telegram " + method + " rejected request")
    return result.get("result")


def _message(chat_id, text, markup=None, parse_mode=None):
    body = {"chat_id": int(chat_id), "text": str(text)[:4000],
            "disable_web_page_preview": True}
    if markup:
        body["reply_markup"] = markup
    if parse_mode:
        body["parse_mode"] = parse_mode
    return _telegram("sendMessage", body)


def _keyboard(rows):
    return {"inline_keyboard": rows}


def _webapp_url():
    raw = os.getenv("MAKIA_SHOP_PUBLIC_URL", "").strip()
    return raw if re.fullmatch(r"https://[A-Za-z0-9.-]+(?::443)?/telegram/shop/?", raw) else ""


def _home(chat_id):
    rows = [[{"text": "🛍 مشاهده سرویس‌ها", "callback_data": "catalog"}],
            [{"text": "📦 سفارش‌های من", "callback_data": "orders"}],
            [{"text": "🛟 پشتیبانی", "callback_data": "support"}]]
    if _webapp_url():
        rows.insert(0, [{"text": "✨ فروشگاه اختصاصی ماکیا", "web_app": {"url": _webapp_url()}}])
    return _message(chat_id,
        "✦ MAKiA | PRIVATE ACCESS\n\n"
        "به فضای اختصاصی ماکیا خوش آمدید.\n"
        "سرویس مناسب را انتخاب کنید، با ⭐ تلگرام پرداخت کنید "
        "و وضعیت تحویل خود را همین‌جا ببینید.\n\n"
        "🔒 دسترسی‌ها تنها پس از تأیید پرداخت صادر می‌شوند.",
        _keyboard(rows))


def _catalog():
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM tg_shop_offers WHERE active=1 ORDER BY sort_order,id"
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        plan = get_service_plan(item["plan_id"])
        if plan and plan.get("active"):
            out.append(item)
    return out


def _order(order_id):
    with connect() as con:
        row = con.execute("SELECT * FROM tg_shop_orders WHERE id=?", (int(order_id),)).fetchone()
    return dict(row) if row else None


def _order_for(buyer_id, order_id):
    item = _order(order_id)
    if not item or item["buyer_id"] != int(buyer_id):
        raise HTTPException(404, "order not found")
    return item


def _create_order(buyer_id, offer_id):
    if not isinstance(buyer_id, int) or buyer_id <= 0:
        raise HTTPException(403, "invalid Telegram identity")
    offer = next((x for x in _catalog() if x["id"] == int(offer_id)), None)
    if not offer:
        raise HTTPException(404, "offer unavailable")
    plan = get_service_plan(offer["plan_id"])
    if not plan or not plan.get("active"):
        raise HTTPException(409, "linked plan is unavailable")
    config = plan.get("config") or {}
    # A snapshot freezes pricing, profile, quotas and duration at checkout.
    snapshot = {"name": plan["name"], "kind": plan["protocol_kind"],
                "config": config}
    ts = _timestamp()
    with connect() as con:
        recent = con.execute(
            "SELECT COUNT(*) AS n FROM tg_shop_orders WHERE buyer_id=? AND created_at>?",
            (buyer_id, ts - 300)).fetchone()["n"]
        if recent >= 4:
            raise HTTPException(429, "too many orders; please retry later")
        cur = con.execute(
            """INSERT INTO tg_shop_orders
            (buyer_id,offer_id,title,profile,endpoint,price_stars,plan_json,
             invoice_nonce,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (buyer_id, offer["id"], offer["title"], offer["profile"],
             offer["endpoint"], offer["price_stars"],
             json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
             secrets.token_urlsafe(22), ts, ts))
        return _order(cur.lastrowid)


def _invoice_payload(item):
    return f"makia:{item['id']}:{item['invoice_nonce']}"


def _invoice(item, chat_id=None):
    data = {"title": item["title"][:32],
            "description": "دسترسی دیجیتال ماکیا | تحویل پس از پرداخت قطعی"[:255],
            "payload": _invoice_payload(item), "provider_token": "",
            "currency": "XTR", "prices": [
                {"label": item["title"][:32], "amount": item["price_stars"]}
            ]}
    if chat_id is not None:
        data["chat_id"] = int(chat_id)
        return _telegram("sendInvoice", data)
    return _telegram("createInvoiceLink", data)


def _invoice_lookup(payload):
    match = re.fullmatch(r"makia:(\d{1,18}):([A-Za-z0-9_-]{12,64})", str(payload or ""))
    if not match:
        return None
    item = _order(int(match.group(1)))
    if not item or not secrets.compare_digest(item["invoice_nonce"], match.group(2)):
        return None
    return item


def _precheckout(query):
    sender = int((query.get("from") or {}).get("id") or 0)
    item = _invoice_lookup(query.get("invoice_payload"))
    ok = bool(item and item["buyer_id"] == sender
              and item["status"] == "pending_invoice"
              and query.get("currency") == "XTR"
              and int(query.get("total_amount") or 0) == item["price_stars"])
    body = {"pre_checkout_query_id": query.get("id"), "ok": ok}
    if not ok:
        body["error_message"] = "این فاکتور معتبر نیست. لطفاً سفارش جدید ثبت کنید."
    _telegram("answerPreCheckoutQuery", body)
    return ok


def _paid(user_id, payment):
    item = _invoice_lookup(payment.get("invoice_payload"))
    charge = str(payment.get("telegram_payment_charge_id") or "")
    if not item or item["buyer_id"] != int(user_id):
        return None
    if payment.get("currency") != "XTR" or payment.get("total_amount") != item["price_stars"]:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_:-]{8,240}", charge):
        return None
    ts = _timestamp()
    with connect() as con:
        try:
            changed = con.execute(
                """UPDATE tg_shop_orders SET status='paid',telegram_charge_id=?,
                   paid_at=?,updated_at=? WHERE id=? AND status='pending_invoice'""",
                (charge,ts,ts,item["id"])).rowcount
        except sqlite3.IntegrityError:
            changed = 0
    return _order(item["id"]) if changed else None


def _claim_fulfillment(order_id, expected_status="paid"):
    with connect() as con:
        return con.execute(
            "UPDATE tg_shop_orders SET status='fulfilling',updated_at=? WHERE id=? AND status=?",
            (_timestamp(),order_id,expected_status)).rowcount == 1


def _update_order(order_id, status, **fields):
    permitted = {"delivery_enc","provision_ref","error_code","fulfilled_at"}
    pairs = [(k,v) for k,v in fields.items() if k in permitted]
    columns = ["status=?","updated_at=?"] + [k+"=?" for k,_ in pairs]
    vals = [status,_timestamp()] + [v for _,v in pairs] + [order_id]
    with connect() as con:
        con.execute(f"UPDATE tg_shop_orders SET {','.join(columns)} WHERE id=?", vals)


def _notify_admins(item, status):
    text = (f"✦ سفارش #{item['id']}\n"
            f"وضعیت: {status}\n"
            f"محصول: {item['title']}\n"
            f"مبلغ: {item['price_stars']} ⭐\n"
            f"مشتری: {item['buyer_id']}")
    for admin in _admins():
        try: _message(admin, text)
        except integration_ops.IntegrationError: pass


def _provision(item):
    """Call Makia's existing scoped, loopback-only, idempotent commerce API."""
    token = os.getenv("MAKIA_SHOP_COMMERCE_TOKEN", "").strip()
    if not token:
        return None
    profile = str(item["profile"])
    if not (profile in SUPPORTED_AUTO or re.fullmatch(r"xray:[A-Za-z0-9_.:-]{1,100}",profile)):
        return None
    snapshot = json.loads(item["plan_json"])
    cfg = snapshot.get("config") or {}
    payload = {
        "external_id": f"telegram:{item['id']}",
        "name": f"tg{item['id']}",
        "profile": profile,
        "product_slug": f"tg-offer-{item['offer_id']}",
        "quota_gb": float(cfg.get("quota_gb") or 0),
        "expire_days": int(cfg.get("expire_days") or 30),
        "ip_limit": int(cfg.get("ip_limit") or 1),
        "attributes": {"endpoint": item["endpoint"], "endpoint_mode": "auto"}
    }
    result = integration_ops._json_request(
        "http://127.0.0.1:8787/api/v1/commerce/provision",
        method="POST", body=payload, timeout=45,
        headers={"Authorization": "Bearer " + token,
                 "Idempotency-Key": f"telegram-shop-order-{item['id']}"})
    if not result.get("ok") or not result.get("credential"):
        raise RuntimeError("commerce provision did not return access credentials")
    return result


def _delivery_text(item, credential):
    escaped = html.escape(str(credential), quote=False)
    return (f"✅ سفارش #{item['id']} تحویل شد\n"
            "🔒 کانفیگ شما خصوصی است؛ آن را در اختیار دیگران قرار ندهید.\n"
            f"<code>{escaped}</code>")


def _send_delivery(item):
    if not item or not item.get("delivery_enc"):
        return False
    try:
        data = access_ops.open_payload(item["delivery_enc"])
        value = data.get("credential") or ""
        if not value:
            return False
        message = _delivery_text(item, value)
        if len(message) > 3990:
            # Do not leak just the first bytes of a broken private-key/config.
            _message(item["buyer_id"],
                     f"✅ سفارش #{item['id']} آماده است. فایل بزرگ‌تر از پیام تلگرام است؛ لطفاً برای تحویل امن به پشتیبانی مراجعه کنید.")
            return False
        _message(item["buyer_id"], message, parse_mode="HTML")
        _update_order(item["id"], "delivered", fulfilled_at=_timestamp())
        return True
    except Exception:
        return False


def _fulfill(item):
    if not _claim_fulfillment(item["id"]):
        return
    try:
        result = _provision(item)
    except Exception:
        # NEVER automatically retry after an ambiguous backend timeout:
        # a VPN credential may already have been created.
        _update_order(item["id"], "needs_review", error_code="provision_unknown")
        _notify_admins(item, "نیاز به بررسی دستی ساخت دسترسی")
        return
    if result is None:
        _update_order(item["id"], "awaiting_fulfillment")
        _notify_admins(item, "پرداخت شده | تحویل دستی لازم")
        try: _message(item["buyer_id"],f"✅ پرداخت سفارش #{item['id']} تأیید شد.\nصدور دسترسی در صف بررسی تیم ماکیا است.")
        except Exception: pass
        return
    _update_order(item["id"], "delivery_pending",
                  delivery_enc=access_ops.seal_payload({"credential": result["credential"]}),
                  provision_ref=str(result.get("provision_ref") or ""))
    if not _send_delivery(_order(item["id"])):
        _notify_admins(item, "سرویس ساخته شده | ارسال به مشتری بررسی شود")


def _orders_message(user_id):
    with connect() as con:
        rows = con.execute(
            "SELECT id,title,price_stars,status FROM tg_shop_orders "
            "WHERE buyer_id=? ORDER BY id DESC LIMIT 8",(int(user_id),)).fetchall()
    if not rows:
        return _message(user_id,"📦 هنوز سفارشی ثبت نشده است.")
    states = {"pending_invoice":"منتظر پرداخت","paid":"پرداخت شد",
              "fulfilling":"در حال صدور","delivery_pending":"آماده ارسال",
              "delivered":"تحویل شد","awaiting_fulfillment":"تحویل توسط پشتیبانی",
              "needs_review":"در حال بررسی"}
    txt = "📦 سفارش‌های شما\n\n" + "\n".join(
        f"#{x['id']} · {x['title']} · {x['price_stars']} ⭐ · {states.get(x['status'],x['status'])}"
        for x in rows)
    return _message(user_id,txt)


def _catalog_message(user_id):
    rows = _catalog()
    if not rows:
        return _message(user_id,"✦ فروشگاه ماکیا\n\nفعلاً سرویس فعالی برای خرید موجود نیست.")
    buttons = [[{"text":f"{x['icon']} {x['title']} · {x['price_stars']} ⭐",
                 "callback_data":f"offer:{x['id']}"}] for x in rows[:35]]
    return _message(user_id,"🛍 فروشگاه اختصاصی ماکیا\n\n"
        "سرویس مناسب خود را انتخاب کنید. پرداخت امن از طریق Stars انجام می‌شود.",
        _keyboard(buttons))


def _support(user_id):
    username = os.getenv("MAKIA_SHOP_SUPPORT", "").strip().lstrip("@")
    link = f"https://t.me/{username}" if re.fullmatch(r"[A-Za-z0-9_]{5,32}",username) else ""
    text = ("🛟 پشتیبانی MAKiA\n\n"
            "برای سؤالات خرید، مشکلات اتصال یا پیگیری پرداخت با تیم پشتیبانی ارتباط بگیرید.\n"
            "فرمان /paysupport نیز برای پیگیری پرداخت در دسترس است.")
    rows = [[{"text":"💬 ارتباط با پشتیبانی","url":link}]] if link else None
    return _message(user_id,text,_keyboard(rows) if rows else None)


def _handle_callback(callback):
    actor = int((callback.get("from") or {}).get("id") or 0)
    msg = callback.get("message") or {}
    chat = int((msg.get("chat") or {}).get("id") or 0)
    data = str(callback.get("data") or "")
    try:
        _telegram("answerCallbackQuery",{"callback_query_id":callback["id"]})
    except Exception:
        pass
    if not actor or chat != actor:
        return
    if data == "catalog":
        _catalog_message(actor)
    elif data == "orders":
        _orders_message(actor)
    elif data == "support":
        _support(actor)
    elif re.fullmatch(r"offer:\d{1,8}",data):
        offer_id = int(data.split(":")[1])
        offer = next((x for x in _catalog() if x["id"] == offer_id),None)
        if offer:
            _message(actor, f"{offer['icon']} {offer['title']}\n\n"
                f"{offer['summary']}\n\n⭐ قیمت: {offer['price_stars']} Stars",
                _keyboard([[{"text":"💳 پرداخت با Stars","callback_data":f"buy:{offer_id}"}],
                           [{"text":"↩️ فهرست سرویس‌ها","callback_data":"catalog"}]]))
    elif re.fullmatch(r"buy:\d{1,8}",data):
        try:
            item = _create_order(actor,int(data.split(":")[1]))
            _invoice(item,actor)
        except HTTPException as exc:
            _message(actor,f"⚠️ سفارش قابل ثبت نیست: {exc.detail}")
        except Exception:
            _message(actor,"⚠️ صدور فاکتور انجام نشد. لطفاً دوباره تلاش کنید.")


def process_update(payload):
    if not isinstance(payload,dict):
        return
    update_id = payload.get("update_id")
    if not isinstance(update_id,int) or update_id<0:
        return
    # Claim update before side effects. Duplicate Telegram delivery never
    # repeats invoice issuance or service provisioning.
    with connect() as con:
        inserted=con.execute(
            "INSERT OR IGNORE INTO tg_shop_updates(update_id,received_at) VALUES(?,?)",
            (update_id,_timestamp())).rowcount
        con.execute("DELETE FROM tg_shop_updates WHERE received_at<?",
                    (_timestamp()-14*86400,))
    if not inserted:
        return
    if "pre_checkout_query" in payload:
        _precheckout(payload["pre_checkout_query"])
        return
    if "callback_query" in payload:
        _handle_callback(payload["callback_query"])
        return
    msg=payload.get("message") or {}
    actor=int((msg.get("from") or {}).get("id") or 0)
    chat=msg.get("chat") or {}
    if not actor or int(chat.get("id") or 0)!=actor or chat.get("type")!="private":
        return
    payment=msg.get("successful_payment")
    if payment:
        item=_paid(actor,payment)
        if item:
            _message(actor,f"💚 پرداخت سفارش #{item['id']} با موفقیت ثبت شد.")
            _fulfill(item)
        return
    text=str(msg.get("text") or "").split(maxsplit=1)[0].split("@",1)[0].lower()
    if text in {"/start","/menu","/help"}: _home(actor)
    elif text in {"/shop","/products"}: _catalog_message(actor)
    elif text in {"/orders","/myorders"}: _orders_message(actor)
    elif text in {"/support","/paysupport"}: _support(actor)
    elif text == "/terms":
        _message(actor,"📜 قوانین فروش ماکیا\n"
            "محصول دیجیتال است؛ پرداخت از طریق Telegram Stars انجام می‌شود. "
            "تحویل پس از تأیید پرداخت و بررسی آمادگی پروتکل صورت می‌گیرد. "
            "در صورت خطا یا اختلاف مالی با /paysupport ارتباط بگیرید. "
            "برای سفارش خود از قوانین سرویس و مقررات تلگرام پیروی کنید.")
    elif text == "/redeliver":
        with connect() as con:
            rows=con.execute("SELECT id FROM tg_shop_orders WHERE buyer_id=? AND "
                "status IN ('delivered','delivery_pending') ORDER BY id DESC LIMIT 1",(actor,)).fetchall()
        if rows: _send_delivery(_order(rows[0]["id"]))
        else: _orders_message(actor)
    else: _home(actor)


def verify_init_data(raw, max_age=300):
    """Verify Telegram Mini App HMAC before trusting identity or order action."""
    _require_enabled()
    if not isinstance(raw,str) or not 10<len(raw)<8192:
        raise HTTPException(401,"missing Telegram authorization")
    pairs=urllib.parse.parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=36)
    data={}
    for k,v in pairs:
        if k in data:
            raise HTTPException(401,"duplicate Telegram field")
        data[k]=v
    provided=data.pop("hash","")
    data.pop("signature",None)
    if not re.fullmatch(r"[a-fA-F0-9]{64}",provided):
        raise HTTPException(401,"invalid Telegram signature")
    secret=hmac.new(b"WebAppData",_token().encode(),hashlib.sha256).digest()
    base="\n".join(f"{k}={v}" for k,v in sorted(data.items()))
    expected=hmac.new(secret,base.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided.lower(),expected):
        raise HTTPException(401,"invalid Telegram authorization")
    try:
        ts=int(data["auth_date"]);user=json.loads(data["user"])
        actor=int(user["id"])
    except (ValueError,KeyError,TypeError,json.JSONDecodeError):
        raise HTTPException(401,"invalid Telegram user")
    if actor<=0 or not 0<=_timestamp()-ts<=max_age:
        raise HTTPException(401,"expired Telegram authorization")
    return actor


def _mini_user(request):
    return verify_init_data(request.headers.get("x-telegram-init-data",""))


@router.get("/telegram/shop")
def miniapp():
    _require_enabled()
    return FileResponse(BASE/"templates"/"telegram_shop.html",media_type="text/html",
                        headers={"Cache-Control":"no-store"})


@router.get("/api/telegram-shop/catalog")
def public_catalog():
    _require_enabled()
    return [{"id":x["id"],"title":x["title"],"summary":x["summary"],
             "icon":x["icon"],"price_stars":x["price_stars"]}
            for x in _catalog()]


class CheckoutRequest(BaseModel):
    offer_id:int=Field(gt=0)


@router.post("/api/telegram-shop/checkout")
def mini_checkout(payload:CheckoutRequest,request:Request):
    actor=_mini_user(request)
    item=_create_order(actor,payload.offer_id)
    try:
        link=_invoice(item)
    except Exception:
        raise HTTPException(503,"invoice creation unavailable")
    return {"order_id":item["id"],"invoice_url":link}


@router.get("/api/telegram-shop/orders")
def mini_orders(request:Request):
    actor=_mini_user(request)
    with connect() as con:
        rows=con.execute("SELECT id,title,price_stars,status,created_at "
            "FROM tg_shop_orders WHERE buyer_id=? ORDER BY id DESC LIMIT 25",(actor,)).fetchall()
    return [dict(x) for x in rows]


@router.post("/telegram/shop/webhook")
async def webhook(request:Request):
    _require_enabled()
    expected=_secret()
    received=request.headers.get("x-telegram-bot-api-secret-token","")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", expected or "") or not hmac.compare_digest(expected,received):
        raise HTTPException(403,"invalid Telegram webhook secret")
    if int(request.headers.get("content-length") or 0)>262144:
        raise HTTPException(413,"update too large")
    try:
        update=await request.json()
    except Exception:
        raise HTTPException(400,"invalid Telegram update")
    try:
        process_update(update)
    except Exception:
        # Telegram can redeliver; the order state always remains reviewable.
        # Never expose credentials, charge IDs or bot token via errors.
        return {"ok":True,"queued":False}
    return {"ok":True}


class OfferWrite(BaseModel):
    plan_id:int=Field(gt=0)
    title:str=Field(min_length=3,max_length=80)
    summary:str=Field(default="",max_length=360)
    icon:str=Field(default="🔐",max_length=8)
    profile:str=Field(min_length=1,max_length=120)
    endpoint:str=Field(default="",max_length=200)
    price_stars:int=Field(ge=1,le=1000000)
    active:bool=False
    sort_order:int=Field(default=100,ge=0,le=10000)


class ManualDelivery(BaseModel):
    credential:str=Field(min_length=3,max_length=20000)


def register_admin(app, require_admin, require_mutation, audit_func, ip_func):
    @app.get("/api/telegram-shop/admin/status")
    def admin_status(request:Request):
        require_admin(request)
        with connect() as con:
            count=con.execute("SELECT COUNT(*) FROM tg_shop_orders").fetchone()[0]
            pending=con.execute("SELECT COUNT(*) FROM tg_shop_orders WHERE status "
                "IN ('paid','needs_review','awaiting_fulfillment','delivery_pending')").fetchone()[0]
        return {"enabled":_configured(),"bot_token_configured":bool(_token()),
                "webhook_secret_configured":bool(_secret()),
                "commerce_token_configured":bool(os.getenv("MAKIA_SHOP_COMMERCE_TOKEN")),
                "mini_app_url":_webapp_url(),"orders_total":count,"needs_attention":pending,
                "payment_currency":"XTR","payment_method":"Telegram Stars"}

    @app.get("/api/telegram-shop/admin/offers")
    def admin_offers(request:Request):
        require_admin(request)
        with connect() as con:
            return [dict(x) for x in con.execute(
                "SELECT * FROM tg_shop_offers ORDER BY sort_order,id").fetchall()]

    @app.post("/api/telegram-shop/admin/offers")
    def admin_offer_new(payload:OfferWrite,request:Request):
        actor=require_admin(request);require_mutation(request)
        plan=get_service_plan(payload.plan_id)
        if not plan: raise HTTPException(404,"Makia service plan not found")
        kind=plan["protocol_kind"]
        profile=payload.profile.strip()
        if profile not in {f"manual:{kind}",kind} and not (
            kind=="xray" and re.fullmatch(r"xray:[A-Za-z0-9_.:-]{1,100}",profile)):
            raise HTTPException(422,"profile must match its Makia plan kind")
        if kind=="xray" and not profile.startswith("xray:"):
            raise HTTPException(422,"Xray requires a specific inbound: xray:<tag>")
        if profile in SUPPORTED_AUTO or profile.startswith("xray:"):
            if profile!="outline" and not payload.endpoint.strip():
                raise HTTPException(422,"public endpoint is required for auto-provision")
        ts=_timestamp()
        with connect() as con:
            cur=con.execute(
                """INSERT INTO tg_shop_offers
                (plan_id,title,summary,icon,profile,endpoint,price_stars,active,
                 sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (payload.plan_id,payload.title.strip(),payload.summary.strip(),payload.icon,
                 profile,payload.endpoint.strip(),payload.price_stars,int(payload.active),
                 payload.sort_order,ts,ts))
        audit_func(actor,"tg_shop_offer_create",str(cur.lastrowid),f"plan={payload.plan_id}",ip_func(request))
        return {"ok":True,"offer_id":cur.lastrowid}

    @app.post("/api/telegram-shop/admin/offers/{offer_id}/state")
    def admin_offer_state(offer_id:int,request:Request,active:bool=False):
        actor=require_admin(request);require_mutation(request)
        with connect() as con:
            changed=con.execute("UPDATE tg_shop_offers SET active=?,updated_at=? WHERE id=?",
                (int(active),_timestamp(),offer_id)).rowcount
        if not changed:raise HTTPException(404,"offer not found")
        audit_func(actor,"tg_shop_offer_state",str(offer_id),f"active={active}",ip_func(request))
        return {"ok":True,"active":active}

    @app.get("/api/telegram-shop/admin/orders")
    def admin_orders(request:Request,limit:int=100):
        require_admin(request)
        with connect() as con:
            rows=con.execute("SELECT id,buyer_id,offer_id,title,profile,price_stars,"
                "status,provision_ref,error_code,created_at,paid_at,fulfilled_at "
                "FROM tg_shop_orders ORDER BY id DESC LIMIT ?",(max(1,min(limit,200)),)).fetchall()
        return [dict(x) for x in rows]

    @app.post("/api/telegram-shop/admin/orders/{order_id}/deliver")
    def admin_manual_deliver(order_id:int,payload:ManualDelivery,request:Request):
        actor=require_admin(request);require_mutation(request)
        item=_order(order_id)
        if not item:raise HTTPException(404,"order not found")
        if not item.get("telegram_charge_id") or item["status"] not in {
            "awaiting_fulfillment","needs_review","delivery_pending"}:
            raise HTTPException(409,"order must have verified Telegram payment")
        if item["status"]=="delivery_pending" and item.get("delivery_enc"):
            raise HTTPException(409,"existing paid credential must not be overwritten")
        _update_order(order_id,"delivery_pending",
            delivery_enc=access_ops.seal_payload({"credential":payload.credential}),
            error_code="",fulfilled_at=0)
        sent=_send_delivery(_order(order_id))
        audit_func(actor,"tg_shop_manual_deliver",str(order_id),f"sent={sent}",ip_func(request))
        return {"ok":True,"sent":sent}

    @app.post("/api/telegram-shop/admin/orders/{order_id}/resend")
    def admin_resend(order_id:int,request:Request):
        actor=require_admin(request);require_mutation(request)
        item=_order(order_id)
        if not item or not item.get("telegram_charge_id") or not item.get("delivery_enc"):
            raise HTTPException(409,"no verified order with a stored delivery")
        sent=_send_delivery(item)
        audit_func(actor,"tg_shop_resend",str(order_id),f"sent={sent}",ip_func(request))
        return {"ok":True,"sent":sent}
