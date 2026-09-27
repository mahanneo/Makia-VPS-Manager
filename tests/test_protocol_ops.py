import pytest
from app import protocol_ops
from app.protocol_ops import _validate_port, _validate_endpoint_host, _uri_host, _endpoint_is_private, create_xray_inbound, validate_endpoint_selection, ProtocolError

def test_valid_port():
    assert _validate_port(443) == 443

@pytest.mark.parametrize("value", [0, 65536, -1])
def test_invalid_port(value):
    with pytest.raises(ProtocolError):
        _validate_port(value)


@pytest.mark.parametrize("value,expected", [
    ("178.83.45.215","178.83.45.215"),
    (" example.com ","example.com"),
    ("VPN.Example.COM","vpn.example.com"),
    ("[2001:db8::1]","2001:db8::1"),
])
def test_valid_endpoint_host(value, expected):
    assert _validate_endpoint_host(value) == expected

@pytest.mark.parametrize("value", [
    "",
    "https://example.com",
    "example.com:443",
    "example.com/path",
    "bad host",
    "-bad.example.com",
    "bad_.example.com",
])
def test_invalid_endpoint_host(value):
    with pytest.raises(ProtocolError):
        _validate_endpoint_host(value)

def test_ipv6_uri_host_is_bracketed():
    assert _uri_host("2001:db8::1") == "[2001:db8::1]"

def test_ipv4_uri_host_is_not_bracketed():
    assert _uri_host("178.83.45.215") == "178.83.45.215"


def test_public_ipv4_is_not_private():
    assert _endpoint_is_private("178.83.45.215") is False

def test_private_ipv4_is_private():
    assert _endpoint_is_private("10.10.0.2") is True

def test_public_vless_none_is_rejected_before_core_mutation():
    with pytest.raises(ProtocolError, match="choose REALITY or TLS"):
        create_xray_inbound("vless",2087,"mahan","178.83.45.215","xhttp","none","/makia","","")

def test_explicit_endpoint_mode_rejects_wrong_type_and_private_ip():
    for endpoint,mode in [("vpn.example.com","ip"),("8.8.8.8","domain"),("10.0.0.1","ip"),("2001:db8::1","ip")]:
        with pytest.raises(ProtocolError):
            validate_endpoint_selection(endpoint,mode)
    assert validate_endpoint_selection("8.8.8.8","ip")=="8.8.8.8"

def test_direct_domain_selection_checks_a_record_and_vps_match(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["8.8.8.8"])
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,("8.8.8.8",0))])
    assert validate_endpoint_selection("VPN.Example.com","domain",direct=True)=="vpn.example.com"
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,("1.1.1.1",0))])
    with pytest.raises(ProtocolError,match="does not match"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True)
    assert validate_endpoint_selection("vpn.example.com","domain",direct=False)=="vpn.example.com"
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[(None,None,None,None,(ip,0)) for ip in ("8.8.8.8","1.1.1.1")])
    with pytest.raises(ProtocolError,match="does not match"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True)

def test_domain_selection_requires_a_record(monkeypatch):
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",lambda *args:[])
    with pytest.raises(ProtocolError,match="A/IPv4"):
        validate_endpoint_selection("vpn.example.com","domain")

def test_ssh_domain_rejects_aaaa_pointing_away_from_vps(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_local_ipv4_candidates",lambda:["8.8.8.8"])
    monkeypatch.setattr(protocol_ops,"_local_ipv6_candidates",lambda:[])
    def resolve(host,port,family):
        ip="8.8.8.8" if family==protocol_ops.socket.AF_INET else "2001:4860:4860::8888"
        return [(family,None,None,None,(ip,0))]
    monkeypatch.setattr(protocol_ops.socket,"getaddrinfo",resolve)
    with pytest.raises(ProtocolError,match="AAAA"):
        validate_endpoint_selection("vpn.example.com","domain",direct=True,check_aaaa=True)


def test_port_collision_check_is_transport_aware(monkeypatch):
    class FakeSocket:
        def __init__(self, kind):
            self.kind=kind
        def bind(self, address):
            if self.kind==protocol_ops.socket.SOCK_DGRAM:
                raise OSError("udp occupied")
        def close(self):
            pass
    monkeypatch.setattr(protocol_ops.socket,"socket",lambda family,kind:FakeSocket(kind))
    assert protocol_ops._port_transport_in_use(443,"udp") is True
    assert protocol_ops._port_transport_in_use(443,"tcp") is False


def test_invalid_port_transport_is_rejected():
    with pytest.raises(ProtocolError, match="transport"):
        protocol_ops._port_transport_in_use(443,"sctp")


def test_select_available_port_uses_fallback(monkeypatch):
    occupied={(443,"udp"),(51820,"udp")}
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:(int(port),str(proto)) in occupied)
    assert protocol_ops._select_available_port(443,"udp",(51820,51821,8443)) == 51821


