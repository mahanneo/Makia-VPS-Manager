# MAKiA Commerce — Multi-Payment Contract (2026-10-10)

## دامنه و مرز قوانین تلگرام

این سند انتخاب مالک پروژه را ثبت می‌کند: پرداخت با کارت‌به‌کارت، انتقال رمزارز، تأیید مدیر و در آینده درگاه داخلی **علاوه بر Stars** باید پشتیبانی شود.

**قانون محصول:** اشتراک VPN یک *خدمت دیجیتال* است. در رابط ربات یا Telegram Mini App، فروش آن فقط با Telegram Stars (`XTR`) انجام می‌شود. نمایش شماره کارت، کیف پول، لینک پرداخت غیرStars یا هدایت از چت/Mini App به خرید همان خدمت در سایت خارجی، راهکار فروش داخل تلگرام نیست و نباید اضافه شود. منابع: https://core.telegram.org/bots/payments-stars و https://telegram.org/tos/bot-developers

پرداخت‌های دیگر باید در **فروشگاه وب مستقل** با گردش خرید مستقل از Telegram Bot/Mini App انجام شوند و فروش داخل تلگرام را دور نزنند. ربات می‌تواند برای خدمات پس از فروش و تحویل امن دسترسی‌ای که قبلاً مستقل خریداری و به حساب مشتری متصل شده، استفاده شود.

## معماری بدون Owner موازی

```
Independent web storefront (MahiNet)
  -> Payment options: bank transfer / approved crypto rail / licensed local PSP
  -> Web order + amount + currency + terms snapshot
  -> Proof submitted / PSP callback
  -> Finance validation / signed PSP callback
  -> Web order: paid (only after independent verification)
  -> Existing Makia commerce API (scoped, localhost, Idempotency-Key)
  -> Encrypted delivery + entitlement binding
  -> Telegram bot: optional AFTER-SALE subscription view and delivery

Telegram MAKiA customer bot / Mini App
  -> XTR invoice only for any inside-Telegram sale
  -> Telegram verified successful_payment
  -> same existing Makia commerce API
  -> entitlement binding and private delivery
```

**Makia is the single owner of actual VPN access and provisioning.**
MahiNet or Telegram never writes WireGuard/OpenVPN/Xray/system configuration
directly, and do not independently implement protocol users or policy.
Use the existing `/api/v1/commerce/provision` contract with a dedicated
scope-limited token and unique external order ID; never retry an ambiguous
upstream response blindly. A single server entitlement may be linked to a
web order or Stars order with a source tag, never duplicated.

## Independent web payment requirements

1. **Card-to-card** (web only): admin-configured bank name/cardholder/masked
   account presentation and payment instructions. Buyer submits bank reference,
   transfer date/time and optional receipt; neither screenshot nor customer
   statement is payment verification. Operator must reconcile actual bank
   settlement and exact amount before marking paid. Never store card secrets.
2. **Crypto** (web only): only administrator-approved currency + **network**
   + receiving public address. Display network prominently to prevent asset loss.
   Buyer submits `txid`; backend validates transaction on the correct chain,
   matching destination, token contract, amount and confirmation threshold.
   No private key/seed phrase may be entered or stored by the bot.
   Reused txid or payment evidence cannot settle multiple orders. Applicable
   local laws and the payment provider's acceptable-use policies govern.
3. **Iranian PSP (future)**: require merchant account, gateway API credentials
   in server-side secrets, signed/verified callback, server-to-server verification,
   unique PSP transaction reference, exact amount in documented units and
   idempotency. Do not assume VPN subscription sales are approved by PSP.
4. **Price and records:** independently configured real price; amounts stored
   as integer tomans with explicit rial↔toman conversion for gateways that
   use rial. Crypto amounts use decimal precision and a rate/expiry snapshot.
   Do not infer web price from Stars or vice versa.
5. **Order machine:** `created → awaiting_payment → verification_pending →
   paid → provisioning → delivered`; disputes can enter `needs_review`.
   Payment decline/expiry/cancel/refund are explicit audited transitions.
   Every manual approval records actor, UTC time, reconciliation evidence
   reference and order ID. Paid is irreversible without an auditable refund.
6. **Fraud prevention:** unique payment reference per order, buyer ownership,
   rate limits, CSRF, immutable order amount, independent duplicate transfer
   detection, two-person review option, maximum approval limits and financial
   reconciliation report. Financial and VPN provisioning audit logs must not
   contain VPN credential plaintext.
7. **After-sale Telegram account linking:** signed one-use short-lived pairing
   code initiated from authenticated web account, redeemed by same Telegram
   user. The bot must not accept a user-supplied order number alone to reveal
   a credential. No alternative payment options, card numbers, crypto wallet
   addresses or outbound checkout links appear in the Telegram bot/Mini App.
8. **Safety:** never enable a new payment method without sandbox/payment
   tests, refund flow, real notification and manual reconciliation tests.
   Install without restarting current active VPN listeners.

## Current implementation status

- Draft PR #116: Telegram Stars route with signed initData, scoped commerce
  fulfillment and MAKiA Studio; default OFF; no live bot or payments yet.
- Legacy Makia MahiNet commerce API already has idempotent provisioning;
  web payment workflows, bank confirmations, chain verification, PSP API and
  secure account pairing **are not yet implemented** by this change.
- Production remains Makia 1.6.5 until an approved update + UAT.
- Browser extension/mobile/Outline sessions and MahiNet must be preserved.

## Practical next steps

1. Connect the Edari-Sec remote agent under the same authorized Desktop
   Commander account; validate device and SSH access to the production VPS.
2. Collect **only** nonsecret bot username (`@...`) in the chat. Bot token
   goes exclusively into root-only `telegram-shop.env` on VPS; use separate
   bot token from existing operator notifications.
3. Configure customer support username, admin Telegram numeric IDs, HTTPS
   webhook, optional Mini App launch button after offline UAT.
4. Build independent web payment ledger and admin reconciliation surface in
   MahiNet with a provider-neutral adapter, then integrate only through
   Makia commerce API. Payment methods start disabled.
5. Test real Telegram Stars test purchases and independent web payments
   separately. Confirm all protocols actually supported by the live host.
