from pathlib import Path


def test_release_workflow_tests_before_ghcr_publish():
    text = Path('.github/workflows/publish-container.yml').read_text(encoding='utf-8')
    assert 'types: [published]' in text
    assert 'packages: write' in text
    assert 'ghcr.io' in text
    assert 'python -m pytest -q' in text
    assert 'docker/build-push-action@v6' in text
    assert 'actions/attest-build-provenance@v3' in text
    assert text.index('Run tests') < text.index('Build and push image')


def test_ghcr_compose_uses_release_image_and_persistent_data():
    text = Path('docker-compose.ghcr.yml').read_text(encoding='utf-8')
    assert 'ghcr.io/emnl51/jobtrack:${JOBTRACK_IMAGE_TAG:-latest}' in text
    assert 'tracker_data:/data' in text
    assert 'env_file:' in text
    assert '.env' in text
