from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_signed_android_release_requires_explicit_manual_approval():
    workflow=(ROOT/".github/workflows/android-release.yml").read_text(encoding="utf-8")
    triggers=workflow.split("on:",1)[1].split("permissions:",1)[0]
    assert "workflow_dispatch:" in triggers
    assert "  push:" not in triggers
    assert "publish_release:" in triggers
    assert "default: false" in triggers
    publish=workflow.split("- name: Publish signed Android connector to stable GitHub release",1)[1]
    assert "if: ${{ inputs.publish_release == true }}" in publish
    assert 'git fetch --force --depth=1 origin "refs/tags/$tag:refs/tags/$tag"' in publish
    assert 'git rev-list -n 1 "$tag"' in publish


def test_one_time_release_safety_workflow_is_removed():
    assert not (ROOT/".github/workflows/one-time-android-release-stop.yml").exists()
