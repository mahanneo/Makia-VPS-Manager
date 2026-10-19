"""Offline native Windows launcher tests; no VPN interface or live account needed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from client.windows import makia_windows as ui


class WindowsLauncherTests(unittest.TestCase):
    def test_login_is_only_official_https_client_portal(self):
        self.assertEqual(ui.PORTAL_URL,"https://p.mahinet.shop/client/")
        with patch.object(ui.webbrowser,"open",return_value=True) as opener:
            self.assertTrue(ui.open_official_portal())
            opener.assert_called_once_with(ui.PORTAL_URL,new=2)

    def test_healthcheck_does_not_launch_browser_or_gui(self):
        with patch.object(ui.sys,"argv",["MakiaWindows.exe","--healthcheck"]), \
             patch.object(ui.webbrowser,"open",side_effect=AssertionError("browser launched")), \
             patch.object(ui.tk,"Tk",side_effect=AssertionError("GUI launched")):
            self.assertEqual(ui.main(),0)

    def test_empty_corrupt_and_metadata_status_never_claim_verified_vpn(self):
        with tempfile.TemporaryDirectory() as root,patch.object(ui,"STATE",Path(root)/"state.json"):
            self.assertIn("ثبت نشده",ui.local_state())
            ui.STATE.write_text("{",encoding="utf-8")
            self.assertIn("ثبت نشده",ui.local_state())
            ui.STATE.write_text(json.dumps({"mode":"process","pid":123}),encoding="utf-8")
            self.assertIn("آخرین فرمان",ui.local_state())
            self.assertNotIn("تأییدشده",ui.local_state())

    def test_gui_connector_is_same_installation_directory(self):
        with tempfile.TemporaryDirectory() as root:
            gui=Path(root)/"MakiaWindows.exe"
            with patch.object(ui.sys,"executable",str(gui)):
                self.assertEqual(ui.connector_path().name,"MakiaClientConnector.exe")
                self.assertEqual(ui.connector_path().parent,gui.parent.resolve())


if __name__=="__main__":
    unittest.main()
