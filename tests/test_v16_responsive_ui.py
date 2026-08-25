from pathlib import Path
import re


def _contrast(first: str, second: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _theme_tokens(shell: str, selector: str, prefix: str = "") -> dict[str, str]:
    match = re.search(rf"{re.escape(selector)}\{{{re.escape(prefix)}([^}}]+)\}}", shell)
    assert match
    return dict(re.findall(r"--([\w-]+):(#[0-9a-fA-F]{6})", match.group(1)))


def test_v16_shell_has_mobile_navigation_and_table_cards():
    js = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "jt-mobile-menu" in js
    assert "jt-sidebar-overlay" in js
    assert "@media(max-width:980px)" in js
    assert "@media(max-width:720px)" in js
    assert "data-label" in js
    assert "annotateTables" in js
    assert "prefers-reduced-motion" in js


def test_v16_shell_has_searchable_hierarchical_navigation_and_workspace_context():
    js = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "jtNavigationSearch" in js
    assert 'aria-label="Search navigation"' in js
    assert "setSectionExpanded" in js
    assert "bert-nav-row" in js
    assert "children.forEach(button=>" in js
    assert ".app.jt-collapsed .bert-nav-label{display:none}" in js
    assert ".app.jt-collapsed .bert-nav-submenu{display:none}" in js
    assert "toLocaleLowerCase(locale)" in js
    assert "jtBreadcrumb" in js
    assert "jtPageDescription" in js
    assert "jtOverviewWelcome" in js
    assert "jt-quick-actions" in js
    assert "jt-sidebar-footer" in js
    assert "Version ${String(SHELL.version" in js
    assert "main=document.querySelector(\'.main\')" in js
    assert "if(!app||!side||!main||!top||!brand)" in js


def test_workspace_has_persistent_accessible_color_themes():
    shell = Path("app/ui-shell.js").read_text(encoding="utf-8")
    template = Path("app/templates/index.html").read_text(encoding="utf-8")
    login = Path("app/templates/login.html").read_text(encoding="utf-8")

    assert "bert-theme" in shell
    assert "prefers-color-scheme:dark" in shell
    assert 'html[data-theme="dark"]' in shell
    assert 'id="jtThemeSelect"' in shell
    assert "installInterfaceSettings" in shell
    assert "button.dataset.tab='interface'" in shell
    assert "jt-theme-control" not in shell
    assert "jt-interface-language" not in shell
    assert "System theme" in shell and "Light theme" in shell and "Dark theme" in shell
    assert "focus-visible" in shell
    assert "jt-skip-link" in shell
    assert "bert-theme" in template
    assert 'id="themePicker"' in login


def test_light_and_dark_theme_text_colors_meet_wcag_aa_contrast():
    shell = Path("app/ui-shell.js").read_text(encoding="utf-8")
    light = _theme_tokens(shell, ":root", "color-scheme:light;")
    dark = _theme_tokens(shell, 'html[data-theme="dark"]')

    for theme in (light, dark):
        assert _contrast(theme["text"], theme["bg"]) >= 4.5
        assert _contrast(theme["text"], theme["card"]) >= 4.5
        assert _contrast(theme["muted"], theme["bg"]) >= 4.5
        assert _contrast(theme["muted"], theme["card"]) >= 4.5
        assert _contrast(theme["on-accent"], theme["accent-solid"]) >= 4.5


def test_job_cards_open_an_accessible_detail_dialog_before_external_listing():
    review = Path("app/review-ui.js").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")

    assert 'role="dialog"' in review
    assert 'aria-modal="true"' in review
    assert "openJobDetail" in review
    assert "Open original listing" in review
    assert 'tabindex="0"' in review
    assert '@app.get("/api/jobs/{job_key:path}/detail")' in main


def test_v16_main_loads_shell_last():
    text = Path("app/v16_main.py").read_text(encoding="utf-8")
    shell = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "from .version import VERSION" in text
    assert "app.version = VERSION" in text
    assert 'f\'<script src="/ui-shell.js?v={VERSION}"></script>\'' in text
    assert text.index('<script src="/log-ui.js"></script>') < text.index('f\'<script src="/ui-shell.js?v={VERSION}"></script>\'')
    assert '{"appName": settings.app_name, "version": VERSION}' in text
    assert "window.APP_SHELL" in text
    assert "SHELL.appName" in shell
    assert "SHELL.version" in shell
    assert '<span class="jt-brand-text">JobTrack</span>' not in shell


def test_v16_owns_current_public_health_route():
    text = Path("app/v16_main.py").read_text(encoding="utf-8")
    assert 'getattr(r, "path", None) in {"/", "/health"}' in text
    assert '@app.get("/health")' in text
    assert '"version": app.version' in text
    assert "hybrid_cv_intelligence" in text
    assert "evidence_based_cv_match" in text
    assert "intelligence_cache" in text
    assert "web_database_backup_restore" in text


def test_database_backup_restore_api_and_ui_are_wired():
    main = Path("app/v16_main.py").read_text(encoding="utf-8")
    ui = Path("app/database-ui.js").read_text(encoding="utf-8")
    assert '@app.post("/api/database/backup")' in main
    assert '@app.post("/api/database/restore")' in main
    assert "require_same_origin(request)" in main
    assert 'request.headers.get("x-bert-confirmation") != "RESTORE DATABASE"' in main
    assert "create_download_backup" in main
    assert "restore_database" in main
    assert "Download backup" in ui
    assert "Restore from backup" in ui
    assert "X-Bert-Action" in ui
    assert "RESTORE DATABASE" in ui


def test_stepstone_ui_is_loaded_after_source_ui():
    text = Path("app/v16_main.py").read_text(encoding="utf-8")
    source_ui = '<script src="/source-ui.js"></script>'
    stepstone_ui = '<script src="/stepstone-ui.js"></script>'
    assert source_ui in text and stepstone_ui in text
    assert text.index(source_ui) < text.index(stepstone_ui)
    assert '@app.get("/stepstone-ui.js")' in text
    assert "stepstone_experimental_provider" in text


def test_legacy_jobs_refresh_is_routed_to_review_queue():
    main = Path("app/v16_main.py").read_text(encoding="utf-8")
    compat = Path("app/legacy-compat-ui.js").read_text(encoding="utf-8")
    review = '<script src="/review-ui.js"></script>'
    shim = '<script src="/legacy-compat-ui.js"></script>'
    assert review in main and shim in main
    assert main.index(review) < main.index(shim)
    assert '@app.get("/legacy-compat-ui.js")' in main
    assert "window.loadJobs = routeLegacyJobsRefresh" in compat
    assert "window.loadReviewJobs" in compat


def test_initial_legacy_jobs_request_survives_review_table_replacement():
    main = Path("app/v16_main.py").read_text(encoding="utf-8")
    template = Path("app/templates/index.html").read_text(encoding="utf-8")
    guard = "if(document.body.dataset.jobReviewUi==='true')return"
    request = "const d=await api(`/api/jobs?limit=100"
    assert 'data-job-review-ui="true"' in main
    assert guard in template
    assert template.index(guard) < template.index(request)
    assert "$('jobsMinScore')?.value" in template
    assert "$('jobsDecision')?.value" in template
    assert "const jobsBody=$('jobsBody');if(!jobsBody)return" in template
    assert "jobsBody.innerHTML=d.jobs.length" in template


def test_initial_legacy_settings_request_skips_modern_workspace_and_guards_removed_controls():
    template = Path("app/templates/index.html").read_text(encoding="utf-8")
    guard = "if(document.body.dataset.jobReviewUi==='true')return"
    request = "const s=await api('/api/settings')"
    settings_function = template.index("async function loadSettings()")
    guard_position = template.index(guard, settings_function)
    request_position = template.index(request, settings_function)
    assert guard_position < request_position
    assert "if($('jobsMinScore'))$('jobsMinScore').value" in template
    assert "const frequency=$('schedule_frequency');if(!frequency)return" in template


def test_candidate_assignment_ui_restores_saved_mapping():
    js = Path("app/intelligence-ui.js").read_text(encoding="utf-8")
    assert "assignments=d.assignments||[]" in js
    assert "function syncAssignmentSelection()" in js
    assert "el.onchange=syncAssignmentSelection" in js
    assert "await loadCandidates();toast(c?" in js


def test_docker_runs_v16():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "app.application:app" in dockerfile
    application = Path("app/application.py").read_text(encoding="utf-8")
    assert "from .v16_main import app" in application
