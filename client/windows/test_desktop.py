"""Windows-specific Makia Desktop smoke tests; no live VPN or credentials."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("makia_desktop",Path(__file__).with_name("makia_desktop.py"))
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DesktopTests(unittest.TestCase):
    def test_controller_https_only(self):
        self.assertEqual(app.origin("https://P.MAHINET.SHOP/"),"https://p.mahinet.shop")
        for url in ("http://p.mahinet.shop","https://user:pass@p.mahinet.shop",
                    "https://p.mahinet.shop/client/","https://p.mahinet.shop?a=1"):
            with self.assertRaises(ValueError):
                app.origin(url)

    def test_dpapi_current_user_round_trip(self):
        if os.name!="nt": self.skipTest("Windows CurrentUser DPAPI required")
        raw=b"synthetic-only-test-token-not-a-production-credential"
        sealed=app.dpapi(raw)
        self.assertNotEqual(raw,sealed)
        self.assertEqual(app.dpapi(sealed,True),raw)
        self.assertEqual(app.unseal(app.seal(raw.decode())),raw.decode())

    def test_save_record_never_persists_unencrypted_token(self):
        if os.name!="nt": self.skipTest("Windows CurrentUser DPAPI required")
        old_root,old_store=app.ROOT,app.STORE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                app.ROOT=Path(tmp)
                app.STORE=app.ROOT/"device.json"
                app.save_record("https://p.mahinet.shop","dev-private-test","ms_secret_dummy_token",9999999999,True)
                raw=app.STORE.read_text("utf-8")
                self.assertNotIn("ms_secret_dummy_token",raw)
                self.assertNotIn("dev-private-test",raw)
                payload=app.read_saved()
                self.assertEqual(app.unseal(payload["token_sealed"]),"ms_secret_dummy_token")
                app.save_record("https://p.mahinet.shop","dev-private-test",remember=False)
                self.assertFalse(app.read_saved()["token_sealed"])
        finally:
            app.ROOT,app.STORE=old_root,old_store

    def test_profile_launch_never_accepts_arbitrary_uri(self):
        for url in ("https://evil.example","makia://disconnect",
                    "makia://connect?controller=http%3A%2F%2Fevil.example&ticket=abc",
                    "makia://connect?controller=https%3A%2F%2Fp.mahinet.shop&ticket=abc&extra=1"):
            with self.assertRaises((ValueError,RuntimeError)):
                app.launch_ticket(url)


if __name__=="__main__":
    unittest.main()
