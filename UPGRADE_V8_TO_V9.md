# Upgrade JobTrack v8 → v9

v9 introduces multiple independent search/scoring profiles.

## Preserved data

Keep the existing `/data` Docker volume. The following remain intact:

- jobs and deduplication history
- Application Tracker
- sources and API credentials
- notification settings
- language data
- v7/v8 feedback and learned rules

Existing learning records are assigned to the first/default profile during migration.

## New database structures

Created automatically on startup:

- `search_profiles`
- `job_profile_scores`

The learning tables receive a `profile_id` scope. v8 single-profile rules/events are migrated to the default profile.

## Upgrade commands

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Check:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
```

Expected health version:

```json
{"status":"ok","version":"9.0.0"}
```

## First run

Open **Profiles**. Two profiles are seeded automatically on a new v9 profile schema:

1. Werkstudent / Part-time (default)
2. Full-time Supply Chain

Run **Run search now** once after upgrading. This populates `job_profile_scores` for existing/rescanned vacancies.

## Verify database

```bash
docker compose exec tracker python -c "import sqlite3; from app.config import settings; c=sqlite3.connect(settings.database_path); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('search_profiles','job_profile_scores') ORDER BY name\")])"
```

Expected:

```text
['job_profile_scores', 'search_profiles']
```

## Important

Do not replace your existing `.env`, do not delete the `/data` volume, and do not change `APP_SECRET_KEY` during the upgrade.
