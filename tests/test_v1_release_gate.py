from pathlib import Path

import pytest
from fastapi import HTTPException

from app import main as main_app


ROOT=Path(__file__).resolve().parents[1]


class DummyRequest:
    method="DELETE"
    headers={"x-makia-request":"1"}
    client=None
    url=type("U",(),{"path":"/api/access/outline/7","netloc":"testserver"})()


def test_outline_managed_delete_revokes_runtime_then_local(monkeypatch):
    row={"id":7,"engine":"outline","inbound_tag":"key-77","name":"phone","enabled":1}
    calls=[]
    monkeypatch.setattr(main_app.integration_ops,"outline_list_keys",lambda:[{"id":"key-77"},{"id":"other"}])
    monkeypatch.setattr(main_app.integration_ops,"outline_delete_key",lambda key:calls.append(("runtime",key)) or {"removed":True})
    monkeypatch.setattr(main_app,"delete_access_artifact_by_key",lambda kind,key:calls.append(("artifact",kind,key)))
    monkeypatch.setattr(main_app,"delete_protocol_client",lambda client_id:calls.append(("db",client_id)))
    result=main_app._delete_outline_managed_client(row)
    assert result["ok"] is True and result["runtime_removed"] is True
    assert calls==[
        ("runtime","key-77"),
        ("artifact","outline","7"),
        ("db",7),
    ]


def test_outline_managed_delete_is_safe_when_runtime_key_already_missing(monkeypatch):
    row={"id":8,"engine":"outline","inbound_tag":"missing-key","name":"phone","enabled":0}
    calls=[]
    monkeypatch.setattr(main_app.integration_ops,"outline_list_keys",lambda:[{"id":"other"}])
    monkeypatch.setattr(main_app.integration_ops,"outline_delete_key",lambda key:(_ for _ in ()).throw(AssertionError("must not call delete")))
    monkeypatch.setattr(main_app,"delete_access_artifact_by_key",lambda kind,key:calls.append(("artifact",kind,key)))
    monkeypatch.setattr(main_app,"delete_protocol_client",lambda client_id:calls.append(("db",client_id)))
    result=main_app._delete_outline_managed_client(row)
    assert result["runtime_removed"] is False
    assert calls==[("artifact","outline","8"),("db",8)]


def test_outline_managed_delete_keeps_local_state_when_api_unreachable(monkeypatch):
    row={"id":9,"engine":"outline","inbound_tag":"key-99","name":"phone","enabled":1}
    calls=[]
    monkeypatch.setattr(
        main_app.integration_ops,"outline_list_keys",
        lambda:(_ for _ in ()).throw(main_app.integration_ops.IntegrationError("Outline API offline")),
    )
    monkeypatch.setattr(main_app,"delete_access_artifact_by_key",lambda *a,**k:calls.append(("artifact",a)))
    monkeypatch.setattr(main_app,"delete_protocol_client",lambda *a,**k:calls.append(("db",a)))
    with pytest.raises(HTTPException) as exc:
        main_app._delete_outline_managed_client(row)
    assert exc.value.status_code==400
    assert calls==[]


def test_generic_access_revoke_supports_outline(monkeypatch):
    row={"id":11,"engine":"outline","inbound_tag":"key-11","name":"alice","enabled":1}
    monkeypatch.setattr(main_app,"require_access_kind",lambda *a,**k:"admin")
    monkeypatch.setattr(main_app,"get_protocol_client",lambda client_id:row if int(client_id)==11 else None)
    monkeypatch.setattr(main_app,"_delete_outline_managed_client",lambda value:{"ok":True,"client_id":value["id"],"outline_key_id":value["inbound_tag"]})
    monkeypatch.setattr(main_app,"audit",lambda *a,**k:None)
    result=main_app.access_revoke("outline","11",DummyRequest())
    assert result["ok"] is True
    assert result["outline_key_id"]=="key-11"


def test_access_revoke_has_all_first_class_protocols():
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    start=main.index('@app.delete("/api/access/{kind}/{key}")')
    block=main[start:start+5000]
    for kind in ["ssh","xray","wireguard","openvpn","outline"]:
        assert f'kind=="{kind}"' in block


def test_ui_actions_have_delegated_handlers():
    import re
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    actions=set(re.findall(r'data-action=["\']([^"\']+)["\']',js))
    handlers=set(re.findall(r'action===["\']([^"\']+)["\']',js))
    allowed_inline={"modal-close"}
    assert sorted(actions-handlers-allowed_inline)==[]


