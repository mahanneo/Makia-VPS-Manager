# Makia Telegram Commerce Studio — customer bot / Mini App

## راهنمای سریع فارسی

**وضعیت فعلی:** کد فروشگاه و ربات مشتری در نسخه کاندید ۱.۶.۶ آماده شده، اما روی سرور اصلی فعال نشده است. بدون توکن رباتی که خود مالک در BotFather ایجاد می‌کند، امکان فعال‌سازی وجود ندارد.

**اجزای ربات:** منوی اختصاصی فارسی، فروشگاه Mini App با ظاهر تیره و طراحی ماکیا، پلن‌ها و قیمت به ⭐ Stars، فاکتور داخل تلگرام، سوابق سفارش، تحویل محرمانه کانفیگ، پشتیبانی پرداخت و صفحه مدیر در مسیر `/telegram/shop/admin`.

**انواع سرویس:** هر پروتکلی که واقعاً در Makia امکان صدور دارد، می‌تواند به‌صورت کالای دستی در فروشگاه نمایش داده شود. Xray با inbound مشخص، Outline، WireGuard و OpenVPN در صورت داشتن API Token محدود و پیکربندی صحیح قابلیت صدور خودکار دارند. SSH، IKEv2 و حالت‌های WStunnel فعلاً فقط با تحویل بررسی‌شدهٔ مدیر عرضه می‌شوند؛ گزینهٔ دستی به معنی صدور خودکار نیست.

**قانون مهم:** فروش سرویس دیجیتال در محیط تلگرام با Telegram Stars و واحد `XTR` انجام می‌شود. فقط پیام معتبر `successful_payment` پس از تطبیق شناسهٔ خریدار، مبلغ و شناسهٔ فاکتور باعث انتقال سفارش به پرداخت‌شده می‌شود. فیش، تصویر و دکمهٔ «پرداخت کردم» هیچ‌کدام تأیید پرداخت محسوب نمی‌شوند.

**فعال‌سازی امن:** از BotFather یک ربات **جداگانه** برای مشتریان بسازید؛ توکن را فقط روی VPS در `/etc/makia-vps-manager/telegram-shop.env` با دسترسی 0600 ذخیره کنید، نه در چت یا GitHub. تنظیمات `MAKIA_SHOP_ENABLED` به‌صورت پیش‌فرض خاموش است. پس از نصب نسخه آزموده‌شده، اتصال وبهوک و تست پرداخت در محیط آزمایشی تلگرام انجام می‌شود. نسخه زنده و کاربران VPN فعلی نباید برای راه‌اندازی ربات قطع شوند.

در ادامه همین سند، جزئیات فنی، فایل تنظیمات نمونه، ساخت API Token محدود، تست، بازگشت و شرایط انتشار آمده است.

---

**State: opt-in feature candidate, OFF by default.** Does not reuse the existing operator
notification bot token and does not publish anything to Telegram until the bot owner connects
a new BotFather bot and registers its webhook.

## Product architecture

