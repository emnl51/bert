from pathlib import Path


def test_release_workflow_tests_before_ghcr_publish():
    text = Path(".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    assert "types: [published]" in text
    assert "packages: write" in text
    assert "ghcr.io" in text
    assert "python -m pytest -q" in text
    assert "docker/build-push-action@v6" in text
    assert "actions/attest-build-provenance@v3" in text
    assert text.index("Run tests") < text.index("Build and push image")


def test_ghcr_compose_uses_release_image_persistent_data_and_ollama_host():
    text = Path("docker-compose.ghcr.yml").read_text(encoding="utf-8")
    assert "ghcr.io/emnl51/jobtrack:${JOBTRACK_IMAGE_TAG:-latest}" in text
    assert "tracker_data:/data" in text
    assert "env_file:" in text
    assert ".env" in text
    assert "host.docker.internal:host-gateway" in text


def test_source_compose_can_reach_local_ollama_on_linux():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "host.docker.internal:host-gateway" in text
