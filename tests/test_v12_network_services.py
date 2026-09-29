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
    secret="ee0123456789abcdef0123456789abcdef6578616d706c652e636f6d"
    env.write_text(
        "MTPROXY_PUBLIC_HOST=proxy.example.com\n"
        "MTPROXY_PORT=8443\n"
        "MTPROXY_FRONT_DOMAIN=proxy.example.com\n",
        encoding="utf-8",
    )
    config=tmp_path/"mtproxy.toml"
    config.write_text(f'secret = "{secret}"\nbind-to = "0.0.0.0:8443"\n',encoding="utf-8")
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_CONFIG",config)
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
        "MTPROXY_FRONT_DOMAIN=proxy.example.com\n",
        encoding="utf-8",
    )
    config=tmp_path/"mtproxy.toml"
    config.write_text(f'secret = "{secret}"\nbind-to = "0.0.0.0:443"\n',encoding="utf-8")
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_CONFIG",config)
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"_active",lambda service:True)
    monkeypatch.setattr(network_services,"_port_busy",lambda port,proto="tcp",address="0.0.0.0":int(port)==443)
    monkeypatch.setattr(network_services,"_run",lambda *a,**k:"")
    monkeypatch.setattr(network_services,"_write_mtproxy_config",lambda value,port:config.write_text(f'secret = "{value}"\nbind-to = "0.0.0.0:{port}"\n',encoding="utf-8"))
    monkeypatch.setattr(network_services,"_ufw_allow",lambda *a,**k:{"active":False})
    def must_not_allocate(*a,**k):
        raise AssertionError("active owned port must be preserved")
    monkeypatch.setattr(network_services,"_free_port",must_not_allocate)
    state=network_services.configure_mtproxy("proxy.example.com",443,False)
    assert state["port"]==443
    assert state["port_adjusted"] is False
    assert "MTPROXY_PORT=443" in env.read_text(encoding="utf-8")
    assert secret in config.read_text(encoding="utf-8")


def test_mtproxy_requires_domain_for_faketls(tmp_path,monkeypatch):
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"MTPROXY_ENV",tmp_path/"missing.env")
    monkeypatch.setattr(network_services,"MTPROXY_CONFIG",tmp_path/"missing.toml")
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
    firewall=[]
    monkeypatch.setattr(network_services,"_ufw_reconcile_dns",lambda networks:firewall.extend(networks) or {"active":True})
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
    assert firewall==["10.66.66.0/24"]
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
    assert "User=makia-mtproxy" in text
    assert "ExecStart=/opt/makia-mtproxy/mtg run /etc/makia-vps-manager/mtproxy.toml" in text
    assert "MTPROXY_SECRET" not in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "MemoryDenyWriteExecute=true" in text
    assert "mtg run /etc/makia-vps-manager/mtproxy.toml" in text


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
    assert """<span class="protocol-card-icon '+x[0]+'">'+x[4]+'</span>""" not in js
    assert "protocol-card-copy" in js


def test_network_views_and_actions_are_wired():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    for view in ("telegramproxy","dnscenter"):
        assert f'data-view="{view}"' in dashboard
        assert view in js
    for action in ("mtproxy-configure","mtproxy-rotate","dns-configure"):
        assert action in js


def test_dns_ufw_is_source_scoped():
    source=(ROOT/"app/network_services.py").read_text(encoding="utf-8")
    assert '"ufw","allow","from",network,"to","any","port","53"' in source
    assert '_ufw_allow(53,"udp"' not in source
    assert '_ufw_allow(53,"tcp"' not in source


def test_mtproxy_secret_is_not_in_process_argv_or_state_file():
    service=(ROOT/"systemd/makia-mtproxy.service").read_text(encoding="utf-8")
    installer=(ROOT/"scripts/install-mtproxy.sh").read_text(encoding="utf-8")
    assert "MTPROXY_SECRET" not in service
    assert "ExecStart=/opt/makia-mtproxy/mtg run /etc/makia-vps-manager/mtproxy.toml" in service
    state_block=installer.split('cat >"$STATE_FILE"',1)[1].split("EOF",1)[0]
    assert "MTPROXY_SECRET" not in state_block
    assert 'chown root:makia-mtproxy "$CONFIG_FILE"' in installer
    assert 'chmod 0640 "$CONFIG_FILE"' in installer


def test_network_service_navigation_is_visible_in_protocol_group():
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    protocol_panel=dashboard.split('data-group-panel="protocols"',1)[1].split("</div>",1)[0]
    infra_panel=dashboard.split('data-group-panel="infra"',1)[1].split("</div>",1)[0]
    assert 'data-view="telegramproxy"' in protocol_panel
    assert 'data-view="dnscenter"' in protocol_panel
    assert 'data-view="telegramproxy"' not in infra_panel
    assert 'data-view="dnscenter"' not in infra_panel


def test_dns_client_delivery_never_presents_loopback_as_remote_address():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "remoteAddresses=[...new Set([r.wireguard_address,r.public_address].filter(Boolean))]" in js
    assert "dnsUserDelivery" in js
    assert "127.0.0.1" not in js.split("const remoteAddresses=",1)[1].split("const upstreamOptions",1)[0]


