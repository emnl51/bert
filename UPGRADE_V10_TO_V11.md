# Upgrade v10 → v11

JobTrack v11 adds Candidate Profiles and CV-based Job Intelligence.

## New capabilities

- Candidate Profiles with CV text, skills, languages and target roles
- Candidate assignment per Search Job
- automatic CV analysis for new Search Job matches
- CV Match score (0–100)
- Apply / Maybe / Skip recommendation
- strengths, gaps and risk indicators
- Candidate and Intelligence web UI tabs
- CV Match included in Telegram/e-mail digests when a candidate is assigned

## Database

New tables are created automatically:

- `candidate_profiles`
- `search_job_candidates`
- `job_intelligence`

Existing jobs, Search Jobs, profiles, applications, learning rules, sources and notification settings are preserved.

Candidate CV text is encrypted at rest using the existing `APP_SECRET_KEY`. Keep this key unchanged during the upgrade.

## Upgrade

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Verify:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
```

Authenticated v11 check:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" http://127.0.0.1:8080/api/v11-health
```

Expected version: `11.0.0`.

## First use

1. Open **Candidates**.
2. Create a candidate profile and paste the CV text.
3. Define target roles, skills and language levels.
4. Assign the candidate to a Search Job.
5. Run that Search Job manually once or wait for its schedule.
6. Open **Intelligence** to review CV Match, recommendation, strengths, gaps and risks.

The v11 engine is local and deterministic (`heuristic-v1`); it does not require an external AI API. A future provider can replace or augment this engine without changing the database model.
