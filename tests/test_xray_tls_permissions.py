import os
import pwd
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import protocol_ops


class XrayTlsPermissionsTests(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0, "requires root to verify service-user ownership")
    def test_service_user_can_traverse_tls_root_without_listing(self):
        user = pwd.getpwnam("nobody")
        with tempfile.TemporaryDirectory() as td:
            os.chmod(td, 0o711)
            root = Path(td) / "xray" / "tls"
            with patch.object(protocol_ops, "XRAY_TLS_DIR", root), patch.object(protocol_ops, "_xray_service_user", return_value="nobody"):
                prepared = protocol_ops._xray_prepare_tls_root()
                st = prepared.stat()
                self.assertEqual(st.st_uid, 0)
                self.assertEqual(st.st_gid, user.pw_gid)
                self.assertEqual(st.st_mode & 0o777, 0o710)
                domain = prepared / "vpn.example.test"
                domain.mkdir(mode=0o700)
                os.chown(domain, user.pw_uid, user.pw_gid)
                os.chmod(domain, 0o700)
                cert = domain / "fullchain.pem"
                cert.write_text("test certificate", encoding="utf-8")
                os.chown(cert, user.pw_uid, user.pw_gid)
                os.chmod(cert, 0o600)
                self.assertTrue(protocol_ops._xray_assert_path_readable(cert, "nobody"))

    def test_tls_sni_rejects_ip_address_with_actionable_message(self):
        issue = protocol_ops._xray_tls_certificate_issue("212.100.171.183")
        self.assertIn("DNS hostname", issue)
        self.assertIn("IP address", issue)

    def test_tls_domain_without_certificate_reports_renewal_step(self):
        issue = protocol_ops._xray_tls_certificate_issue("missing-certificate.example.test")
        self.assertIn("Issue a certificate first", issue)


if __name__ == "__main__":
    unittest.main()
