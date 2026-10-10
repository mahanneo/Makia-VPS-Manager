"""One-time setup for Makia's independent customer bot. Never print the token."""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import dotenv_values
from .integration_ops import _json_request

CONFIG=Path("/etc/makia-vps-manager/telegram-shop.env")


def main():
    if not CONFIG.is_file():
        raise SystemExit("Missing root-only /etc/makia-vps-manager/telegram-shop.env")
    if CONFIG.stat().st_mode & 0o077:
        raise SystemExit("Shop env must be chmod 600 and inaccessible to group/others")
    env={str(k):str(v or "") for k,v in dotenv_values(CONFIG).items()}
    token=env.get("MAKIA_SHOP_BOT_TOKEN","")
    secret=env.get("MAKIA_SHOP_WEBHOOK_SECRET","")
    public=env.get("MAKIA_SHOP_PUBLIC_URL","")
    enabled=env.get("MAKIA_SHOP_ENABLED","0")=="1"
    if not enabled:
        raise SystemExit("Shop disabled. No bot/webhook changes.")
    if not re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}",token):
        raise SystemExit("Bot token missing or invalid")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}",secret):
        raise SystemExit("Webhook secret missing or invalid")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::443)?/telegram/shop/?",public):
        raise SystemExit("Use an HTTPS Mini App URL ending /telegram/shop")
    api="https://api.telegram.org/bot"+token+"/"
    result=_json_request(api+"getMe")
    if not result.get("ok") or not (result.get("result") or {}).get("is_bot"):
        raise SystemExit("Telegram getMe could not verify the bot")
    host=public.split("/telegram/shop")[0]
    hook=host+"/telegram/shop/webhook"
    # Never register webhook unless independent bot and HTTPS app are valid.
    result=_json_request(api+"setWebhook",method="POST",body={
        "url":hook,"secret_token":secret,
        "allowed_updates":["message","callback_query","pre_checkout_query"],
        "drop_pending_updates":False,
        "max_connections":10
    })
    if not result.get("ok"): raise SystemExit("setWebhook failed")
    _json_request(api+"setMyCommands",method="POST",body={"commands":[
        {"command":"start","description":"ورود به ماکیا"},
        {"command":"shop","description":"مشاهده سرویس‌ها"},
        {"command":"orders","description":"سفارش‌های من"},
        {"command":"terms","description":"قوانین خرید"},
        {"command":"support","description":"ارتباط با پشتیبانی"},
        {"command":"paysupport","description":"پیگیری پرداخت"},
        {"command":"redeliver","description":"دریافت مجدد آخرین کانفیگ"}
    ]})
    _json_request(api+"setChatMenuButton",method="POST",body={
        "menu_button":{"type":"web_app","text":"✦ فروشگاه ماکیا",
                       "web_app":{"url":public}}
    })
    print("Makia Telegram Shop setup verified; webhook, commands and Mini App menu configured.")
    print("Bot username:",(result.get("result") or {}).get("username","(available in @BotFather)"))
    print("Webhook path: /telegram/shop/webhook")


if __name__=="__main__":
    main()