def test_select_available_port_raises_when_all_candidates_busy(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:True)
    with pytest.raises(ProtocolError, match="no free UDP port"):
        protocol_ops._select_available_port(443,"udp",(51820,51821))


def test_full_stack_provisions_missing_engines(monkeypatch):
    state={
        "xray":False,
        "wg_installed":False,"wg_config":False,"wg_active":False,"wg_port":0,
        "ovpn_installed":False,"ovpn_config":False,"ovpn_active":False,"ovpn_port":0,
        "stunnel":False,
    }
    def xray_status():
        return {"installed":state["xray"],"service_active":state["xray"],"config_path":"/usr/local/etc/xray/config.json" if state["xray"] else None}
    def wg_status():
        return {"installed":state["wg_installed"],"service_active":state["wg_active"],"config":"/etc/wireguard/wg0.conf" if state["wg_config"] else None,"port":state["wg_port"]}
    def ovpn_status():
        return {"installed":state["ovpn_installed"],"service_active":state["ovpn_active"],"config":"/etc/openvpn/server/server.conf" if state["ovpn_config"] else None,"port":state["ovpn_port"],"proto":"udp"}
    def st_status():
        return {"installed":state["stunnel"],"service_active":False}
    def install_component(name):
        if name=="xray":
            state["xray"]=True
            return xray_status()
        if name=="wireguard":
            state["wg_installed"]=True
            return wg_status()
        if name=="openvpn":
            state["ovpn_installed"]=True
            return ovpn_status()
        if name=="stunnel":
            state["stunnel"]=True
            return st_status()
        raise AssertionError(name)
    def bootstrap_wg(port,cidr,iface,mtu):
        state.update(wg_config=True,wg_active=True,wg_port=int(port))
        return {"port":int(port)}
    def bootstrap_ovpn(port,proto):
        state.update(ovpn_config=True,ovpn_active=True,ovpn_port=int(port))
        return {"port":int(port),"proto":proto}

    monkeypatch.setattr(protocol_ops,"xray_status",xray_status)
    monkeypatch.setattr(protocol_ops,"wireguard_status",wg_status)
    monkeypatch.setattr(protocol_ops,"openvpn_status",ovpn_status)
    monkeypatch.setattr(protocol_ops,"stunnel_status",st_status)
    monkeypatch.setattr(protocol_ops,"install_component",install_component)
    monkeypatch.setattr(protocol_ops,"bootstrap_wireguard",bootstrap_wg)
    monkeypatch.setattr(protocol_ops,"bootstrap_openvpn",bootstrap_ovpn)
    monkeypatch.setattr(protocol_ops,"_select_available_port",lambda preferred,proto,fallbacks=():preferred)
    monkeypatch.setattr(protocol_ops,"wireguard_endpoint_diagnostics",lambda endpoint="",iface="wg0":{"runtime_ok":True,"port":state["wg_port"],"warnings":[]})
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{"service_active":state["ovpn_active"],"listener":state["ovpn_active"],"port":state["ovpn_port"]})

    result=protocol_ops.ensure_full_protocol_stack()
    assert result["xray"]["service_active"] is True
    assert result["wireguard"]["service_active"] is True
    assert result["openvpn"]["service_active"] is True
    assert result["stunnel"]["installed"] is True
    assert result["ports"]=={"wireguard":443,"openvpn":1194}


