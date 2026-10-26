import unittest
from unittest.mock import patch

from app import main


class XrayPresetPreflightTests(unittest.TestCase):
    def test_every_preset_has_an_available_port_suggestion(self):
        with patch.object(main, "require_capability", return_value="admin"):
            result = main.xray_inbound_capabilities(object())
        presets = result.get("presets") or []
        self.assertGreaterEqual(len(presets), 5)
        for preset in presets:
            with self.subTest(preset=preset.get("id")):
                self.assertIsNotNone(preset.get("suggested_port"), preset.get("port_error"))
                self.assertGreater(int(preset["suggested_port"]), 0)


if __name__ == "__main__":
    unittest.main()
