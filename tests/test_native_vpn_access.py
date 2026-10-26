import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import access_ops, protocol_ops


class NativeVpnPayloadTests(unittest.TestCase):
    def test_ikev2_profile_has_native_fields(self):
        payload = access_ops.native_vpn_payload(
            "ikev2", "demo", "vpn.example.test", "demo", "x" * 16
        )
        manual = payload["files"][payload["summary"]["manual_details"]].decode("utf-8")
        self.assertIn("Remote ID: vpn.example.test", manual)
        self.assertIn("Username: demo", manual)
        self.assertIn("Password: " + "x" * 16, manual)
        self.assertTrue(payload["native_filename"].endswith(".mobileconfig"))
        profile = plistlib.loads(payload["files"][payload["native_filename"]])
        vpn = profile["PayloadContent"][0]
        self.assertEqual(vpn["PayloadType"], "com.apple.vpn.managed")
        self.assertEqual(vpn["VPNType"], "IKEv2")
        self.assertEqual(vpn["IKEv2"]["AuthenticationMethod"], "None")
        self.assertEqual(vpn["IKEv2"]["ExtendedAuthEnabled"], 1)
        self.assertEqual(vpn["IKEv2"]["RemoteAddress"], "vpn.example.test")
        self.assertEqual(vpn["IKEv2"]["RemoteIdentifier"], "vpn.example.test")
        self.assertEqual(vpn["IKEv2"]["AuthName"], "demo")
        self.assertEqual(vpn["IKEv2"]["AuthPassword"], "x" * 16)
        self.assertEqual(vpn["IKEv2"]["IncludeAllNetworks"], 1)
        self.assertIn("connection-guide-fa.txt", payload["files"])

    def test_l2tp_profile_has_psk_and_login(self):
        payload = access_ops.native_vpn_payload(
            "l2tp", "demo", "vpn.example.test", "demo", "x" * 16, "y" * 20
        )
        manual = payload["files"][payload["summary"]["manual_details"]].decode("utf-8")
        self.assertIn("IPsec pre-shared key: " + "y" * 20, manual)
        self.assertIn("Username: demo", manual)
        self.assertIn("Password: " + "x" * 16, manual)
        profile = plistlib.loads(payload["files"][payload["native_filename"]])
        vpn = profile["PayloadContent"][0]
        self.assertEqual(vpn["VPNType"], "L2TP")
        self.assertEqual(vpn["IPSec"]["AuthenticationMethod"], "SharedSecret")
        self.assertEqual(vpn["IPSec"]["SharedSecret"], "y" * 20)
        self.assertEqual(vpn["PPP"]["CommRemoteAddress"], "vpn.example.test")
        self.assertEqual(vpn["PPP"]["AuthName"], "demo")
        self.assertEqual(vpn["PPP"]["AuthPassword"], "x" * 16)
        self.assertEqual(vpn["IPv4"]["OverridePrimary"], 1)


class L2TPManagedUserTests(unittest.TestCase):
    def test_create_list_export_and_revoke_in_temp_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chap = root / "chap-secrets"
            backups = root / "backups"
            backups.mkdir()
            with patch.object(protocol_ops, "L2TP_CHAP", chap), \
                 patch.object(protocol_ops, "_backup_dir", return_value=backups), \
                 patch.object(protocol_ops, "l2tp_status", return_value={"ready": True, "domain": "vpn.example.test"}), \
                 patch.object(protocol_ops, "_l2tp_shared_psk", return_value="y" * 20):
                result = protocol_ops.create_l2tp_user("demo-user")
                self.assertTrue(result["ok"])
                saved = protocol_ops.get_l2tp_user_credentials("demo-user")
                self.assertEqual(saved["password"], result["password"])
                self.assertEqual(protocol_ops.list_l2tp_users(), [{"name": "demo-user"}])
                payload = access_ops.native_vpn_payload(
                    "l2tp", "demo-user", result["server"], "demo-user",
                    result["password"], result["psk"]
                )
                manual = payload["files"][payload["summary"]["manual_details"]].decode("utf-8")
                self.assertIn("IPsec pre-shared key", manual)
                self.assertTrue(payload["native_filename"].endswith(".mobileconfig"))
                self.assertIn(payload["native_filename"], payload["files"])
                protocol_ops.remove_l2tp_user("demo-user")
                self.assertIsNone(protocol_ops.get_l2tp_user_credentials("demo-user"))
                self.assertEqual(protocol_ops.list_l2tp_users(), [])


class IKEv2CredentialReaderTests(unittest.TestCase):
    def test_managed_eap_credential_can_be_recovered_for_export(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ipsec-secrets"
            path.write_text('demo-user : EAP "demo-password" # makia-eap:demo-user\n', encoding="utf-8")
            with patch.object(protocol_ops, "IKEV2_SECRETS", path):
                self.assertEqual(
                    protocol_ops.get_ikev2_user_credentials("demo-user"),
                    {"name": "demo-user", "password": "demo-password"},
                )


if __name__ == "__main__":
    unittest.main()