@pytest.mark.parametrize("protocol,transport,security,expected",[
    ("vless","tcp","reality",("tcp","reality")),
    ("vless","grpc","reality",("grpc","reality")),
    ("vless","xhttp","reality",("xhttp","reality")),
    ("vmess","ws","none",("ws","none")),
    ("vmess","grpc","tls",("grpc","tls")),
    ("trojan","tcp","tls",("tcp","tls")),
    ("shadowsocks","tcp","none",("tcp","none")),
    ("hysteria2","tcp","none",("hysteria","tls")),
    ("http","tcp","none",("tcp","none")),
    ("socks","tcp","none",("tcp","none")),
])
def test_xray_guided_compatibility_accepts_tested_profiles(protocol,transport,security,expected):
    assert protocol_ops._validate_xray_guided_combo(protocol,transport,security)==expected


@pytest.mark.parametrize("protocol,transport,security",[
    ("vmess","tcp","reality"),
    ("trojan","tcp","none"),
    ("trojan","kcp","tls"),
    ("shadowsocks","ws","none"),
    ("http","grpc","none"),
    ("socks","tcp","tls"),
    ("vless","ws","reality"),
])
def test_xray_guided_compatibility_rejects_invalid_profiles(protocol,transport,security):
    with pytest.raises(ProtocolError):
        protocol_ops._validate_xray_guided_combo(protocol,transport,security)


def test_xray_service_validation_skips_runuser_under_no_new_privileges(monkeypatch,tmp_path):
    cfg=tmp_path/"config.json"
    cfg.write_text('{"inbounds":[],"outbounds":[]}',encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"_xray_service_user",lambda:"nobody")
    monkeypatch.setattr(protocol_ops,"_process_no_new_privileges",lambda:True)
    monkeypatch.setattr(protocol_ops,"_xray_static_service_validation",lambda path,user:"static-permission-check")
    monkeypatch.setattr(protocol_ops.os,"geteuid",lambda:0)
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:pytest.fail("runuser must not run under NoNewPrivileges"))
    assert protocol_ops._xray_test_config_as_service("/usr/local/bin/xray",cfg)=="static-permission-check"


def test_xray_service_validation_falls_back_when_runuser_setuid_is_blocked(monkeypatch,tmp_path):
    cfg=tmp_path/"config.json"
    cfg.write_text('{"inbounds":[],"outbounds":[]}',encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"_xray_service_user",lambda:"nobody")
    monkeypatch.setattr(protocol_ops,"_process_no_new_privileges",lambda:False)
    monkeypatch.setattr(protocol_ops.shutil,"which",lambda name:"/usr/sbin/runuser" if name=="runuser" else None)
    monkeypatch.setattr(protocol_ops.os,"geteuid",lambda:0)
    monkeypatch.setattr(protocol_ops,"_xray_static_service_validation",lambda path,user:"static-permission-check")
    def blocked(*args,**kwargs):
        raise ProtocolError("runuser: cannot set user id: Operation not permitted")
    monkeypatch.setattr(protocol_ops,"_run",blocked)
    assert protocol_ops._xray_test_config_as_service("/usr/local/bin/xray",cfg)=="static-permission-check"


def test_openvpn_reconfigure_switches_transport_and_policy(monkeypatch,tmp_path):
    ovpn=tmp_path/"openvpn"
    server=ovpn/"server"
    server.mkdir(parents=True)
    conf=server/"server.conf"
    conf.write_text(
        'port 1194\nproto udp4\nlocal 0.0.0.0\ndev tun\n'
        'server 10.8.0.0 255.255.255.0\n'
        'push "redirect-gateway def1 bypass-dhcp"\n'
        'push "dhcp-option DNS 1.1.1.1"\n'
        'keepalive 10 120\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"OVPN_DIR",ovpn)
    monkeypatch.setenv("MAKIA_BACKUP_DIR",str(tmp_path/"backups"))
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:False)
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    monkeypatch.setattr(protocol_ops,"_ufw_allow_if_active",lambda port,proto,label:{"active":True,"changed":True})
    def runtime():
        text=conf.read_text(encoding="utf-8")
        import re
        port=int(re.search(r"(?m)^port\s+(\d+)",text).group(1))
        proto=re.search(r"(?m)^proto\s+(\S+)",text).group(1)
        return {"service_active":True,"listener":True,"port":port,"proto":proto}
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",runtime)
    result=protocol_ops.reconfigure_openvpn_server(
        2443,"tcp",["9.9.9.9","1.1.1.1"],15,90,True,True
    )
    text=conf.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert "port 2443" in text
    assert "proto tcp4-server" in text
    assert 'push "dhcp-option DNS 9.9.9.9"' in text
    assert 'push "dhcp-option DNS 1.1.1.1"' in text
    assert "keepalive 15 90" in text
    assert "client-to-client" in text


