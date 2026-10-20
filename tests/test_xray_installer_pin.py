"""Prevent regression to mutable or shell-evaluated upstream Xray installer."""
from pathlib import Path
from app import protocol_ops


def test_installer_is_pinned_to_compatible_official_script():
    assert protocol_ops.XRAY_INSTALLER_COMMIT=="e741a4f56d368afbb9e5be3361b40c4552d3710d"
    source=(Path(__file__).resolve().parents[1]/"app/protocol_ops.py").read_text(encoding="utf-8")
    assert "raw.githubusercontent.com/XTLS/Xray-install/{XRAY_INSTALLER_COMMIT}" in source
    assert '["bash","-n",installer]' in source
    assert '["bash",installer,"install","--version",XRAY_VALIDATED_VERSION,"-u","nobody"]' in source
    assert 'bash -c "$(curl' not in source
    assert "Path(installer).unlink(missing_ok=True)" in source
