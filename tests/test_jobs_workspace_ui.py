from pathlib import Path


def test_navigation_uses_five_grouped_main_menus():
    text = Path("app/ui-shell.js").read_text(encoding="utf-8")
    for label in ("Control Panel", "Jobs", "Job Review", "Settings", "Administration"):
        assert f"label:'{label}'" in text
    assert "primary:'overview',children:[]" in text
    assert "primary:'searchJobs',children:['applications']" in text
    assert "primary:'jobReview',children:['intelligence','candidates','learning']" in text
    assert "buildNavigation" in text
    assert "setSectionExpanded" in text
    assert "bert-nav-row" in text
    assert "bert-nav-toggle" in text
    assert "bert-nav-chevron" in text
    assert "jt-nav-primary-row" not in text


def test_job_workspace_lists_jobs_and_uses_full_page_editor():
    text = Path("app/search-job-ui.js").read_text(encoding="utf-8")
    assert 'id="sjListView"' in text
    assert 'id="sjEditorView"' in text
    assert 'class="sj-list-table"' in text
    assert 'id="sjFilter"' in text
    assert "sj-modal" not in text
    for section in ("sjGeneral", "sjSearch", "sjFilters", "sjSourcesCard", "sjNotifications", "sjSchedule"):
        assert f'id="{section}"' in text


def test_job_editor_exposes_inheritance_and_hard_filter_semantics():
    text = Path("app/search-job-ui.js").read_text(encoding="utf-8")
    assert 'id="sjSearchInherit"' in text
    assert 'id="sjAllowInherit"' in text
    assert 'id="sjBlockInherit"' in text
    assert "allowlist_terms" in text
    assert "blocklist_terms" in text
    assert "Any match excludes the vacancy" in text
    assert "A match can only add points" in text
    assert 'id="sjCandidate"' in text


def test_review_queue_has_its_own_jobs_submenu_page():
    text = Path("app/review-ui.js").read_text(encoding="utf-8")
    assert "button.dataset.tab='jobReview'" in text
    assert "section.id='jobReview'" in text
