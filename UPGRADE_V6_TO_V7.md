# Upgrade JobTrack v6 → v7

v7 adds the Job Review Queue and feedback-driven Search Learning.

## What changes

New files/modules:

- `app/feedback_store.py`
- `app/review-ui.js`

New SQLite tables are created automatically at application startup:

- `job_feedback`
- `learned_rules`

The existing `jobs`, `applications`, `job_language`, sources, keywords and settings remain in place.

## Upgrade

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

Expected health response includes version `7.0.0`.

## Verify feedback schema

```bash
docker compose exec tracker python -c "import sqlite3; from app.config import settings; c=sqlite3.connect(settings.database_path); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('job_feedback','learned_rules') ORDER BY name\")])"
```

Expected:

```text
['job_feedback', 'learned_rules']
```

## Review workflow

Open Overview and review a vacancy:

- Suitable → queues it as `To Apply`
- Maybe → keeps it in the review queue
- Not suitable → choose a reason and optionally allow Search Learning

Open the new **Learning** tab to inspect, disable or delete generated rules.

## Rollback

The v7 feedback tables are additive. Rolling the application image/code back to v6 leaves the new tables unused. Do not delete the Docker `/data` volume during rollback.
