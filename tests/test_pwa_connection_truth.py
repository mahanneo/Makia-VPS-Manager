"""PWA must not imply VPN connectivity from account/session/internet state."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_pwa_marks_network_indicator_as_device_internet_not_vpn():
    page=(ROOT/"app/templates/client_app.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    assert 'id="networkState"' in page
    assert "وضعیت اینترنت دستگاه" in page
    assert "اینترنت دستگاه: برقرار (VPN تأیید نشده)" in js
    assert 'navigator.onLine?"آنلاین":"آفلاین"' not in js


def test_pwa_explains_it_cannot_establish_a_vpn_tunnel():
    page=(ROOT/"app/templates/client_app.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/client.js").read_text(encoding="utf-8")
    assert "وضعیت حساب یا آنلاین بودن مرورگر به معنی اتصال VPN نیست." in page
    assert "اتصال کامل دستگاه با نصب صرف PWA ایجاد نمی‌شود." in page
    assert "نصب PWA تونل VPN ایجاد نمی‌کند" in js
    assert "این صفحه فقط اطلاعات حساب و تحویل کانفیگ را مدیریت می‌کند" in js
    assert "برقراری تونل VPN یا تغییر IP دستگاه هنوز در این صفحه تأیید نشده است." in js
