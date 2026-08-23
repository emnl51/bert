from pathlib import Path


def test_profile_editor_separates_provider_queries_roles_and_working_arrangements():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    assert 'id="pfSearchPhrases"' in text
    assert 'id="pfRolePhrases"' in text
    assert 'id="pfFormatPhrases"' in text
    assert "One phrase per line. These are provider queries, not scoring rules." in text


def test_review_cards_explain_role_schedule_language_and_strong_matches():
    text = Path("app/review-ui.js").read_text(encoding="utf-8")
    assert "function insightMarkup(job)" in text
    assert "job-insight schedule" in text
    assert "scheduleDetail" in text
    assert "job-insight language" in text
    assert "job-language-reasons" in text
    assert "Strong profile match" in text


def test_interface_offers_persistent_english_and_turkish_language_selection():
    text = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert 'id="jtInterfaceLanguage"' in text
    assert '<option value="en">English</option>' in text
    assert '<option value="tr">Türkçe</option>' in text
    assert "installInterfaceSettings" in text
    assert "bert-interface-language" in text
    assert "translateInterface" in text
    assert "Sağlayıcı arama ifadeleri" in text
