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

    def test_outline_access_key_uses_bundled_singbox_full_device_tun(self):
        import base64
        credentials=base64.urlsafe_b64encode(b"aes-256-gcm:opaque-test-password").decode().rstrip("=")
        outbound=mod.outbound_from_share(
            "ss://"+credentials+"@outline.example:443/?outline=1#Makia"
        )
        self.assertEqual(outbound["type"],"shadowsocks")
        self.assertEqual(outbound["server"],"outline.example")
        cfg=mod.singbox_config(outbound)
        self.assertEqual(cfg["inbounds"][0]["type"],"tun")
        self.assertTrue(cfg["inbounds"][0]["auto_route"])
        self.assertEqual(cfg["route"]["final"],"proxy")

    def test_dry_run_never_disconnects_current_vpn(self):
        previous=mod.stop_current
        mod.stop_current=lambda: (_ for _ in ()).throw(AssertionError("dry-run stopped a live VPN"))
        try:
            data=mod.connect_delivery({
                "engine":"outline",
                "share_link":"ss://YWVzLTI1Ni1nY206cGFzcw@outline.example:443"
            },dry_run=True)
            self.assertEqual(data["outbound"],"shadowsocks")
        finally:
            mod.stop_current=previous

    def test_openvpn_does_not_claim_connected_without_handshake(self):
        from unittest.mock import patch
        class Exited:
            pid=123
            def poll(self): return 1
        with patch.object(mod.subprocess,"Popen",return_value=Exited()):
            with self.assertRaisesRegex(RuntimeError,"did not confirm tunnel initialization"):
                mod.start_openvpn_verified("openvpn.exe",mod.ROOT/"test.ovpn",timeout=3)

    def test_openvpn_accepts_real_completion_marker_not_process_pid_only(self):
        from unittest.mock import patch
        class Active:
            pid=123
            def poll(self): return None
        def spawn(*args,**kwargs):
            (mod.ROOT/"openvpn-runtime.log").write_text(
                "2026-10-20 10:00:00 Initialization Sequence Completed\\n",encoding="utf-8"
            )
            return Active()
        with patch.object(mod.subprocess,"Popen",side_effect=spawn):
            self.assertEqual(mod.start_openvpn_verified("openvpn.exe",mod.ROOT/"test.ovpn",timeout=3),123)

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
