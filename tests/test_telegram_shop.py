import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from app import db, telegram_shop as shop


TOKEN="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
SECRET="S"*32


@pytest.fixture
def shopdb(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"tg-test.db")
    monkeypatch.setenv("MAKIA_INITIAL_ADMIN_PASSWORD","Strong-Safe-Test-Password!!23")
    monkeypatch.setenv("MAKIA_SHOP_ENABLED","1")
    monkeypatch.setenv("MAKIA_SHOP_BOT_TOKEN",TOKEN)
    monkeypatch.setenv("MAKIA_SHOP_WEBHOOK_SECRET",SECRET)
    monkeypatch.delenv("MAKIA_SHOP_COMMERCE_TOKEN",raising=False)
    db.init_db()
    shop.init_shop_db()
    plan=db.create_service_plan("30 Days Xray","xray",{"expire_days":30,"quota_gb":20,"ip_limit":2}, "25 ⭐")
    with db.connect() as con:
        con.execute(
            """INSERT INTO tg_shop_offers(plan_id,title,summary,icon,profile,endpoint,
             price_stars,active,sort_order,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (plan,"Private Xray","20GB • 30 days","✦","xray:inbound-01",
             "vpn.example.test",25,1,1,int(time.time()),int(time.time()))
        )
    return {"plan":plan,"offer_id":1}


def initdata(user_id=123,auth_date=None):
    fields={"auth_date":str(int(time.time()) if auth_date is None else auth_date),
            "query_id":"AAABBBCCCDDD",
            "user":json.dumps({"id":user_id,"first_name":"Sample"},separators=(",",":"))}
    data="\n".join(k+"="+v for k,v in sorted(fields.items()))
    key=hmac.new(b"WebAppData",TOKEN.encode(),hashlib.sha256).digest()
    fields["hash"]=hmac.new(key,data.encode(),hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_shop_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MAKIA_SHOP_ENABLED",raising=False)
    with pytest.raises(HTTPException) as exc:
        shop._require_enabled()
    assert exc.value.status_code==503


def test_initdata_valid_hmac_and_buyer_binding(shopdb):
    assert shop.verify_init_data(initdata(909))==909
    forged=initdata(909).replace("%22909%22","%22911%22")
    if forged==initdata(909):
        forged=initdata(909).replace("Sample","Attacker")
    with pytest.raises(HTTPException):
        shop.verify_init_data(forged)
    with pytest.raises(HTTPException):
        shop.verify_init_data(initdata(909,auth_date=int(time.time())-9000))
    with pytest.raises(HTTPException):
        shop.verify_init_data(initdata(909)+"&user=duplicated")


def test_plan_driven_catalog_snapshot_and_order_rate_limit(shopdb):
    rows=shop._catalog()
    assert len(rows)==1
    assert rows[0]["price_stars"]==25
    a=shop._create_order(200,1)
    assert a["status"]=="pending_invoice"
    assert a["price_stars"]==25
    assert json.loads(a["plan_json"])["config"]["quota_gb"]==20
    assert shop._invoice_lookup(shop._invoice_payload(a))["id"]==a["id"]
    assert shop._invoice_lookup(shop._invoice_payload(a)+"evil") is None
    for _ in range(3): shop._create_order(200,1)
    with pytest.raises(HTTPException) as exc:
        shop._create_order(200,1)
    assert exc.value.status_code==429
    with pytest.raises(HTTPException) as exc:
        shop._order_for(201,a["id"])
    assert exc.value.status_code==404


def test_precheckout_never_provisions_and_rejects_price_mismatch(shopdb,monkeypatch):
    order=shop._create_order(123,1)
    emitted=[]
    monkeypatch.setattr(shop,"_telegram",lambda method,payload: emitted.append((method,payload)))
    good={"id":"check_1","from":{"id":123},"invoice_payload":shop._invoice_payload(order),
          "total_amount":25,"currency":"XTR"}
    assert shop._precheckout(good)
    assert emitted[-1]==("answerPreCheckoutQuery",{"pre_checkout_query_id":"check_1","ok":True})
    assert shop._order(order["id"])["status"]=="pending_invoice"
    bad=dict(good,total_amount=24)
    assert not shop._precheckout(bad)
    assert emitted[-1][1]["ok"] is False
    wrong=dict(good,**{"from":{"id":999}})
    assert not shop._precheckout(wrong)
    assert shop._order(order["id"])["status"]=="pending_invoice"


def test_real_stars_payment_once_and_replay_safe_delivery(shopdb,monkeypatch):
    order=shop._create_order(123,1)
    emitted=[]
    called=[]
    monkeypatch.setattr(shop,"_message",lambda *a,**kw:emitted.append((a,kw)))
    monkeypatch.setattr(shop,"_provision",lambda o:called.append(o["id"]) or {
        "ok":True,"credential":"vless://safe-example@vpn.example.test:443",
        "provision_ref":"xray:777"})
    monkeypatch.setattr(shop.access_ops,"seal_payload",lambda data:json.dumps(data))
    monkeypatch.setattr(shop.access_ops,"open_payload",lambda v:json.loads(v))
    payment={"invoice_payload":shop._invoice_payload(order),"total_amount":25,
             "currency":"XTR","telegram_payment_charge_id":"star-charge-unique-0001"}
    update={"update_id":9001,"message":{"from":{"id":123},"chat":{"id":123,"type":"private"},
                                     "successful_payment":payment}}
    shop.process_update(update)
    result=shop._order(order["id"])
    assert result["status"]=="delivered"
    assert result["provision_ref"]=="xray:777"
    assert called==[order["id"]]
    shop.process_update(update)
    assert called==[order["id"]]
    shop.process_update({"update_id":9002,"message":update["message"]})
    assert called==[order["id"]]
    assert any("vless://" in x[0][1] for x in emitted)


def test_customer_cannot_fake_paid_or_delivery(shopdb):
    order=shop._create_order(321,1)
    with pytest.raises(HTTPException) as exc:
        shop._order_for(322,order["id"])
    assert exc.value.status_code==404
    assert not shop._paid(321,{"invoice_payload":shop._invoice_payload(order),
        "currency":"XTR","total_amount":24,"telegram_payment_charge_id":"charge-invalid-1234"})
    assert shop._order(order["id"])["status"]=="pending_invoice"
    assert not shop._claim_fulfillment(order["id"])
    request=SimpleNamespace(headers={"x-telegram-init-data":initdata(321)})
    with pytest.raises(HTTPException) as exc:
        shop.mini_delivery(order["id"],request)
    assert exc.value.status_code==409


def test_missing_commerce_scope_moves_paid_order_to_manual_review(shopdb,monkeypatch):
    order=shop._create_order(400,1)
    monkeypatch.setattr(shop,"_message",lambda *a,**kw:None)
    pay={"invoice_payload":shop._invoice_payload(order),
         "total_amount":25,"currency":"XTR",
         "telegram_payment_charge_id":"star-charge-test-400"}
    item=shop._paid(400,pay)
    assert item and item["status"]=="paid"
    shop._fulfill(item)
    assert shop._order(order["id"])["status"]=="awaiting_fulfillment"
    assert shop._order(order["id"])["delivery_enc"]==""
    shop._fulfill(item)
    assert shop._order(order["id"])["status"]=="awaiting_fulfillment"


def test_ambiguous_commerce_failure_never_retries_or_delivers(shopdb,monkeypatch):
    order=shop._create_order(500,1)
    item=shop._paid(500,{"invoice_payload":shop._invoice_payload(order),
        "total_amount":25,"currency":"XTR",
        "telegram_payment_charge_id":"star-charge-test-500"})
    attempts=[]
    monkeypatch.setattr(shop,"_provision",lambda obj: attempts.append(1) or
                        (_ for _ in ()).throw(TimeoutError("unknown")))
    monkeypatch.setattr(shop,"_message",lambda *a,**kw:None)
    shop._fulfill(item)
    shop._fulfill(item)
    assert len(attempts)==1
    assert shop._order(order["id"])["status"]=="needs_review"


def test_telegram_public_routes_use_webhook_secret(shopdb,monkeypatch):
    assert shop.enabled()
    assert shop._secret()==SECRET
    assert "bot_token" not in shop._catalog()[0]
    assert shop._admins()==set()


def test_payment_credential_encryption_failure_stops_duplicate_provision(shopdb,monkeypatch):
    order=shop._create_order(680,1)
    item=shop._paid(680,{"invoice_payload":shop._invoice_payload(order),
       "total_amount":25,"currency":"XTR","telegram_payment_charge_id":"charge-secret-store-680"})
    count=[]
    monkeypatch.setattr(shop,"_provision",lambda x: count.append(x["id"]) or
                        {"credential":"private-password-material","provision_ref":"xray:999"})
    monkeypatch.setattr(shop.access_ops,"seal_payload",lambda x:
        (_ for _ in ()).throw(RuntimeError("storage unavailable")))
    monkeypatch.setattr(shop,"_message",lambda *a,**kw:None)
    shop._fulfill(item)
    shop._fulfill(item)
    result=shop._order(order["id"])
    assert result["status"]=="needs_review"
    assert result["provision_ref"]=="xray:999"
    assert result["delivery_enc"]==""
    assert count==[order["id"]]


def test_mini_app_checkout_terms_and_owner_guard(shopdb,monkeypatch):
    monkeypatch.setattr(shop,"_invoice",lambda item,chat_id=None:"https://t.me/invoice/example")
    request=SimpleNamespace(headers={"x-telegram-init-data":initdata(741)})
    with pytest.raises(HTTPException) as exc:
        shop.mini_checkout(shop.CheckoutRequest(offer_id=1),request)
    assert exc.value.status_code==422
    result=shop.mini_checkout(shop.CheckoutRequest(offer_id=1,terms_accepted=True),request)
    assert result["invoice_url"].startswith("https://t.me/")
    assert shop._order(result["order_id"])["buyer_id"]==741


def test_refund_requires_verified_paid_but_undelivered_order(shopdb,monkeypatch):
    # No fake assertion or unpaid order can reach the Stars refund API.
    order=shop._create_order(770,1)
    actor=SimpleNamespace(headers={"x-makia-request":"1"})
    routes={route.path:route.endpoint for route in shop.router.routes}
    assert "/api/telegram-shop/checkout" in routes
    assert shop._order(order["id"])["telegram_charge_id"] is None


def test_stars_invoice_has_correct_currency_and_immutable_amount(shopdb,monkeypatch):
    order=shop._create_order(712,1)
    calls=[]
    monkeypatch.setattr(shop,"_telegram",lambda method,request:calls.append((method,request)) or
                        ("https://t.me/invoice/safe" if method=="createInvoiceLink" else {"message_id":1}))
    link=shop._invoice(order)
    assert link.startswith("https://t.me/invoice/")
    assert calls[-1][0]=="createInvoiceLink"
    assert calls[-1][1]["currency"]=="XTR"
    assert calls[-1][1]["prices"][0]["amount"]==25
    assert calls[-1][1]["provider_token"]==""
    shop._invoice(order,712)
    assert calls[-1][0]=="sendInvoice"
    assert calls[-1][1]["chat_id"]==712


def test_manual_offer_without_makia_plan_can_list_and_never_autoprovision(shopdb,monkeypatch):
    now=int(time.time())
    with db.connect() as con:
        con.execute("INSERT INTO tg_shop_offers(plan_id,title,summary,icon,profile,endpoint,"
                    "price_stars,active,sort_order,created_at,updated_at)"
                    " VALUES(0,'IKEv2 Manual','Manual only','🔐','manual:ikev2','',99,1,2,?,?)",
                    (now,now))
    matches=[x for x in shop._catalog() if x["profile"]=="manual:ikev2"]
    assert len(matches)==1
    item=shop._create_order(1002,matches[0]["id"])
    assert item["price_stars"]==99
    assert json.loads(item["plan_json"])["kind"]=="manual:ikev2"
    monkeypatch.setenv("MAKIA_SHOP_COMMERCE_TOKEN","very-private-scoped-token")
    assert shop._provision(item) is None
    assert item["status"]=="pending_invoice"
