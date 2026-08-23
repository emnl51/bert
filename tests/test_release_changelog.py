import json
import subprocess
import sys
from pathlib import Path

from scripts.sync_release_changelog import build_release_entry, sync_release


def test_build_release_entry_demotes_release_note_headings():
    entry = build_release_entry(
        "20.0.0",
        "Search improvements",
        "## What's Changed\n\n- Better matching",
        "https://github.com/example/bert/releases/tag/20.0.0",
    )

    assert entry.startswith("## 20.0.0 — Search improvements")
    assert "### What's Changed" in entry
    assert "[GitHub Release](https://github.com/example/bert/releases/tag/20.0.0)" in entry


def test_sync_release_is_idempotent(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## Unreleased\n\nNo unreleased changes yet.\n", encoding="utf-8")
    release = {"tag_name": "20.0.0", "name": "20.0.0", "body": "- Added a feature", "html_url": ""}

    assert sync_release(changelog, release) is True
    assert sync_release(changelog, release) is False
    assert changelog.read_text(encoding="utf-8").count("## 20.0.0") == 1


def test_sync_release_preserves_unreleased_notes(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## Unreleased\n\n### Added\n\n- Pending work.\n\n## 19.0.0\n\nOld notes.\n",
        encoding="utf-8",
    )

    assert sync_release(changelog, {"tag_name": "20.0.0", "name": "", "body": "New notes", "html_url": ""})
    text = changelog.read_text(encoding="utf-8")
    assert text.index("- Pending work.") < text.index("## 20.0.0") < text.index("## 19.0.0")


def test_sync_release_cli_reads_github_event(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## Unreleased\n\nNo unreleased changes yet.\n", encoding="utf-8")
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"release": {"tag_name": "20.1.0", "name": "", "body": "Notes", "html_url": ""}}),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/sync_release_changelog.py", str(event), "--changelog", str(changelog)],
        check=True,
    )

    assert "## 20.1.0" in changelog.read_text(encoding="utf-8")


def test_release_workflow_opens_an_idempotent_changelog_pull_request():
    workflow = Path(".github/workflows/sync-release-changelog.yml").read_text(encoding="utf-8")

    assert "types: [published]" in workflow
    assert "contents: write" in workflow
    assert "pull-requests: write" in workflow
    assert 'python scripts/sync_release_changelog.py "$GITHUB_EVENT_PATH"' in workflow
    assert "git diff --quiet -- CHANGELOG.md" in workflow
    assert "gh pr create" in workflow