def test_network_tooling_is_prepared_by_install_and_update():
    install=(ROOT/"scripts/install.sh").read_text(encoding="utf-8")
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    mt=(ROOT/"scripts/install-mtproxy.sh").read_text(encoding="utf-8")
    dns=(ROOT/"scripts/install-dns.sh").read_text(encoding="utf-8")
    for text in (install,update):
        assert "makia-install-mtproxy --install-only" in text
        assert "makia-install-dns --install-only" in text
    assert "--install-only) INSTALL_ONLY=1" in mt
    assert "--install-only) INSTALL_ONLY=1" in dns


def test_panel_install_commands_prepare_only_then_configure_in_ui(tmp_path,monkeypatch):
    env=tmp_path/"missing.env"
    config=tmp_path/"missing.toml"
    binary=tmp_path/"mtg"
    binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_CONFIG",config)
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"_active",lambda service:False)
    state=network_services.mtproxy_status("panel.example.com")
    assert state["installed"] is True
    assert state["configured"] is False
    assert state["install_command"].endswith("makia-install-mtproxy --install-only")
    assert network_services.dns_install_command().endswith("makia-install-dns --install-only")


def test_update_preserves_network_service_state_contract():
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    for path in (
        "/etc/makia-vps-manager/mtproxy.env",
        "/etc/makia-vps-manager/mtproxy.toml",
        "/etc/makia-vps-manager/dns.json",
        "/etc/unbound/unbound.conf.d/makia.conf",
    ):
        assert path in update
    assert "file_sha256" in update
    assert "assert_preserved_file" in update
    assert 'assert_preserved_file "$MTPROXY_ENV_PATH"' in update
    assert 'assert_preserved_file "$MTPROXY_CONFIG_PATH"' in update
    assert 'assert_preserved_file "$DNS_STATE_PATH"' in update
    assert 'assert_preserved_file "$DNS_CONFIG_PATH"' in update
    assert "MTProxy was active before update but is not active after tooling refresh" in update
    assert "DNS resolver was active before update but is not active after tooling refresh" in update
    assert "systemctl restart makia-mtproxy" in update
    assert "systemctl restart unbound" in update


def test_mtproxy_firewall_failure_preserves_config(tmp_path,monkeypatch):
    env=tmp_path/"mtproxy.env"
    config=tmp_path/"mtproxy.toml"
    binary=tmp_path/"mtg";binary.write_text("binary",encoding="utf-8")
    monkeypatch.setattr(network_services,"MTPROXY_ENV",env)
    monkeypatch.setattr(network_services,"MTPROXY_CONFIG",config)
    monkeypatch.setattr(network_services,"MTPROXY_BIN",binary)
    monkeypatch.setattr(network_services,"_free_port",lambda *a,**k:8443)
    monkeypatch.setattr(network_services,"_run",lambda *a,**k:"ee0123456789abcdef0123456789abcdef6578616d706c652e636f6d" if "generate-secret" in a[0] else "")
    monkeypatch.setattr(network_services,"_active",lambda service:True)
    monkeypatch.setattr(network_services,"_port_busy",lambda port,proto="tcp",address="0.0.0.0":True)
    monkeypatch.setattr(network_services.grp,"getgrnam",lambda name:type("G",(),{"gr_gid":0})())
    monkeypatch.setattr(network_services.os,"chown",lambda *a,**k:None)
    monkeypatch.setattr(network_services,"_ufw_allow",lambda *a,**k:(_ for _ in ()).throw(network_services.NetworkServiceError("ufw failed")))
    monkeypatch.setattr(network_services,"_ufw_port_status",lambda *a,**k:{"active":True,"allowed":False})
    result=network_services.configure_mtproxy("proxy.example.com",443,False)
    assert result["configured"] is True
    assert result["service_active"] is True
    assert result["listener"] is True
    assert result["firewall_warning"]=="ufw failed"
    assert env.exists() and "MTPROXY_PORT=8443" in env.read_text(encoding="utf-8")
    assert config.exists() and "secret = " in config.read_text(encoding="utf-8")


def test_mtproxy_ui_explains_firewall_failure_without_claiming_deletion():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "firewall_warning" in js
    assert "Proxy configuration is preserved" in js


def test_mtproxy_systemd_avoids_go_incompatible_wx_hardening():
    service=(ROOT/"systemd/makia-mtproxy.service").read_text(encoding="utf-8")
    assert "User=makia-mtproxy" in service
    assert "AmbientCapabilities=CAP_NET_BIND_SERVICE" in service
    assert "ProtectSystem=strict" in service
    assert "MemoryDenyWriteExecute=true" not in service


def test_mtproxy_runtime_failure_returns_bounded_diagnostics(monkeypatch):
    outputs=[
        type("P",(),{"stdout":"service failed with secret eeSECRET","stderr":"","returncode":3})(),
        type("P",(),{"stdout":"journal says bind failed eeSECRET","stderr":"","returncode":0})(),
    ]
    def fake_run(*args,**kwargs):
        return outputs.pop(0)
    monkeypatch.setattr(network_services.subprocess,"run",fake_run)
    text=network_services._mtproxy_runtime_diagnostics("eeSECRET")
    assert "<redacted-secret>" in text
    assert "eeSECRET" not in text
    assert "bind failed" in text


def test_mtproxy_listener_startup_window_is_not_eight_seconds():
    source=(ROOT/"app/network_services.py").read_text(encoding="utf-8")
    assert "deadline=time.monotonic()+25" in source
    assert "deadline=time.monotonic()+8" not in source
