# Makia VPS Manager 0.23.0-rc1 — UAT — Neon UI Rebuild

این UAT مخصوص بازطراحی کامل رابط کاربری پنل است و باید علاوه بر Gateهای نسخه 0.22، روی مرورگر واقعی Desktop و Mobile اجرا شود.

## 1. Login / 2FA
- صفحه Login باید دارای هویت MAKIA، پس‌زمینه Dark/Blue، Card مرکزی شفاف و فیلدهای واضح Username/Password باشد.
- Error ورود باید بدون شکستن Layout نمایش داده شود.
- در صورت فعال بودن 2FA، صفحه OTP باید همان Design Language را حفظ کند.
- Login و Logout واقعی باید بدون تغییر در Session Security کار کنند.

## 2. Main shell
- Sidebar ثابت RTL روی Desktop و Drawer روی Mobile.
- منو باید به بخش‌های «مدیریت کاربران»، «مدیریت سرور و سرویس‌ها»، «گزارش‌ها و نگهداری»، «تنظیمات و ابزارها» تقسیم شود.
- زیرمنوی کاربران شامل SSH، V2Ray/Xray، WireGuard و OpenVPN باشد.
- Topbar شامل Search / Refresh / Account باشد.
- هیچ قابلیت Backend به دلیل بازطراحی UI حذف نشود.

## 3. Dashboard
- چهار کارت اصلی: کاربران فعال، ترافیک ثبت‌شده، وضعیت شبکه، سرویس‌های فعال.
- نمودار 24h از داده واقعی Metrics API.
- Donut توزیع کاربران از Access API و بدون مقدار Fake.
- وضعیت سرویس‌ها از Overview API.
- کلیه مقادیر باید از API واقعی Panel خوانده شوند.

## 4. User workspaces
### SSH
- Header مستقل + Create User.
- Total / Active / Disabled.
- Search / Filter / Bulk lock-unlock / Extend / Disconnect.
- Edit/Delete/Disconnect واقعی.

### Xray
- Header مستقل + Create Client.
- Client count / active / disabled / traffic.
- Quota / Expiry / Reset / IP Limit / Status.
- Subscription / Policy / Reset actions.
- Diagnostics و Advanced JSON.

### WireGuard
- Peer count / active / recent handshake / aggregate traffic.
- QR / Config / Enable-Disable / Delete.
- Diagnostics.
- Mobile layout بدون horizontal page overflow.

### OpenVPN
- Client count / service state / port.
- Create Client / Diagnostics / Repair.
- Native/Protected delivery.
- UI نباید Quota جعلی per-client نمایش دهد.

## 5. Service management
- همه سرویس‌های Allowlist شده در List جدید نمایش داده شوند.
- Running/Stopped/Missing باید از Runtime واقعی تعیین شود.
- Start/Restart/Stop باید به API واقعی سرویس متصل باشد.

## 6. Port management
- SSH/Xray/WireGuard/OpenVPN از Endpoint Matrix خوانده شوند.
- Port، Transport، Runtime status و Manage action نمایش داده شود.
- TCP/443 و UDP/443 نباید به‌عنوان Collision اشتباه نمایش داده شوند.
- Endpoint readiness باید همچنان در دسترس باشد.

## 7. Settings / Security / Backups / Reports
- تمام Tabها و Actionهای قبلی باید قابل استفاده باقی بمانند.
- تغییر UI نباید API Token، 2FA، Backup، Update، Support یا Node management را حذف کند.

## 8. Responsive
Desktop: 1280×800 و 1440×900.
Mobile: 390×844 و 430×932.
- Sidebar در Mobile باید Drawer باشد.
- Dashboard cardها collapse شوند.
- Tableهای عریض فقط داخل container خود scroll شوند؛ کل Document نباید overflow افقی داشته باشد.

## 9. Release Gate
قبل از Stable:
- Unit/contract tests PASS
- Browser Smoke PASS
- Xray Core Smoke PASS
- یک Clean Install واقعی روی Ubuntu 22.04/24.04
- یک Upgrade واقعی از 0.22.0-rc1
- Screenshot review از Login, Dashboard, SSH, Xray, WireGuard, OpenVPN, Services, Ports, Settings
