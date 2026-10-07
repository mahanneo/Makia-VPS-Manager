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


    def test_openvpn_wstunnel_dry_run_requires_structured_loopback_transport(self):
        raw=b"client\nproto tcp4-client\nremote 127.0.0.1 11941\n"
        delivery={
            "engine":"openvpn_wstunnel",
            "native_base64":__import__("base64").b64encode(raw).decode(),
            "native_filename":"alice-wstunnel.ovpn",
            "transport_config":{
                "server":"vpn.example.com",
                "port":443,
                "path_prefix":"abcdefghijklmnopqrstuvwx",
                "local_host":"127.0.0.1",
                "local_port":11941,
                "remote_host":"127.0.0.1",
                "remote_port":11940,
                "tls_verify":True,
            },
        }
        result=mod.connect_delivery(delivery,dry_run=True)
        self.assertEqual(result["mode"],"openvpn-wstunnel")
        self.assertEqual(result["server"],"vpn.example.com")
        self.assertEqual(result["port"],443)
        self.assertTrue(Path(result["profile"]).is_file())

    def test_openvpn_wstunnel_rejects_non_loopback_backend(self):
        raw=b"client\n"
        delivery={
            "engine":"openvpn_wstunnel",
            "native_base64":__import__("base64").b64encode(raw).decode(),
            "transport_config":{
                "server":"vpn.example.com",
                "port":443,
                "path_prefix":"abcdefghijklmnopqrstuvwx",
                "local_port":11941,
                "remote_host":"10.0.0.8",
                "remote_port":11940,
            },
        }
        with self.assertRaisesRegex(RuntimeError,"loopback"):
            mod.connect_delivery(delivery,dry_run=True)


if __name__=="__main__":
    unittest.main()
