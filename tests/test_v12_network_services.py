from pathlib import Path

import pytest

from app import network_services, protocol_ops


ROOT=Path(__file__).resolve().parents[1]


def test_xray_allocator_moves_off_busy_requested_port(monkeypatch):
    monkeypatch.setattr(protocol_ops,"xray_status",lambda:{"inbounds":[{"port":2087}]})
    busy={443,8443,2087}
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",lambda port,proto:int(port) in busy)
    result=protocol_ops.allocate_xray_inbound_port(443,"vless","tcp")
    assert result["requested_port"]==443
    assert result["port"]==2053
    assert result["adjusted"] is True
    assert result["transports"]==["tcp"]


def test_xray_allocator_checks_udp_for_hysteria(monkeypatch):
    monkeypatch.setattr(protocol_ops,"xray_status",lambda:{"inbounds":[]})
    calls=[]
    def used(port,proto):
        calls.append((int(port),proto))
        return int(port)==443 and proto=="udp"
    monkeypatch.setattr(protocol_ops,"_port_transport_in_use",used)
    result=protocol_ops.allocate_xray_inbound_port(443,"hysteria2","hysteria")
    assert result["port"]==2053
    assert result["transports"]==["udp"]
    assert all(proto=="udp" for _,proto in calls)


def test_mtproxy_status_generates_real_telegram_links(tmp_path,monkeypatch):
    env=tmp_path/"mtproxy.env"
    env.write_text(
        "MTPROXY_PUBLIC_HOST=proxy.example.com\n"
        "MTPROXY_PORT=8443\n"
        "MTPROXY_FRONT_DOMAIN=proxy.example.com\n"
        "MTPROXY_SECRET=ee0123456789abcdef0123456789abcdef6578616d706c652e636f6d\n",
        encoding="utf-8",
    )
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"_active",lambda service:True)
    monkeypatch.setattr(network_services,"_port_busy",lambda port,proto="tcp",address="0.0.0.0":True)
    state=network_services.mtproxy_status()
    assert state["installed"] is True
    assert state["configured"] is True
    assert state["service_active"] is True
    assert state["listener"] is True
    assert state["https_link"].startswith("https://t.me/proxy?")
    assert "server=proxy.example.com" in state["https_link"]
    assert "port=8443" in state["https_link"]
    assert "secret=ee" in state["https_link"]
    assert state["tg_link"].startswith("tg://proxy?")


def test_mtproxy_reconfigure_keeps_its_own_live_port(tmp_path,monkeypatch):
    env=tmp_path/"mtproxy.env"
    secret="ee0123456789abcdef0123456789abcdef6578616d706c652e636f6d"
    env.write_text(
        "MTPROXY_PUBLIC_HOST=proxy.example.com\n"
        "MTPROXY_PORT=443\n"
        "MTPROXY_FRONT_DOMAIN=proxy.example.com\n"
        f"MTPROXY_SECRET={secret}\n",
        encoding="utf-8",
    )
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"_active",lambda service:True)
    monkeypatch.setattr(network_services,"_port_busy",lambda port,proto="tcp",address="0.0.0.0":int(port)==443)
    monkeypatch.setattr(network_services,"_run",lambda *a,**k:"")
    monkeypatch.setattr(network_services,"_ufw_allow",lambda *a,**k:{"active":False})
    def must_not_allocate(*a,**k):
        raise AssertionError("active owned port must be preserved")
    monkeypatch.setattr(network_services,"_free_port",must_not_allocate)
    state=network_services.configure_mtproxy("proxy.example.com",443,False)
    assert state["port"]==443
    assert state["port_adjusted"] is False
    assert "MTPROXY_PORT=443" in env.read_text(encoding="utf-8")


def test_mtproxy_requires_domain_for_faketls(tmp_path,monkeypatch):
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"MTPROXY_ENV",tmp_path/"missing.env")
    monkeypatch.setattr(network_services,"_free_port",lambda *a,**k:8443)
    with pytest.raises(network_services.NetworkServiceError,match="DNS hostname"):
        network_services.configure_mtproxy("203.0.113.10",443,False)


