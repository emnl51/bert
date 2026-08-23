from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _demote_headings(markdown: str) -> str:
    return re.sub(r"^(#{2,5})(?=\s)", lambda match: f"#{match.group(1)}", markdown, flags=re.MULTILINE)


def build_release_entry(tag: str, name: str, body: str, html_url: str) -> str:
    title = name.strip()
    if not title or title == tag:
        heading = f"## {tag}"
    elif title.startswith(tag):
        heading = f"## {title}"
    else:
        heading = f"## {tag} — {title}"

    notes = _demote_headings(body.strip()) or "Release notes were not provided."
    source = f"\n\n[GitHub Release]({html_url})" if html_url else ""
    return f"{heading}\n\n{notes}{source}\n"


def sync_release(changelog: Path, release: dict[str, object]) -> bool:
    tag = str(release.get("tag_name") or "").strip()
    if not tag:
        raise ValueError("Release event does not contain tag_name")

    text = changelog.read_text(encoding="utf-8")
    if re.search(rf"^## {re.escape(tag)}(?:\s|$)", text, flags=re.MULTILINE):
        return False
    unreleased = re.search(r"^## Unreleased[^\n]*\n.*?(?=^##\s|\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not unreleased:
        raise ValueError("CHANGELOG.md does not contain the expected Unreleased section")

    entry = build_release_entry(
        tag,
        str(release.get("name") or ""),
        str(release.get("body") or ""),
        str(release.get("html_url") or ""),
    )
    insertion = unreleased.end()
    changelog.write_text(f"{text[:insertion]}{entry}\n{text[insertion:]}", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a published GitHub Release to CHANGELOG.md")
    parser.add_argument("event", type=Path, help="Path to the GitHub release event JSON")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = parser.parse_args()

    payload = json.loads(args.event.read_text(encoding="utf-8"))
    release = payload.get("release")
    if not isinstance(release, dict):
        raise SystemExit("GitHub event does not contain a release object")
    changed = sync_release(args.changelog, release)
    print("CHANGELOG.md updated." if changed else "Release already exists in CHANGELOG.md.")


if __name__ == "__main__":
    main()
