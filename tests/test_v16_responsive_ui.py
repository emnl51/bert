from pathlib import Path


def test_v16_shell_has_mobile_navigation_and_table_cards():
    js = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "jt-mobile-menu" in js
    assert "jt-sidebar-overlay" in js
    assert "@media(max-width:980px)" in js
    assert "@media(max-width:720px)" in js
    assert "data-label" in js
    assert "annotateTables" in js
    assert "prefers-reduced-motion" in js


def test_v16_shell_has_searchable_grouped_navigation_and_workspace_context():
    js = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "jtNavigationSearch" in js
    assert 'aria-label="Search navigation"' in js
    assert "jt-group-count" in js
    assert "jtBreadcrumb" in js
    assert "jtPageDescription" in js
    assert "jtOverviewWelcome" in js
    assert "jt-quick-actions" in js
    assert "jt-sidebar-footer" in js
    assert "Version ${String(SHELL.version" in js


def test_v16_main_loads_shell_last():
    text = Path("app/v16_main.py").read_text(encoding="utf-8")
    shell = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "from .version import VERSION" in text
    assert "app.version = VERSION" in text
    assert '<script src="/ui-shell.js"></script>' in text
    assert text.index('<script src="/log-ui.js"></script>') < text.index('<script src="/ui-shell.js"></script>')
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
