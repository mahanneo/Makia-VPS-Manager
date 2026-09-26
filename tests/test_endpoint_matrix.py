from app import protocol_ops

def test_protocol_endpoint_matrix_ip_marks_all_runtime_ready(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_endpoint_runtime_state",lambda endpoint,label="endpoint":{
        "endpoint":endpoint,"endpoint_is_ip":True,"endpoint_ip_version":4,
        "resolved_ipv4":["203.0.113.10"],"resolved_ipv6":[],
        "local_ipv4":["203.0.113.10"],"dns_matches_server":True,
    })
    monkeypatch.setattr(protocol_ops,"ssh_endpoint_diagnostics",lambda endpoint:{
        "service_active":True,"listener":True,"endpoint_ok":True,"port":22,"warnings":[]
    })
    monkeypatch.setattr(protocol_ops,"xray_endpoint_diagnostics",lambda endpoint:{
        "installed":True,"service_active":True,"endpoint_ok":True,
        "inbounds":[{"port":443,"listener":True}],"warnings":[]
    })
    monkeypatch.setattr(protocol_ops,"WG_DIR",type("FakeWG",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:True})()})())
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",type("FakeO",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:True})()})())
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint:{
        "runtime_ok":True,"endpoint_ok":True,"service_active":True,"listener":True,"port":51820,"warnings":[]
    })
    monkeypatch.setattr(protocol_ops,"openvpn_endpoint_diagnostics",lambda endpoint:{
        "service_active":True,"listener":True,"endpoint_is_ip":True,
        "resolved_ipv4":["203.0.113.10"],"dns_matches_server":True,"port":1194,"proto":"udp4","warnings":[]
    })
    result=protocol_ops.protocol_endpoint_matrix("203.0.113.10")
    assert result["all_ready"] is True
    assert all(row["ready"] for row in result["rows"])
    assert all("listener" in row for row in result["rows"])

def test_protocol_endpoint_matrix_fails_when_ssh_listener_is_missing(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_endpoint_runtime_state",lambda endpoint,label="endpoint":{
        "endpoint":endpoint,"endpoint_is_ip":True,"endpoint_ip_version":4,
        "resolved_ipv4":["203.0.113.10"],"resolved_ipv6":[],
        "local_ipv4":["203.0.113.10"],"dns_matches_server":True,
    })
    monkeypatch.setattr(protocol_ops,"ssh_endpoint_diagnostics",lambda endpoint:{
        "service_active":True,"listener":False,"endpoint_ok":True,"port":22,"warnings":["listener missing"]
    })
    monkeypatch.setattr(protocol_ops,"xray_endpoint_diagnostics",lambda endpoint:{
        "installed":True,"service_active":True,"endpoint_ok":True,
        "inbounds":[{"port":443,"listener":True}],"warnings":[]
    })
    monkeypatch.setattr(protocol_ops,"WG_DIR",type("FakeWG",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:False})()})())
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",type("FakeO",(object,),{"__truediv__":lambda self,x:type("P",(object,),{"exists":lambda self:False})()})())
    result=protocol_ops.protocol_endpoint_matrix("203.0.113.10")
    ssh=next(row for row in result["rows"] if row["id"]=="ssh")
    assert ssh["runtime"] is False
    assert ssh["ready"] is False
    assert result["all_ready"] is False
