from pathlib import Path

import pytest

from app import scheduled_backup, system_ops


ROOT=Path(__file__).resolve().parents[1]


def test_outline_disaster_recovery_requires_docker_before_mutation():
    restore=(ROOT/"scripts/restore-portable.py").read_text(encoding="utf-8")
    install=(ROOT/"scripts/install.sh").read_text(encoding="utf-8")
    update=(ROOT/"scripts/update.sh").read_text(encoding="utf-8")
    assert '"payload/outline.tar.gz" in payload and not shutil.which("docker")' in restore
    assert "sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade" in restore
    assert 'if [[ "${MAKIA_ENABLE_OUTLINE:-0}" == "1" ]]; then' in install
    assert '[[ "${MAKIA_ENABLE_OUTLINE:-0}" == "1" || -s /opt/outline/access.txt ]]' in update
    assert "OUTLINE_HOST_PACKAGES+=(docker.io)" in update


def test_remote_backup_failure_does_not_advance_schedule(monkeypatch,tmp_path):
    settings=[]
    backup_path=tmp_path/"makia-full-migration-test.zip"
    backup_path.write_bytes(b"encrypted")
    manifest={"format":"makia-portable-migration","format_version":2}

    monkeypatch.setattr(scheduled_backup,"init_db",lambda:None)
    monkeypatch.setattr(scheduled_backup,"_config",lambda:{
        "enabled":True,
        "frequency_hours":24,
        "keep_local":7,
        "remote":{
            "enabled":True,"host":"backup.example.com","user":"makia",
            "path":"/srv/makia","port":22,"key_path":"/root/.ssh/id_ed25519",
        },
    })
    monkeypatch.setattr(scheduled_backup,"_secret",lambda:{"password":"strong-test-password"})
    monkeypatch.setattr(scheduled_backup,"get_setting",lambda key,default="":"0" if key=="backup_schedule_last_run" else default)
    monkeypatch.setattr(scheduled_backup,"set_setting",lambda key,value:settings.append((key,value)))
    monkeypatch.setattr(scheduled_backup,"all_profiles",lambda:{})
    monkeypatch.setattr(scheduled_backup.system_ops,"portable_migration_files",lambda *a,**k:{
        "manifest.json":__import__("json").dumps(manifest).encode("utf-8"),
        "payload/data.tar.gz":b"data",
        "payload/ssh-users.json":b"[]",
    })
    monkeypatch.setattr(scheduled_backup.access_ops,"protected_zip",lambda files,password:b"encrypted")
    monkeypatch.setattr(scheduled_backup.access_ops,"verify_protected_zip",lambda *a,**k:{"ok":True})
    monkeypatch.setattr(scheduled_backup.system_ops,"save_full_migration_backup",lambda *a,**k:{
        "name":backup_path.name,"path":str(backup_path),"sha256":"a"*64,
    })
    monkeypatch.setattr(scheduled_backup.system_ops,"prune_backup_files",lambda *a,**k:[])
    monkeypatch.setattr(
        scheduled_backup.system_ops,"remote_backup_scp",
        lambda *a,**k:(_ for _ in ()).throw(system_ops.OperationError("remote unavailable")),
    )

    with pytest.raises(system_ops.OperationError,match="remote unavailable"):
        scheduled_backup.run_once(False)
    assert not any(key=="backup_schedule_last_run" for key,_ in settings)


def test_integration_errors_redact_credential_bearing_urls(monkeypatch):
    token="123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
    url=f"https://api.telegram.org/bot{token}/sendMessage"

    def explode(*args,**kwargs):
        raise RuntimeError(f"network failure while opening {url}")

    monkeypatch.setattr(__import__("urllib.request",fromlist=["urlopen"]),"urlopen",explode)
    from app import integration_ops
    with pytest.raises(integration_ops.IntegrationError) as exc:
        integration_ops._json_request(url)
    message=str(exc.value)
    assert token not in message
    assert "/[redacted]" in message


def test_telegram_webhook_validates_bot_token_before_network():
    from app import integration_ops
    with pytest.raises(integration_ops.IntegrationError,match="invalid Telegram bot token"):
        integration_ops.telegram_set_webhook("not-a-token","https://panel.example.com/hook","A"*32)