- Storefront: private chat buttons and premium Persian mobile-first Mini App
  at \`https://p.mahinet.shop/telegram/shop\`.
- Inventory source: Makia's existing \`service_plans\`. An administrator creates a
  shop **offer** linked to a plan; Stars price, title and profile are separately
  set explicitly. Active offers are hidden when their source plan is inactive.
  Price and plan limits are snapshot into an order so later edits cannot change an invoice.
- Payment: Telegram Stars **XTR** only. Bot invokes \`sendInvoice\`; Mini App invokes
  \`createInvoiceLink\`/the Telegram payment sheet. Pre-checkout is validated by
  buyer identity, payload and exact price. Only a genuine \`successful_payment\`
  update authenticated with Telegram's webhook secret can move an order to Paid.
  The unique \`telegram_payment_charge_id\` prevents duplicate paid records.
- Fulfillment: selected \`xray:<inbound_tag>\`, \`outline\`, \`wireguard\`,
  \`openvpn\` offers can use Makia's *existing* \`commerce:provision\` API over
  \`127.0.0.1:8787\` with a **dedicated scoped API token** and per-order
  \`Idempotency-Key\`. Token configured only on the server.
- Other profiles (including SSH) are **manual fulfillment** after verified
  Stars payment. They are not misrepresented as auto-provisioned. On missing
  commerce credentials, the order stays paid/awaiting fulfillment. Ambiguous
  upstream provisioning failures become \`needs_review\`, never automatically retried.
- Delivery: encrypted at rest with Makia's existing payload encryption,
  private Telegram chat message when it fits and authenticated Mini App order
  retrieval/copy. No credential appears in public catalog or admin order lists.
- Admin Studio: \`/telegram/shop/admin\` behind existing local-admin login and
  \`X-Makia-Request: 1\` CSRF contract. Offer creation/editing, activation,
  paid-order queue, authenticated manual fulfillment, resend and guarded Stars
  refund for unpaid-outstanding (paid but undelivered) manual orders.
- Existing Telegram operator status/backup bot continues using its old
  \`/integrations/telegram/webhook\` and own settings. No token reuse.

**Telegram rules:** digital services sold inside bots and Mini Apps must use
Stars (XTR). Do not add card-to-card, crypto or external gateways to these
in-Telegram purchase actions. See
https://core.telegram.org/bots/payments-stars and
https://telegram.org/tos/bot-developers .

## 1 — Install the software (without activating commerce)

Install only a tested, release-approved Makia build that includes
\`app/telegram_shop.py\` and the new systemd EnvironmentFile. The module uses
the existing SQLite database and creates *new* tables:
\`tg_shop_offers\`, \`tg_shop_orders\`, \`tg_shop_updates\`.
It does not alter old \`service_plans\`, commerce idempotency,
credential tables or VPN runtime configurations.

Before updating a production VPS: make a data and runtime backup; preserve
MahiNet, Outline and running VPN listeners. Do **not** run a new feature branch
on live production without CI, clean install, migration and host-UAT gates.

## 2 — Create a **separate** customer bot

1. In Telegram, open the genuine verified **@BotFather** and issue \`/newbot\`.
   Set a branded display name such as \`MAKiA | Access Atelier\` and choose an
   available unique bot username ending with \`bot\`.
2. Configure its avatar, short description, About and commands in BotFather.
   The setup tool later configures commands and Mini App menu automatically.
3. **Never paste the API token into ChatGPT or the repository.** Keep the token
   inside a root-only file on the VPS. Use the real numeric Telegram IDs for
   authorized admin notifications, not usernames. Owners should enable
   Telegram account two-step verification.

Example \`/etc/makia-vps-manager/telegram-shop.env\` (placeholders only):

\`\`\`dotenv
MAKIA_SHOP_ENABLED=0
MAKIA_SHOP_BOT_TOKEN=123456789:REPLACE_WITH_PRIVATE_BOTFATHER_TOKEN
MAKIA_SHOP_WEBHOOK_SECRET=REPLACE_WITH_RANDOM_32PLUS_URLSAFE_CHARS
MAKIA_SHOP_PUBLIC_URL=https://p.mahinet.shop/telegram/shop
MAKIA_SHOP_ADMIN_IDS=123456789
MAKIA_SHOP_SUPPORT=YourSupportUsername
MAKIA_SHOP_COMMERCE_TOKEN=
\`\`\`

Create the secret with Python's \`secrets.token_urlsafe(32)\` locally on VPS,
**not** in chat. Edit as root and \`chmod 600\` the environment file.
The bot token must be different from Makia's existing operator
\`telegram_secret\`; each Telegram bot has only one webhook.
\`MAKIA_SHOP_ENABLED=0\` is an intentional sales kill-switch.

## 3 — Prepare offers and scoped provisioning

Log into the Makia panel and open
\`https://p.mahinet.shop/telegram/shop/admin\`.

- Create source plans through Makia's existing Plan Manager.
- In Commerce Studio select a plan, enter accurate Stars amount, name,
  support description, icon, endpoint, fulfillment profile and sort order.
- For Xray, choose the exact live inbound tag in \`xray:<tag>\`.
  For Outline, \`outline\`; WireGuard, \`wireguard\`; OpenVPN, \`openvpn\`.
  For SSH, select \`manual:ssh\` and deliver a verified account only via
  the existing Makia admin procedures.
- Keep offers disabled until both payment and delivery have passed test-UAT.
- Make a **new** Makia API token limited to \`commerce:provision\`, then add
  it to the root-only environment file as \`MAKIA_SHOP_COMMERCE_TOKEN\`.
  The commerce endpoint is restricted by default to local loopback callers.
  Avoid sharing the broader MahiNet storefront token or panel admin session.

Note: real Xray/Outline enforcement differs from native WireGuard/OpenVPN.
For the latter, per-customer quota/expiry enforcement is not native to
commerce provisioning. Do not advertise hard limits that the selected
protocol does not enforce.

## 4 — Enable and configure Telegram

After reviewing test invoices and completing offline UAT:

- Change \`MAKIA_SHOP_ENABLED=1\` in the root-only env.
- Reload only the Makia application backend under a reviewed maintenance
  procedure. Do not restart VPN services, Nginx, MahiNet or Outline.
- Run \`cd /opt/makia-vps-manager && .venv/bin/python -m app.telegram_shop_setup\`
  to validate the bot via \`getMe\`, register the HTTPS secret-token webhook,
  set Persian commands and set its Mini App menu button.
- Open the bot in Telegram and test \`/start\`, \`/shop\`, \`/orders\`, \`/terms\`,
  \`/support\`, \`/paysupport\`.
- Configure the customer-facing mini app in BotFather when applicable.
- Use Telegram's test environment for payment testing.
  **Never execute real Stars purchases merely for unattended CI.**

For a rollback, switch \`MAKIA_SHOP_ENABLED=0\` and reload only the backend.
Disabling the feature rejects all customer checkout/webhook calls. Coordinate
with Telegram webhook configuration and reconcile pending Stars payments
before final shutdown.

## Order lifecycle and failure policy

\`\`\`text
catalog -> pending_invoice (NOT PAID)
  -> Telegram pre_checkout_query [amount + buyer + nonce checked]
  -> successful_payment (XTR and charge ID checked)
  -> paid -> fulfilling
      -> delivery_pending -> delivered (encrypted + private)
      -> awaiting_fulfillment (manual/commerce token missing)
      -> needs_review (ambiguous commerce result, NEVER blind retry)
      -> refunding -> refunded (guarded, undelivered-only)
\`\`\`

Admin Studio never marks a click, invoice, screenshot or customer
assertion as paid. If delivery does not reach Telegram the encrypted
credential can be retrieved from authenticated Mini App orders. A
payment dispute is handled through \`/paysupport\`, customer support and
the verified Stars refund method. Do not delete transaction history.

## Security gate before public sales

- HTTPS certificate works, bot \`setWebhook\` secret validates, HMAC
  \`initData\` is checked server-side, stale auth and duplicate fields rejected.
- Unauthorized visitors cannot read shop orders or delivery links.
- Legacy operator Telegram webhook and current MahiNet payments unaffected.
- Test payment success with the exact user, invoice amount, currency XTR,
  duplicate update ID, duplicate charge ID, and denied fake callback.
- Test existing Makia profile issuance from a **test** offer with a
  dedicated scoped token, verify real client connect and exit IP.
- Verify quota/expiry/refund/revocation semantics by actual protocol.
- Confirm correct Telegram Stars pricing, availability, refund policy,
  operator account two-step verification and support response workflow.
- CI, clean install and safe update/rollback before public deployment.

This feature is not described as LIVE until the owner supplies a new BotFather
identity/secret and real Telegram payment and device UAT have passed.
