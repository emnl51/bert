import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.update_client import require_same_origin_update, update_status
from scripts.jobtrack_updater import JobTrackUpdater


def request_with_headers(**headers: str) -> Request:
    raw_headers = [(name.replace("_", "-").encode(), value.encode()) for name, value in headers.items()]
    return Request({"type": "http", "method": "POST", "path": "/api/update/apply", "headers": raw_headers})


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def test_update_status_is_disabled_without_host_agent(monkeypatch):
    monkeypatch.setattr(settings, "update_agent_socket", "")
    monkeypatch.setattr(settings, "update_agent_token", "")
    assert update_status() == {
        "configured": False,
        "state": "disabled",
        "message": "The host update agent is not configured.",
        "update_available": False,
    }


def test_update_posts_require_matching_origin_and_action_header():
    request = request_with_headers(
        host="jobtakip.duckdns.org",
        origin="https://jobtakip.duckdns.org",
        sec_fetch_site="same-origin",
        x_jobtrack_action="update",
    )
    require_same_origin_update(request)

    with pytest.raises(HTTPException, match="Cross-site"):
        require_same_origin_update(
            request_with_headers(
                host="jobtakip.duckdns.org",
                origin="https://evil.example",
                sec_fetch_site="cross-site",
                x_jobtrack_action="update",
            )
        )

    with pytest.raises(HTTPException, match="Missing update action"):
        require_same_origin_update(
            request_with_headers(host="jobtakip.duckdns.org", origin="https://jobtakip.duckdns.org")
        )


def test_updater_detects_fast_forward_update_and_blocks_dirty_tree(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "jobtrack"
    publisher = tmp_path / "publisher"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, stdout=subprocess.PIPE)
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "app").mkdir()
    (repo / "app/version.py").write_text('VERSION = "1.0.0"\n', encoding="utf-8")
    (repo / "docker-compose.yml").write_text("services:\n  tracker:\n    image: test\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")

    subprocess.run(["git", "clone", "-b", "main", str(remote), str(publisher)], check=True, stdout=subprocess.PIPE)
    git(publisher, "config", "user.email", "test@example.com")
    git(publisher, "config", "user.name", "Test")
    (publisher / "app/version.py").write_text('VERSION = "1.1.0"\n', encoding="utf-8")
    git(publisher, "add", "app/version.py")
    git(publisher, "commit", "-m", "release 1.1")
    git(publisher, "push", "origin", "main")

    monkeypatch.setenv("JOBTRACK_REPO_DIR", str(repo))
    monkeypatch.setenv("JOBTRACK_BRANCH", "main")
    monkeypatch.setenv("JOBTRACK_COMPOSE_FILES", "docker-compose.yml")
    monkeypatch.setenv("JOBTRACK_UPDATE_STATE_FILE", str(tmp_path / "status.json"))
    monkeypatch.setenv("JOBTRACK_UPDATE_TOKEN", "x" * 48)
    updater = JobTrackUpdater()

    status = updater.check()
    assert status["safe_to_update"] is True
    assert status["update_available"] is True
    assert status["commits_behind"] == 1
    assert status["local_version"] == "1.0.0"
    assert status["remote_version"] == "1.1.0"

    (repo / "app/version.py").write_text('VERSION = "locally-modified"\n', encoding="utf-8")
    status = updater.check()
    assert status["working_tree_clean"] is False
    assert status["safe_to_update"] is False
    assert status["update_available"] is False


def test_update_feature_is_wired_without_docker_socket_mount():
    main = Path("app/v16_main.py").read_text(encoding="utf-8")
    ui = Path("app/update-ui.js").read_text(encoding="utf-8")
    compose = Path("docker-compose.updater.yml").read_text(encoding="utf-8")
    updater = Path("scripts/jobtrack_updater.py").read_text(encoding="utf-8")

    assert '<script src="/update-ui.js"></script>' in main
    assert 'id="applyUpdateBtn"' in ui
    assert "/run/jobtrack-updater" in compose
    assert "docker.sock" not in compose
    assert "shell=True" not in updater
    assert '"--ff-only"' in updater
    assert "source.backup(backup)" in updater
    assert "_wait_for_health" in updater
