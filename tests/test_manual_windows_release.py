from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_windows_build_does_not_publish_untested_package_on_main_push():
    workflow=(ROOT/".github/workflows/native-connector.yml").read_text(encoding="utf-8")
    assert 'actions/upload-artifact@v4' in workflow
    assert 'Makia-Client-Connector-Windows-x64-1.6.4' in workflow
    assert 'publish-windows-uat:' not in workflow
    assert 'gh release upload' not in workflow
    assert 'gh release create' not in workflow
