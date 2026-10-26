import unittest
from app.protocol_ops import _l2tp_ppp_option_issues


class L2TPPppOptionTests(unittest.TestCase):
    def test_rejected_lock_option_is_reported(self):
        issues = _l2tp_ppp_option_issues("# BEGIN MAKIA L2TP PPP OPTIONS\nlock\nauth\n")
        self.assertEqual(len(issues), 1)
        self.assertIn("lock", issues[0])

    def test_supported_profile_has_no_lock_warning(self):
        issues = _l2tp_ppp_option_issues("require-mschap-v2\nrefuse-pap\nauth\nmtu 1280\n")
        self.assertEqual(issues, [])

    def test_missing_ppp_options_file_is_reported(self):
        self.assertTrue(_l2tp_ppp_option_issues(""))


if __name__ == "__main__":
    unittest.main()
