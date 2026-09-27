# Makia VPS Manager 0.24.0-rc1 — UAT — Sanaei-style Structure

این UAT مخصوص بازطراحی ساختاری پنل با الگوی تعامل و معماری اطلاعاتی نزدیک به 3x-ui/Sanaei است. هویت Makia و Backend فعلی حفظ می‌شوند.

## 1. Login
- Login باید ساده، مرکزی و کم‌تزئین باشد.
- Logo/Brand Makia حفظ شود.
- Username/Password و Toggle نمایش رمز کار کنند.
- 2FA همان ساختار بصری را ادامه دهد.

## 2. Sidebar / Navigation
- Desktop: Rail باریک به‌صورت پیش‌فرض، Expand روی Hover و قابلیت Pin.
- Mobile: Drawer.
- ترتیب اصلی: Dashboard، Inbounds، Clients، Protocol Clients، Nodes، Network/Ports، Services، Live Sessions، Settings، Xray Tools، Logs، Backup، Update، Docs، Support.
- Settings و Xray Tools باید Submenu داشته باشند.
- Pin sidebar باید در localStorage حفظ شود.
- Ctrl+K باید Command Palette را باز کند.

## 3. Dashboard
- Action bar فشرده در بالا.
- Xray runtime state و Version واقعی.
- چهار Vital Tile برای CPU، Memory، Disk و Services.
- History واقعی 24h از Metrics API.
- Protocol/client distribution از Access API.
- System strip شامل uptime، traffic، live sessions و panel endpoint.
- هیچ عدد نمونه یا Fake مجاز نیست.

## 4. Inbounds
- صفحه مستقل Inbounds باید از Xray runtime واقعی خوانده شود.
- هر Inbound: Tag، Protocol، Listen/Port، Client count و Managed client count.
- Add Inbound/Client، Diagnostics و Advanced JSON باید از Backend واقعی استفاده کنند.
- UI نباید قابلیت Edit/Delete جعلی برای Inbound بسازد؛ Advanced JSON مرجع عملیات پیشرفته است.

## 5. Clients
- یک Client list واحد برای SSH/Xray/WireGuard/OpenVPN.
- Filter بر اساس Protocol و Search.
- Create User از Wizard واقعی.
- Export/QR/Protected ZIP/Manage/Revoke مطابق قابلیت واقعی هر Protocol.

## 6. Protocol-specific workspaces
- SSH، Xray، WireGuard و OpenVPN از Submenu دسترسی‌ها قابل دسترسی باشند.
- هیچ قابلیت موجود نسخه قبل حذف نشود.
- Xray: quota/expiry/reset/IP limit فقط جایی که Backend پشتیبانی دارد.
- OpenVPN: quota جعلی نمایش داده نشود.

## 7. Settings
- تنظیمات از Main Sidebar submenu قابل دسترسی باشند.
- داخل صفحه، category tabs فشرده و افقی باشند.
- General/Security/Subscription/API/Recovery از submenu اصلی باز شوند.
- همه settings backend واقعی قبلی باقی بمانند.

## 8. Services / Network
- Service controls واقعی Start/Stop/Restart حفظ شوند.
- Network/Ports از Endpoint Matrix و Runtime واقعی استفاده کند.
- Transport-aware collision rule حفظ شود.

## 9. Responsive
Desktop: 1280×800 و 1440×900.
Mobile: 390×844 و 430×932.
- Document نباید horizontal overflow داشته باشد.
- Tables می‌توانند داخل container خود scroll شوند.
- Sidebar drawer باید بعد از انتخاب View بسته شود.

## 10. Stable Gate
- Unit/contract tests PASS.
- Browser smoke PASS.
- Xray core smoke PASS.
- Screenshot review: Login, Dashboard, Inbounds, Clients, SSH, Xray, WireGuard desktop/mobile, OpenVPN, Services, Ports, Settings.
- Clean install و Upgrade واقعی روی Ubuntu 22.04/24.04.
