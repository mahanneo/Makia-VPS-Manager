from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .config import DATA_DIR, SECRET_PATH
from .db import connect, audit

router = APIRouter()
BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE / "templates")
CONFIG_PATH = Path("/etc/makia-vps-manager/payments.json")
RECEIPTS_DIR = DATA_DIR / "payments" / "receipts"
MAX_RECEIPT_BYTES = 5 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normal_digits(value: str) -> str:
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return str(value or "").translate(table)


def _load_settings() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return {
        "brand": "MAKIA PAY",
        "card_number": re.sub(r"\D", "", str(data.get("card_number") or "")),
        "card_holder": str(data.get("card_holder") or "ماهان")[:60],
        "enabled": bool(data.get("enabled", True)),
        "wallets": data.get("wallets") if isinstance(data.get("wallets"), list) else [],
    }


def _save_settings(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "brand": "MAKIA PAY",
        "card_number": re.sub(r"\D", "", str(data["card_number"])),
        "card_holder": str(data["card_holder"]).strip()[:60],
        "enabled": bool(data.get("enabled", True)),
        "wallets": data.get("wallets") if isinstance(data.get("wallets"), list) else [],
        "updated_at": _utc_now(),
    }
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)
    os.chmod(CONFIG_PATH, 0o600)


def init() -> None:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(RECEIPTS_DIR.parent, 0o700)
    os.chmod(RECEIPTS_DIR, 0o700)
    if not CONFIG_PATH.exists():
        _save_settings({
            "card_number": "6219861435634778",
            "card_holder": "ماهان",
            "enabled": True,
            "wallets": [],
        })
    else:
        os.chmod(CONFIG_PATH, 0o600)
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS payment_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          reference TEXT NOT NULL UNIQUE,
          payer_name TEXT NOT NULL,
          payer_phone TEXT NOT NULL DEFAULT '',
          amount_toman INTEGER NOT NULL CHECK(amount_toman > 0),
          tracking_code TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          receipt_filename TEXT,
          receipt_mime TEXT,
          status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','verified','rejected')),
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          reviewed_by TEXT,
          ip_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_payment_requests_created
          ON payment_requests(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_payment_requests_status
          ON payment_requests(status, created_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_tracking_unique
          ON payment_requests(tracking_code)
          WHERE tracking_code <> '';
        CREATE TABLE IF NOT EXISTS payment_submit_limits (
          ip_hash TEXT PRIMARY KEY,
          window_started INTEGER NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0
        );
        """)


def _ip_hash(request: Request) -> str:
    raw_ip = request.client.host if request.client else "unknown"
    try:
        secret = SECRET_PATH.read_bytes()
    except OSError:
        secret = b"makia-payment-rate-limit"
    return hmac.new(secret, raw_ip.encode("utf-8", "replace"), hashlib.sha256).hexdigest()


def _check_rate_limit(request: Request) -> str:
    key = _ip_hash(request)
    now = int(time.time())
    with connect() as con:
        row = con.execute(
            "SELECT window_started,attempts FROM payment_submit_limits WHERE ip_hash=?",
            (key,),
        ).fetchone()
        if row and now - int(row["window_started"]) < 3600:
            if int(row["attempts"]) >= 8:
                raise HTTPException(429, "تعداد درخواست‌ها بیش از حد مجاز است؛ یک ساعت دیگر تلاش کنید.")
            con.execute(
                "UPDATE payment_submit_limits SET attempts=attempts+1 WHERE ip_hash=?",
                (key,),
            )
        else:
            con.execute(
                """INSERT INTO payment_submit_limits(ip_hash,window_started,attempts)
                   VALUES(?,?,1) ON CONFLICT(ip_hash) DO UPDATE SET
                   window_started=excluded.window_started,attempts=1""",
                (key, now),
            )
    return key


def _qr_data_uri(value: str) -> str:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(
        image_factory=qrcode.image.svg.SvgPathImage,
        fill_color="#10172a",
        back_color="#ffffff",
    )
    buf = BytesIO()
    image.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@router.get("/pay", response_class=HTMLResponse)
def public_payment_page(request: Request):
    settings = _load_settings()
    if not settings["enabled"] or len(settings["card_number"]) != 16:
        raise HTTPException(503, "درگاه پرداخت موقتاً در دسترس نیست.")
    card = settings["card_number"]
    formatted = " - ".join(card[i:i + 4] for i in range(0, 16, 4))
    return templates.TemplateResponse(
        request=request,
        name="payment_page.html",
        context={
            "brand": settings["brand"],
            "card_number": card,
            "card_formatted": formatted,
            "card_holder": settings["card_holder"],
            "card_qr": _qr_data_uri(card),
        },
    )


@router.get("/pay/", include_in_schema=False)
def public_payment_page_slash():
    return RedirectResponse("/pay", status_code=308)


@router.post("/api/public/payments/submit")
async def submit_payment(
    request: Request,
    payer_name: str = Form(..., min_length=2, max_length=80),
    payer_phone: str = Form("", max_length=24),
    amount_toman: str = Form(..., max_length=16),
    tracking_code: str = Form("", max_length=100),
    note: str = Form("", max_length=500),
    website: str = Form(""),
    receipt: UploadFile | None = File(default=None),
):
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc.lower() != (request.headers.get("host") or "").lower():
            raise HTTPException(403, "درخواست نامعتبر است.")
    if (request.headers.get("sec-fetch-site") or "").lower() == "cross-site":
        raise HTTPException(403, "درخواست نامعتبر است.")
    if website.strip():
        return {"ok": True, "reference": "درخواست ثبت شد"}
    name = " ".join(payer_name.strip().split())
    if len(name) < 2 or any(ord(c) < 32 for c in name):
        raise HTTPException(422, "نام پرداخت‌کننده معتبر نیست.")
    digits = _normal_digits(amount_toman)
    if not digits.isdigit():
        raise HTTPException(422, "مبلغ را فقط با عدد وارد کنید.")
    amount = int(digits)
    if amount < 1000 or amount > 1_000_000_000:
        raise HTTPException(422, "مبلغ باید بین ۱٬۰۰۰ تا ۱٬۰۰۰٬۰۰۰٬۰۰۰ تومان باشد.")
    phone = re.sub(r"[\s()\-]", "", _normal_digits(payer_phone))
    if phone and not re.fullmatch(r"\+?[0-9]{7,20}", phone):
        raise HTTPException(422, "شماره تماس معتبر نیست.")
    tracking = " ".join(tracking_code.strip().split())[:100]
    clean_note = " ".join(note.strip().split())[:500]
    has_receipt = bool(receipt is not None and receipt.filename)
    if not tracking and not has_receipt:
        raise HTTPException(422, "شناسه پیگیری یا تصویر رسید را وارد کنید.")
    ip_key = _check_rate_limit(request)

    receipt_name = None
    receipt_mime = None
    receipt_path = None
    if has_receipt:
        data = await receipt.read(MAX_RECEIPT_BYTES + 1)
        if len(data) > MAX_RECEIPT_BYTES:
            raise HTTPException(413, "حجم رسید نباید بیشتر از ۵ مگابایت باشد.")
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            ext, receipt_mime = ".png", "image/png"
        elif data.startswith(b"\xff\xd8\xff"):
            ext, receipt_mime = ".jpg", "image/jpeg"
        elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            ext, receipt_mime = ".webp", "image/webp"
        elif data.startswith(b"%PDF-"):
            ext, receipt_mime = ".pdf", "application/pdf"
        else:
            raise HTTPException(415, "فقط تصویر JPG، PNG، WebP یا فایل PDF معتبر است.")
        receipt_name = secrets.token_hex(20) + ext
        receipt_path = RECEIPTS_DIR / receipt_name
        with open(receipt_path, "xb") as fp:
            fp.write(data)
        os.chmod(receipt_path, 0o600)

    reference = "MP-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + secrets.token_hex(4).upper()
    try:
        with connect() as con:
            con.execute(
                """INSERT INTO payment_requests
                   (reference,payer_name,payer_phone,amount_toman,tracking_code,note,
                    receipt_filename,receipt_mime,status,created_at,ip_hash)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference, name, phone, amount, tracking, clean_note,
                    receipt_name, receipt_mime, "pending", _utc_now(), ip_key,
                ),
            )
    except sqlite3.IntegrityError:
        if receipt_path and receipt_path.exists():
            receipt_path.unlink()
        raise HTTPException(409, "این شناسه پیگیری قبلاً ثبت شده است.")
    except Exception:
        if receipt_path and receipt_path.exists():
            receipt_path.unlink()
        raise
    return {"ok": True, "reference": reference, "status": "pending"}


