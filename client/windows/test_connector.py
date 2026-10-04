import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["LOCALAPPDATA"]=tempfile.mkdtemp(prefix="makia-connector-test-")
spec=importlib.util.spec_from_file_location("makia_connector",Path(__file__).with_name("makia_client_connector.py"))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ConnectorTests(unittest.TestCase):
    def test_device_dry_run_builds_tun_profile(self):
        delivery={
            "engine":"xray",
            "share_link":"trojan://secret@example.com:443?security=tls&sni=example.com"
        }
        result=mod.connect_delivery(delivery,dry_run=True)
        self.assertEqual(result["connection_mode"],"device")
        self.assertEqual(result["outbound"],"trojan")
        cfg=json.loads(Path(result["profile"]).read_text(encoding="utf-8"))
        inbound=cfg["inbounds"][0]
        self.assertEqual(inbound["type"],"tun")
        self.assertTrue(inbound["auto_route"])

    def test_wireguard_dry_run_is_full_device(self):
        raw=b"[Interface]\nPrivateKey = test\n"
        delivery={
            "engine":"wireguard",
            "native_base64":__import__("base64").b64encode(raw).decode(),
            "native_filename":"makia.conf",
        }
        result=mod.connect_delivery(delivery,dry_run=True)
        self.assertEqual(result["mode"],"wireguard")

    def test_windows_source_has_no_browser_native_host_runtime(self):
        source=Path(__file__).with_name("makia_client_connector.py").read_text(encoding="utf-8")
        self.assertNotIn("nativeMessaging",source)
        self.assertNotIn("MakiaBrowserHost",source)
        self.assertNotIn("BROWSER_STATE",source)
        self.assertNotIn("--native-host",source)


if __name__=="__main__":
    unittest.main()
