import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

os.environ["LOCALAPPDATA"]=tempfile.mkdtemp(prefix="makia-connector-test-")
spec=importlib.util.spec_from_file_location("makia_connector",Path(__file__).with_name("makia_client_connector.py"))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ConnectorTests(unittest.TestCase):
    def test_browser_config_uses_local_mixed_proxy(self):
        delivery={
            "engine":"xray",
            "share_link":"vless://11111111-1111-1111-1111-111111111111@example.com:443?security=tls&sni=example.com"
        }
        result=mod.connect_delivery(delivery,dry_run=True,connection_mode="browser")
        self.assertEqual(result["connection_mode"],"browser")
        self.assertGreaterEqual(result["proxy_port"],2080)
        cfg=__import__("json").loads(Path(result["profile"]).read_text(encoding="utf-8"))
        inbound=cfg["inbounds"][0]
        self.assertEqual(inbound["type"],"mixed")
        self.assertEqual(inbound["listen"],"127.0.0.1")
        self.assertFalse(inbound["set_system_proxy"])

    def test_device_dry_run_no_longer_uses_undefined_delivery(self):
        delivery={
            "engine":"xray",
            "share_link":"trojan://secret@example.com:443?security=tls&sni=example.com"
        }
        result=mod.connect_delivery(delivery,dry_run=True,connection_mode="device")
        self.assertEqual(result["connection_mode"],"device")
        self.assertEqual(result["outbound"],"trojan")

    def test_browser_rejects_wireguard(self):
        with self.assertRaisesRegex(RuntimeError,"Full Device"):
            mod.connect_delivery({"engine":"wireguard","native_base64":""},dry_run=True,connection_mode="browser")

    def test_browser_and_device_state_are_isolated(self):
        self.assertNotEqual(mod.BROWSER_STATE,mod.STATE)
        self.assertNotEqual(mod.BROWSER_PROFILE,mod.PROFILE)

if __name__=="__main__":
    unittest.main()