def test_xray_mkcp_uses_xray_26327_schema_without_removed_seed_header():
    stream,meta=protocol_ops._build_xray_stream(
        "/unused/xray","vless","kcp","none","legacy-seed","",""
    )
    assert stream["method"]=="mkcp"
    assert stream["kcpSettings"]=={}
    assert "seed" not in stream["kcpSettings"]
    assert "header" not in stream["kcpSettings"]
    assert meta=={}


def test_replace_managed_block_is_idempotent():
    first=protocol_ops._replace_managed_block("config setup\n","# BEGIN X","# END X","value=1")
    second=protocol_ops._replace_managed_block(first,"# BEGIN X","# END X","value=2")
    assert second.count("# BEGIN X")==1
    assert second.count("# END X")==1
    assert "value=1" not in second
    assert "value=2" in second


def test_protocol_modes_reports_six_real_modes(monkeypatch):
    monkeypatch.setattr(protocol_ops,"wireguard_status",lambda:{
        "service_active":True,"config":"/etc/wireguard/wg0.conf","port":443
    })
    monkeypatch.setattr(protocol_ops,"_openvpn_server_runtime",lambda:{
        "service_active":True,"listener":True,"port":1194,"proto":"udp4"
    })
    monkeypatch.setattr(protocol_ops,"ikev2_status",lambda:{
        "configured":True,"service_active":True
    })
    monkeypatch.setattr(protocol_ops,"stealth_status",lambda:{
        "service_active":False,"listener":False,"port":8443
    })
    monkeypatch.setattr(protocol_ops,"wstunnel_status",lambda:{
        "service_active":True,"listener":True,"port":8444
    })
    data=protocol_ops.protocol_modes()
    ids=[row["id"] for row in data["modes"]]
    assert ids==["ikev2","wireguard","udp","tcp","stealth","wstunnel"]
    by_id={row["id"]:row for row in data["modes"]}
    assert by_id["ikev2"]["ready"] is True
    assert by_id["wireguard"]["ready"] is True
    assert by_id["udp"]["ready"] is True
    assert by_id["tcp"]["ready"] is False
    assert by_id["stealth"]["ready"] is False
    assert by_id["wstunnel"]["ready"] is True
    assert data["constraints"]["openvpn_single_active_transport"] is True


def test_create_ikev2_user_writes_managed_eap_secret(monkeypatch,tmp_path):
    secrets_file=tmp_path/"ipsec.secrets"
    secrets_file.write_text(": RSA makia-ikev2.key\n",encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"IKEV2_SECRETS",secrets_file)
    monkeypatch.setattr(protocol_ops,"ikev2_status",lambda:{
        "configured":True,"domain":"vpn.example.com"
    })
    calls=[]
    monkeypatch.setattr(protocol_ops,"_run",lambda args,**kwargs:calls.append(args) or "")
    result=protocol_ops.create_ikev2_user("alice","StrongPass123!")
    text=secrets_file.read_text(encoding="utf-8")
    assert 'alice : EAP "StrongPass123!"  # makia-eap:alice' in text
    assert result["server"]=="vpn.example.com"
    assert result["password"]=="StrongPass123!"
    assert ["ipsec","rereadsecrets"] in calls


