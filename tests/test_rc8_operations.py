import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from starlette.requests import Request

from app import access_ops, integration_ops, main as main_app, system_ops


ROOT=Path(__file__).resolve().parents[1]


def _request(path="/api/test", method="POST", token="node-token"):
    return Request({
        "type":"http","method":method,"path":path,
        "headers":[(b"authorization",f"Bearer {token}".encode())],
        "query_string":b"","scheme":"https",
        "server":("panel.example.com",443),"client":("127.0.0.1",1234),
    })


def test_cloudflare_cutover_is_always_dns_only(monkeypatch):
    monkeypatch.setattr(
        integration_ops,"cloudflare_record",
        lambda token,zone,name:{"id":"rec1","name":name,"proxied":True},
    )
    calls=[]
    def fake_json(url,method="GET",body=None,headers=None,timeout=15,context=None):
        calls.append({"url":url,"method":method,"body":body,"headers":headers})
        return {"success":True,"result":{"id":"rec1","name":"vpn.example.com","content":"203.0.113.9","proxied":body["proxied"],"ttl":body["ttl"]}}
    monkeypatch.setattr(integration_ops,"_json_request",fake_json)
    result=integration_ops.cloudflare_update_a("A"*24,"zone_id_123456","vpn.example.com","203.0.113.9",120)
    assert calls[-1]["body"]["proxied"] is False
    assert result["proxied"] is False


def test_telegram_mock_send_and_delete_webhook(monkeypatch):
    calls=[]
    def fake_json(url,method="GET",body=None,headers=None,timeout=15,context=None):
        calls.append((url,method,body))
        if url.endswith("/sendMessage"):
            return {"ok":True,"result":{"message_id":7}}
        return {"ok":True,"result":True}
    monkeypatch.setattr(integration_ops,"_json_request",fake_json)
    token="123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
    result=integration_ops.telegram_send(token,"-1001234567","Makia test")
    assert result["message_id"]==7
    assert calls[-1][2]["chat_id"]=="-1001234567"
    integration_ops.telegram_delete_webhook(token)
    assert calls[-1][0].endswith("/deleteWebhook")
    assert calls[-1][2]["drop_pending_updates"] is False


def test_remote_backup_scp_requires_pinned_known_host_and_private_key(monkeypatch,tmp_path):
    backup=tmp_path/"backup.zip";backup.write_bytes(b"encrypted")
    key=tmp_path/"id_ed25519";key.write_text("private",encoding="utf-8");key.chmod(0o600)
    seen=[]
    monkeypatch.setattr(system_ops,"_run",lambda args,timeout=180:seen.append(args) or "")
    result=system_ops.remote_backup_scp(backup,"backup.example.com","makia","/srv/makia",22,str(key))
    args=seen[0]
    assert "StrictHostKeyChecking=yes" in args
    assert "IdentitiesOnly=yes" in args
    assert result["target"].endswith("/srv/makia/backup.zip")
    key.chmod(0o644)
    with pytest.raises(system_ops.OperationError,match="permissions"):
        system_ops.remote_backup_scp(backup,"backup.example.com","makia","/srv/makia",22,str(key))


def test_outline_metrics_mocked_api(monkeypatch):
    monkeypatch.setattr(
        integration_ops,"_outline_request",
        lambda path,method="GET",body=None:{"bytesTransferredByUserId":{"17":123456,"18":0}},
    )
    assert integration_ops.outline_transfer_metrics()=={"17":123456,"18":0}


def test_outline_reissue_preserves_managed_identity(monkeypatch):
    identities=[];states=[];artifacts=[];deleted=[]
    row={
        "id":11,"engine":"outline","inbound_tag":"old-key","credential":"old-key",
        "share_link":"ss://old","name":"alice","quota_bytes":1024,"expire_at":999999,
        "enabled":1,
    }
    monkeypatch.setattr(integration_ops,"outline_create_key",lambda name,quota:{"id":"new-key","accessUrl":"ss://new-secret@example.com:443"})
    monkeypatch.setattr(integration_ops,"outline_delete_key",lambda key:deleted.append(str(key)) or {"removed":True})
    monkeypatch.setattr(main_app,"replace_protocol_client_identity",lambda client_id,inbound,credential,share:identities.append((client_id,inbound,credential,share)))
    monkeypatch.setattr(main_app,"update_protocol_client_state",lambda *args:states.append(args))
    monkeypatch.setattr(main_app,"artifact_save",lambda *args,**kwargs:artifacts.append((args,kwargs)) or 1)
    result=main_app._outline_reissue_managed_client(row,2048)
    assert result["client_id"]==11
    assert result["outline_key_id"]=="new-key"
    assert identities[0]==(11,"new-key","new-key","ss://new-secret@example.com:443")
    assert artifacts
    assert deleted==["old-key"]


def test_bulk_renew_outline_updates_real_server_limit(monkeypatch):
    row={"id":7,"engine":"outline","inbound_tag":"key7","name":"bob","enabled":1,"quota_bytes":1024,"expire_at":int(time.time())+3600}
    limits=[];states=[]
    monkeypatch.setattr(main_app,"get_protocol_client",lambda client_id:row if int(client_id)==7 else None)
    monkeypatch.setattr(integration_ops,"outline_set_limit",lambda key,quota:limits.append((key,quota)) or {"id":key})
    monkeypatch.setattr(main_app,"update_protocol_client_state",lambda *args:states.append(args))
    result=main_app._renew_managed_item("outline","7",30,1,"admin",_request())
    assert limits and limits[0][0]=="key7"
    assert limits[0][1]>1024
    assert states and states[0][1] is True
    assert result["expire_at"]>row["expire_at"]


