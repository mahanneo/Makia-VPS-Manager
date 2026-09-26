from app import protocol_ops

def test_protocol_endpoint_matrix_ip_marks_all_runtime_ready(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["203.0.113.10"])
    monkeypatch.setattr(protocol_ops,"xray_status",lambda:{"service_active":True,"inbounds":[{"port":443}]})
    monkeypatch.setattr(protocol_ops,"ssh_status",lambda:{"service_active":True})
    monkeypatch.setattr(protocol_ops,"WG_DIR",type("FakeWG",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:True})()})())
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",type("FakeO",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:True})()})())
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint:{"runtime_ok":True,"endpoint_ok":True,"port":51820})
    monkeypatch.setattr(protocol_ops,"openvpn_endpoint_diagnostics",lambda endpoint:{"service_active":True,"listener":True,"endpoint_is_ip":True,"resolved_ipv4":["203.0.113.10"],"dns_matches_server":True,"port":1194,"proto":"udp4"})
    result=protocol_ops.protocol_endpoint_matrix("203.0.113.10")
    assert result["all_ready"] is True
    assert all(row["ready"] for row in result["rows"])
