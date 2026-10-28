from app import protocol_ops


def test_tuic_and_mtproto_are_reported_as_managed_engines():
    caps = {item["id"]: item for item in protocol_ops.catalog()["capabilities"]}
    assert caps["tuic"]["engine"] == "sing-box"
    assert caps["tuic"]["mode"] == "managed"
    assert "installed" in caps["tuic"]
    assert caps["hysteria2"]["engine"] == "sing-box"
    assert caps["hysteria2"]["mode"] == "managed"
    assert "installed" in caps["hysteria2"]
    assert caps["amneziawg"]["engine"] == "awg"
    assert caps["amneziawg"]["mode"] == "managed"
    assert caps["mtproto"]["engine"] == "mtg"
    assert caps["mtproto"]["mode"] == "managed"
