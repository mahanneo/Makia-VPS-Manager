import unittest
from unittest.mock import patch
from app import protocol_ops, access_ops
from app.protocol_ops import _build_xray_stream

class XrayTransportSchemaTests(unittest.TestCase):
    def check_transport(self, transport, expected):
        stream, _ = _build_xray_stream(
            "/usr/local/bin/xray", "vless", transport, "none", "/makia-test", "", ""
        )
        self.assertEqual(stream.get("network"), expected)
        self.assertNotIn("method", stream)

    def test_xhttp_uses_network_field(self):
        self.check_transport("xhttp", "xhttp")

    def test_grpc_uses_network_field(self):
        self.check_transport("grpc", "grpc")

    def test_tcp_alias_uses_raw_network(self):
        self.check_transport("tcp", "raw")

class XrayPortAllocationTests(unittest.TestCase):
    def test_udp_can_share_port_with_tcp_listener(self):
        existing={"inbounds":[{"port":443,"protocol":"vless","transport":"raw"}]}
        with patch.object(protocol_ops,"xray_status",return_value=existing), patch.object(protocol_ops,"_port_transport_in_use",return_value=False):
            result=protocol_ops.allocate_xray_inbound_port(443,"hysteria2","hysteria")
        self.assertEqual(result["port"],443)
        self.assertEqual(result["transports"],["udp"])

    def test_tcp_avoids_existing_tcp_port(self):
        existing={"inbounds":[{"port":443,"protocol":"vless","transport":"raw"}]}
        with patch.object(protocol_ops,"xray_status",return_value=existing), patch.object(protocol_ops,"_port_transport_in_use",return_value=False):
            result=protocol_ops.allocate_xray_inbound_port(443,"vless","raw")
        self.assertNotEqual(result["port"],443)
        self.assertEqual(result["transports"],["tcp"])

    def test_dynamic_fallback_is_available_after_managed_ports(self):
        ports=[443,2053,2087,8443,9443,10443,11443,12443,13001,13002,13003,13004,13005]
        existing={"inbounds":[{"port":port,"protocol":"vless","transport":"raw"} for port in ports]}
        with patch.object(protocol_ops,"xray_status",return_value=existing), patch.object(protocol_ops,"_port_transport_in_use",return_value=False):
            result=protocol_ops.allocate_xray_inbound_port(2053,"vless","raw")
        self.assertEqual(result["port"],13006)


if __name__ == "__main__":
    unittest.main()