def test_expiry_snapshot_combines_ssh_and_managed_protocols(monkeypatch):
    tomorrow=(date.today()+timedelta(days=1)).isoformat()
    now=int(time.time())
    monkeypatch.setattr(main_app,"all_profiles",lambda:{"ssh-user":{"expire_date":tomorrow}})
    monkeypatch.setattr(main_app,"list_protocol_clients",lambda:[{
        "id":9,"engine":"outline","name":"outline-user","protocol":"outline",
        "expire_at":now+2*86400,"enabled":1,
    }])
    snap=main_app._expiry_snapshot(7)
    assert snap["count"]==2
    assert {x["kind"] for x in snap["rows"]}=={"ssh","outline"}
    assert all(x["renew_supported"] for x in snap["rows"])


def test_node_telemetry_heartbeat_maps_all_operational_fields(monkeypatch):
    captured=[]
    monkeypatch.setattr(main_app,"node_by_token",lambda token:{"id":3} if token=="node-token" else None)
    monkeypatch.setattr(main_app,"update_node_heartbeat",lambda *args:captured.append(args))
    payload=main_app.NodeHeartbeat(
        hostname="edge-1",version="0.26.0-rc8",cpu=10.5,memory=20.5,disk=30.5,
        public_ip="203.0.113.10",region="de-fra",users=25,online_users=4,
        traffic_bytes=987654,services={"xray":True,"outline":True},last_error="",
    )
    result=main_app.node_heartbeat(payload,_request("/api/node/heartbeat"))
    assert result["ok"] is True
    args=captured[0]
    assert args[0]==3 and args[1]=="edge-1"
    assert args[6]=="203.0.113.10" and args[7]=="de-fra"
    assert args[8:11]==(25,4,987654)
    assert args[11]["outline"] is True


def test_service_plans_strip_unenforceable_policy_fields():
    wg=main_app.ServicePlanPayload(
        name="wg-template",protocol_kind="wireguard",
        config={"expire_days":30,"quota_gb":50,"ip_limit":2,"mtu":1280},
    )
    kind,cfg=main_app._validate_service_plan(wg)
    assert kind=="wireguard"
    assert cfg=={"mtu":1280}
    outline=main_app.ServicePlanPayload(
        name="outline",protocol_kind="outline",
        config={"expire_days":30,"quota_gb":50,"ip_limit":4,"reset_days":30},
    )
    _,cfg2=main_app._validate_service_plan(outline)
    assert cfg2["expire_days"]==30 and cfg2["quota_gb"]==50
    assert "ip_limit" not in cfg2 and "reset_days" not in cfg2
    ssh=main_app.ServicePlanPayload(name="ssh",protocol_kind="ssh",config={"expire_days":30,"quota_gb":20,"device_limit":2})
    _,cfg3=main_app._validate_service_plan(ssh)
    assert cfg3["expire_days"]==30 and cfg3["device_limit"]==2
    assert "quota_gb" not in cfg3


def test_secret_snapshots_never_return_tokens(monkeypatch):
    values={
        "cloudflare_secret":"sealed-cloudflare-token","cloudflare_zone_id":"zone1234567890",
        "cloudflare_record_name":"vpn.example.com","cloudflare_ttl":"60",
        "telegram_secret":"sealed-telegram-token","telegram_chat_id":"-1001234567",
        "telegram_webhook_enabled":"1",
    }
    monkeypatch.setattr(main_app,"get_setting",lambda key,default="":values.get(key,default))
    cf=main_app._cloudflare_snapshot();tg=main_app._telegram_snapshot()
    joined=json.dumps({"cf":cf,"tg":tg})
    assert "sealed-cloudflare-token" not in joined
    assert "sealed-telegram-token" not in joined
    assert "api_token" not in cf and "bot_token" not in tg


def test_protected_backup_payload_verifies_before_restore():
    password="RC8-strong-backup-password"
    files={"manifest.json":json.dumps({"format":"makia-portable-migration","format_version":2}).encode(),"payload/test.txt":b"state"}
    blob=access_ops.protected_zip(files,password)
    assert access_ops.verify_protected_zip(blob,password,"manifest.json")["ok"] is True
    with pytest.raises(access_ops.AccessPackageError):
        access_ops.verify_protected_zip(blob,"wrong-password","manifest.json")


def test_restore_and_installer_static_safety_contracts():
    restore=(ROOT/"scripts/restore-portable.py").read_text(encoding="utf-8")
    installer=(ROOT/"scripts/install-outline.sh").read_text(encoding="utf-8")
    system_ops=(ROOT/"app/system_ops.py").read_text(encoding="utf-8")
    assert "automatic rollback" in restore
    assert 'Path("/opt/outline")' in restore
    assert 'OUTLINE_VERSION="server-v1.12.0"' in installer
    assert 'OUTLINE_GIT_BLOB_SHA="39ba2b0d4ed6cb60ef94bc6015fcc619f092633b"' in installer
    assert "Pinned Outline installer integrity check failed" in installer
    assert "StrictHostKeyChecking=yes" in system_ops


def test_rc8_ui_contract_exposes_real_outline_operations():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    html=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    for marker in [
        'data-view="outline"','data-view="plans"','data-view="expiry"',
        'data-view="operations"','data-view="diagnostics"','data-view="nodes"',
    ]:
        assert marker in html
    for marker in [
        "outline-quota","outline-renew","outline-reissue","access-diagnostics",
        "Protected ZIP","Client portal link","MULTI-VPS FLEET",
    ]:
        assert marker in js
    assert "/api/protocols/outline/clients/{client_id}/reissue" in main
    assert "/api/protocols/outline/clients/{client_id}/quota" in main