def test_ui_static_api_calls_have_backend_routes():
    import re
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    registered_modules=[
        (ROOT/"app/client_admin.py").read_text(encoding="utf-8")
    ]
    route_source=main+"\n"+"\n".join(registered_modules)
    calls=sorted(set(
        m.group(2).split("?")[0]
        for m in re.finditer(r"api\(([\'\"\x60])([^\'\"\x60]+)\1",js)
        if m.group(2).startswith("/api/")
    ))
    routes=[
        (m.group(1).upper(),m.group(2))
        for m in re.finditer(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',route_source)
    ]
    missing=[]
    for call in calls:
        if not any(path==call or ("{" in path and call.startswith(path.split("{")[0])) for _,path in routes):
            missing.append(call)
    assert missing==[]


def test_no_duplicate_fastapi_routes():
    import re
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    routes=[
        (m.group(1).upper(),m.group(2))
        for m in re.finditer(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',main)
    ]
    assert len(routes)==len(set(routes))


def test_outline_management_action_contract_present():
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    main=(ROOT/"app/main.py").read_text(encoding="utf-8")
    for marker in [
        "outline-renew","outline-reissue","outline-quota","revoke-access",
        "client-portal","protected-export","access-share","access-diagnostics",
    ]:
        assert marker in js
    for marker in [
        '/api/protocols/outline/keys',
        '/api/protocols/outline/clients/{client_id}/reissue',
        '/api/protocols/outline/clients/{client_id}/quota',
        '/api/access/{kind}/{key}',
        '/api/diagnostics/access/{kind}/{key}',
    ]:
        assert marker in main


def test_inline_onclick_handlers_exist():
    import re
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    login=(ROOT/"app/templates/login.html").read_text(encoding="utf-8")
    combined=js+"\n"+dashboard+"\n"+login
    inline=re.findall(r'onclick=["\']([^"\']+)["\']',combined)
    calls={
        m.group(1)
        for code in inline
        for m in re.finditer(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",code)
    }
    ignore={"if","confirm","alert","Number","String","encodeURIComponent","decodeURIComponent"}
    definitions=set(re.findall(r"(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",js))
    assert sorted(calls-ignore-definitions)==[]


def test_shell_actions_are_wired():
    import re
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    actions=set(re.findall(r'data-shell-action=["\']([^"\']+)["\']',dashboard))
    missing=[a for a in sorted(actions) if f"'"+a+"'" not in js and '"'+a+'"' not in js]
    assert missing==[]


def test_official_brand_asset_is_referenced():
    dashboard=(ROOT/"app/templates/dashboard.html").read_text(encoding="utf-8")
    login=(ROOT/"app/templates/login.html").read_text(encoding="utf-8")
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    assert (ROOT/"app/static/makia-brand.png").is_file()
    assert (ROOT/"docs/assets/makia-brand.png").is_file()
    assert "/static/makia-brand.png" in dashboard
    assert "/static/makia-brand.png" in login
    assert "docs/assets/makia-brand.png" in readme


def test_client_only_update_preserves_active_vpn_runtimes_when_protocol_code_unchanged():
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert 'cmp -s "$APP/app/protocol_ops.py" "$SRC/app/protocol_ops.py"' in update
    assert 'PROTOCOL_RUNTIME_CHANGED=0' in update
    assert 'if [[ "$PROTOCOL_RUNTIME_CHANGED" -eq 1 ]]; then' in update
    assert 'skipping automatic Xray/WireGuard/OpenVPN provisioning and repair' in update
    assert 'Existing protocol runtime state preserved.' in update
    for service in ["xray","openvpn-server@server","wg-quick@wg0"]:
        assert f"systemctl is-active --quiet {service}" in update

def test_v140_uat_artifact_provenance_contract():
    uat=(ROOT/"docs/UAT-1.4.0.md").read_text(encoding="utf-8")
    release=(ROOT/"docs/RELEASE-1.4.0.md").read_text(encoding="utf-8")
    win=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    android=(ROOT/".github/workflows/android-connector.yml").read_text(encoding="utf-8")
    assert "release/v1.4.0-uat1" in uat
    assert "Makia-Client-Connector-Windows-x64" in uat
    assert "Makia-Android-Connector-1.4.0-UAT" in uat
    assert "Makia-Android-Connector-RC" not in uat
    assert "PR #73" in uat
    assert "MAKIA_REF=<FROZEN_UAT_SHA_FROM_PR_73>" in uat
    assert "MAKIA_FORCE_MAIN=0" in uat
    assert "Do not run plain `sudo makia-upgrade` for pre-merge UAT" in uat
    assert "Frozen UAT branch: `release/v1.4.0-uat1`" in release
    assert "\\\\n\\\\nFrozen UAT branch" not in release
    for workflow in (win, android):
        assert "BUILD-INFO.txt" in workflow
        assert "GITHUB_SHA" in workflow
        assert "GITHUB_RUN_ID" in workflow


def test_clean_installer_bootstrap_contract():
    bootstrap=(ROOT/"install.sh").read_text(encoding="utf-8")
    install=(ROOT/"scripts/install.sh").read_text(encoding="utf-8")

    # The public bootstrap must accept both branch names and exact frozen SHAs.
    assert "https://codeload.github.com/${REPO}/tar.gz/${REF}" in bootstrap
    assert "refs/heads/${REF}" not in bootstrap
    assert "--retry 5 --retry-all-errors" in bootstrap
    assert 'MAKIA_INSTALL_SOURCE_REF="$REF"' in bootstrap

    # Fresh minimal Ubuntu must receive runtime dependencies before Python is used.
    password='ADMIN_PASSWORD="$(python3 - <<\'PY\''
    packages='apt_retry install -y'
    assert packages in install
    assert "python3 python3-venv python3-pip" in install
    for dependency in ("iproute2","iptables","openssl","wireguard-tools","openvpn","easy-rsa","stunnel4"):
        assert dependency in install
    assert install.index(packages) < install.index(password)

    # A rerun after a partial install must preserve the existing admin credential.
    assert 'ADMIN_EXISTS=0' in install
    assert 'SELECT 1 FROM admins LIMIT 1' in install
    assert 'Existing administrator detected' in install
    assert 'existing credential preserved' in install
    assert 'sudo makia-reset-admin' in install
    assert 'from app.security import ensure_secret; init_db(); ensure_secret()' in install

    # Fail early with an actionable message on unsupported raw-host environments.
    assert 'Makia requires an Ubuntu VPS booted with systemd' in install
    assert 'At least 1 GiB of free disk space is required' in install
    assert 'DPkg::Lock::Timeout=180' in install
