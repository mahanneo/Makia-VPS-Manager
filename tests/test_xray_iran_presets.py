from pathlib import Path

from app import protocol_ops


ROOT=Path(__file__).resolve().parents[1]


def test_iran_xray_preset_catalog_is_valid_and_unique():
    caps=protocol_ops.xray_inbound_builder_capabilities()
    presets=caps.get("presets") or []
    assert len(presets)>=7
    ids=[p["id"] for p in presets]
    assert len(ids)==len(set(ids))
    for preset in presets:
        protocol=preset["protocol"]
        transport=preset["transport"]
        security=preset["security"]
        normalized=protocol_ops._xray_builder_validate_combo(protocol,transport,security)
        assert normalized
        assert preset["tier"] in {"recommended","alternative","compatibility","experimental"}
        assert preset.get("summary")
        assert preset.get("note")
        assert all(1<=int(port)<=65535 for port in preset.get("ports") or [])


def test_primary_recommended_preset_avoids_experimental_xhttp():
    presets=protocol_ops.xray_inbound_builder_capabilities()["presets"]
    recommended=[p for p in presets if p["tier"]=="recommended"]
    assert recommended
    assert all(p["transport"]!="xhttp" for p in recommended)
    assert any(
        p["protocol"]=="vless"
        and p["transport"]=="tcp"
        and p["security"]=="reality"
        and p["flow"]=="xtls-rprx-vision"
        for p in recommended
    )


def test_xhttp_is_explicitly_lab_only_for_pinned_core():
    presets=protocol_ops.xray_inbound_builder_capabilities()["presets"]
    xhttp=[p for p in presets if p["transport"]=="xhttp"]
    assert xhttp
    assert all(p["tier"]=="experimental" for p in xhttp)
    assert all("26.3.27" in p["note"] for p in xhttp)


def test_tls_presets_declare_domain_requirement():
    presets=protocol_ops.xray_inbound_builder_capabilities()["presets"]
    tls=[p for p in presets if p["security"]=="tls"]
    assert tls
    assert all(p["requires_domain"] is True for p in tls)


def test_udp_requirement_is_only_used_for_udp_profile():
    presets=protocol_ops.xray_inbound_builder_capabilities()["presets"]
    udp=[p for p in presets if p.get("requires_udp")]
    assert udp
    assert all(p["protocol"]=="hysteria2" and p["transport"]=="hysteria" for p in udp)


def test_builder_ui_exposes_preset_selection_and_apply_handler():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    css=(ROOT/"app/static/app.css").read_text(encoding="utf-8")
    assert "Iran Network Presets" in js
    assert 'data-action="xray-inbound-preset"' in js
    assert "function applyXrayInboundPreset" in js
    assert "xray-inbound-preset" in js
    assert ".xray-preset-grid" in css
    assert ".tier-experimental" in css


def test_preset_apply_keeps_normal_validated_builder_path():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "applyXrayInboundPreset" in js
    assert "createXrayInboundBuilder" in js
    assert "/api/protocols/xray/inbounds" in js
    assert "Validate & Create" in js


def test_presets_do_not_claim_guaranteed_connectivity():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "Preset = شروع سریع، نه تضمین اتصال" in js
