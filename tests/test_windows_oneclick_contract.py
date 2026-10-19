"""One-click Windows setup must be per-user and cannot bypass real VPN UAT."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_windows_installer_is_single_exe_with_user_scope_and_safe_shortcuts():
    script=(ROOT/"client/windows/setup.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert r"DefaultDirName={localappdata}\Makia\Connector\bin" in script
    assert "Makia-Windows-Setup-{#MyVersion}-x64" in script
    assert r"{autoprograms}\Makia Windows" in script
    assert r"Software\Classes\makia" in script
    assert "InitializeUninstall()" in script
    assert "TunnelStateExists()" in script
    assert "UninstallDisplayIcon=" in script
    assert "AppVersion={#MyVersion}" in script
    assert "AppId=Makia.Windows.FullDevice" in script
    assert "[Run]" in script and "postinstall skipifsilent" in script


def test_native_gui_does_not_confuse_local_state_with_verified_egress():
    source=(ROOT/"client/windows/makia_windows.py").read_text(encoding="utf-8")
    assert 'PORTAL_URL="https://p.mahinet.shop/client/"' in source
    assert "open_official_portal()" in source
    assert "MakiaClientConnector.exe" in source
    assert "آخرین فرمان اتصال ثبت شده" in source
    assert "--disconnect" in source
    assert "webbrowser.open" in source
    assert "password_hash" not in source
    assert "api_token" not in source
    assert "login_password" not in source


def test_windows_ci_compiles_and_smoke_installs_uninstalls_setup_without_releasing():
    flow=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    assert "pyinstaller --noconfirm --clean --onefile --windowed --name MakiaWindows" in flow
    assert "choco install innosetup --version 6.7.1" in flow
    assert "client\\windows\\setup.iss" in flow
    assert "Start-Process -FilePath $setup" in flow
    assert "Start-Process -FilePath $uninstall" in flow
    assert "Setup smoke PASS" in flow
    assert "installer/SHA256SUMS.txt" in flow
    assert "Makia-Windows-OneClick-x64-1.6.5.1-UAT" in flow
    assert "gh release upload" not in flow
    assert "gh release create" not in flow


def test_full_device_install_requires_user_action_not_auto_started():
    script=(ROOT/"client/windows/setup.iss").read_text(encoding="utf-8")
    assert "skipifsilent" in script
    assert "RestartApplications=no" in script
    assert "TunnelStateExists" in script
    assert "MAKIA_INITIAL_ADMIN_PASSWORD" not in script
