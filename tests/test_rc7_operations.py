import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import automation_ops, main as main_app, outline_ops


def _request(path="/api/test", method="POST"):
    return Request({
        "type":"http","method":method,"path":path,
        "headers":[(b"x-makia-request",b"1")],
        "query_string":b"","scheme":"https",
        "server":("panel.example.com",443),"client":("127.0.0.1",1234),
    })


def test_cloudflare_cutover_payload_can_be_forced_dns_only(monkeypatch):
    monkeypatch.setattr(
        automation_ops,"cloudflare_resolve",
        lambda token,zone,record:{
            "zone_id":"zone1","record_id":"record1","record":{"id":"record1"},
            "zone":zone,"name":record,
        }
    )
    calls=[]
    def fake_json(url,method="GET",headers=None,payload=None,timeout=15):
        calls.append({"url":url,"method":method,"payload":payload})
        return 200,{"success":True,"result":{"id":"record1","content":payload["content"],"proxied":payload["proxied"]}}
    monkeypatch.setattr(automation_ops,"_json_request",fake_json)
    result=automation_ops.cloudflare_update_a(
        "A"*24,"example.com","vpn.example.com","203.0.113.9",120,False
    )
    assert result["record"]["content"]=="203.0.113.9"
    assert calls[-1]["payload"]["proxied"] is False
    assert calls[-1]["method"]=="PUT"


def test_telegram_send_is_scoped_to_exact_chat(monkeypatch):
    calls=[]
    def fake_json(url,method="GET",headers=None,payload=None,timeout=15):
        calls.append((url,method,payload))
        return 200,{"ok":True,"result":{"message_id":7}}
    monkeypatch.setattr(automation_ops,"_json_request",fake_json)
    result=automation_ops.telegram_send(
        "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd","-1001234567","Makia test"
    )
    assert result["message_id"]==7
    assert calls[0][2]["chat_id"]=="-1001234567"
    assert calls[0][2]["text"]=="Makia test"


def test_remote_quick_backup_is_rejected_before_persist(monkeypatch):
    monkeypatch.setattr(main_app,"require_local_admin",lambda request:"admin")
    monkeypatch.setattr(main_app,"require_mutation",lambda request:"admin")
    payload=main_app.BackupSchedulePayload(
        name="unsafe-remote-quick",backup_type="quick",interval_hours=24,
        keep_last=7,password="",
        remote={"type":"s3","bucket":"bucket","access_key":"a","secret_key":"b"},
        enabled=True,
    )
    with pytest.raises(HTTPException,match="Remote backups must use encrypted Full Migration"):
        main_app.scheduled_backups_create(payload,_request("/api/automation/backups"))


def test_device_detection_and_one_tap_are_protocol_safe():
    assert main_app._detect_client_device("Mozilla/5.0 (Linux; Android 14)")=="android"
    assert main_app._detect_client_device("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)")=="ios"
    assert main_app._detect_client_device("Mozilla/5.0 (Windows NT 10.0)")=="windows"
    assert main_app._detect_client_device("Mozilla/5.0 (Macintosh; Intel Mac OS X)")=="macos"
    assert main_app._one_tap_import_url("vless://abc@example.com:443")=="vless://abc@example.com:443"
    assert main_app._one_tap_import_url("ss://YWVzLTEyOC1nY206cGFzcw@example.com:8388").startswith("ss://")
    assert main_app._one_tap_import_url("https://example.com/config.ovpn")==""


def test_outline_access_config_parser_matches_official_format(monkeypatch,tmp_path):
    access=tmp_path/"access.txt"
    access.write_text(
        "apiUrl:https://127.0.0.1:12345/abcdefghijkl\n"
        "certSha256:"+"a"*64+"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(outline_ops,"ACCESS_CONFIG",access)
    cfg=outline_ops._read_access_config()
    assert cfg["apiUrl"].startswith("https://")
    assert cfg["certSha256"]=="a"*64


def test_outline_disable_really_revokes_key(monkeypatch):
    deleted=[]
    states=[]
    row={"id":9,"engine":"outline","inbound_tag":"outline:77","name":"alice","enabled":1}
    monkeypatch.setattr(outline_ops,"delete_key",lambda key:deleted.append(str(key)) or {"ok":True})
    import app.db as db
    monkeypatch.setattr(db,"set_protocol_client_enabled",lambda client_id,enabled,reason="":states.append((client_id,enabled,reason)))
    result=main_app._outline_disable_managed_client(row,"manual")
    assert result["disabled"] is True
    assert deleted==["77"]
    assert states==[(9,False,"manual")]


def test_outline_reissue_rotates_runtime_identity_and_preserves_managed_row(monkeypatch):
    identities=[]
    artifacts=[]
    row={
        "id":11,"engine":"outline","inbound_tag":"outline:old",
        "name":"bob","quota_bytes":1234,"enabled":0,
    }
    monkeypatch.setattr(
        outline_ops,"create_key",
        lambda name,limit_bytes=0:{"id":"88","accessUrl":"ss://new-secret@example.com:443"}
    )
    monkeypatch.setattr(
        main_app,"replace_protocol_client_identity",
        lambda client_id,inbound_tag,credential,share_link:identities.append(
            (client_id,inbound_tag,credential,share_link)
        )
    )
    monkeypatch.setattr(
        main_app,"artifact_save",
        lambda kind,key,name,protocol,payload,metadata=None:artifacts.append(
            (kind,key,payload["share_text"],metadata)
        ) or 1
    )
    result=main_app._outline_reissue_managed_client(row,2048)
    assert result["outline_id"]=="88"
    assert identities==[(11,"outline:88","88","ss://new-secret@example.com:443")]
    assert artifacts[0][0:3]==("outline","11","ss://new-secret@example.com:443")
    assert artifacts[0][3]["quota_bytes"]==2048


def test_outline_expiry_revokes_instead_of_removing_quota(monkeypatch):
    deleted=[]
    states=[]
    monkeypatch.setattr(automation_ops,"list_protocol_clients",lambda:[{
        "id":4,"engine":"outline","enabled":1,
        "expire_at":1,"inbound_tag":"outline:123","name":"expired"
    }])
    monkeypatch.setattr(outline_ops,"delete_key",lambda key:deleted.append(str(key)) or {"ok":True})
    monkeypatch.setattr(
        automation_ops,"set_protocol_client_enabled",
        lambda client_id,enabled,reason="":states.append((client_id,enabled,reason))
    )
    monkeypatch.setattr(automation_ops.time,"time",lambda:1000)
    automation_ops.enforce_outline_expiry()
    assert deleted==["123"]
    assert states==[(4,False,"expiry")]


def test_rc7_ui_contract_exposes_all_operations():
    root=Path(__file__).resolve().parents[1]
    js=(root/"app/static/app.js").read_text(encoding="utf-8")
    html=(root/"app/templates/dashboard.html").read_text(encoding="utf-8")
    main=(root/"app/main.py").read_text(encoding="utf-8")
    for marker in [
        "plansView","openQuickRenew","openBulkAccess","expiryView",
        "automationView","disasterView","integrationsView","diagnosticsView",
        "outlineView","one_tap_url","Fleet",
    ]:
        assert marker in js or marker in main
    for marker in [
        'data-view="outline"','data-view="plans"','data-view="expiry"',
        'data-view="automation"','data-view="diagnostics"','data-view="integrations"'
    ]:
        assert marker in html
    assert "/api/integrations/cloudflare/cutover" in main
    assert "/api/protocols/outline/clients" in main
