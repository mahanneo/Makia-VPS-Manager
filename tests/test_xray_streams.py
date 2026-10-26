import pytest
from app import protocol_ops
from app.protocol_ops import _build_xray_stream, ProtocolError

def test_websocket_stream_uses_current_method_schema():
    stream, meta = _build_xray_stream("/bin/true","vless","ws","none","/socket","","")
    assert stream["network"] == "websocket"
    assert stream["wsSettings"]["path"] == "/socket"
    assert stream["security"] == "none"
    assert meta == {}

def test_grpc_stream_service_name():
    stream, _ = _build_xray_stream("/bin/true","vless","grpc","none","makia-grpc","","")
    assert stream["network"] == "grpc"
    assert stream["grpcSettings"]["serviceName"] == "makia-grpc"

def test_reality_rejects_incompatible_protocol():
    with pytest.raises(ProtocolError):
        _build_xray_stream("/bin/true","trojan","tcp","reality","/","example.com","example.com:443")

def test_reality_rejects_incompatible_transport():
    with pytest.raises(ProtocolError):
        _build_xray_stream("/bin/true","vless","ws","reality","/","example.com","example.com:443")


def test_reality_uses_current_target_key(monkeypatch):
    monkeypatch.setattr(protocol_ops, "_x25519_pair", lambda binary: ("private-key","public-key"))
    stream, meta = _build_xray_stream(
        "/bin/true","vless","xhttp","reality","/makia",
        "www.microsoft.com","www.microsoft.com:443"
    )
    assert stream["network"] == "xhttp"
    assert stream["security"] == "reality"
    assert stream["realitySettings"]["target"] == "www.microsoft.com:443"
    assert "dest" not in stream["realitySettings"]
    assert meta["public_key"] == "public-key"