class PaymentSettingsUpdate(BaseModel):
    card_number: str = Field(min_length=16, max_length=32)
    card_holder: str = Field(min_length=2, max_length=60)


@router.get("/api/payments/settings")
def admin_payment_settings(request: Request):
    from .main import require_local_admin
    require_local_admin(request)
    settings = _load_settings()
    return {
        "brand": settings["brand"],
        "card_number": settings["card_number"],
        "card_holder": settings["card_holder"],
        "wallets": settings["wallets"],
        "public_url": str(request.base_url).rstrip("/") + "/pay",
    }


@router.put("/api/payments/settings")
def update_payment_settings(payload: PaymentSettingsUpdate, request: Request):
    from .main import require_local_admin, require_mutation
    actor = require_local_admin(request)
    require_mutation(request)
    card = re.sub(r"\D", "", _normal_digits(payload.card_number))
    holder = " ".join(payload.card_holder.strip().split())
    if not re.fullmatch(r"[0-9]{16}", card):
        raise HTTPException(422, "شماره کارت باید دقیقاً ۱۶ رقم باشد.")
    if len(holder) < 2:
        raise HTTPException(422, "نام صاحب کارت معتبر نیست.")
    current = _load_settings()
    current.update({"card_number": card, "card_holder": holder})
    _save_settings(current)
    audit(actor, "payment_settings_update", "MAKIA PAY", "Card details updated", ip=request.client.host if request.client else "")
    return {"ok": True}