def test_create_ikev2_user_replaces_existing_named_secret(monkeypatch,tmp_path):
    secrets_file=tmp_path/"ipsec.secrets"
    secrets_file.write_text('alice : EAP "old"  # makia-eap:alice\n',encoding="utf-8")
    monkeypatch.setattr(protocol_ops,"IKEV2_SECRETS",secrets_file)
    monkeypatch.setattr(protocol_ops,"ikev2_status",lambda:{
        "configured":True,"domain":"vpn.example.com"
    })
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    protocol_ops.create_ikev2_user("alice","NewStrongPass456!")
    text=secrets_file.read_text(encoding="utf-8")
    assert text.count("# makia-eap:alice")==1
    assert "old" not in text
    assert "NewStrongPass456!" in text


@pytest.mark.parametrize("name",["a","bad user","bad/user","نام"])
def test_create_ikev2_user_rejects_invalid_username(monkeypatch,name):
    monkeypatch.setattr(protocol_ops,"ikev2_status",lambda:{"configured":True})
    with pytest.raises(ProtocolError):
        protocol_ops.create_ikev2_user(name,"StrongPass123!")


def test_wstunnel_status_reads_runtime_env(monkeypatch,tmp_path):
    env=tmp_path/"wstunnel.env"
    env.write_text(
        "WSTUNNEL_LISTEN_PORT=8444\n"
        "WSTUNNEL_TARGET_PORT=443\n"
        "WSTUNNEL_PATH_PREFIX=abc123securepath\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"WSTUNNEL_ENV",env)
    monkeypatch.setattr(protocol_ops.shutil,"which",lambda name:"/usr/local/bin/wstunnel" if name=="wstunnel" else None)
    monkeypatch.setattr(protocol_ops,"_active",lambda name:name=="makia-wstunnel")
    monkeypatch.setattr(protocol_ops,"_listener_present",lambda port,proto="tcp":int(port)==8444 and proto=="tcp")
    status=protocol_ops.wstunnel_status()
    assert status["installed"] is True
    assert status["configured"] is True
    assert status["service_active"] is True
    assert status["port"]==8444
    assert status["target_port"]==443
    assert status["listener"] is True


def test_component_install_is_blocked_inside_hardened_web_service(monkeypatch):
    monkeypatch.setattr(protocol_ops,"_process_no_new_privileges",lambda:True)
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:pytest.fail("package manager must not run"))
    with pytest.raises(ProtocolError,match="sudo makia-upgrade"):
        protocol_ops.install_component("wireguard")


def test_ikev2_user_replacement_does_not_remove_prefix_neighbor(monkeypatch,tmp_path):
    secrets_file=tmp_path/"ipsec.secrets"
    secrets_file.write_text(
        'alice : EAP "old"  # makia-eap:alice\n'
        'alice2 : EAP "keep"  # makia-eap:alice2\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"IKEV2_SECRETS",secrets_file)
    monkeypatch.setattr(protocol_ops,"ikev2_status",lambda:{"configured":True,"domain":"vpn.example.com"})
    monkeypatch.setattr(protocol_ops,"_run",lambda *args,**kwargs:"")
    protocol_ops.create_ikev2_user("alice","NewStrongPass456!")
    text=secrets_file.read_text(encoding="utf-8")
    assert '# makia-eap:alice2' in text
    assert 'alice2 : EAP "keep"' in text
    assert text.count("# makia-eap:alice")==2  # alice marker + alice2 prefix text
    assert len(protocol_ops.list_ikev2_users())==2


def test_remove_ikev2_user_keeps_other_managed_users(monkeypatch,tmp_path):
    secrets_file=tmp_path/"ipsec.secrets"
    secrets_file.write_text(
        ': RSA makia-ikev2.key\n'
        'alice : EAP "one"  # makia-eap:alice\n'
        'bob : EAP "two"  # makia-eap:bob\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol_ops,"IKEV2_SECRETS",secrets_file)
    calls=[]
    monkeypatch.setattr(protocol_ops,"_run",lambda args,**kwargs:calls.append(args) or "")
    result=protocol_ops.remove_ikev2_user("alice")
    text=secrets_file.read_text(encoding="utf-8")
    assert result["name"]=="alice"
    assert "makia-eap:alice" not in text
    assert "makia-eap:bob" in text
    assert protocol_ops.list_ikev2_users()==[{"name":"bob"}]
    assert ["ipsec","rereadsecrets"] in calls
