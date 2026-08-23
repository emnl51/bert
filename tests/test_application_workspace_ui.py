from pathlib import Path


def test_application_workspace_exposes_board_manual_capture_and_handoff():
    script = Path("app/applications-profile-ui.js").read_text(encoding="utf-8")

    assert 'id="applicationBoard"' in script
    assert 'id="applicationList"' in script
    assert 'id="manualJobForm"' in script
    assert "application-card" in script
    assert "dragstart" in script
    assert "next_action_at" in script
    assert "api('/api/application-analytics?'" in script
    assert "api('/api/jobs/manual'" in script
    assert "/career-ops`" in script


def test_application_workspace_has_turkish_interface_labels():
    shell = Path("app/ui-shell.js").read_text(encoding="utf-8")

    assert "'Application Workspace':'Başvuru çalışma alanı'" in shell
    assert "'Due actions':'Bekleyen işlemler'" in shell
    assert "'Export for career-ops':'career-ops için dışa aktar'" in shell
