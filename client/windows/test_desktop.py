"""Desktop client contract; does not require a desktop/session on CI."""
import importlib.util
import http.cookiejar
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE=Path(__file__).with_name("makia_desktop.py")
spec=importlib.util.spec_from_file_location("makia_desktop",MODULE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DesktopContractTests(unittest.TestCase):
    def test_pinned_https_controller_and_no_default_password(self):
        self.assertEqual(mod.CONTROLLER,"https://p.mahinet.shop")
        self.assertTrue(mod.CONTROLLER.startswith("https://"))
        self.assertNotIn("password",str(mod.SESSION_FILE).lower())

    def test_only_owned_ticket_kind_and_id_allowed(self):
        c=mod.ClientAPI()
        with self.assertRaises(ValueError):
            c.ticket({"delivery_kind":"../../admin","delivery_id":1})
        with self.assertRaises(ValueError):
            c.ticket({"delivery_kind":"protocol","delivery_id":0})

    def test_login_authentication_must_verify_account_endpoint(self):
        c=mod.ClientAPI()
        with mock.patch.object(c,"_request",side_effect=[{"ok":True},PermissionError("expired")]) as req:
            with self.assertRaises(PermissionError):
                c.login("customer","password",False)
            self.assertEqual(req.call_args_list[0].args[0],"/client/login")
            self.assertEqual(req.call_args_list[1].args[0],"/client/api/me")

    def test_connect_ticket_never_directly_fetches_a_profile(self):
        c=mod.ClientAPI()
        item={"delivery_kind":"protocol","delivery_id":11}
        with mock.patch.object(c,"_request",return_value={"launch_url":"makia://connect?ticket=opaque"}) as req:
            c.ticket(item)
            self.assertEqual(req.call_args.args[0],"/client/api/connect/protocol/11/ticket")
            self.assertEqual(req.call_args.args[1],{})

    def test_session_file_carries_only_encrypted_current_user_cookie(self):
        c=mod.ClientAPI()
        c.jar.set_cookie(mod._cookie("makia_client_session","fake-session",9999999999))
        c.jar.set_cookie(mod._cookie("malicious","no",9999999999))
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(mod,"ROOT",Path(temp)),mock.patch.object(mod,"SESSION_FILE",Path(temp)/"auth.dat"):
                with mock.patch.object(mod,"protect",side_effect=lambda raw,decrypt=False:b"dpapi"+raw) as cipher:
                    c.save()
                    self.assertTrue((Path(temp)/"auth.dat").read_bytes().startswith(b"dpapi"))
                    text=cipher.call_args.args[0].decode("utf-8")
                    self.assertIn("makia_client_session",text)
                    self.assertNotIn("malicious",text)

    def test_profile_engines_are_explicitly_limited(self):
        c=mod.ClientAPI()
        with mock.patch.object(c,"_request",return_value={"items":[
            {"engine":"xray"},{"engine":"openvpn_wstunnel"},{"engine":"unsupported"}
        ]}):
            self.assertEqual(len(c.profiles()),2)

    def test_actual_connector_binary_is_required(self):
        with mock.patch.object(mod,"CONNECTOR",Path("Z:/missing/makia.exe")):
            with self.assertRaisesRegex(RuntimeError,"نصب نیست"):
                mod.connector("--disconnect")


if __name__=="__main__":
    unittest.main()
