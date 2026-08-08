from pathlib import Path


def test_v16_shell_has_mobile_navigation_and_table_cards():
    js = Path('app/ui-shell.js').read_text(encoding='utf-8')
    assert 'jt-mobile-menu' in js
    assert 'jt-sidebar-overlay' in js
    assert '@media(max-width:980px)' in js
    assert '@media(max-width:720px)' in js
    assert 'data-label' in js
    assert 'annotateTables' in js
    assert 'prefers-reduced-motion' in js


def test_v16_main_loads_shell_last():
    text = Path('app/v16_main.py').read_text(encoding='utf-8')
    # Patch releases (16.1, 16.2, ...) should not break a responsive-shell test.
    assert "app.version = '16." in text
    assert '<script src="/ui-shell.js"></script>' in text
    assert text.index('<script src="/log-ui.js"></script>') < text.index('<script src="/ui-shell.js"></script>')


def test_docker_runs_v16():
    dockerfile = Path('Dockerfile').read_text(encoding='utf-8')
    assert 'app.v16_main:app' in dockerfile
