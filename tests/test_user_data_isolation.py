from fastapi.testclient import TestClient

from app import db
from app.candidate_store import get_candidate, list_candidates, save_candidate
from app.models import Job
from app.profile_store import get_profile, list_profiles, save_profile
from app.search_job_store import get_search_job, list_search_jobs, save_search_job
from app.user_store import create_user_session, ensure_user_schema, hash_password
from app.v16_main import app


def setup_tenants(tmp_path, monkeypatch):
    path = tmp_path / "tenant.db"
    monkeypatch.setattr(db.settings, "database_path", str(path))
    db.init_db()
    ensure_user_schema()
    now = db._now()
    with db.connection() as con:
        ids = []
        for email in ("one@example.com", "two@example.com"):
            cursor = con.execute(
                """INSERT INTO users
                   (email,password_hash,full_name,role,status,email_verified_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (email, hash_password("a-secure-password"), email, "user", "active", now, now, now),
            )
            ids.append(int(cursor.lastrowid))
    return ids


def test_profiles_searches_candidates_and_settings_are_isolated(tmp_path, monkeypatch):
    one, two = setup_tenants(tmp_path, monkeypatch)
    assert list_profiles(user_id=one) == []
    assert list_profiles(user_id=two) == []
    p1_id = save_profile({"name": "Shared name", "slug": "shared", "is_default": True}, user_id=one)
    p2_id = save_profile({"name": "Shared name", "slug": "shared", "is_default": True}, user_id=two)
    p1 = get_profile(p1_id, user_id=one)
    p2 = get_profile(p2_id, user_id=two)
    assert p1["name"] == p2["name"]
    assert p1["id"] != p2["id"]
    assert get_profile(p2["id"], user_id=one) is None

    extra_one = save_profile({"name": "Extra", "slug": "extra"}, user_id=one)
    extra_two = save_profile({"name": "Extra", "slug": "extra"}, user_id=two)
    assert extra_one != extra_two

    search_one = save_search_job({"name": "Daily", "profile_id": p1["id"]}, user_id=one)
    search_two = save_search_job({"name": "Daily", "profile_id": p2["id"]}, user_id=two)
    assert get_search_job(search_two, user_id=one) is None
    assert search_one in {item["id"] for item in list_search_jobs(user_id=one)}
    assert search_two in {item["id"] for item in list_search_jobs(user_id=two)}

    candidate_one = save_candidate({"name": "My CV", "cv_text": "one"}, user_id=one)
    candidate_two = save_candidate({"name": "My CV", "cv_text": "two"}, user_id=two)
    assert get_candidate(candidate_two, user_id=one) is None
    assert [item["id"] for item in list_candidates(user_id=one)] == [candidate_one]
    assert [item["id"] for item in list_candidates(user_id=two)] == [candidate_two]

    db.set_setting("telegram_chat_id", "111", user_id=one)
    db.set_setting("telegram_chat_id", "222", user_id=two)
    assert db.get_setting("telegram_chat_id", user_id=one) == "111"
    assert db.get_setting("telegram_chat_id", user_id=two) == "222"
    assert db.get_setting("telegram_chat_id") != "111"


def test_job_decisions_and_applications_are_isolated(tmp_path, monkeypatch):
    one, two = setup_tenants(tmp_path, monkeypatch)
    job = Job(
        source="test",
        external_id="shared",
        title="Shared job",
        company="Factory",
        location="Berlin",
        url="https://example.test/job",
        description="Process engineering",
    )
    db.upsert_job(job)
    db.set_job_decision(job.key, "apply", user_id=one)
    db.set_job_decision(job.key, "skip", user_id=two)
    db.save_application(job.key, "interview", notes="private one", user_id=one)

    apps_one = db.list_applications(user_id=one)
    apps_two = db.list_applications(user_id=two)
    assert apps_one[0]["notes"] == "private one"
    assert apps_one[0]["decision"] == "apply"
    assert apps_two == []
    with db.connection() as con:
        decisions = {
            row["owner_key"]: row["decision"]
            for row in con.execute("SELECT owner_key,decision FROM user_job_state WHERE job_key=?", (job.key,))
        }
    assert decisions == {f"user:{one}": "apply", f"user:{two}": "skip"}


def test_api_rejects_cross_user_resource_ids(tmp_path, monkeypatch):
    one, two = setup_tenants(tmp_path, monkeypatch)
    p1 = get_profile(save_profile({"name": "One", "slug": "one"}, user_id=one), user_id=one)
    p2 = get_profile(save_profile({"name": "Two", "slug": "two"}, user_id=two), user_id=two)
    other_search = save_search_job({"name": "Other private search", "profile_id": p2["id"]}, user_id=two)
    token = create_user_session(one)
    client = TestClient(app)
    client.cookies.set("bert_session", token)

    assert client.get("/api/profiles").status_code == 200
    visible_ids = {item["id"] for item in client.get("/api/profiles").json()["profiles"]}
    assert p1["id"] in visible_ids
    assert p2["id"] not in visible_ids
    assert (
        client.put(f"/api/search-jobs/{other_search}", json={"name": "stolen", "profile_id": p1["id"]}).status_code
        == 404
    )
    assert client.delete(f"/api/search-jobs/{other_search}").status_code == 404
    assert client.get(f"/api/search-jobs/{other_search}/runs").status_code == 404
    assert client.get("/search-job-ui.js").status_code == 200
    assert client.get("/intelligence-ui.js").status_code == 200
    assert client.get("/ui-shell.js").status_code == 200
    assert client.get("/api/search-jobs").status_code == 200
    assert client.get("/api/candidates").status_code == 200
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/database/status").status_code == 401