@router.get("/api/payments")
def admin_payment_list(request: Request, limit: int = 100):
    from .main import require_local_admin
    require_local_admin(request)
    limit = max(1, min(int(limit), 200))
    with connect() as con:
        rows = con.execute(
            """SELECT id,reference,payer_name,payer_phone,amount_toman,tracking_code,note,
                      receipt_filename,status,created_at,reviewed_at,reviewed_by
               FROM payment_requests ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        counts = {
            row["status"]: int(row["n"])
            for row in con.execute("SELECT status,COUNT(*) AS n FROM payment_requests GROUP BY status").fetchall()
        }
    result = []
    for row in rows:
        item = dict(row)
        item["has_receipt"] = bool(item.pop("receipt_filename", None))
        result.append(item)
    return {"items": result, "counts": counts, "total": sum(counts.values())}


class PaymentStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=16)


@router.post("/api/payments/{payment_id}/status")
def update_payment_status(payment_id: int, payload: PaymentStatusUpdate, request: Request):
    from .main import require_local_admin, require_mutation
    actor = require_local_admin(request)
    require_mutation(request)
    status = payload.status
    if status not in {"pending", "verified", "rejected"}:
        raise HTTPException(422, "وضعیت پرداخت معتبر نیست.")
    with connect() as con:
        row = con.execute("SELECT reference,status FROM payment_requests WHERE id=?", (payment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "درخواست پرداخت پیدا نشد.")
        reviewed_at = None if status == "pending" else _utc_now()
        con.execute(
            "UPDATE payment_requests SET status=?,reviewed_at=?,reviewed_by=? WHERE id=?",
            (status, reviewed_at, actor if reviewed_at else None, payment_id),
        )
    audit(actor, "payment_status_update", row["reference"], status, ip=request.client.host if request.client else "")
    return {"ok": True, "status": status}


@router.get("/api/payments/{payment_id}/receipt")
def admin_payment_receipt(payment_id: int, request: Request):
    from .main import require_local_admin
    require_local_admin(request)
    with connect() as con:
        row = con.execute(
            "SELECT receipt_filename,receipt_mime,reference FROM payment_requests WHERE id=?",
            (payment_id,),
        ).fetchone()
    if not row or not row["receipt_filename"]:
        raise HTTPException(404, "رسید برای این پرداخت ثبت نشده است.")
    path = (RECEIPTS_DIR / row["receipt_filename"]).resolve()
    if path.parent != RECEIPTS_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "فایل رسید پیدا نشد.")
    return FileResponse(
        path,
        media_type=row["receipt_mime"] or "application/octet-stream",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )
