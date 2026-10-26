import unittest
from pathlib import Path
from unittest.mock import patch

from app import protocol_ops
from app.protocol_ops import _build_xray_stream, _xray_builder_stream


class XrayTransportAlpnTests(unittest.TestCase):
    def build_tls(self, transport):
        with patch.object(
            protocol_ops, "_xray_materialize_tls",
            return_value=(Path("/tmp/test-fullchain.pem"), Path("/tmp/test-privkey.pem")),
        ):
            stream, _ = _build_xray_stream(
                "/usr/local/bin/xray", "vless", transport, "tls",
                "/makia-test", "vpn.example.test", "",
            )
        return stream

    def test_websocket_tls_uses_http11_only(self):
        self.assertEqual(self.build_tls("ws")["tlsSettings"]["alpn"], ["http/1.1"])

    def test_httpupgrade_tls_uses_http11_only(self):
        self.assertEqual(self.build_tls("httpupgrade")["tlsSettings"]["alpn"], ["http/1.1"])

    def test_grpc_tls_uses_h2_only(self):
        self.assertEqual(self.build_tls("grpc")["tlsSettings"]["alpn"], ["h2"])

    def test_custom_alpn_cannot_break_websocket(self):
        with patch.object(
            protocol_ops, "_xray_materialize_tls",
            return_value=(Path("/tmp/test-fullchain.pem"), Path("/tmp/test-privkey.pem")),
        ):
            stream, _ = _xray_builder_stream(
                "/usr/local/bin/xray", "vless", "ws", "tls",
                {"server_name": "vpn.example.test", "path": "/makia-test", "alpn": "h2,http/1.1"},
            )
        self.assertEqual(stream["tlsSettings"]["alpn"], ["http/1.1"])


class XrayOutboundDefaultTests(unittest.TestCase):
    def test_legacy_config_gets_direct_outbound(self):
        result = protocol_ops._ensure_xray_stats({"inbounds": []})
        self.assertEqual(result["outbounds"], [{"protocol": "freedom", "tag": "direct"}])

    def test_existing_outbounds_are_preserved(self):
        existing = [{"protocol": "blackhole", "tag": "block"}]
        result = protocol_ops._ensure_xray_stats({"inbounds": [], "outbounds": existing})
        self.assertEqual(result["outbounds"], existing)


if __name__ == "__main__":
    unittest.main()