def test_dns_public_mode_never_allows_open_resolver(monkeypatch):
    monkeypatch.setattr(network_services.shutil,"which",lambda name:f"/usr/bin/{name}")
    with pytest.raises(network_services.NetworkServiceError,match="allowlist"):
        network_services.configure_dns("public","cloudflare",[],"203.0.113.10")


def test_dns_private_config_is_acl_restricted_and_dot(tmp_path,monkeypatch):
    conf=tmp_path/"makia.conf"
    state=tmp_path/"dns.json"
    monkeypatch.setattr(network_services,"DNS_CONF",conf)
    monkeypatch.setattr(network_services,"DNS_STATE",state)
    monkeypatch.setattr(network_services.shutil,"which",lambda name:f"/usr/bin/{name}")
    monkeypatch.setattr(network_services,"_interface_ipv4",lambda name:"10.66.66.1" if name=="wg0" else "")
    monkeypatch.setattr(network_services,"_run",lambda *a,**k:"")
    monkeypatch.setattr(network_services,"_active",lambda service:True)
    monkeypatch.setattr(network_services,"dns_status",lambda:{
        "configured":True,"service_active":True,"mode":"private","upstream":"cloudflare"
    })
    result=network_services.configure_dns("private","cloudflare",[],"")
    text=conf.read_text(encoding="utf-8")
    assert "access-control: 0.0.0.0/0 refuse" in text
    assert "access-control: 127.0.0.0/8 allow" in text
    assert "access-control: 10.66.66.0/24 allow" in text
    assert "forward-tls-upstream: yes" in text
    assert "1.1.1.1@853#cloudflare-dns.com" in text
    assert "interface: 0.0.0.0" not in text
    assert result["service_active"] is True


def test_mtproxy_installer_is_version_and_checksum_pinned():
    text=(ROOT/"scripts/install-mtproxy.sh").read_text(encoding="utf-8")
    assert 'MTG_VERSION="2.2.8"' in text
    assert "7ef19d079d85f4e00d4f8334ec1f3f3c8718e3d0ed1f3109ea9a8673138a2102" in text
    assert "562a94dd4cafcb8f179b76cfeafb76da12747c8e230bc76235bf8746cc189644" in text
    assert "sha256sum" in text
    assert "generate-secret --hex" in text


def test_mtproxy_systemd_is_unprivileged_and_hardened():
    text=(ROOT/"systemd/makia-mtproxy.service").read_text(encoding="utf-8")
    assert "User=nobody" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "MemoryDenyWriteExecute=true" in text
    assert "simple-run" in text


def test_optional_network_components_are_packaged():
    install=(ROOT/"scripts/install.sh").read_text(encoding="utf-8")
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    for text in (install,update):
        assert "makia-mtproxy.service" in text
        assert "makia-install-mtproxy" in text
        assert "makia-install-dns" in text


def test_full_migration_declares_mtproxy_and_dns_assets():
    system=(ROOT/"app/system_ops.py").read_text(encoding="utf-8")
    restore=(ROOT/"scripts/restore-portable.py").read_text(encoding="utf-8")
    assert '"mtproxy":"/opt/makia-mtproxy"' in system
    assert '"unbound_conf":"/etc/unbound/unbound.conf.d/makia.conf"' in system
    assert 'payload/mtproxy.tar.gz' in restore
    assert 'payload/unbound_conf' in restore
    assert "makia-mtproxy.service" in restore


def test_provisioning_wizard_no_longer_renders_missing_card_index():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "protocolGlyph(x[0])" in js
    assert '<span class="protocol-card-icon '+x[0]+'">'+x[4]+'</span>' not in js
    assert "protocol-card-copy" in js


def test_network_views_and_actions_are_wired():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    for view in ("telegramproxy","dnscenter"):
        assert f'data-view="{view}"' in dashboard
        assert view in js
    for action in ("mtproxy-configure","mtproxy-rotate","dns-configure"):
        assert action in js
