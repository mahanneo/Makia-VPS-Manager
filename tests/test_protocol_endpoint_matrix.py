from pathlib import Path

from app import protocol_ops


def test_endpoint_matrix_reports_all_configured_engines(tmp_path,monkeypatch):
    wg=tmp_path/"wireguard"; wg.mkdir()
    (wg/"wg0.conf").write_text("[Interface]\nAddress=10.66.66.1/24\nListenPort=443\n",encoding="utf-8")
    ovpn=tmp_path/"openvpn"; (ovpn/"server").mkdir(parents=True)
    (ovpn/"server"/"server.conf").write_text("port 1194\nproto udp4\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setattr(protocol_ops,"_binary",lambda:"/usr/local/bin/xray")
    xconfig=tmp_path/"xray.json"; xconfig.write_text("{}",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"_config_path",lambda:str(xconfig))
    monkeypatch.setattr(protocol_ops,"ssh_endpoint_diagnostics",lambda endpoint:{"ok":True,"warnings":[]})
    monkeypatch.setattr(protocol_ops,"wireguard_diagnostics",lambda iface,endpoint:{"ok":True,"warnings":[]})
    monkeypatch.setattr(protocol_ops,"openvpn_endpoint_diagnostics",lambda endpoint:{"ok":True,"warnings":[]})
    monkeypatch.setattr(protocol_ops,"xray_endpoint_diagnostics",lambda endpoint:{"ok":True,"warnings":[]})

    d=protocol_ops.endpoint_connectivity_matrix("vpn.example.test")
    assert d["checked"]==4
    assert d["passed"]==4
    assert d["ok"] is True


def test_endpoint_matrix_surfaces_one_protocol_failure(tmp_path,monkeypatch):
    wg=tmp_path/"wireguard"; wg.mkdir()
    (wg/"wg0.conf").write_text("[Interface]\nAddress=10.66.66.1/24\nListenPort=443\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"WG_DIR",wg)
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",tmp_path/"missing-openvpn")
    monkeypatch.setattr(protocol_ops,"_binary",lambda:None)
    monkeypatch.setattr(protocol_ops,"_installed",lambda binary:False)
    monkeypatch.setattr(protocol_ops,"ssh_endpoint_diagnostics",lambda endpoint:{"ok":True,"warnings":[]})
    monkeypatch.setattr(protocol_ops,"wireguard_diagnostics",lambda iface,endpoint:{"ok":False,"warnings":["NAT missing"]})

    d=protocol_ops.endpoint_connectivity_matrix("203.0.113.10")
    assert d["checked"]==2
    assert d["passed"]==1
    assert d["ok"] is False
    assert d["wireguard"]["warnings"]==["NAT missing"]
