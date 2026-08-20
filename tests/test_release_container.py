from pathlib import Path


def test_release_workflow_tests_before_ghcr_publish():
    text = Path(".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    assert "types: [published]" in text
    assert "packages: write" in text
    assert "ghcr.io" in text
    assert "python -m pytest -q" in text
    assert "docker/build-push-action@v6" in text
    assert "actions/attest-build-provenance@" in text
    assert text.index("Run tests") < text.index("Build and push image")


def test_release_workflow_uses_release_tag_as_application_version():
    text = Path(".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    assert "Resolve application version" in text
    assert "RELEASE_TAG: ${{ github.event.release.tag_name }}" in text
    assert "INPUT_TAG: ${{ inputs.tag }}" in text
    assert 'runpy.run_path("app/version.py")["VERSION"]' in text
    assert '.removeprefix("v")' in text
    assert "APP_VERSION=${{ steps.version.outputs.app_version }}" in text
    assert text.index("Resolve application version") < text.index("Run tests")


def test_container_exposes_release_version_to_application():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "ARG APP_VERSION" in dockerfile
    assert "APP_VERSION=${APP_VERSION}" in dockerfile


def test_application_version_uses_release_build_version(monkeypatch):
    import runpy

    monkeypatch.setenv("APP_VERSION", "v23.4.5")
    assert runpy.run_path("app/version.py")["VERSION"] == "23.4.5"


def test_application_version_keeps_source_fallback(monkeypatch):
    import runpy

    monkeypatch.delenv("APP_VERSION", raising=False)
    assert runpy.run_path("app/version.py")["VERSION"] == "17.2.2"

    monkeypatch.setenv("APP_VERSION", "")
    assert runpy.run_path("app/version.py")["VERSION"] == "17.2.2"


def test_ghcr_compose_uses_release_image_persistent_data_and_ollama_host():
    text = Path("docker-compose.ghcr.yml").read_text(encoding="utf-8")
    assert "ghcr.io/whojan/bert:${BERT_IMAGE_TAG:-latest}" in text
    assert "bert_data:/data" in text
    assert "env_file:" in text
    assert ".env" in text
    assert "host.docker.internal:host-gateway" in text


def test_source_compose_can_reach_local_ollama_on_linux():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "host.docker.internal:host-gateway" in text
