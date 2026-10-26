import plistlib
import unittest

from app.access_ops import AccessPackageError, native_vpn_payload


class NativeVpnProfileTests(unittest.TestCase):
    def test_ikev2_apple_profile_contains_required_server_and_eap_fields(self):
        payload = native_vpn_payload(
            "ikev2", "test-user", "vpn.example.test", "test-user", "safe-test-password"
        )
        self.assertTrue(payload["native_filename"].endswith(".mobileconfig"))
        profile = plistlib.loads(payload["files"][payload["native_filename"]])
        vpn = profile["PayloadContent"][0]
        self.assertEqual(vpn["VPNType"], "IKEv2")
        self.assertEqual(vpn["IKEv2"]["RemoteAddress"], "vpn.example.test")
        self.assertEqual(vpn["IKEv2"]["RemoteIdentifier"], "vpn.example.test")
        self.assertEqual(vpn["IKEv2"]["LocalIdentifier"], "test-user")
        self.assertEqual(vpn["IKEv2"]["AuthenticationMethod"], "None")
        self.assertEqual(vpn["IKEv2"]["ExtendedAuthEnabled"], 1)
        self.assertEqual(vpn["IKEv2"]["AuthName"], "test-user")
        self.assertEqual(vpn["IKEv2"]["AuthPassword"], "safe-test-password")
        self.assertIn("Remote ID: vpn.example.test", payload["primary_text"])
        self.assertIn("Username: test-user", payload["primary_text"])

    def test_l2tp_apple_profile_contains_ipsec_secret_and_ppp_credentials(self):
        payload = native_vpn_payload(
            "l2tp", "test-user", "vpn.example.test", "test-user", "safe-test-password", "safe-test-psk"
        )
        self.assertTrue(payload["native_filename"].endswith(".mobileconfig"))
        profile = plistlib.loads(payload["files"][payload["native_filename"]])
        vpn = profile["PayloadContent"][0]
        self.assertEqual(vpn["VPNType"], "L2TP")
        self.assertEqual(vpn["IPSec"]["AuthenticationMethod"], "SharedSecret")
        self.assertEqual(vpn["IPSec"]["SharedSecret"], "safe-test-psk")
        self.assertEqual(vpn["PPP"]["CommRemoteAddress"], "vpn.example.test")
        self.assertEqual(vpn["PPP"]["AuthName"], "test-user")
        self.assertEqual(vpn["PPP"]["AuthPassword"], "safe-test-password")
        self.assertIn("IPsec pre-shared key: safe-test-psk", payload["primary_text"])
        self.assertIn("Username: test-user", payload["primary_text"])

    def test_native_profile_rejects_missing_required_credentials(self):
        with self.assertRaises(AccessPackageError):
            native_vpn_payload("ikev2", "test-user", "", "user", "password")
        with self.assertRaises(AccessPackageError):
            native_vpn_payload("l2tp", "test-user", "vpn.example.test", "user", "password", "")


if __name__ == "__main__":
    unittest.main()
